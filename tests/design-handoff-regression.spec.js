const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;

test('all presets carry exact tokens, requirements and complete selected skill', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const results = await page.evaluate(async () => {
    const output = [];
    for (const key of Object.keys(PRESETS)) {
      VASSetupDesign.apply(key);
      const result = await VASAgentHandoffWeb.buildNew({
        project_name: 'Audit fixture', problem_desc: 'Build a mobile stock screen',
        reference: 'https://example.com/home/design', env_mobile: ['mobile'],
        deadline: '90 days', budget: ['enterprise'], attached_files: ['reference.png'],
        extra: 'Preserve React'
      }, VASSetupDesign.context());
      const design = result.document.context.design;
      const profile = VASAgentResources.profiles[getTasteProfileKey(key, PRESETS[key])];
      output.push({ key, prompt: result.pasteText, tokens: design.tokens,
        requirements: result.document.context.requirements.value,
        rules: profile.rules, designer: VASAgentResources.designer, roles: VASAgentResources.roles });
    }
    return output;
  });
  expect(results).toHaveLength(18);
  for (const item of results) {
    for (const color of Object.values(item.tokens.colors)) expect(item.prompt, item.key).toContain(color);
    for (const rule of item.rules) expect(item.prompt, item.key).toContain(rule);
    expect(item.prompt).toContain(item.designer);
    expect(item.prompt).toContain('[OUTPUT CONTRACT]');
    for (const role of ['implementer', 'designer', 'reviewer']) expect(item.prompt).toContain('[ROLE INSTRUCTIONS: ' + role + ']');
    for (const instructions of Object.values(item.roles)) expect(item.prompt).toContain(instructions);
    expect(item.prompt).toContain('https://example.com/home/design');
    expect(item.prompt).toContain('90 days');
    expect(item.prompt).toContain('enterprise');
    expect(item.prompt).toContain('mobile');
    expect(item.prompt).toContain('reference.png');
    expect(item.prompt).toContain('Preserve React');
    expect(item.prompt).not.toContain('Use only standalone HTML');
    expect(item.requirements.attachments.contentsIncluded).toBe(false);
    expect(item.prompt).toContain('별도로 첨부');
  }
});

test('public URLs survive while local paths and secrets are removed', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    const references = ['https://example.com/design', 'http://example.com/design', 'https://www.figma.com/design/ABC/sample', 'https://example.com/home/sample'];
    const publicValues = [];
    for (const reference of references) {
      const built = await VASAgentHandoffWeb.buildNew({ problem_desc: 'test', reference }, { included: false });
      publicValues.push([reference, built.document.context.requirements.value.reference, VASAgentContract.clean(reference)]);
    }
    const value = 'path:C:\\private\\sample /home/private/sample file:///home/private/sample api_key=FIXTUREONLY123456';
    const built = await VASAgentHandoffWeb.buildNew({ problem_desc: value }, { included: false });
    return { publicValues, safe: built.pasteText, clean: VASAgentContract.clean(value) };
  });
  for (const [input, output, contract] of result.publicValues) { expect(output).toBe(input); expect(contract).toBe(input); }
  for (const value of [result.safe, result.clean]) { expect(value).not.toContain('private'); expect(value).not.toContain('FIXTUREONLY123456'); }
});

test('minor edits preserve the base preset and auto profile across reload and undo', async ({ page }) => {
  await page.goto(source('design-controller.html'));
  await page.locator('[data-preset="awwwards"]').first().click();
  await page.locator('#colorPrimary').evaluate(element => { element.value = '#123abc'; element.dispatchEvent(new Event('input', { bubbles: true })); });
  let state = await page.evaluate(() => VASThemeState.get());
  expect(state.preset).toBe('custom');
  expect(state.basePreset).toBe('awwwards');
  await expect(page.locator('#aiPrompt')).toHaveValue(/Taste Profile: Editorial Motion/);
  await expect(page.locator('#aiPrompt')).toHaveValue(/#123abc/);
  await page.reload();
  await expect(page.locator('#aiPrompt')).toHaveValue(/Taste Profile: Editorial Motion/);
  await expect(page.locator('#colorPrimary')).toHaveValue('#123abc');
  await page.locator('#padding').evaluate(element => { element.value = '48'; element.dispatchEvent(new Event('input', { bubbles: true })); });
  await page.locator('.reset-theme').click();
  state = await page.evaluate(() => VASThemeState.get());
  expect(state.tokens.padding).toBe(40);
  expect(state.tokens.colors.primary).toBe('#123abc');
  expect(state.basePreset).toBe('awwwards');
  await page.goto(source('client-application.html'));
  const handoff = await page.evaluate(() => VASSetupDesign.context());
  expect(handoff.basePreset).toBe('awwwards');
  expect(handoff.direction).toContain('Editorial Motion');
  expect(handoff.tokens.colors.primary).toBe('#123abc');
});

test('taste profile changes preview structure without changing confirmed colors', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(source('design-controller.html'));
  await page.locator('#shadow').evaluate(element => { element.value = '12'; element.dispatchEvent(new Event('input', { bubbles: true })); });
  const before = await page.locator('#advPreview').evaluate(element => ({color: element.style.getPropertyValue('--p-primary'), layout: getComputedStyle(element.querySelector('.p-grid')).display}));
  const shadow = await page.locator('.p-stat-card').first().evaluate(element => getComputedStyle(element).boxShadow);
  await page.locator('#tasteProfileMode').selectOption('dataTool');
  await expect(page.locator('#advPreview')).toHaveAttribute('data-taste-profile', 'dataTool');
  const after = await page.locator('#advPreview').evaluate(element => ({color: element.style.getPropertyValue('--p-primary'), layout: getComputedStyle(element.querySelector('.p-grid')).display}));
  expect(after.color).toBe(before.color);
  expect(after.layout).not.toBe(before.layout);
  await expect(page.locator('.p-stat-card').first()).toHaveCSS('box-shadow', shadow);
  await page.screenshot({ path: testInfo.outputPath('desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('[data-studio-view="preview"]').click();
  const size = await page.evaluate(() => ({width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth}));
  expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('mobile.png') });
  await page.locator('.p-input').scrollIntoViewIfNeeded();
  const input = await page.locator('.p-input').boundingBox();
  const footer = await page.locator('.studio-applybar').boundingBox();
  expect(input.y + input.height).toBeLessThanOrEqual(footer.y);
});
