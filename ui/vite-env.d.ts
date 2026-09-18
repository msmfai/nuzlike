// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
/// <reference types="vite/client" />
declare module "virtual:nuzlike-worker" {
  export default class PatcherWorker extends Worker { constructor(); }
}
