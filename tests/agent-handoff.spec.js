const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const importUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'project-import.html')).href;

async function installFolder(page, name = '레거시 앱') {
  await page.addInitScript(({ folderName }) => {
    window.showDirectoryPicker = async () => ({
      name: folderName,
      async *values() {
        yield { kind: 'file', name: 'package.json', getFile: async () => ({ size: 140 }) };
        yield { kind: 'file', name: 'src-main.js', getFile: async () => ({ size: 320 }) };
        yield { kind: 'file', name: '.env', getFile: async () => ({ size: 30 }) };
        yield { kind: 'file', name: '<img src=x onerror=alert(1)>.js', getFile: async () => ({ size: 20 }) };
      }
    });
  }, { folderName: name });
}

test('web AI handoff produces safe stable JSON and provider-only prompt changes', async ({ page }) => {
  await installFolder(page);
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#selectFolder').click();
  await page.locator('#taskRequest').fill('모바일 오류를 고쳐 주세요. contact@example.com api_key=sk-proj-1234567890abcdef');
  await page.locator('#analyzeButton').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await expect(page.locator('#analysisGrid')).toContainText('JavaScript/TypeScript');
  await expect(page.locator('#riskList')).toContainText('비밀값 후보 1개');
  const firstJson = await page.locator('#previewContent').textContent();
  expect(firstJson).not.toContain('.env');
  expect(firstJson).not.toContain('C:\\');
  expect(firstJson).not.toContain('contact@example.com');
  expect(firstJson).not.toContain('sk-proj-1234567890abcdef');
  await page.locator('#continueReview').click();
  await expect(page.locator('#handoffDesignPreset')).toHaveValue('awwwards');
  await page.locator('#provider').selectOption('claude');
  await page.locator('[data-preview="prompt"]').click();
  await expect(page.locator('#previewContent')).toContainText('Claude에서 원본 프로젝트 폴더를 연 뒤');
  await page.locator('#provider').selectOption('codex');
  await expect(page.locator('#previewContent')).toContainText('Codex에서 원본 프로젝트 폴더를 연 뒤');
  await page.locator('[data-preview="json"]').click();
  expect(await page.locator('#previewContent').textContent()).toBe(firstJson);
});

test('download and clipboard fallback finish without executing hostile file names', async ({ page }) => {
  await installFolder(page, '<script>alert(1)</script>');
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => { document.execCommand = () => true; });
  await page.locator('#selectFolder').click();
  await page.locator('#taskRequest').fill('안전하게 오류를 고쳐 주세요.');
  await page.locator('#analyzeButton').click();
  await page.locator('#continueReview').click();
  const download = page.waitForEvent('download');
  await page.locator('#downloadJson').click();
  expect((await download).suggestedFilename()).toBe('VAS-AI-HANDOFF.json');
  await expect(page.locator('[data-step="4"]')).toHaveClass(/active/);
  expect(await page.locator('script').count()).toBeGreaterThan(0);
  expect(await page.locator('img').count()).toBe(0);
});

test('AI handoff layout has no horizontal overflow on small screens', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  const size = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(size.scroll).toBeLessThanOrEqual(size.viewport + 1);
  await expect(page.locator('#selectFolder')).toBeVisible();
  await expect(page.locator('.preview')).toBeVisible();
});
