// Copyright (C) 2026 Quicklocke contributors
// SPDX-License-Identifier: GPL-3.0-or-later
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { readFile, writeFile } from "@tauri-apps/plugin-fs";
import "./styles.css";

type WipeMode = "forgiving" | "hardcore";
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
  wipe_mode: WipeMode;
  overflow_percent: number;
  level_caps: Record<string, number>;
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
  outputSha256: string;
  writes: number;
  levelCapOverrides: Record<string, number>;
  wipeMode: WipeMode | null;
  overflowPercent: number | null;
}

const app = document.querySelector<HTMLElement>("#app")!;

let catalog: Catalog;
let selectedGame: GameEntry | null = null;
let selectedPath: string | null = null;
let selectedBytes: Uint8Array | null = null;
let inspection: Inspection | null = null;
let config: UserConfig | null = null;
let capSelection: LevelCapSelection = "medium";

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
    ? `<strong>${escapeHtml(selectedGame.name)}</strong><span>${selectedBytes ? `${(selectedBytes.length / 1048576).toFixed(2)} MiB` : ""}</span>`
    : "<strong>No game selected</strong><span>Red through LeafGreen</span>";

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
        <p>Choose your own game backup. The patcher identifies the version, applies its matching Quicklocke recipe, and writes a separate file.</p>
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
        </section>

        <section class="card options-card ${config ? "" : "disabled"}">
          <div class="step"><span>2</span><h2>Challenge options</h2></div>
          <fieldset ${config ? "" : "disabled"}>
            <legend>Wipe rule</legend>
            <label class="mode-option ${config?.wipe_mode === "forgiving" ? "selected" : ""}">
              <input type="radio" name="wipe-mode" value="forgiving" ${config?.wipe_mode === "forgiving" ? "checked" : ""} />
              <span><strong>Forgiving</strong><small>Return to the checkpoint made after the previous Gym.</small></span>
            </label>
            <label class="mode-option ${config?.wipe_mode === "hardcore" ? "selected" : ""}">
              <input type="radio" name="wipe-mode" value="hardcore" ${config?.wipe_mode === "hardcore" ? "checked" : ""} />
              <span><strong>Hardcore</strong><small>A full-party wipe permanently ends the run.</small></span>
            </label>
          </fieldset>
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
        </section>
      </div>

      <section class="action-bar">
        <div id="status" data-kind="idle">${selectedGame ? "Configuration ready" : "Choose a supported game backup to begin"}</div>
        <button id="patch-rom" class="primary" type="button" ${ready ? "" : "disabled"}>Patch and save copy</button>
      </section>

      <footer>
        <span>Supports Red, Blue, Yellow, Gold, Silver, Crystal, Ruby, Sapphire, Emerald, FireRed, and LeafGreen.</span>
        <span>GPL-3.0-or-later</span>
      </footer>
    </section>`;

  document.querySelector("#choose-rom")?.addEventListener("click", chooseRom);
  document.querySelector("#patch-rom")?.addEventListener("click", patchAndSave);
  document.querySelectorAll<HTMLInputElement>('input[name="wipe-mode"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (config) config.wipe_mode = input.value as WipeMode;
      render();
    });
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
    const details = await invoke<Inspection>("inspect_rom", bytes);
    const game = catalog.games.find(
      (entry) => entry.canonicalSha1.toLowerCase() === details.sha1.toLowerCase(),
    );
    selectedPath = path;
    selectedBytes = bytes;
    inspection = details;
    selectedGame = game ?? null;
    config = game ? structuredClone(game.defaultConfig) : null;
    capSelection = "medium";
    render();
    if (!game) {
      setStatus("Unsupported or modified backup. No bytes were changed.", "error");
    } else if (!game.recipeId) {
      setStatus(`${game.name} identified, but this build has no recipe for it.`, "error");
    } else {
      setStatus(`${game.name} identified and ready.`, "success");
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
    setStatus(`Saved safely · ${report.outputSha256.slice(0, 12)}… · ${report.wipeMode}`, "success");
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
