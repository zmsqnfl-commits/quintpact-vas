const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;
const sample = key => source('design-sample.html') + '?preset=' + key;
const curated = ['awwwards', 'linear', 'stripe', 'notion'];

test('catalog shows fourteen choices with real sample thumbnails and preserves legacy settings', async ({ page }) => {
  await page.goto(source('design-controller.html'));
  await expect(page.locator('.btn-preset')).toHaveCount(14);
  await expect(page.getByRole('heading', { name: '추천 샘플 사이트 · 4가지' })).toBeVisible();
  const thumbnails = page.locator('.preset-palette[data-sample] img');
  await expect(thumbnails).toHaveCount(4);
  for (const image of await thumbnails.all()) {
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate(el => el.complete && el.naturalWidth >= 1000)).toBe(true);
  }
  await page.evaluate(() => { localStorage.setItem('vasFavorites', JSON.stringify(['carbon','linear'])); applyPreset('carbon'); });
  await page.reload();
  await expect(page.locator('#colorPrimary')).toHaveValue('#2f5f9a');
  await expect(page.getByRole('heading', { name: '저장된 이전 스타일' })).toHaveCount(1);
  await expect(page.locator('.btn-preset[data-preset="carbon"]')).toHaveCount(1);
  await expect(page.locator('.btn-preset[data-preset="glow"]')).toHaveCount(0);
  await page.goto(source('client-application.html'));
  const choices = await page.evaluate(() => Array.from(document.querySelectorAll('option')).filter(o => o.value === 'carbon' || o.value === 'glow').map(o => o.value));
  expect(choices).toEqual(['carbon']);
  const design = await page.evaluate(() => VASSetupDesign.context());
  expect(design.preset).toBe('carbon');
  expect(design.tokens.colors.primary).toBe('#2f5f9a');
});

for (const width of [1440, 390, 320]) {
  test('sample sites render native content without overflow at ' + width, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [], remote = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('requestfailed', r => errors.push(r.url()));
    page.on('request', r => { if (/^https?:/.test(r.url())) remote.push(r.url()); });
    for (const key of curated) {
      await page.goto(sample(key));
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, img => img.decode())); });
      const root = page.locator('#advPreview');
      await expect(root).toHaveAttribute('data-sample', key);
      await expect(page.locator('#samplePreset option')).toHaveCount(14);
      await expect(root.locator('.p-stat-card')).toHaveCount(0);
      const overflow = await root.evaluate(el => ({ own: el.scrollWidth > el.clientWidth + 1, page: document.documentElement.scrollWidth > innerWidth + 1 }));
      expect(overflow, key).toEqual({ own: false, page: false });
      await page.screenshot({ path: info.outputPath(key + '-' + width + '.png'), fullPage: true });
    }
    expect(errors).toEqual([]);
    expect(remote).toEqual([]);
  });
}

test('full sample uses exact edited tokens and manual layout without writing shared state', async ({ page, context }) => {
  await page.goto(source('design-controller.html'));
  await page.locator('[data-preset="stripe"]').click();
  await page.locator('#colorPrimary').evaluate(el => { el.value = '#123abc'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  await page.locator('#tasteProfileMode').selectOption('curatedProduct');
  const state = await page.evaluate(() => VASThemeState.get());
  const before = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => /^vas(?:Theme|Current|Taste)/.test(k))));
  const [viewer] = await Promise.all([context.waitForEvent('page'), page.locator('#openDesignSample').click()]);
  await viewer.waitForLoadState();
  await expect(viewer.locator('#advPreview')).toHaveAttribute('data-sample', 'linear');
  const tokens = await viewer.locator('#advPreview').evaluate(el => ({ primary: el.style.getPropertyValue('--p-primary'), font: el.style.getPropertyValue('--p-font'), radius: el.style.getPropertyValue('--p-radius') }));
  expect(tokens).toEqual({ primary: '#123abc', font: state.tokens.fontFamily, radius: state.tokens.radius + 'px' });
  await viewer.locator('#samplePreset').selectOption('notion');
  await expect(viewer.locator('#advPreview')).toHaveAttribute('data-sample', 'notion');
  const after = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => /^vas(?:Theme|Current|Taste)/.test(k))));
  expect(after).toEqual(before);
  await viewer.goto(source('design-sample.html') + '?preset=__proto__#vas=not-json');
  await expect(viewer.locator('#advPreview')).toHaveAttribute('data-sample', 'awwwards');
  const customHash = await page.evaluate(() => {
    const value = VASThemeState.get();
    value.preset = 'custom'; value.basePreset = 'custom'; value.tasteProfileMode = 'curatedKnowledge';
    return VASThemeState.encodeNavigationState(value);
  });
  await viewer.goto(source('design-sample.html') + '?preset=custom#vas=' + customHash);
  await expect(viewer.locator('#advPreview')).toHaveAttribute('data-sample', 'notion');
  expect(await viewer.locator('#advPreview').evaluate(el => el.style.getPropertyValue('--p-primary'))).toBe('#123abc');
});

test('architecture sample has keyboard navigation, project disclosures and local inquiry feedback', async ({ page }) => {
  await page.goto(sample('awwwards'));
  await page.getByRole('button', { name: 'Explore projects' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#previewProjects')).toBeFocused();
  await page.locator('.ds-projects summary').first().click();
  await expect(page.locator('.ds-projects details').first()).toHaveAttribute('open', '');
  await page.getByLabel('미리보기 입력창').fill('작은 도서관과 정원이 있는 공간');
  await page.getByRole('button', { name: 'Preview inquiry' }).click();
  await expect(page.getByRole('status')).toContainText('실제 전송하지 않습니다');
});

test('project board filters, searches, edits status and safely creates a task', async ({ page }) => {
  await page.goto(sample('linear'));
  await page.locator('[data-filter="Engineering"]').click();
  await expect(page.locator('.ds-task')).toHaveCount(1);
  await page.getByLabel('작업 상태').selectOption('Done');
  await expect(page.locator('.ds-board > section').last()).toContainText('Build the component library');
  await expect(page.locator('[data-progress-label]')).toHaveText('50% complete');
  await page.getByLabel('작업 검색').fill('missing task');
  await expect(page.locator('.ds-task')).toHaveCount(0);
  await page.getByRole('button', { name: '＋ New task' }).click();
  await page.getByLabel('작업 이름').fill('<img src=x onerror=alert(1)>');
  await page.getByRole('button', { name: 'Add task', exact: true }).click();
  await expect(page.locator('.ds-task')).toHaveCount(7);
  await expect(page.locator('[data-task-title]')).toHaveText('<img src=x onerror=alert(1)>');
  await expect(page.locator('.ds-task img')).toHaveCount(0);
  await expect(page.locator('[data-progress-label]')).toHaveText('43% complete');
  await page.locator('[data-owner="AL"]').click();
  await expect(page.locator('.ds-task')).toHaveCount(3);
});

test('subscription plans update exact amounts and announce local selections', async ({ page }) => {
  await page.goto(sample('stripe'));
  await page.getByRole('button', { name: 'Find your plan' }).click();
  await expect(page.locator('#samplePricing')).toBeFocused();
  await page.locator('[data-period="yearly"]').click();
  await expect(page.locator('[data-price="24"]')).toHaveText('$19.2');
  await expect(page.locator('[data-price="64"]')).toHaveText('$51.2');
  await expect(page.locator('[data-billing-note]')).toContainText('$230.40');
  await page.locator('[data-plan="Studio"]').click();
  await expect(page.getByRole('status')).toContainText('Studio · 연 결제');
  await page.locator('[data-period="monthly"]').click();
  await expect(page.locator('[data-price="24"]')).toHaveText('$24');
  await expect(page.getByRole('status')).toContainText('Studio · 월 결제');
});

test('wiki searches and opens documents and updates checklist completion', async ({ page }) => {
  await page.goto(sample('notion'));
  await page.getByLabel('문서 검색').fill('missing');
  await expect(page.locator('.ds-no-docs')).toBeVisible();
  await page.getByLabel('문서 검색').fill('product');
  await expect(page.locator('.ds-sidebar [data-doc]:visible')).toHaveCount(1);
  await page.locator('.ds-sidebar [data-doc="2"]').click();
  await expect(page.locator('[data-doc-title]')).toContainText('Less noise.');
  await page.getByLabel('Keep the language human').check();
  await expect(page.locator('[data-check-count]')).toHaveText('2 / 3 complete');
  await page.locator('[data-check-all]').click();
  await expect(page.locator('[data-check-count]')).toHaveText('3 / 3 complete');
});
