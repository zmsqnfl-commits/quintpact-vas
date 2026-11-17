const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const preview = pathToFileURL(path.join(__dirname, '..', 'ui', 'style-preview.html')).href;

for (const width of [1440, 390]) {
  test(`style tile preview opens from a file and keeps one number per style at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const failures = [];
    page.on('pageerror', error => failures.push(error.message));
    page.on('requestfailed', request => failures.push(request.url()));
    await page.goto(preview);
    await page.evaluate(() => document.fonts.ready);
    const numbers = async () => page.locator('.tile').evaluateAll(tiles => tiles.map(tile =>
      tile.querySelector('.tile-num').textContent + ':' + tile.querySelector('.stage').dataset.key));
    const publicTiles = await numbers();
    expect(publicTiles.slice(0, 2)).toEqual(['01:bento', '02:aurora']);
    await page.locator('button[data-mode="core"]').click();
    expect(await numbers()).toEqual(['11:awwwards', '12:linear', '13:stripe', '14:notion']);
    await page.locator('.tile', { has: page.locator('.stage[data-key="stripe"]') }).click();
    await expect(page.locator('#pickedStatus')).toContainText('13번');
    await page.locator('button[data-mode="all"]').click();
    const all = await numbers();
    expect(all).toHaveLength(28);
    expect(all.map(entry => entry.slice(0, 2))).toEqual(all.map((_, index) => String(index + 1).padStart(2, '0')));
    const state = await page.evaluate(() => ({
      loaded: [...document.fonts].filter(font => font.status === 'loaded').length,
      overflow: document.documentElement.scrollWidth > innerWidth + 1
    }));
    expect(state).toEqual({ loaded: 6, overflow: false });
    expect(failures).toEqual([]);
  });
}
