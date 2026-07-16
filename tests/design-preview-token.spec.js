const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const appUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'design-controller.html')).href;
const hubUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'vas-hub.html')).href;
const clientUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'client-application.html')).href;
const importUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'project-import.html')).href;
const searchUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'knowledge-search.html')).href;
const memoryUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'memory-center.html')).href;
const requiredSections = [
  '[BASELINE RULES]',
  '[TASTE PROFILE RULES]',
  '[PRESET DIRECTION]',
  '[CONFLICT POLICY]',
  '[OUTPUT CONTRACT]'
];
const requiredPreviewPresets = ['linear', 'github', 'neobrutal', 'stripe', 'notion', 'carbon'];

test('design preview reflects preset tokens', async ({ page }) => {
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', error => errors.push(error.message));

  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });

  const result = await page.evaluate(({ requiredSections, requiredPreviewPresets }) => {
    const optionValues = [...document.querySelectorAll('#fontFamily option')].map(option => option.value);
    const unsupportedFonts = Object.entries(PRESETS)
      .filter(([, preset]) => !optionValues.includes(preset.font))
      .map(([key, preset]) => ({ key, font: preset.font }));

    const tokenIssues = [];
    const promptIssues = [];

    for (const key of requiredPreviewPresets) {
      applyPreset(key);
      const preset = PRESETS[key];
      const preview = document.getElementById('advPreview');
      const prompt = document.getElementById('aiPrompt').value;
      const values = {
        selectFont: document.getElementById('fontFamily').value,
        font: preview.style.getPropertyValue('--p-font').trim(),
        primary: preview.style.getPropertyValue('--p-primary').trim(),
        bg: preview.style.getPropertyValue('--p-bg').trim(),
        surface: preview.style.getPropertyValue('--p-surface').trim(),
        text: preview.style.getPropertyValue('--p-text').trim(),
        radius: preview.style.getPropertyValue('--p-radius').trim()
      };
      const expected = {
        selectFont: preset.font,
        font: preset.font,
        primary: preset.primary,
        bg: preset.bg,
        surface: preset.surface,
        text: preset.text,
        radius: `${preset.rad}px`
      };
      const failedTokens = Object.keys(expected).filter(name => values[name] !== expected[name]);
      if (failedTokens.length > 0) tokenIssues.push({ key, failedTokens, expected, actual: values });

      const missingSections = requiredSections.filter(section => !prompt.includes(section));
      if (missingSections.length > 0) promptIssues.push({ key, missingSections });
    }

    return {
      presetCount: Object.keys(PRESETS).length,
      unsupportedFonts,
      tokenIssues,
      promptIssues
    };
  }, { requiredSections, requiredPreviewPresets });

  expect(errors).toEqual([]);
  expect(result.presetCount).toBeGreaterThanOrEqual(requiredPreviewPresets.length);
  expect(result.unsupportedFonts).toEqual([]);
  expect(result.tokenIssues).toEqual([]);
  expect(result.promptIssues).toEqual([]);
});

test('taste profile manual override updates prompt and can return to auto', async ({ page }) => {
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', error => errors.push(error.message));

  await page.addInitScript(() => localStorage.clear());
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });

  const result = await page.evaluate(({ requiredSections }) => {
    const select = document.getElementById('tasteProfileMode');
    const optionValues = [...select.options].map(option => option.value);

    applyPreset('carbon');
    const autoCarbonPrompt = document.getElementById('aiPrompt').value;

    setTasteProfileMode('minimalistUtility');
    const manualPrompt = document.getElementById('aiPrompt').value;

    applyPreset('linear');
    const manualLinearPrompt = document.getElementById('aiPrompt').value;

    setTasteProfileMode('auto');
    applyPreset('linear');
    const autoLinearPrompt = document.getElementById('aiPrompt').value;

    const sectionsOk = requiredSections.every(section => autoLinearPrompt.includes(section));

    return {
      hasAutoOption: optionValues.includes('auto'),
      profileOptionCount: optionValues.length,
      autoCarbonOk: autoCarbonPrompt.includes('Taste Profile: Dense Data Tool'),
      manualOk: manualPrompt.includes('Taste Profile: Minimalist Utility'),
      manualPersists: manualLinearPrompt.includes('Taste Profile: Minimalist Utility'),
      autoRestored: autoLinearPrompt.includes('Taste Profile: Premium Frontend'),
      manualKeyCleared: getManualTasteProfileKey() === null,
      storedMode: localStorage.getItem('vasTasteProfileMode'),
      sectionsOk
    };
  }, { requiredSections });

  expect(errors).toEqual([]);
  expect(result.hasAutoOption).toBe(true);
  expect(result.profileOptionCount).toBeGreaterThan(1);
  expect(result.autoCarbonOk).toBe(true);
  expect(result.manualOk).toBe(true);
  expect(result.manualPersists).toBe(true);
  expect(result.autoRestored).toBe(true);
  expect(result.manualKeyCleared).toBe(true);
  expect(result.storedMode).toBe('auto');
  expect(result.sectionsOk).toBe(true);
});

test('corrupted local storage heals without breaking the design studio', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('vasFavorites', '{broken');
    localStorage.setItem('vasThemeHistory', 'not-json');
  });

  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });

  await expect(page.locator('#preset-container')).toBeVisible();
  await expect(page.locator('#aiPrompt')).not.toHaveValue('');
  const healed = await page.evaluate(() => ({
    favorites: JSON.parse(localStorage.getItem('vasFavorites')),
    history: JSON.parse(localStorage.getItem('vasThemeHistory'))
  }));
  expect(errors).toEqual([]);
  expect(healed.favorites).toEqual([]);
  expect(Array.isArray(healed.history)).toBe(true);
});

test('blocked local storage falls back without runtime errors', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error('blocked'); };
    Storage.prototype.setItem = () => { throw new Error('blocked'); };
  });

  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });

  await expect(page.locator('#preset-container')).toBeVisible();
  await expect(page.locator('#aiPrompt')).not.toHaveValue('');
  expect(errors).toEqual([]);
});

test('legacy font tokens migrate without changing theme colors', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('vasThemeTokens', JSON.stringify({
      fontFamily: "'Pretendard', 'Geist', sans-serif",
      fontSize: 16,
      padding: 24,
      radius: 0,
      borderWidth: 2,
      shadow: 0,
      colors: {
        primary: '#123456', background: '#f5f5f4', surface: '#ffffff',
        text: '#09090b', border: '#09090b', success: '#10b981'
      }
    }));
    localStorage.setItem('vasThemeTokensVersion', '2.5.2');
  });

  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  const migrated = await page.evaluate(() => JSON.parse(localStorage.getItem('vasThemeTokens')));
  expect(migrated.fontFamily).toContain('system-ui');
  expect(migrated.fontFamily).not.toContain('Pretendard');
  expect(migrated.colors.primary).toBe('#123456');
});

test('all entry pages load without external network requests', async ({ page }) => {
  const externalRequests = [];
  page.on('request', request => {
    if (/^https?:/i.test(request.url())) externalRequests.push(request.url());
  });

  for (const url of [hubUrl, appUrl, clientUrl, importUrl, searchUrl, memoryUrl]) {
    await page.goto(url, { waitUntil: 'load' });
  }

  expect(externalRequests).toEqual([]);
});
