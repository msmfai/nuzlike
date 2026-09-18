// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium, expect } from '@playwright/test';

let browser;
const url = process.env.NUZLIKE_WEB_URL || pathToFileURL(resolve('ui-dist/index.html')).href;
before(async () => {
  browser = await chromium.launch({ executablePath: process.env.NUZLIKE_CHROMIUM || undefined });
});
after(async () => { await browser?.close(); });

async function openPage(mobile = false) {
  const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 900 }, isMobile: mobile, hasTouch: mobile });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(url);
  await expect(page.locator('#choose-rom')).toBeVisible({ timeout: 30000 });
  // After loading, block every network connection. Patching must remain local.
  const requests = [];
  await context.route(/^https?:/, route => { requests.push(route.request().url()); return route.abort(); });
  return { page, context, errors, requests };
}

async function choose(page, button, file) {
  const chooser = page.waitForEvent('filechooser');
  await page.locator(button).click();
  await (await chooser).setFiles(file);
}

async function build(page, expectedHash) {
  await page.locator('#patch-rom').click();
  await expect(page.locator('#status')).toHaveAttribute('data-kind', 'success', { timeout: 60000 });
  const link = page.locator('#downloads a').first();
  await expect(link).toBeVisible();
  const downloading = page.waitForEvent('download');
  await link.click();
  const download = await downloading;
  const bytes = await readFile(await download.path());
  assert.equal(createHash('sha256').update(bytes).digest('hex'), expectedHash);
  return download.suggestedFilename();
}

for (const mobile of [false, true]) {
  test(`offline startup and invalid input (${mobile ? 'mobile' : 'desktop'})`, async () => {
    const { page, context, errors, requests } = await openPage(mobile);
    try {
      await expect(page.locator('#patch-rom')).toBeDisabled();
      await choose(page, '#choose-rom', { name: 'red.gb', mimeType: 'application/octet-stream', buffer: Buffer.alloc(1024) });
      await expect(page.locator('#status')).toContainText('Unsupported backup');
      await expect(page.locator('#patch-rom')).toBeDisabled();
      assert.equal(await page.locator('#downloads a').count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      assert.deepEqual(requests, []);
    } finally { await context.close(); }
  });
}

test('oversized input is rejected before it reaches the worker', async () => {
  const { page, context } = await openPage();
  try {
    await choose(page, '#choose-rom', { name: 'too-big.gba', mimeType: 'application/octet-stream', buffer: Buffer.alloc(32 * 1024 * 1024 + 513) });
    await expect(page.locator('#status')).toContainText('too large');
    await expect(page.locator('#patch-rom')).toBeDisabled();
  } finally { await context.close(); }
});

// Optional private inputs are generated locally; public CI never downloads ROMs.
const matrix = process.env.NUZLIKE_WEB_MATRIX
  ? JSON.parse(await readFile(process.env.NUZLIKE_WEB_MATRIX, 'utf8')) : [];
for (const entry of matrix) {
  test(`${entry.game}: browser output matches CLI (${entry.mode})`, async () => {
    const { page, context, errors, requests } = await openPage(entry.game === 'emerald');
    try {
      await choose(page, '#choose-rom', entry.input);
      await expect(page.locator('#status')).toHaveAttribute('data-kind', 'success', { timeout: 30000 });
      if (entry.mode === 'configured') {
        await page.locator('input[name="cap-preset"][value="hard"]').check();
        await page.locator('#overflow-percent').fill('23');
        await page.locator('#overflow-percent').blur();
      }
      if (entry.mode === 'debug') {
        for (const toggle of await page.locator('.debug-toggle').all()) await toggle.check();
      }
      if (entry.mode === 'fvx') {
        await page.locator('#randomizer-enabled').check();
        await choose(page, '#choose-randomized', entry.randomized);
        await choose(page, '#choose-manifest', entry.manifest);
      }
      await build(page, entry.sha256);
      // Rebuild without reselecting: catches accidentally transferred/detached input.
      if (entry.mode === 'default') {
        await build(page, entry.sha256);
        await page.locator('#overflow-percent').fill('42');
        await page.locator('#overflow-percent').blur();
        assert.equal(await page.locator('#downloads a').count(), 0);
        await expect(page.locator('#status')).toContainText('Options changed');
        await choose(page, '#choose-rom', { name: 'unsupported.gba', mimeType: 'application/octet-stream', buffer: Buffer.alloc(1024) });
        await expect(page.locator('#status')).toContainText('Unsupported backup');
        await expect(page.locator('#patch-rom')).toBeDisabled();
      }
      if (entry.mode === 'fvx') {
        assert.equal(await page.locator('#downloads a').count(), 2);
        const manifest = JSON.parse(await readFile(entry.manifest, 'utf8'));
        manifest.randomized_sha256 = '0'.repeat(64);
        await choose(page, '#choose-manifest', { name: 'tampered.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(manifest)) });
        await page.locator('#patch-rom').click();
        await expect(page.locator('#status')).toHaveAttribute('data-kind', 'error', { timeout: 30000 });
        assert.equal(await page.locator('#downloads a').count(), 0);
      }
      assert.deepEqual(errors, []);
      assert.deepEqual(requests, []);
    } finally { await context.close(); }
  });
}
