const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;
const hubUrl = source('vas-hub.html');
const clientUrl = source('client-application.html');
const designUrl = source('design-controller.html');
const importUrl = source('project-import.html');

test('first visit asks for personalization consent and respects decline', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#privacyDialog')).toBeVisible();
  await page.locator('#declinePersonalization').click();
  await expect(page.locator('#privacyDialog')).not.toBeVisible();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#privacyDialog')).not.toBeVisible();
  expect(await page.evaluate(() => VASPersonalization.getConsent())).toBe(false);
});

test('theme state flows from design studio to client form', async ({ page }) => {
  await page.goto(designUrl, { waitUntil: 'domcontentloaded' });
  const expected = await page.evaluate(() => {
    applyPreset('stripe');
    return { primary: PRESETS.stripe.primary, href: document.querySelector('a[data-vas-link]').href };
  });
  expect(expected.href).toContain('#vas=');
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim())).toBe(expected.primary);
});

test('form draft is explicit and restorable', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.draft-policy')).toContainText('자동 저장');
  await page.locator('input[name="client_name"]').fill('Restore Test');
  await page.locator('input[name="contact"]').fill('restore@example.com');
  await page.waitForTimeout(350);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#draftNotice')).toBeVisible();
  await page.getByRole('button', { name: '복원' }).click();
  await expect(page.locator('input[name="client_name"]')).toHaveValue('Restore Test');
});

test('RAG searches local docs and sanitizes personal memory', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const result = await page.evaluate(async () => {
    await VASPersonalization.init();
    await VASPersonalization.consent(true);
    await VASPersonalization.record({
      type: 'navigation', source: 'test',
      payload: { topic: '기존 프로젝트 마이그레이션', path: 'C:\\Users\\name\\secret.txt', note: 'api_key=sk-test-secret-1234567890' }
    });
    const events = await VASPersonalization.list();
    const matches = await VASPersonalization.retrieve('기존 프로젝트 가져오기', { limit: 5 });
    return { payload: events[0] && events[0].payload, matches };
  });
  expect(JSON.stringify(result.payload)).not.toContain('C:\\Users');
  expect(JSON.stringify(result.payload)).not.toContain('sk-test');
  expect(result.matches.some(item => item.kind === 'knowledge')).toBe(true);
});

test('consented local memory produces a transparent next-work recommendation', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await page.evaluate(async () => {
    await VASPersonalization.init();
    await VASPersonalization.consent(true);
    await VASPersonalization.record({
      type: 'navigation', source: 'test', payload: { action: '기존 프로그램 가져오기 마이그레이션' }
    });
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#nextRecommendation')).toBeVisible();
  await expect(page.locator('#recommendationTitle')).toContainText('기존 프로그램 가져오기');
  await expect(page.locator('#recommendationCopy')).toContainText('이 기기');
});

test('blocked session storage keeps runtime token in memory and URL fragment', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'sessionStorage', { configurable: true, get() { throw new Error('blocked'); } });
  });
  const token = 'runtime_token_12345678901234567890';
  await page.goto(hubUrl + '?vasToken=' + token, { waitUntil: 'domcontentloaded' });
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
  expect(page.url()).not.toContain('vasToken=');
  expect(page.url()).toContain('vasRuntime=');
  expect(await page.locator('a[data-vas-link]').first().getAttribute('href')).toContain('vasRuntime=');
});

test('web migration mode analyzes a selected folder without importing', async ({ page }) => {
  await page.addInitScript(() => {
    window.showDirectoryPicker = async () => ({
      name: 'legacy-app',
      async *values() {
        yield { kind: 'file', name: 'package.json', getFile: async () => ({ size: 120 }) };
        yield { kind: 'file', name: 'index.html', getFile: async () => ({ size: 240 }) };
        yield { kind: 'file', name: '.env', getFile: async () => ({ size: 30 }) };
      }
    });
  });
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#createIndex')).not.toBeChecked();
  await page.locator('#selectFolder').click();
  await expect(page.locator('#selectedPath')).toHaveText('legacy-app');
  await page.locator('#analyzeButton').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await expect(page.locator('#analysisGrid')).toContainText('JavaScript/TypeScript');
  await expect(page.locator('#webNote')).toBeVisible();
  await expect(page.locator('#configureButton')).toBeDisabled();
});
