// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
import PatcherWorker from "virtual:nuzlike-worker";

export const browser = !("__TAURI_INTERNALS__" in window);
let worker: Worker | undefined;
let nextId = 0;
const pending = new Map<number, { resolve: (value: unknown) => void; reject: (error: Error) => void }>();

export async function invoke<T>(command: string, bytes?: Uint8Array): Promise<T> {
  if (!browser) return (await import("@tauri-apps/api/core")).invoke<T>(command, bytes);
  if (!worker) {
    worker = new PatcherWorker();
    worker.onmessage = ({ data }) => {
      const request = pending.get(data.id);
      if (!request) return;
      pending.delete(data.id);
      if (data.error) request.reject(new Error(data.error));
      else request.resolve(data.result);
    };
    worker.onerror = () => {
      for (const request of pending.values()) request.reject(new Error("The patcher stopped unexpectedly. Reload the page to try again."));
      pending.clear();
      worker?.terminate();
      worker = undefined;
    };
  }
  return new Promise<T>((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve: value => resolve(value as T), reject });
    // Copy before transfer: the selected backup stays intact for subsequent builds.
    const copy = bytes?.slice();
    worker!.postMessage({ id, command, bytes: copy }, copy ? [copy.buffer] : []);
  });
}

export async function chooseFile(accept: string, maxBytes = 32 * 1024 * 1024 + 512): Promise<{ name: string; bytes: Uint8Array } | null> {
  if (!browser) {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const path = await open({ multiple: false, directory: false, filters: [{ name: "Game files", extensions: accept.split(",").map(s => s.trim().replace(".", "")) }] });
    if (!path || Array.isArray(path)) return null;
    const bytes = await (await import("@tauri-apps/plugin-fs")).readFile(path);
    if (bytes.length > maxBytes) throw new Error("This file is too large for a supported game backup.");
    return { name: path, bytes };
  }
  return new Promise((resolve, reject) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.hidden = true;
    document.body.append(input);
    input.oncancel = () => { input.remove(); resolve(null); };
    input.onchange = async () => {
      try {
        const file = input.files?.[0];
        if (!file) { resolve(null); return; }
        if (file.size > maxBytes) throw new Error("This file is too large. Choose a supported game backup or its FVX manifest.");
        resolve({ name: file.name, bytes: new Uint8Array(await file.arrayBuffer()) });
      } catch (error) { reject(error); }
      finally { input.remove(); }
    };
    input.click();
  });
}

const downloadUrls: string[] = [];
export function clearDownloads(): void {
  downloadUrls.splice(0).forEach(url => URL.revokeObjectURL(url));
  document.querySelector("#downloads")?.replaceChildren();
}

export async function saveResult(name: string, bytes: Uint8Array, sidecars: Record<string, string>): Promise<boolean> {
  if (!browser) {
    const { save } = await import("@tauri-apps/plugin-dialog");
    const path = await save({ defaultPath: name });
    if (!path) return false;
    const { writeFile } = await import("@tauri-apps/plugin-fs");
    await writeFile(path, bytes);
    for (const [suffix, text] of Object.entries(sidecars)) await writeFile(path + suffix, new TextEncoder().encode(text));
    return true;
  }
  clearDownloads();
  const files: [string, Blob][] = [[name, new Blob([bytes.slice().buffer], { type: "application/octet-stream" })]];
  for (const [suffix, text] of Object.entries(sidecars)) files.push([name + suffix, new Blob([text], { type: "text/plain;charset=utf-8" })]);
  for (const [filename, blob] of files) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    downloadUrls.push(link.href);
    link.download = filename;
    link.textContent = `Download ${filename}`;
    document.querySelector("#downloads")!.append(link);
  }
  // Explicit links retain a user gesture on mobile and allow re-downloading.
  return true;
}
