/** Reproduce the real VAS form -> downloaded JSON -> coding prompt flow. */
const { chromium } = require('@playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
  const root = path.resolve(__dirname, '..');
  const folder = path.join(root, 'docs/verification');
  const request = JSON.parse(fs.readFileSync(path.join(folder, 'creative-board-request.json'), 'utf8'));
  const chrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await chromium.launch(fs.existsSync(chrome) ? { executablePath: chrome } : {});
  try {
    const page = await browser.newPage({ acceptDownloads: true });
    await page.goto(pathToFileURL(path.join(root, 'src/client-application.html')).href);
    await page.getByLabel('프로젝트 이름', { exact: true }).fill(request.project_name);
    await page.getByLabel('해결할 문제와 원하는 결과').fill(request.problem_desc);
    await page.locator('#nextBtn').click();
    await page.locator('label').filter({ has: page.locator('[name="sense_text"]') }).click();
    await page.locator('label').filter({ has: page.locator('[name="data_status"][value="none"]') }).click();
    await page.locator('#nextBtn').click();
    await page.locator('label').filter({ has: page.locator('[name="env_web"]') }).click();
    await page.locator('#nextBtn').click();
    await page.locator('#projectDeadline').fill(request.deadline);
    await page.locator('label').filter({ has: page.locator('[name="budget"][value="mvp"]') }).click();
    await page.locator('#projectExtra').fill(request.extra);
    await page.locator('#nextBtn').click();
    await page.locator('#projectDesignPreset').selectOption(request.preset);
    await page.locator('#nextBtn').click();
    await page.locator('#doneScreen.active').waitFor();
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#downloadHandoff').click();
    const download = await downloadPromise;
    const output = path.join(folder, 'creative-board-handoff.json');
    await download.saveAs(output);
    const document = JSON.parse(fs.readFileSync(output, 'utf8'));
    assert.equal(document.context.design.preset, request.preset);
    assert.equal(document.context.design.tasteProfileMode, 'auto');
    assert.equal(document.task.request, request.problem_desc);
    assert.equal(document.integrity.payloadSha256.length, 64);
    for (const role of ['designer', 'implementer', 'reviewer']) assert.ok(document.assistantGuide.pasteText.includes('[ROLE INSTRUCTIONS: ' + role + ']'));
    const prompt = await page.locator('#handoffReview').textContent();
    assert.equal(prompt, document.assistantGuide.pasteText);
    fs.writeFileSync(path.join(folder, 'creative-board-handoff.txt'), prompt + '\n', 'utf8');
    console.log(JSON.stringify({ exportedThrough: 'five-step VAS form and JSON download', handoffId: document.workflow.handoffId,
      payloadSha256: document.integrity.payloadSha256, preset: document.context.design.preset, rolesIncluded: 3 }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
