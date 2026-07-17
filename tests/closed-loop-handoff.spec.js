const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const root = path.join(__dirname, '..', 'src');
const importUrl = pathToFileURL(path.join(root, 'project-import.html')).href;
const clientUrl = pathToFileURL(path.join(root, 'client-application.html')).href;

async function prepareExisting(page) {
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#folderPath').fill('Z:\\work\\legacy-app');
  await page.locator('#projectName').fill('legacy-app');
  await page.locator('#taskRequest').fill('모바일 오류를 고쳐 주세요.');
  await page.locator('#continueSettings').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await page.locator('[data-context-confirm]').click();
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

test('approved RAG only enters handoff v3 and the prompt', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await page.evaluate(async () => {
    await VASPersonalization.init();
    await VASPersonalization.consent(true);
    await VASPersonalization.clear();
    await VASPersonalization.record({
      type: 'feedback', source: 'closed-loop-test',
      payload: { topic: '모바일 오류', outcome: '작은 화면에서 선택 영역을 명확하게 표시' }
    });
  });
  await page.locator('#projectName').fill('RAG 연결');
  await page.locator('#problemDescription').fill('모바일 오류를 고쳐 주세요.');
  await page.locator('#nextBtn').click();
  await page.locator('input[name="data_status"][value="none"]').check();
  await page.locator('#nextBtn').click();
  await page.locator('input[name="env_web"]').check();
  await page.locator('#nextBtn').click();
  await page.locator('input[name="budget"][value="unknown"]').check();
  await page.locator('#nextBtn').click();
  await expect(page.locator('[data-context-item]')).toHaveCount(1);
  await page.locator('[data-context-item]').check();
  await page.locator('[data-context-confirm]').click();
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
  const handoff = await downloadHandoff(page, '#downloadHandoff');
  expect(handoff.schemaVersion).toBe(3);
  expect(handoff.context.rag.included).toBe(true);
  expect(handoff.context.rag.items).toHaveLength(1);
  expect(handoff.context.rag.items[0].userApproved).toBe(true);
  expect(handoff.assistantGuide.pasteText).toContain('승인된 작업 기억(RAG)');
  expect(handoff.assistantGuide.pasteText).toContain('VAS-AI-RESULT.json');
});

test('verified AI result creates the next handoff iteration', async ({ page }) => {
  await prepareExisting(page);
  const first = await downloadHandoff(page, '#downloadJson');
  expect(first.workflow.iteration).toBe(1);

  await page.locator('[data-result-import]:visible').first().click();
  await page.locator('#vasResultPasteButton').click();
  await page.locator('#vasResultPaste').fill(JSON.stringify(aiResult(first)));
  await page.locator('#vasResultReadPaste').click();
  await expect(page.locator('#vasResultStatus')).toContainText('일치합니다');
  await expect(page.locator('#vasResultState')).toHaveText('incomplete');
  await page.locator('#vasResultAccept').click();
  await expect(page.locator('.result-dialog')).not.toHaveAttribute('open', '');

  const second = await downloadHandoff(page, '#downloadJson');
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
  await page.locator('[data-result-import]:visible').first().click();
  await page.locator('#vasResultPasteButton').click();
  await page.locator('#vasResultPaste').fill(JSON.stringify(unsafe));
  await page.locator('#vasResultReadPaste').click();
  await expect(page.locator('#vasResultStatus')).toContainText(/경로|형식/);
  await expect(page.locator('#vasResultReview')).toBeHidden();
});

test('blocked storage and no memory still allow a reviewed handoff', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new Error('blocked'); } });
    Object.defineProperty(window, 'indexedDB', { configurable: true, get() { throw new Error('blocked'); } });
  });
  await prepareExisting(page);
  await expect(page.locator('[data-context-item]')).toHaveCount(0);
  const handoff = await downloadHandoff(page, '#downloadJson');
  expect(handoff.context.rag).toEqual({ included: false, items: [] });
  expect(handoff.qualityGate.ragReviewed).toBe(true);
});
