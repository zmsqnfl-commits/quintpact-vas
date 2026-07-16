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
  await expect(page.locator('#privacyRail')).toBeVisible();
  await expect(page.locator('#privacyRail h2')).toHaveText('이 기기에서 작업 흐름을 기억할까요?');
  await expect(page.locator('#privacyRail')).toContainText('현재 프로젝트');
  await expect(page.locator('#declinePersonalization')).toHaveText('기억하지 않기');
  await expect(page.locator('#acceptPersonalization')).toHaveText('기억하고 계속');
  await page.locator('#declinePersonalization').click();
  await expect(page.locator('#privacyRail')).not.toBeVisible();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#privacyRail')).not.toBeVisible();
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

test('project context stays minimal and automatically scopes new memory', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const result = await page.evaluate(async () => {
    VASProjectContext.set({
      projectId: 'project-123', sourceType: 'imported', goal: 'redesign', stage: 'design',
      name: 'should-not-travel', path: 'C:\\private\\project'
    });
    const wrapper = document.createElement('div');
    wrapper.innerHTML = '<a data-vas-project-link href="design-controller.html">계속</a>';
    VASProjectContext.decorateLinks(wrapper);
    await VASPersonalization.init();
    await VASPersonalization.consent(true);
    const event = await VASPersonalization.record({
      type: 'navigation', source: 'test', payload: { action: 'continue' }
    });
    return {
      context: VASProjectContext.get(),
      href: wrapper.querySelector('a').href,
      eventProjectId: event && event.projectId,
      stored: JSON.parse(sessionStorage.getItem('vasProjectContext'))
    };
  });
  expect(result.context.projectId).toBe('project-123');
  expect(result.href).toContain('vasProject=project-123');
  expect(result.href).not.toContain('should-not-travel');
  expect(JSON.stringify(result.stored)).not.toContain('private');
  expect(result.eventProjectId).toBe('project-123');
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
