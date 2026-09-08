const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const root = path.join(__dirname, '..', 'src');
const importUrl = pathToFileURL(path.join(root, 'project-import.html')).href;
const clientUrl = pathToFileURL(path.join(root, 'client-application.html')).href;

async function prepareExisting(page) {
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-result-import], .context-review')).toHaveCount(0);
  await page.locator('#folderPath').fill('Z:\\work\\legacy-app');
  await page.locator('#projectName').fill('legacy-app');
  await page.locator('#taskRequest').fill('모바일 오류를 고쳐 주세요.');
  await page.locator('#continueSettings').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
}

async function openCompatibilityResultImport(page) {
  await page.addScriptTag({ path: path.join(root, 'ai-result-import.js') });
  await page.evaluate(() => {
    VASAIResultImport.init({ sourceType: 'existing' });
    VASAIResultImport.open();
  });
}

async function downloadHandoff(page, selector) {
  const pending = page.waitForEvent('download');
  await page.locator(selector).click();
  const download = await pending;
  return JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
}

function aiResult(handoff, updates = {}) {
  return Object.assign({
    format: 'vas-ai-result', schemaVersion: 1,
    resultId: 'r_1234567890abcdef',
    handoffId: handoff.workflow.handoffId,
    handoffPayloadSha256: handoff.integrity.payloadSha256,
    iteration: handoff.workflow.iteration,
    sourceType: handoff.project.sourceType,
    status: 'incomplete',
    generatedBy: { tool: 'codex' },
    readback: {
      checkedFiles: ['src/app.js'], confirmedRules: ['AGENTS.md 확인'],
      confirmedEntrypoints: ['src/app.js'], commands: [], facts: ['진입점 확인'], assumptions: []
    },
    changes: { summary: '모바일 레이아웃을 수정했습니다.', relativeFiles: [{ path: 'src/app.js', action: 'modified', fromPath: null }] },
    tests: [{ name: 'browser', command: 'npm test', status: 'failed', summary: '1 failed' }],
    remaining: [{ severity: 'high', summary: '모바일 테스트 수정 필요', nextAction: '실패 테스트를 고칩니다.' }],
    nextRecommendedTask: '실패한 모바일 테스트를 고쳐 주세요.',
    safety: { absolutePathsExcluded: true, secretsExcluded: true, rawCommandOutputExcluded: true }
  }, updates);
}

test('default handoff skips repeat import and RAG review UI', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-result-import], .context-review')).toHaveCount(0);
  await page.locator('#projectName').fill('RAG 연결');
  await page.locator('#problemDescription').fill('모바일 오류를 고쳐 주세요.');
  await page.locator('#nextBtn').click();
  await page.locator('input[name="data_status"][value="none"]').check();
  await page.locator('#nextBtn').click();
  await page.locator('input[name="env_web"]').check();
  await page.locator('#nextBtn').click();
  await page.locator('input[name="budget"][value="unknown"]').check();
  await page.locator('#nextBtn').click();
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
  const handoff = await downloadHandoff(page, '#downloadHandoff');
  expect(handoff.schemaVersion).toBe(3);
  expect(handoff.context.rag).toEqual({ included: false, items: [] });
  expect(handoff.qualityGate.ragReviewed).toBe(true);
  expect(handoff.assistantGuide.pasteText).not.toContain('승인된 작업 기억(RAG)');
  expect(handoff.assistantGuide.pasteText).not.toContain('VAS-AI-RESULT.json');
});

test('verified AI result creates the next handoff iteration', async ({ page }) => {
  await prepareExisting(page);
  const first = await downloadHandoff(page, '#downloadJson');
  expect(first.workflow.iteration).toBe(1);
  await page.evaluate(document => VASHandoffWorkflow.remember(document), first);

  await openCompatibilityResultImport(page);
  await page.locator('#vasResultPasteButton').click();
  await page.locator('#vasResultPaste').fill(JSON.stringify(aiResult(first)));
  await page.locator('#vasResultReadPaste').click();
  await expect(page.locator('#vasResultStatus')).toContainText('일치합니다');
  await expect(page.locator('#vasResultState')).toHaveText('incomplete');
  await page.locator('#vasResultAccept').click();
  await expect(page.locator('.result-dialog')).not.toHaveAttribute('open', '');

  const second = await page.evaluate(async () => {
    const linked = VASHandoffWorkflow.current();
    const built = await VASAgentHandoffWeb.buildExisting('legacy-app', '모바일 오류를 고쳐 주세요.', {
      requirements: { included: true, value: { request: '모바일 오류를 고쳐 주세요.' } },
      design: VASSetupDesign.context(), rag: { included: false, items: [] },
      continuation: linked.context, preferences: { included: false, items: [] }
    }, { rag: { included: false, items: [] }, ragReviewed: true, continuation: linked.context, workflow: linked.workflow });
    return built.document;
  });
  expect(second.workflow.iteration).toBe(2);
  expect(second.workflow.parentResultId).toBe('r_1234567890abcdef');
  expect(second.context.continuation.included).toBe(true);
  expect(second.context.continuation.tests[0].status).toBe('failed');
  expect(JSON.stringify(second)).not.toContain('Z:\\work\\legacy-app');
});

test('unsafe or mismatched result cannot be connected', async ({ page }) => {
  await prepareExisting(page);
  const handoff = await downloadHandoff(page, '#downloadJson');
  const unsafe = aiResult(handoff, {
    handoffId: 'h_00000000000000000000000000000000',
    changes: { summary: 'bad', relativeFiles: [{ path: '../secret.txt', action: 'modified' }] }
  });
  await openCompatibilityResultImport(page);
  await page.locator('#vasResultPasteButton').click();
  await page.locator('#vasResultPaste').fill(JSON.stringify(unsafe));
  await page.locator('#vasResultReadPaste').click();
  await expect(page.locator('#vasResultStatus')).toContainText(/경로|형식/);
  await expect(page.locator('#vasResultReview')).toBeHidden();
});

test('compatibility review clears rejected input and rechecks duplicate acceptance', async ({ page }) => {
  await prepareExisting(page);
  const handoff = await downloadHandoff(page, '#downloadJson');
  await page.evaluate(document => VASHandoffWorkflow.remember(document), handoff);
  await openCompatibilityResultImport(page);
  const result = aiResult(handoff);
  await page.evaluate(raw => VASAIResultImport.readText(JSON.stringify(raw)), result);
  await expect(page.locator('#vasResultReview')).toBeVisible();
  await page.evaluate(() => VASAIResultImport.readText('{invalid'));
  await expect(page.locator('#vasResultReview')).toBeHidden();
  expect(await page.evaluate(() => VASAIResultImport.current())).toBeNull();
  await page.evaluate(raw => VASAIResultImport.readText(JSON.stringify(raw)), result);
  await page.evaluate(() => { document.getElementById('vasResultAccept').click(); document.getElementById('vasResultAccept').click(); });
  await expect(page.locator('#vasResultStatus')).toContainText(/이미|중복/);
  expect(await page.evaluate(() => VASHandoffWorkflow.current().workflow.iteration)).toBe(2);
});

test('a removed receipt requires a new visible manual confirmation before acceptance', async ({ page }) => {
  await prepareExisting(page);
  const handoff = await downloadHandoff(page, '#downloadJson');
  await page.evaluate(document => VASHandoffWorkflow.remember(document), handoff);
  await openCompatibilityResultImport(page);
  await page.evaluate(raw => VASAIResultImport.readText(JSON.stringify(raw)), aiResult(handoff));
  await page.evaluate(() => VASHandoffWorkflow.clearReceipts());
  await page.locator('#vasResultAccept').click();
  await expect(page.locator('#vasResultManualRow')).toBeVisible();
  await expect(page.locator('#vasResultManual')).not.toBeChecked();
  expect(await page.evaluate(() => VASHandoffWorkflow.current())).toBeNull();
  await page.locator('#vasResultManual').check(); await page.locator('#vasResultAccept').click();
  expect(await page.evaluate(() => VASHandoffWorkflow.current().workflow.iteration)).toBe(2);
});

test('compatibility import rejects results without the payload hash', async ({ page }) => {
  await prepareExisting(page);
  const handoff = await downloadHandoff(page, '#downloadJson');
  const missingHash = aiResult(handoff);
  delete missingHash.handoffPayloadSha256;
  await openCompatibilityResultImport(page);
  await page.locator('#vasResultPasteButton').click();
  await page.locator('#vasResultPaste').fill(JSON.stringify(missingHash));
  await page.locator('#vasResultReadPaste').click();
  await expect(page.locator('#vasResultStatus')).toContainText(/해시|형식/);
  await expect(page.locator('#vasResultReview')).toBeHidden();
});

test('blocked storage still allows a handoff without optional review UI', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new Error('blocked'); } });
    Object.defineProperty(window, 'indexedDB', { configurable: true, get() { throw new Error('blocked'); } });
  });
  await prepareExisting(page);
  await expect(page.locator('[data-context-item], [data-context-confirm]')).toHaveCount(0);
  const handoff = await downloadHandoff(page, '#downloadJson');
  expect(handoff.context.rag).toEqual({ included: false, items: [] });
  expect(handoff.qualityGate.ragReviewed).toBe(true);
});

test('late file reads cannot restore rejected input or supersede a newer file', async ({ page }) => {
  await prepareExisting(page);
  const handoff = await downloadHandoff(page, '#downloadJson');
  await openCompatibilityResultImport(page);
  await page.evaluate(() => {
    window.readers = [];
    window.FileReader = class { constructor() { readers.push(this); } readAsText() {} };
  });
  await page.locator('#vasResultFile').setInputFiles({ name: 'old.json', mimeType: 'application/json', buffer: Buffer.from('{}') });
  await page.evaluate(raw => {
    VASAIResultImport.readText('{invalid');
    readers[0].result = JSON.stringify(raw); readers[0].onload();
  }, aiResult(handoff));
  expect(await page.evaluate(() => VASAIResultImport.current())).toBeNull();
  await expect(page.locator('#vasResultReview')).toBeHidden();
  await page.locator('#vasResultFile').setInputFiles({ name: 'second.json', mimeType: 'application/json', buffer: Buffer.from('{}') });
  await page.locator('#vasResultFile').setInputFiles({ name: 'third.json', mimeType: 'application/json', buffer: Buffer.from('{}') });
  await page.evaluate(raw => {
    readers[2].result = JSON.stringify(raw); readers[2].onload();
    readers[1].result = '{invalid'; readers[1].onload();
  }, aiResult(handoff));
  await expect(page.locator('#vasResultReview')).toBeVisible();
  expect(await page.evaluate(() => VASAIResultImport.current().resultId)).toBe('r_1234567890abcdef');
});

for (const blocked of [false, true]) {
  test('manual result acceptance is once per session with ' + (blocked ? 'blocked storage' : 'missing receipt'), async ({ page }) => {
    if (blocked) await page.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw Error('blocked'); } });
    });
    await prepareExisting(page);
    const handoff = await downloadHandoff(page, '#downloadJson');
    await page.evaluate(() => VASHandoffWorkflow.clearReceipts());
    await openCompatibilityResultImport(page);
    const raw = aiResult(handoff);
    const result = await page.evaluate(value => {
      let accepted = 0;
      VASAIResultImport.init({ sourceType: 'existing', onAccepted: () => { accepted += 1; } });
      VASAIResultImport.readText(JSON.stringify(value));
      document.getElementById('vasResultManual').checked = true;
      document.getElementById('vasResultAccept').click();
      document.getElementById('vasResultAccept').click();
      return accepted;
    }, raw);
    expect(result).toBe(1);
    await page.evaluate(value => {
      document.querySelector('[data-result-close]').click();
      VASAIResultImport.open();
      VASAIResultImport.readText(JSON.stringify({ ...value, resultId: 'r_fedcba0987654321' }));
    }, raw);
    // Deliberately cross the old close timer's deadline to verify cancellation.
    await page.waitForTimeout(650);
    await expect(page.locator('.result-dialog')).toHaveAttribute('open', '');
    await expect(page.locator('#vasResultReview')).toBeVisible();
  });
}
