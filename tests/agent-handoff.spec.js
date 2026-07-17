const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const importUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'project-import.html')).href;

async function prepareExisting(page, name = '레거시 앱') {
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#folderPath').fill('Z:\\work\\legacy-app');
  await page.locator('#projectName').fill(name);
  await page.locator('#taskRequest').fill('모바일 오류를 고쳐 주세요. contact@example.com api_key=sk-proj-1234567890abcdef');
  await page.locator('#continueSettings').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await page.locator('[data-context-confirm]').click();
}

test('existing handoff uses a self-contained prompt without guessing project structure', async ({ page }) => {
  await prepareExisting(page);
  await expect(page.locator('#selectFolder')).toHaveText('폴더 위치');
  await expect(page.locator('#modeLabel, [data-preview], #analyzeButton, #analysisGrid')).toHaveCount(0);
  await expect(page.locator('#previewContent')).toContainText('Z:\\work\\legacy-app');
  await expect(page.locator('#previewContent')).toContainText('실제 파일을 직접 읽어 판단하세요');
  await expect(page.locator('#previewContent')).toContainText('모바일 오류를 고쳐 주세요');
  await expect(page.locator('#previewContent')).toContainText('VAS-AI-RESULT.json');
  const prompt = await page.locator('#previewContent').textContent();
  expect(prompt).not.toContain('contact@example.com');
  expect(prompt).not.toContain('sk-proj-1234567890abcdef');

  await page.locator('#provider').selectOption('claude');
  await expect(page.locator('#previewContent')).toContainText('Claude에서 실제 작업할 원본 프로젝트 폴더를 여세요');
  await page.locator('#provider').selectOption('codex');
  await expect(page.locator('#previewContent')).toContainText('Codex에서 실제 작업할 원본 프로젝트 폴더를 여세요');
});

test('JSON remains optional and copied prompt completes the flow', async ({ page }) => {
  await page.addInitScript(() => { document.execCommand = () => true; });
  await prepareExisting(page, '<script>alert(1)</script>');
  const download = page.waitForEvent('download');
  await page.locator('#downloadJson').click();
  const result = await download;
  expect(result.suggestedFilename()).toBe('VAS-AI-HANDOFF.json');
  const document = JSON.parse(fs.readFileSync(await result.path(), 'utf8'));
  expect(document.schemaVersion).toBe(3);
  expect(document.workflow.handoffId).toMatch(/^h_[a-f0-9]{32}$/);
  expect(document.workflow.iteration).toBe(1);
  expect(document.qualityGate.ragReviewed).toBe(true);
  expect(document.mode).toBe('intent-only');
  expect(document).not.toHaveProperty('analysis');
  expect(document).not.toHaveProperty('inventory');
  expect(document.security.projectStructureInferred).toBe(false);
  expect(document.security.technologyStackInferred).toBe(false);
  expect(JSON.stringify(document)).not.toContain('Z:\\work\\legacy-app');
  await page.locator('#copyPrompt').click();
  await expect(page.locator('[data-step="3"]')).toHaveClass(/active/);
  await expect(page.locator('#resultMessage')).toContainText('프롬프트를 복사했습니다');
  expect(await page.locator('img').count()).toBe(0);
});

test('AI handoff layout has no horizontal overflow on small screens', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  const size = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(size.scroll).toBeLessThanOrEqual(size.viewport + 1);
  await expect(page.locator('#projectName')).toBeVisible();
  await expect(page.locator('#folderPath')).toBeVisible();
  await expect(page.locator('#selectFolder')).toBeVisible();
  await expect(page.locator('.preview')).toBeVisible();
});
