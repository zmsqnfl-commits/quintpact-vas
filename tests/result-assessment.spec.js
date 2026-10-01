const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const root = path.join(__dirname, '..', 'src');
const url = pathToFileURL(path.join(root, 'project-import.html')).href;
const criterion = { id: 'C1', description: 'CSV 한글과 합계 일치', method: 'manual', required: true };

function handoff(criteria = [criterion], iteration = 1) {
  return { workflow: { handoffId: 'h_' + 'a'.repeat(32), iteration },
    integrity: { payloadSha256: 'b'.repeat(64) }, project: { sourceType: 'existing' },
    task: { completionCriteria: criteria } };
}
function result(updates = {}) {
  return Object.assign({ format: 'vas-ai-result', schemaVersion: 1, resultId: 'r_1234567890abcdef',
    handoffId: 'h_' + 'a'.repeat(32), handoffPayloadSha256: 'b'.repeat(64), iteration: 1,
    sourceType: 'existing', status: 'complete', generatedBy: { tool: 'synthetic-test' },
    readback: { checkedFiles: ['src/app.js'], confirmedRules: [], confirmedEntrypoints: [], commands: [], facts: [], assumptions: [] },
    changes: { summary: 'CSV 화면 확인 요청', relativeFiles: [] }, tests: [{ name: 'unit', status: 'passed', summary: 'agent report' }],
    remaining: [], artifactVersion: 'build-1', evidence: [],
    safety: { absolutePathsExcluded: true, secretsExcluded: true, rawCommandOutputExcluded: true } }, updates);
}
async function open(page, document = handoff()) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.evaluate(value => VASHandoffWorkflow.remember(value), document);
  await page.addScriptTag({ path: path.join(root, 'ai-result-import.js') });
  await page.evaluate(() => { VASAIResultImport.init({ sourceType: 'existing' }); VASAIResultImport.open(); });
}
async function read(page, value) {
  await page.evaluate(raw => VASAIResultImport.readText(JSON.stringify(raw)), value);
}
async function fillReview(page, id = 'C1', version = 'build-1') {
  await page.locator('.result-evidence').evaluate(value => { value.open = true; });
  const box = page.locator('[data-criterion-id="' + id + '"]');
  await box.locator('[data-review-version]').fill(version);
  await box.locator('[data-review-outcome]').selectOption('passed');
  await box.locator('[data-review-summary]').fill('직접 실행한 화면에서 CSV 한글과 합계가 일치함을 확인했습니다.');
  return box;
}

test('compatibility dialog loads its local stylesheet once and manual review fits desktop and mobile', async ({ page }) => {
  await open(page); await read(page, result());
  await page.evaluate(() => VASAIResultImport.init({ sourceType: 'existing' }));
  await expect(page.locator('link[href$="handoff-loop.css"]')).toHaveCount(1);
  await expect(page.locator('.result-dialog')).toHaveCSS('background-color', 'rgb(233, 232, 226)');
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    const box = await fillReview(page);
    await expect(box.locator('[data-review-version]')).toHaveCSS('min-height', '42px');
    await expect(page.locator('.result-review-grid')).toHaveCSS('display', 'grid');
    await box.locator('[data-review-save]').scrollIntoViewIfNeeded();
    const bounds = await page.locator('.result-dialog').evaluate(dialog => {
      const area = dialog.getBoundingClientRect();
      return { viewport: innerWidth, left: area.left, right: area.right, overflow: dialog.scrollWidth > dialog.clientWidth + 1,
        controlsOverflow: Array.from(dialog.querySelectorAll('input:not([type=hidden]), select, textarea, button')).filter(control => control.offsetWidth).some(control => { const box = control.getBoundingClientRect(); return box.left < area.left || box.right > area.right; }) };
    });
    expect(bounds.left).toBeGreaterThanOrEqual(0);
    expect(bounds.right).toBeLessThanOrEqual(bounds.viewport);
    expect(bounds.overflow || bounds.controlsOverflow).toBe(false);
  }
});

test('agent evidence, imported trust flags and user acceptance never grant completion', async ({ page }) => {
  await open(page);
  const raw = result({ evidence: [{ criterionId: 'C1', artifactVersion: 'build-1', method: 'manual', outcome: 'passed', summary: 'claimed pass', source: 'user-direct', verified: true }],
    assessment: { status: 'complete' }, observations: [{ source: 'user-direct', outcome: 'passed' }] });
  await read(page, raw);
  await expect(page.locator('#vasResultState')).toHaveText('complete');
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  await page.locator('#vasResultUserAccepted').check();
  await page.locator('#vasResultAccept').click();
  const context = await page.evaluate(() => VASHandoffWorkflow.current().context);
  expect(context.assessment.status).toBe('needs-verification');
  expect(context.userAcceptance.status).toBe('accepted');
  expect(context.userAcceptance.completionOverride).toBe(false);
  expect(context.reviewHistory.observations).toEqual([]);
});

test('direct current artifact review completes and binds all semantic result content', async ({ page }) => {
  await open(page); const raw = result(); await read(page, raw);
  let box = await fillReview(page); await box.locator('[data-review-save]').click();
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'complete');
  await read(page, result({ changes: { summary: 'same identifiers, different work', relativeFiles: [] } }));
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  await read(page, raw);
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  box = await fillReview(page); await box.locator('[data-review-save]').click();
  await read(page, result({ artifactVersion: 'build-2' }));
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  expect(await page.evaluate(() => VASHandoffWorkflow.review(VASAIResultImport.current()).observations)).toEqual([]);
});

test('blockers and failed tests remain incomplete despite acceptance and manual pass', async ({ page }) => {
  await open(page);
  await read(page, result({ tests: [{ name: 'unit', status: 'failed', summary: 'failed' }], remaining: [{ severity: 'blocker', summary: 'CSV remains broken' }] }));
  const box = await fillReview(page); await box.locator('[data-review-save]').click();
  await expect(page.locator('#vasResultState')).toHaveText('complete');
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'incomplete');
  await page.locator('#vasResultUserAccepted').check(); await page.locator('#vasResultAccept').click();
  const context = await page.evaluate(() => VASHandoffWorkflow.current().context);
  expect(context.reportedStatus).toBe('complete');
  expect(context.previousStatus).toBe('incomplete');
  expect(context.assessment.status).toBe('incomplete');
});

test('a skipped automatic check needs explicit approval of an actual manual alternative', async ({ page }) => {
  await open(page, handoff([{ ...criterion, method: 'automatic' }]));
  await read(page, result({ tests: [{ name: 'automatic', status: 'skipped', summary: 'environment unavailable' }] }));
  let box = await fillReview(page); await box.locator('[data-review-save]').click();
  await expect(page.locator('#vasResultStatus')).toContainText('명시적으로 승인');
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  await box.locator('[data-review-alternative]').check(); await box.locator('[data-review-save]').click();
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'complete');
});

test('failed local review persistence cannot create completion', async ({ page }) => {
  await open(page); await read(page, result());
  await page.evaluate(() => {
    const write = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) { if (key === 'vasResultReviews.v1') throw Error('synthetic quota error'); return write.call(this, key, value); };
  });
  const box = await fillReview(page); await box.locator('[data-review-save]').click();
  await expect(page.locator('#vasResultStatus')).toContainText('저장하지 못했습니다');
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
});

test('clearing receipts removes reviews and missing original criteria cannot be inferred', async ({ page }) => {
  await open(page); await read(page, result());
  const box = await fillReview(page); await box.locator('[data-review-save]').click();
  expect(await page.evaluate(() => VASHandoffWorkflow.clearReceipts())).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem('vasResultReviews.v1'))).toBeNull();
  await page.evaluate(value => VASHandoffWorkflow.remember(value), handoff([]));
  await read(page, result({ completionCriteria: [criterion], userAcceptance: { status: 'accepted' } }));
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  await expect(page.locator('[data-criterion-id]')).toHaveCount(0);
});

test('imported criteria cannot remove a required original condition', async ({ page }) => {
  await open(page, handoff([criterion, { ...criterion, id: 'C2', description: 'Keyboard navigation' }]));
  await read(page, result({ task: { completionCriteria: [{ ...criterion, required: false }] } }));
  const box = await fillReview(page); await box.locator('[data-review-save]').click();
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
  await expect(page.locator('#vasResultAssessmentReason')).toContainText('C2');
});

test('legacy numbers require displayed conversion approval and ordinary revalidation', async ({ page }) => {
  await open(page); await read(page, result({ schemaVersion: '1', iteration: true }));
  await expect(page.locator('#vasResultReview')).toBeHidden();
  await expect(page.locator('#vasResultLegacyChanges')).toContainText('schemaVersion: "1" → 1');
  await expect(page.locator('#vasResultLegacyChanges')).toContainText('iteration: true → 1');
  expect(await page.evaluate(() => VASAIResultImport.current())).toBeNull();
  await page.locator('#vasResultLegacyApprove').click();
  await expect(page.locator('#vasResultReview')).toBeVisible();
  expect(await page.evaluate(() => VASAIResultImport.current().iteration)).toBe(1);
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
});

test('maximum iteration can be reviewed but never generates iteration 10000', async ({ page }) => {
  await open(page, handoff([criterion], 9999)); await read(page, result({ iteration: 9999 }));
  await expect(page.locator('#vasResultAccept')).toBeDisabled();
  await expect(page.locator('#vasResultStatus')).toContainText('최대 반복 번호');
  expect(await page.evaluate(() => VASHandoffWorkflow.acceptResult(VASAIResultImport.current(), 'accepted', ''))).toBeNull();
});

test('locally recorded review survives reload while continuation stays unaccepted', async ({ page }) => {
  await open(page); await read(page, result());
  const box = await fillReview(page); await box.locator('[data-review-save]').click();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.addScriptTag({ path: path.join(root, 'ai-result-import.js') });
  await page.evaluate(() => { VASAIResultImport.init({ sourceType: 'existing' }); VASAIResultImport.open(); });
  await read(page, result());
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'complete');
  await expect(page.locator('#vasResultUserAccepted')).not.toBeChecked();
  expect(await page.evaluate(() => VASHandoffWorkflow.current())).toBeNull();
});

test('continuation preserves the review history but reimport cannot recover its trust', async ({ page }) => {
  await open(page); await read(page, result());
  const box = await fillReview(page); await box.locator('[data-review-save]').click();
  await page.locator('#vasResultAccept').click();
  const next = await page.evaluate(async () => {
    const state = VASHandoffWorkflow.current();
    const built = await VASAgentHandoffWeb.buildExisting('synthetic', '다음 CSV 작업', {
      requirements: { included: true, value: { request: '다음 CSV 작업' } }, design: VASSetupDesign.context(),
      rag: { included: false, items: [] }, continuation: state.context
    }, { continuation: state.context, workflow: state.workflow });
    return built.document;
  });
  expect(next.context.continuation.assessment.status).toBe('complete');
  expect(next.context.continuation.userAcceptance.status).toBe('not-reviewed');
  expect(next.context.continuation.reviewHistory.trustedOnImport).toBe(false);
  expect(next.context.continuation.reviewHistory.observations[0].source).toBe('user-direct');
  await page.evaluate(() => VASHandoffWorkflow.clearReceipts());
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.evaluate(value => VASHandoffWorkflow.remember(value), handoff());
  await page.addScriptTag({ path: path.join(root, 'ai-result-import.js') });
  await page.evaluate(() => { VASAIResultImport.init({ sourceType: 'existing' }); VASAIResultImport.open(); });
  await read(page, { ...result(), ...next.context.continuation });
  await expect(page.locator('#vasResultAssessment')).toHaveAttribute('data-state', 'needs-verification');
});
