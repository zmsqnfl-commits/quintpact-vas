const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const cases = require('./fixtures/secret-redaction-cases.json');
const script = name => path.join(__dirname, '..', 'src', name);
const source = name => pathToFileURL(script(name)).href;

test('memory filters current and historical values before export and recommendation', async ({ page }) => {
  await page.evaluate(input => {
    window.rows = input.map((item, i) => ({ id: 'old_' + i, type: 'theme_selected', timestamp: '2026-09-08', payload: { preset: 'bento', note: item.input }, source: 'sk-MetadataCanaryMetadataCanary' }));
    const meta = { consent: true, profile: { terms: ['historicalprofilecanary'] } };
    window.VASLocalMemoryAdapter = { init: async () => {}, list: async () => rows, getMeta: async key => meta[key], setMeta: async (key, value) => { meta[key] = value; }, put: async event => { rows.push(event); return event; }, remove: async () => {}, clear: async () => { rows.length = 0; } };
    window.VASRagLite = { tokenize: value => value.toLowerCase().match(/[a-z0-9]{2,}/g) || [], recommend: (query, settings) => settings };
  }, cases);
  await page.addScriptTag({ path: script('personalization-store.js') });
  const result = await page.evaluate(async input => {
    const legacy = await VASPersonalization.export();
    const recommendation = await VASPersonalization.recommend('bento');
    await VASPersonalization.clear();
    await VASPersonalization.import({ schema: 1, events: input.map(item => ({ type: 'theme_selected', payload: { preset: 'bento', note: item.input } })) });
    return { legacy, recommendation, imported: await VASPersonalization.export() };
  }, cases);
  for (const output of [result.legacy, result.recommendation, result.imported]) {
    const raw = JSON.stringify(output);
    for (const item of cases) expect(raw, item.name).not.toContain(item.marker);
    expect(raw).not.toContain('MetadataCanary');
    expect(raw).not.toContain('historicalprofilecanary');
    expect(raw).toContain('bento');
  }
});

test('profile cache failure cannot turn a committed event into a failed write', async ({ page }) => {
  await page.evaluate(() => {
    const rows = [];
    window.VASLocalMemoryAdapter = { init: async () => {}, list: async () => rows, getMeta: async key => key === 'consent', setMeta: async () => { throw Error('profile disk failure'); }, put: async event => { rows.push(event); return event; }, remove: async () => {}, clear: async () => { rows.length = 0; } };
    window.changes = [];
    addEventListener('vas-memory-change', event => changes.push(event.detail.action));
  });
  await page.addScriptTag({ path: script('personalization-store.js') });
  const result = await page.evaluate(async () => {
    const saved = await VASPersonalization.record('theme_selected', { preset: 'bento' });
    let failed = false;
    try { await VASPersonalization.clear(); } catch (error) { failed = /profile disk failure/.test(error.message); }
    return { saved: !!saved, failed, count: (await VASPersonalization.list()).length, changes };
  });
  expect(result).toEqual({ saved: true, failed: true, count: 1, changes: ['record'] });
});

test('late confirmation cannot overwrite the deduplication state after memory is cleared', async ({ page }) => {
  await page.goto(source('project-import.html'));
  const result = await page.evaluate(async () => {
    let attempts = 0, release;
    const deferred = new Promise(resolve => { release = resolve; });
    window.VASPersonalization = { record: async () => { attempts += 1; if (attempts === 1) await deferred; return { id: 'saved' }; } };
    const old = VASSetupDesign.confirm();
    dispatchEvent(new CustomEvent('vas-memory-change', { detail: { action: 'clear' } }));
    await VASSetupDesign.confirm();
    release(); await old;
    await VASSetupDesign.confirm();
    return attempts;
  });
  expect(result).toBe(2);
});

test('inherited names cannot select a design profile or break prompt generation', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(source('design-controller.html'));
  for (const mode of ['constructor', '__proto__', 'toString']) {
    await page.evaluate(value => setTasteProfileMode(value), mode);
    await expect(page.locator('#tasteProfileMode')).toHaveValue('auto');
    await expect(page.locator('#aiPrompt')).not.toHaveValue('');
  }
  await page.locator('#tasteProfileMode').selectOption('dataTool');
  await expect(page.locator('#aiPrompt')).toHaveValue(/Data Tool/);
  expect(errors).toEqual([]);
});
