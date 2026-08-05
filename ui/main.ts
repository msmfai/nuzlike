// Copyright (C) 2026 Quicklocke contributors
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

const app = document.querySelector<HTMLElement>("#app")!;

let catalog: Catalog;
let selectedGame: GameEntry | null = null;
let selectedPath: string | null = null;
let selectedBytes: Uint8Array | null = null;
let inspection: Inspection | null = null;
let config: UserConfig | null = null;
let capSelection: LevelCapSelection = "medium";
let selectedNormalization = "none";

const releaseRequirements: Record<string, string> = {
  red: "English USA/Europe",
  blue: "English USA/Europe",
  yellow: "English USA/Europe",
  gold: "English USA/Europe",
  silver: "English USA/Europe",
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
  const ready = Boolean(selectedBytes && selectedGame?.recipeId && config);
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
          <h1>Quicklocke Patcher</h1>
        </div>
        <span class="privacy">ROM-free · offline</span>
      </header>

      <section class="intro">
        <p>Choose your own backup of an exact supported English release. The patcher verifies its content, applies the matching Quicklocke recipe, and writes a separate file.</p>
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
        <button id="patch-rom" class="primary" type="button" ${ready ? "" : "disabled"}>Patch and save copy</button>
      </section>

      <footer>
        <span>Supports Red, Blue, Yellow, Gold, Silver, Crystal, Emerald, FireRed, and LeafGreen.</span>
        <span>GPL-3.0-or-later</span>
      </footer>
    </section>`;

  document.querySelector("#choose-rom")?.addEventListener("click", chooseRom);
  document.querySelector("#patch-rom")?.addEventListener("click", patchAndSave);
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
    setStatus("Validating fingerprints and applying Quicklocke…", "working");
    const envelope = encodePatchRequest(selectedGame.recipeId, config, selectedBytes);
    const raw = await invoke<ArrayBuffer>("patch_rom", envelope);
    const { report, bytes } = decodePatchResponse(raw);
    const extension = selectedGame.id === "red" || selectedGame.id === "blue" ? "gb" :
      ["yellow", "gold", "silver", "crystal"].includes(selectedGame.id) ? "gbc" : "gba";
    const destination = await save({
      defaultPath: `quickloke-${selectedGame.id}.${extension}`,
      filters: [{ name: "Patched game backup", extensions: [extension] }],
    });
    if (!destination) {
      setStatus("Patch validated; save cancelled and no file was written.", "idle");
      return;
    }
    await writeFile(destination, bytes);
    const cheats = Object.values(report.debug).filter(Boolean).length;
    const normalized = report.inputNormalization !== "none" ? " · copier header removed" : "";
    setStatus(`Saved safely · ${report.outputSha256.slice(0, 12)}… · hardcore${normalized}${cheats ? ` · ${cheats} debug cheat${cheats === 1 ? "" : "s"}` : ""}`, "success");
  } catch (error) {
    setStatus(String(error), "error");
  }
}

async function start(): Promise<void> {
  app.innerHTML = '<section class="boot">Loading Quicklocke…</section>';
  try {
    catalog = await invoke<Catalog>("get_catalog");
    render();
  } catch (error) {
    app.innerHTML = `<section class="boot error">Could not load patcher catalog: ${escapeHtml(String(error))}</section>`;
  }
}

void start();
