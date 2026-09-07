const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const studio = pathToFileURL(path.join(__dirname, '..', 'src', 'design-controller.html')).href;
const collection = ['bento', 'aurora', 'clay', 'noir', 'botanical', 'retro', 'swiss', 'cyber', 'kinetic', 'collage'];

for (const width of [1440, 390, 320]) {
  test(`new collection renders distinct working compositions at ${width}px`, async ({ page }, testInfo) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width, height: 1000 });
    const failures = [];
    page.on('pageerror', error => failures.push(error.message));
    page.on('requestfailed', request => failures.push(request.url()));
    await page.goto(studio);
    const identities = [];
    for (const key of collection) {
      if (width < 900) await page.locator('[data-studio-view="settings"]').click();
      await page.locator(`.btn-preset[data-preset="${key}"]`).click();
      if (width < 900) await page.locator('[data-studio-view="preview"]').click();
      await page.evaluate(() => document.fonts.ready);
      const root = page.locator('#advPreview');
      const state = await root.evaluate(async element => {
        await Promise.all([...element.querySelectorAll('img')].map(img => img.decode()));
        const fonts = [...document.fonts].filter(font => font.status === 'loaded').map(font => font.family);
        return { identity: element.dataset.collection, heading: element.querySelector('h2').innerText,
          family: getComputedStyle(element).fontFamily.split(',')[0].replaceAll('"', '').replaceAll("'", ''), fonts,
          overflow: element.scrollWidth > element.clientWidth + 1 || document.documentElement.scrollWidth > innerWidth + 1 };
      });
      identities.push(state.identity + ':' + state.heading);
      expect(state.identity, key).toBeTruthy();
      expect(state.overflow, key).toBe(false);
      if (key !== 'cyber') expect(state.fonts, key).toContain(state.family);
      await expect(root.locator('.p-stat-card')).toHaveCount(0);
      const box = await root.boundingBox();
      await page.setViewportSize({ width, height: Math.max(1000, Math.ceil(box.height) + 300) });
      await root.screenshot({ path: testInfo.outputPath(`${key}-${width}.png`), animations: 'disabled' });
      await page.setViewportSize({ width, height: 1000 });
      await root.locator('[data-reveal]').click();
      await expect(root.locator('#ncDetail')).toBeVisible();
      await expect(root.locator('#ncDetail')).toBeFocused();
      await expect(root.locator('[data-reveal]')).toHaveAttribute('aria-expanded', 'true');
      await root.locator('[data-reveal]').click();
      await expect(root.locator('#ncDetail')).toBeHidden();
    }
    expect(new Set(identities).size).toBe(10);
    expect(failures).toEqual([]);
  });
}

test('collection controls, motion preferences and saved fonts survive real interaction', async ({ page }) => {
  await page.goto(studio);
  await page.locator('.btn-preset[data-preset="bento"]').click();
  await page.getByLabel('Make a little mess').check();
  await page.locator('#padding').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByLabel('Make a little mess')).toBeChecked();
  for (const key of ['cyber', 'kinetic']) {
    await page.locator(`.btn-preset[data-preset="${key}"]`).click();
    const animated = page.locator(key === 'cyber' ? '.nc-globe' : '.nc-marquee > div');
    expect(await animated.evaluate(el => getComputedStyle(el).animationName)).not.toBe('none');
    await page.locator('[data-pause]').click();
    expect(await animated.evaluate(el => getComputedStyle(el).animationPlayState)).toBe('paused');
    await expect(page.locator('[data-pause]')).toHaveAttribute('aria-pressed', 'true');
    await page.locator('[data-pause]').click();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    expect(await animated.evaluate(el => getComputedStyle(el).animationName)).toBe('none');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
  }
  await page.locator('.btn-preset[data-preset="cyber"]').click();
  await page.locator('[data-reveal]').click();
  await page.getByRole('button', { name: '예시 진단 실행' }).click();
  await expect(page.locator('.nc-console-output')).toContainText('외부 연결 없음');
  await page.locator('.btn-preset[data-preset="noir"]').click();
  await page.reload();
  await expect(page.locator('#advPreview')).toHaveAttribute('data-collection', 'noirLuxe');
  await expect(page.locator('#fontFamily')).toHaveValue("'Cormorant Garamond', Georgia, 'Batang', serif");
  const prompt = await page.locator('#aiPrompt').inputValue();
  expect(prompt).toContain('Noir Luxe');
  expect(prompt).toContain('Cormorant Garamond');
  await page.locator('.btn-preset[data-preset="awwwards"]').click();
  await expect(page.locator('#advPreview')).not.toHaveAttribute('data-collection');
  await expect(page.locator('#advPreview')).toHaveAttribute('data-sample', 'awwwards');
  await expect(page.locator('.ds-architecture-photo')).toBeVisible();
});
