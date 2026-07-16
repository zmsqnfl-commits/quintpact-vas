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
const requiredPreviewPresets = ['awwwards', 'linear', 'github', 'neobrutal', 'stripe', 'notion', 'carbon'];

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

test('fresh installs use the Awwwards editorial baseline across studio and hub', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  const studio = await page.evaluate(() => ({
    preset: localStorage.getItem('vasCurrentPreset'),
    prompt: document.getElementById('aiPrompt').value,
    active: document.querySelector('.btn-preset.active')?.dataset.preset
  }));
  expect(studio.preset).toBe('awwwards');
  expect(studio.active).toBe('awwwards');
  expect(studio.prompt).toContain('Preset: awwwards');
  expect(studio.prompt).toContain('Taste Profile: Editorial Motion');

  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const hub = await page.evaluate(() => {
    const rootStyle = getComputedStyle(document.documentElement);
    const headingSize = parseFloat(getComputedStyle(document.querySelector('.hero h1')).fontSize);
    return {
      preset: document.documentElement.dataset.preset,
      background: getComputedStyle(document.body).backgroundColor,
      motion: rootStyle.getPropertyValue('--motion').trim(),
      radius: rootStyle.getPropertyValue('--radius').trim(),
      headingSize
    };
  });
  expect(hub.preset).toBe('awwwards');
  expect(hub.background).toBe('rgb(232, 232, 229)');
  expect(hub.motion).toBe('0.5s');
  expect(hub.radius).toBe('0px');
  expect(hub.headingSize).toBeLessThanOrEqual(70);
});

test('existing Neo-Brutalism and custom tokens stay intact', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => {
    localStorage.clear();
    localStorage.setItem('vasCurrentPreset', 'neobrutal');
    localStorage.setItem('vasThemeTokens', JSON.stringify({
      fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif",
      fontSize: 16, letterSpacing: -0.05, padding: 24, radius: 0, borderWidth: 2, shadow: 0, speed: 0.1,
      colors: {
        primary: '#000000', background: '#f0f0f0', surface: '#ffcc00',
        text: '#000000', border: '#000000', success: '#10b981'
      }
    }));
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  const preservedNeo = await page.evaluate(() => ({
    preset: localStorage.getItem('vasCurrentPreset'),
    tokens: JSON.parse(localStorage.getItem('vasThemeTokens'))
  }));
  expect(preservedNeo.preset).toBe('neobrutal');
  expect(preservedNeo.tokens.colors.surface).toBe('#ffcc00');

  const custom = await page.evaluate(() => {
    localStorage.clear();
    localStorage.setItem('vasCurrentPreset', 'neobrutal');
    const tokens = VASStorage.getDefaultTheme();
    tokens.colors.primary = '#123456';
    localStorage.setItem('vasThemeTokens', JSON.stringify(tokens));
    return true;
  });
  expect(custom).toBe(true);
  await page.reload({ waitUntil: 'domcontentloaded' });
  const preserved = await page.evaluate(() => ({
    preset: localStorage.getItem('vasCurrentPreset'),
    tokens: JSON.parse(localStorage.getItem('vasThemeTokens'))
  }));
  expect(preserved.preset).toBe('neobrutal');
  expect(preserved.tokens.colors.primary).toBe('#123456');
});

test('studio preset tokens travel to the hub through the navigation bridge', async ({ page }) => {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  const encoded = await page.evaluate(() => {
    applyPreset('linear');
    return VASThemeState.encodeNavigationState(VASThemeState.get());
  });
  await page.goto(`${hubUrl}#vas=${encoded}`, { waitUntil: 'domcontentloaded' });
  const result = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    return {
      preset: document.documentElement.dataset.preset,
      background: getComputedStyle(document.body).backgroundColor,
      primary: style.getPropertyValue('--primary').trim(),
      accent: style.getPropertyValue('--editorial-accent').trim(),
      padding: style.getPropertyValue('--space').trim(),
      radius: style.getPropertyValue('--radius').trim(),
      shadow: style.getPropertyValue('--shadow-size').trim(),
      motion: style.getPropertyValue('--motion').trim()
    };
  });
  expect(result).toEqual({
    preset: 'linear', background: 'rgb(11, 12, 15)', primary: '#6f7db8', accent: '#6f7db8',
    padding: '24px', radius: '8px', shadow: '20px', motion: '0.2s'
  });

  const largeTypeState = await page.evaluate(() => {
    const tokens = VASStorage.getDefaultTheme();
    tokens.fontSize = 24;
    return VASThemeState.encodeNavigationState({ v: 1, preset: 'custom', tokens });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${hubUrl}#vas=${largeTypeState}`, { waitUntil: 'domcontentloaded' });
  await page.reload({ waitUntil: 'domcontentloaded' });
  const typeScale = await page.evaluate(() => ({
    body: parseFloat(getComputedStyle(document.body).fontSize),
    hero: parseFloat(getComputedStyle(document.querySelector('.hero h1')).fontSize),
    action: parseFloat(getComputedStyle(document.querySelector('.start-copy strong')).fontSize),
    tool: parseFloat(getComputedStyle(document.querySelector('.tool-list strong')).fontSize),
    privacyButton: parseFloat(getComputedStyle(document.querySelector('#acceptPersonalization')).fontSize)
  }));
  expect(typeScale.body).toBe(24);
  expect(typeScale.hero).toBeLessThanOrEqual(70);
  expect(typeScale.action).toBeLessThanOrEqual(28);
  expect(typeScale.tool).toBeLessThanOrEqual(18);
  expect(typeScale.privacyButton).toBeLessThanOrEqual(18);
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

test('all main screens fit narrow mobile widths without horizontal scrolling', async ({ page }) => {
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const url of [hubUrl, appUrl, clientUrl, importUrl, searchUrl, memoryUrl]) {
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      const dimensions = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth
      }));
      expect(dimensions.scroll, `${url} at ${width}px`).toBeLessThanOrEqual(dimensions.viewport + 1);
    }
  }
});

test('design studio mobile tabs keep settings and preview usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.controls')).toBeVisible();
  await page.getByRole('button', { name: '미리보기' }).click();
  await expect(page.locator('.preview')).toBeVisible();
  await expect(page.locator('#advPreview')).toBeVisible();
  await page.getByRole('button', { name: '설정', exact: true }).click();
  await expect(page.locator('#preset-container')).toBeVisible();
});
