const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const appUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'client-application.html')).href;

async function waitStep(page, step) {
  await page.locator(`.step[data-step="${step}"].active`).waitFor();
  await page.waitForTimeout(450);
}

async function reachDone(page) {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('input[name="project_name"]').fill('Safe Flow');
  await page.locator('textarea[name="problem_desc"]').fill('안전한 작업 흐름을 만들어 주세요. contact@example.com api_key=sk-proj-1234567890abcdef');
  await page.locator('#nextBtn').click();
  await waitStep(page, 2);
  await page.locator('.step.active label.v-block').nth(1).click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 3);
  await page.locator('.step.active label.block').first().click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 4);
  await page.locator('.step.active label.v-block').last().click();
  await page.locator('#nextBtn').click();
  await waitStep(page, 5);
  await page.locator('#projectDesignPreset').selectOption('awwwards');
  await expect(page.locator('[data-context-confirm], [data-result-import]')).toHaveCount(0);
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
}

test('new project flow is step-by-step and safely renders file names', async ({ page }) => {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#progressText')).toContainText('01');
  await expect(page.locator('#nextBtn')).toContainText('다음');
  await expect(page.locator('input[name="client_name"], input[name="contact"]')).toHaveCount(0);
  await page.locator('input[name="project_name"]').fill('Safe Flow');
  await page.locator('textarea[name="problem_desc"]').fill('Need a safe workflow.');
  await page.locator('#fileInput').setInputFiles({ name: '<script>alert(1)</script>.txt', mimeType: 'text/plain', buffer: Buffer.from('reference') });
  await expect(page.locator('#fileChips')).toContainText('<script>alert(1)</script>.txt');
  await expect(page.locator('#fileChips script')).toHaveCount(0);
  await page.locator('#nextBtn').click();
  await waitStep(page, 2);
});

test('new project produces the common safe VAS-AI-HANDOFF.json', async ({ page }) => {
  await reachDone(page);
  await expect(page.locator('#handoffReview')).toContainText('사용 중인 코딩 도구에서 새 프로젝트를 만들 빈 폴더를 여세요');
  await expect(page.locator('#handoffReview')).toContainText('Preset: awwwards');
  await expect(page.locator('#handoffReview')).not.toContainText('VAS-AI-RESULT.json');
  const download = page.waitForEvent('download');
  await page.locator('#downloadHandoff').click();
  const result = await download;
  expect(result.suggestedFilename()).toBe('VAS-AI-HANDOFF.json');
  const document = JSON.parse(fs.readFileSync(await result.path(), 'utf8'));
  expect(document.project.sourceType).toBe('new');
  expect(document.context.design.preset).toBe('awwwards');
  const body = JSON.stringify(document);
  expect(body).not.toContain('contact@example.com');
  expect(body).not.toContain('sk-proj-1234567890abcdef');
  expect(body).toContain('[contact]');
  expect(body).toContain('[secret]');
  expect(body).not.toContain('client_name');
  await expect(page.locator('#handoffStatus')).toContainText('저장했습니다');
});

test('new project shows visible required selection feedback', async ({ page }) => {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('input[name="project_name"]').fill('Safe Flow');
  await page.locator('textarea[name="problem_desc"]').fill('Need a safe workflow.');
  await page.locator('#nextBtn').click();
  await waitStep(page, 2);
  await page.locator('#nextBtn').click();
  await expect(page.locator('[data-validation-message]')).toContainText('필수 항목');
  await expect(page.locator('#doneScreen')).not.toHaveClass(/active/);
});
