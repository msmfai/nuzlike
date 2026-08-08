// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { readFile, writeFile } from "@tauri-apps/plugin-fs";
import "./styles.css";

type LevelCapPreset = "easy" | "medium" | "hard";
type LevelCapSelection = LevelCapPreset | "custom";

interface LevelCapPresets {
  easy: Record<string, number>;
  medium: Record<string, number>;
  hard: Record<string, number>;
}

interface UserConfig {
  schema: number;
  game: string;
  overflow_percent: number;
  level_caps: Record<string, number>;
  debug: Record<"infinite_health" | "maximum_damage" | "disable_trainer_sight", boolean>;
}

interface GameEntry {
  id: string;
  name: string;
  canonicalSha1: string;
  defaultConfig: UserConfig;
  levelCapPresets: LevelCapPresets;
  recipeId: string | null;
}

interface Catalog {
  schema: number;
  games: GameEntry[];
}

interface Inspection {
  size: number;
  sha1: string;
  sha256: string;
}

interface PatchReport {
  recipe: string;
  game: string;
  inputSha1: string;
  inputKind: string;
  inputNormalization: string;
  outputSha256: string;
  writes: number;
  levelCapOverrides: Record<string, number>;
  overflowPercent: number | null;
  debug: Record<string, boolean>;
}

interface FvxMetadata {
  manifestJson: string;
  log: string;
}

interface CombinedManifest {
  schema: number;
  pipeline: string;
  seed: string;
  final_sha256: string;
}

const app = document.querySelector<HTMLElement>("#app")!;

let catalog: Catalog;
let selectedGame: GameEntry | null = null;
let selectedPath: string | null = null;
let selectedBytes: Uint8Array | null = null;
let inspection: Inspection | null = null;
let config: UserConfig | null = null;
let capSelection: LevelCapSelection = "medium";
let selectedNormalization = "none";
let randomizerEnabled = false;
let randomizerSeed = "0";
let randomizerSettings = "";

const releaseRequirements: Record<string, string> = {
  red: "English USA/Europe",
  blue: "English USA/Europe",
  yellow: "English USA/Europe",
  crystal: "English USA/Europe · version 1.0",
  emerald: "English USA/Europe",
  firered: "English USA · version 1.0 (not 1.1)",
  leafgreen: "English USA · version 1.0 (not 1.1)",
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function titleCase(value: string): string {
  return value
    .split("_")
    .map((part) => part === "koga" ? "Koga" : part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function compactHash(value: string): string {
  return `${value.slice(0, 10)}…${value.slice(-8)}`;
}

function capsMatch(left: Record<string, number>, right: Record<string, number>): boolean {
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length
    && keys.every((key) => left[key] === right[key]);
}

function detectCapSelection(): LevelCapSelection {
  if (!config || !selectedGame) return "medium";
  for (const preset of ["easy", "medium", "hard"] as const) {
    if (capsMatch(config.level_caps, selectedGame.levelCapPresets[preset])) return preset;
  }
  return "custom";
}

function selectCapPreset(preset: LevelCapPreset): void {
  if (!config || !selectedGame) return;
  config.level_caps = structuredClone(selectedGame.levelCapPresets[preset]);
  capSelection = preset;
  render();
}

function setStatus(message: string, kind: "idle" | "working" | "success" | "error" = "idle"): void {
  const status = document.querySelector<HTMLElement>("#status");
  if (!status) return;
  status.textContent = message;
  status.dataset.kind = kind;
}

function render(): void {
  const caps = config
    ? Object.entries(config.level_caps)
        .map(([id, level]) => `
          <label class="cap-row">
            <span>${escapeHtml(titleCase(id))}</span>
            <input class="cap-input" type="number" min="1" max="100"
              value="${level}" data-cap="${escapeHtml(id)}" />
          </label>`)
        .join("")
    : "";
  const randomizerReady = !randomizerEnabled
    || (randomizerSettings.trim().length > 0 && /^-?(0|[1-9][0-9]*)$/.test(randomizerSeed));
  const ready = Boolean(selectedBytes && selectedGame?.recipeId && config && randomizerReady);
  const capLabel = titleCase(capSelection);
  const detected = selectedGame
    ? `<strong>${escapeHtml(selectedGame.name)}</strong><span>${inspection ? `${(inspection.size / 1048576).toFixed(2)} MiB · ${escapeHtml(releaseRequirements[selectedGame.id])}` : ""}</span>${selectedNormalization !== "none" ? "<span>512-byte copier header detected; output will be normalized.</span>" : ""}`
    : "<strong>No game selected</strong><span>Exact English releases listed below</span>";
  const compatibilityRows = catalog.games.map((game) => `
    <tr>
      <td>${escapeHtml(game.name)}</td>
      <td>${escapeHtml(releaseRequirements[game.id])}</td>
      <td title="${escapeHtml(game.canonicalSha1)}">${escapeHtml(compactHash(game.canonicalSha1))}</td>
    </tr>`).join("");

  app.innerHTML = `
    <section class="shell">
      <header>
        <div class="mark" aria-hidden="true"><span></span></div>
        <div>
          <p class="eyebrow">GENERATION I–III</p>
          <h1>NuzLike Patcher</h1>
        </div>
        <span class="privacy">ROM-free · offline</span>
      </header>

      <section class="intro">
        <p>Choose your own backup of an exact supported English release. The patcher verifies its content, applies the matching NuzLike recipe, and writes a separate file.</p>
      </section>

      <div class="workspace">
        <section class="card source-card">
          <div class="step"><span>1</span><h2>Game backup</h2></div>
          <button id="choose-rom" class="drop-zone" type="button">
            <span class="ball-icon" aria-hidden="true"></span>
            <span class="detected">${detected}</span>
            <span class="choose-label">Choose .gb, .gbc, or .gba file</span>
          </button>
          ${inspection ? `<p class="hash" title="${inspection.sha1}">SHA-1 ${compactHash(inspection.sha1)}</p>` : ""}
          ${selectedGame && !selectedGame.recipeId ? `
            <p class="notice">This development build is incomplete: no patch recipe is installed for this game.</p>` : ""}
          <details class="compatibility">
            <summary>Required game versions <span>exact releases</span></summary>
            <p>Filenames do not matter. A common 512-byte copier header is detected and safely removed only after the underlying game passes validation.</p>
            <div class="compatibility-scroll"><table>
              <thead><tr><th>Game</th><th>Release</th><th>SHA-1</th></tr></thead>
              <tbody>${compatibilityRows}</tbody>
            </table></div>
          </details>
        </section>

        <section class="card options-card ${config ? "" : "disabled"}">
          <div class="step"><span>2</span><h2>Challenge options</h2></div>
          <fieldset class="randomizer-fieldset" ${config ? "" : "disabled"}>
            <legend>FVX randomizer <span>optional · deterministic</span></legend>
            <label class="preset-option">
              <input id="randomizer-enabled" type="checkbox" ${randomizerEnabled ? "checked" : ""} />
              <span><strong>Randomize before applying NuzLike</strong><small>Uses the pinned GPL Universal Pokémon Randomizer FVX engine locally.</small></span>
            </label>
            ${randomizerEnabled ? `
              <label class="cap-row">
                <span>Signed 64-bit seed</span>
                <input id="randomizer-seed" type="text" inputmode="numeric" value="${escapeHtml(randomizerSeed)}" />
              </label>
              <label class="settings-string-row">
                <span>Canonical FVX settings string</span>
                <textarea id="randomizer-settings" rows="4" spellcheck="false" placeholder="Paste an FVX settings string for this game">${escapeHtml(randomizerSettings)}</textarea>
              </label>
              <p class="preset-note">The exact seed and settings are recorded in the combined manifest. Fixed NuzLike caps are not recalculated from randomized trainers.</p>
            ` : ""}
          </fieldset>
          <p class="notice"><strong>Hardcore wipe rule:</strong> a full-party wipe permanently ends the run.</p>
          <fieldset ${config ? "" : "disabled"}>
            <legend>Capped EXP sharing</legend>
            <label class="cap-row">
              <span>Overflow distributed to the rest of the party (%)</span>
              <input id="overflow-percent" type="number" min="0" max="100"
                value="${config?.overflow_percent ?? 75}" />
            </label>
          </fieldset>
          <fieldset class="cap-preset-fieldset" ${config ? "" : "disabled"}>
            <legend>Level-cap difficulty <span>${escapeHtml(capLabel)}</span></legend>
            <div class="preset-options">
              <label class="preset-option ${capSelection === "easy" ? "selected" : ""}">
                <input type="radio" name="cap-preset" value="easy" ${capSelection === "easy" ? "checked" : ""} />
                <span><strong>Easy</strong><small>Curated extra headroom for demanding fights.</small></span>
              </label>
              <label class="preset-option ${capSelection === "medium" ? "selected" : ""}">
                <input type="radio" name="cap-preset" value="medium" ${capSelection === "medium" ? "checked" : ""} />
                <span><strong>Medium</strong><small>Researched community cap defaults.</small></span>
              </label>
              <label class="preset-option ${capSelection === "hard" ? "selected" : ""}">
                <input type="radio" name="cap-preset" value="hard" ${capSelection === "hard" ? "checked" : ""} />
                <span><strong>Hard</strong><small>Curated lower caps for tighter fights.</small></span>
              </label>
            </div>
            <p class="preset-note">Each mode uses an explicit per-boss table; levels are not generated by adding or subtracting a fixed amount.</p>
          </fieldset>
          <details ${config ? "" : "inert"}>
            <summary>Boss level caps <span>${config ? `${capLabel} · ${Object.keys(config.level_caps).length}` : "0"}</span></summary>
            <div class="caps">${caps}</div>
          </details>
          <fieldset class="debug-fieldset" ${config ? "" : "disabled"}>
            <legend>Debug cheats <span>testing only</span></legend>
            <p class="notice"><strong>Debug build:</strong> these toggles deliberately bypass normal gameplay and are off by default.</p>
            <label class="preset-option">
              <input class="debug-toggle" type="checkbox" data-debug="infinite_health" ${config?.debug.infinite_health ? "checked" : ""} />
              <span><strong>Infinite health</strong><small>Player Pokémon do not lose HP in battle.</small></span>
            </label>
            <label class="preset-option">
              <input class="debug-toggle" type="checkbox" data-debug="maximum_damage" ${config?.debug.maximum_damage ? "checked" : ""} />
              <span><strong>Maximum damage</strong><small>Player attacks defeat the current opposing Pokémon immediately.</small></span>
            </label>
            <label class="preset-option">
              <input class="debug-toggle" type="checkbox" data-debug="disable_trainer_sight" ${config?.debug.disable_trainer_sight ? "checked" : ""} />
              <span><strong>Disable trainer sight</strong><small>Trainers engage only when you choose to talk to them.</small></span>
            </label>
          </fieldset>
        </section>
      </div>

      <section class="action-bar">
        <div id="status" data-kind="idle">${selectedGame ? "Configuration ready" : "Choose a supported game backup to begin"}</div>
        <button id="patch-rom" class="primary" type="button" ${ready ? "" : "disabled"}>${randomizerEnabled ? "Randomize, patch, and save" : "Patch and save copy"}</button>
      </section>

      <footer>
        <span>Supports Red, Blue, Yellow, Crystal, Emerald, FireRed, and LeafGreen.</span>
        <span>GPL-3.0-or-later</span>
      </footer>
    </section>`;

  document.querySelector("#choose-rom")?.addEventListener("click", chooseRom);
  document.querySelector("#patch-rom")?.addEventListener("click", patchAndSave);
  document.querySelector<HTMLInputElement>("#randomizer-enabled")?.addEventListener("change", (event) => {
    randomizerEnabled = (event.currentTarget as HTMLInputElement).checked;
    render();
  });
  document.querySelector<HTMLInputElement>("#randomizer-seed")?.addEventListener("input", (event) => {
    randomizerSeed = (event.currentTarget as HTMLInputElement).value.trim();
    renderActionState();
  });
  document.querySelector<HTMLTextAreaElement>("#randomizer-settings")?.addEventListener("input", (event) => {
    randomizerSettings = (event.currentTarget as HTMLTextAreaElement).value.trim();
    renderActionState();
  });
  document.querySelectorAll<HTMLInputElement>('input[name="cap-preset"]').forEach((input) => {
    input.addEventListener("change", () => selectCapPreset(input.value as LevelCapPreset));
  });
  document.querySelector<HTMLInputElement>("#overflow-percent")?.addEventListener("change", (event) => {
    if (!config) return;
    const input = event.currentTarget as HTMLInputElement;
    const value = Number(input.value);
    if (Number.isInteger(value) && value >= 0 && value <= 100) {
      config.overflow_percent = value;
    } else {
      input.value = String(config.overflow_percent);
    }
  });
  document.querySelectorAll<HTMLInputElement>(".cap-input").forEach((input) => {
    input.addEventListener("change", () => {
      if (!config) return;
      const value = Number(input.value);
      if (Number.isInteger(value) && value >= 1 && value <= 100) {
        config.level_caps[input.dataset.cap ?? ""] = value;
        capSelection = detectCapSelection();
        render();
        document.querySelector<HTMLDetailsElement>("details")?.setAttribute("open", "");
      } else {
        input.value = String(config.level_caps[input.dataset.cap ?? ""]);
      }
    });
  });
  document.querySelectorAll<HTMLInputElement>(".debug-toggle").forEach((input) => {
    input.addEventListener("change", () => {
      if (!config) return;
      const name = input.dataset.debug as keyof UserConfig["debug"];
      config.debug[name] = input.checked;
    });
  });
}

function renderActionState(): void {
  const button = document.querySelector<HTMLButtonElement>("#patch-rom");
  if (!button) return;
  let seedValid = false;
  try {
    const seed = BigInt(randomizerSeed);
    seedValid = /^-?(0|[1-9][0-9]*)$/.test(randomizerSeed)
      && seed >= -(2n ** 63n) && seed <= (2n ** 63n) - 1n;
  } catch {
    seedValid = false;
  }
  button.disabled = !selectedBytes || !selectedGame?.recipeId || !config
    || (randomizerEnabled && (!seedValid || !randomizerSettings));
}

async function chooseRom(): Promise<void> {
  try {
    const path = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "Game Boy backups", extensions: ["gb", "gbc", "gba"] }],
    });
    if (!path || Array.isArray(path)) return;
    setStatus("Reading and identifying backup…", "working");
    const bytes = await readFile(path);
    let details = await invoke<Inspection>("inspect_rom", bytes);
    let game = catalog.games.find(
      (entry) => entry.canonicalSha1.toLowerCase() === details.sha1.toLowerCase(),
    );
    selectedNormalization = "none";
    if (!game && bytes.length > 512) {
      const normalizedDetails = await invoke<Inspection>("inspect_rom", bytes.slice(512));
      const normalizedGame = catalog.games.find(
        (entry) => entry.canonicalSha1.toLowerCase() === normalizedDetails.sha1.toLowerCase(),
      );
      if (normalizedGame) {
        details = normalizedDetails;
        game = normalizedGame;
        selectedNormalization = "removed-512-byte-copier-header";
      }
    }
    selectedPath = path;
    selectedBytes = bytes;
    inspection = details;
    selectedGame = game ?? null;
    randomizerSettings = "";
    config = game ? structuredClone(game.defaultConfig) : null;
    capSelection = "medium";
    render();
    if (!game) {
      setStatus("Unsupported backup. Use the exact English region and revision listed above. No bytes were changed.", "error");
    } else if (!game.recipeId) {
      setStatus(`${game.name} identified, but this build has no recipe for it.`, "error");
    } else {
      setStatus(`${game.name} identified and ready${selectedNormalization !== "none" ? "; copier header will be removed" : ""}.`, "success");
    }
  } catch (error) {
    setStatus(String(error), "error");
  }
}

function encodePatchRequest(recipeId: string, userConfig: UserConfig, rom: Uint8Array): Uint8Array {
  const metadata = new TextEncoder().encode(JSON.stringify({ recipe_id: recipeId, config: userConfig }));
  const envelope = new Uint8Array(4 + metadata.length + rom.length);
  new DataView(envelope.buffer).setUint32(0, metadata.length, false);
  envelope.set(metadata, 4);
  envelope.set(rom, 4 + metadata.length);
  return envelope;
}

function encodeRawRequest(metadataValue: unknown, ...parts: Uint8Array[]): Uint8Array {
  const metadata = new TextEncoder().encode(JSON.stringify(metadataValue));
  const size = 4 + metadata.length + parts.reduce((total, part) => total + part.length, 0);
  const envelope = new Uint8Array(size);
  new DataView(envelope.buffer).setUint32(0, metadata.length, false);
  envelope.set(metadata, 4);
  let cursor = 4 + metadata.length;
  for (const part of parts) {
    envelope.set(part, cursor);
    cursor += part.length;
  }
  return envelope;
}

function decodeRawResponse<T>(response: ArrayBuffer): { metadata: T; bytes: Uint8Array } {
  const data = new Uint8Array(response);
  if (data.length < 4) throw new Error("The engine returned a truncated response.");
  const metadataSize = new DataView(data.buffer, data.byteOffset, data.byteLength).getUint32(0, false);
  if (4 + metadataSize > data.length) throw new Error("The engine returned invalid metadata.");
  const metadata = JSON.parse(new TextDecoder().decode(data.subarray(4, 4 + metadataSize))) as T;
  return { metadata, bytes: data.subarray(4 + metadataSize) };
}

function decodePatchResponse(response: ArrayBuffer): { report: PatchReport; bytes: Uint8Array } {
  const data = new Uint8Array(response);
  if (data.length < 4) throw new Error("The patcher returned a truncated response.");
  const reportSize = new DataView(data.buffer, data.byteOffset, data.byteLength).getUint32(0, false);
  if (4 + reportSize > data.length) throw new Error("The patcher returned an invalid report.");
  const report = JSON.parse(new TextDecoder().decode(data.subarray(4, 4 + reportSize))) as PatchReport;
  return { report, bytes: data.subarray(4 + reportSize) };
}

async function patchAndSave(): Promise<void> {
  if (!selectedGame?.recipeId || !selectedBytes || !config) return;
  try {
    let bytes: Uint8Array;
    let outputHash: string;
    let cheats = 0;
    let combinedManifestText: string | null = null;
    let randomizerLog: string | null = null;
    if (randomizerEnabled) {
      setStatus("Randomizing locally with FVX…", "working");
      const clean = selectedNormalization === "removed-512-byte-copier-header"
        ? selectedBytes.slice(512) : selectedBytes;
      const randomizeRequest = encodeRawRequest(
        { settings: randomizerSettings, seed: randomizerSeed },
        clean,
      );
      const randomizedRaw = await invoke<ArrayBuffer>("randomize_with_fvx", randomizeRequest);
      const randomized = decodeRawResponse<FvxMetadata>(randomizedRaw);
      randomizerLog = randomized.metadata.log;
      setStatus("Checking collisions and applying NuzLike…", "working");
      const compositionRequest = encodeRawRequest({
        recipe_id: selectedGame.recipeId,
        manifest_json: randomized.metadata.manifestJson,
        clean_size: clean.length,
        config,
      }, clean, randomized.bytes);
      const composedRaw = await invoke<ArrayBuffer>("compose_randomized_rom", compositionRequest);
      const composed = decodeRawResponse<CombinedManifest>(composedRaw);
      bytes = composed.bytes;
      outputHash = composed.metadata.final_sha256;
      combinedManifestText = JSON.stringify(composed.metadata, null, 2) + "\n";
      cheats = Object.values(config.debug).filter(Boolean).length;
    } else {
      setStatus("Validating fingerprints and applying NuzLike…", "working");
      const envelope = encodePatchRequest(selectedGame.recipeId, config, selectedBytes);
      const raw = await invoke<ArrayBuffer>("patch_rom", envelope);
      const patched = decodePatchResponse(raw);
      bytes = patched.bytes;
      outputHash = patched.report.outputSha256;
      cheats = Object.values(patched.report.debug).filter(Boolean).length;
    }
    const extension = selectedGame.id === "red" || selectedGame.id === "blue" ? "gb" :
      ["yellow", "crystal"].includes(selectedGame.id) ? "gbc" : "gba";
    const destination = await save({
      defaultPath: `nuzlike-${selectedGame.id}.${extension}`,
      filters: [{ name: "Patched game backup", extensions: [extension] }],
    });
    if (!destination) {
      setStatus("Patch validated; save cancelled and no file was written.", "idle");
      return;
    }
    await writeFile(destination, bytes);
    if (combinedManifestText && randomizerLog !== null) {
      await writeFile(`${destination}.nuzlike.json`, new TextEncoder().encode(combinedManifestText));
      await writeFile(`${destination}.fvx.log`, new TextEncoder().encode(randomizerLog));
    }
    const normalized = selectedNormalization !== "none" ? " · copier header removed" : "";
    const randomizedLabel = randomizerEnabled ? ` · FVX seed ${randomizerSeed}` : "";
    const sidecars = combinedManifestText ? " · manifest + log saved" : "";
    setStatus(`Saved safely · ${outputHash.slice(0, 12)}… · hardcore${randomizedLabel}${normalized}${sidecars}${cheats ? ` · ${cheats} debug cheat${cheats === 1 ? "" : "s"}` : ""}`, "success");
  } catch (error) {
    setStatus(String(error), "error");
  }
}

async function start(): Promise<void> {
  app.innerHTML = '<section class="boot">Loading NuzLike…</section>';
  try {
    catalog = await invoke<Catalog>("get_catalog");
    render();
  } catch (error) {
    app.innerHTML = `<section class="boot error">Could not load patcher catalog: ${escapeHtml(String(error))}</section>`;
  }
}

void start();
