const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;
const hubUrl = source('vas-hub.html');
const clientUrl = source('client-application.html');
const designUrl = source('design-controller.html');
const importUrl = source('project-import.html');

test('start screen only shows the two choices and never asks for memory automatically', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.hero')).toBeVisible();
  await expect(page.locator('.start-card')).toHaveCount(2);
  await expect(page.locator('.start-card').first()).toContainText('새 프로젝트 만들기');
  await expect(page.locator('.start-card').last()).toContainText('기존 프로그램 AI로 연결');
  await expect(page.locator('#privacyRail, #onboarding, .tools-section, .projects-section, #nextRecommendation')).toHaveCount(0);
  expect(await page.evaluate(() => VASPersonalization.getConsent())).toBeNull();
});

test('help and memory settings can always be reopened and changed', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const header = page.locator('.site-header');
  await header.getByRole('button', { name: '사용 방법' }).click();
  await expect(page.locator('#vasSetupHelp')).toBeVisible();
  await expect(page.locator('#vasSetupHelp')).toContainText('JSON을 코딩 도구에 줍니다');
  await page.locator('#vasSetupHelp [data-setup-close]').click();
  await header.getByRole('button', { name: '사용 방법' }).click();
  await expect(page.locator('#vasSetupHelp')).toBeVisible();
  await page.locator('#vasSetupHelp [data-setup-close]').click();

  await header.getByRole('button', { name: '설정' }).click();
  await expect(page.locator('#vasSetupMemoryState')).toHaveText('사용 안 함');
  await page.locator('#vasSetupToggleMemory').click();
  await expect(page.locator('#vasSetupMemoryState')).toContainText('사용 중');
  await page.locator('#vasSetupTogglePause').click();
  await expect(page.locator('#vasSetupMemoryState')).toContainText('잠시 중지됨');
  await page.locator('#vasSetupSettings [data-setup-close]').click();
  await header.getByRole('button', { name: '설정' }).click();
  await expect(page.locator('#vasSetupMemoryState')).toContainText('잠시 중지됨');
});

test('theme state flows from design studio to the new project form', async ({ page }) => {
  await page.goto(designUrl, { waitUntil: 'domcontentloaded' });
  const expected = await page.evaluate(() => {
    applyPreset('stripe');
    return { primary: PRESETS.stripe.primary, href: document.querySelector('a[data-vas-link]').href };
  });
  expect(expected.href).toContain('#vas=');
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim())).toBe(expected.primary);
});

test('project context remains minimal for compatibility', async ({ page }) => {
  await page.goto(designUrl, { waitUntil: 'domcontentloaded' });
  const result = await page.evaluate(() => {
    VASProjectContext.set({ projectId: 'project-123', sourceType: 'imported', goal: 'redesign', stage: 'design', name: 'private', path: 'C:\\private' });
    const wrapper = document.createElement('div');
    wrapper.innerHTML = '<a data-vas-project-link href="design-controller.html">계속</a>';
    VASProjectContext.decorateLinks(wrapper);
    return { context: VASProjectContext.get(), href: wrapper.querySelector('a').href, stored: sessionStorage.getItem('vasProjectContext') };
  });
  expect(result.context.projectId).toBe('project-123');
  expect(result.href).toContain('vasProject=project-123');
  expect(result.href).not.toContain('private');
  expect(result.stored).not.toContain('C:\\private');
});

test('form draft is explicit and restorable without contact details', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.draft-policy')).toContainText('자동 저장');
  await page.locator('input[name="project_name"]').fill('Restore Test');
  await page.locator('textarea[name="problem_desc"]').fill('복원할 요구사항');
  await page.waitForTimeout(350);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#draftNotice')).toBeVisible();
  await page.getByRole('button', { name: '복원' }).click();
  await expect(page.locator('input[name="project_name"]')).toHaveValue('Restore Test');
});

test('local memory sanitizes secrets and absolute paths', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const payload = await page.evaluate(async () => {
    await VASPersonalization.init();
    await VASPersonalization.consent(true);
    await VASPersonalization.record({ type: 'navigation', source: 'test', payload: { topic: '마이그레이션', path: 'C:\\Users\\name\\secret.txt', note: 'api_key=sk-test-secret-1234567890' } });
    return (await VASPersonalization.list())[0].payload;
  });
  expect(JSON.stringify(payload)).not.toContain('C:\\Users');
  expect(JSON.stringify(payload)).not.toContain('sk-test');
});

test('blocked session storage keeps runtime token in memory and URL fragment', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'sessionStorage', { configurable: true, get() { throw new Error('blocked'); } }); });
  const token = 'runtime_token_12345678901234567890';
  await page.goto(importUrl + '?vasToken=' + token, { waitUntil: 'domcontentloaded' });
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
  expect(page.url()).not.toContain('vasToken=');
  expect(page.url()).toContain('vasRuntime=');
});

test('web mode analyzes a selected folder without copying or registration controls', async ({ page }) => {
  await page.addInitScript(() => {
    window.showDirectoryPicker = async () => ({ name: 'legacy-app', async *values() {
      yield { kind: 'file', name: 'package.json', getFile: async () => ({ size: 120 }) };
      yield { kind: 'file', name: 'index.html', getFile: async () => ({ size: 240 }) };
      yield { kind: 'file', name: '.env', getFile: async () => ({ size: 30 }) };
    } });
  });
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#selectFolder').click();
  await page.locator('#taskRequest').fill('오류를 고쳐 주세요.');
  await page.locator('#analyzeButton').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await expect(page.locator('#analysisGrid')).toContainText('JavaScript/TypeScript');
  await expect(page.locator('#webNote')).toBeVisible();
  await expect(page.locator('#advancedMigration, #createIndex, #configureButton')).toHaveCount(0);
});
