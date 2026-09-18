// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig(({ mode }) => ({
  resolve: { alias: {
    "virtual:nuzlike-worker": fileURLToPath(new URL(mode === "web"
      ? "./ui/patcher-worker.ts" : "./ui/native-worker.ts", import.meta.url)) + (mode === "web" ? "?worker&inline" : ""),
  } },
  clearScreen: false,
  base: "./",
  server: {
    port: 1420,
    strictPort: true,
  },
  build: {
    outDir: "ui-dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    rolldownOptions: { output: { codeSplitting: false } },
  },
}));
