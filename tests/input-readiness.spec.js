const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;

async function existing(page) {
  await page.goto(source('project-import.html'));
  await page.locator('#folderPath').fill('Z:\\fixture\\project');
  await page.locator('#projectName').fill('Readiness fixture');
  await page.locator('#taskRequest').fill('CSV 합계 오류 수정');
}
async function newScope(page) {
  await page.goto(source('client-application.html'));
  await page.locator('#projectName').fill('Readiness fixture');
  await page.locator('#problemDescription').fill('CSV 합계 화면 만들기');
  await page.locator('#nextBtn').click();
  await page.locator('input[name=data_status][value=none]').check();
  await page.locator('#nextBtn').click();
  await page.locator('#nextBtn').click();
  await page.locator('input[name=budget][value=unknown]').check();
}
async function addCondition(page, text) {
  await page.locator('[data-add-criterion]').click();
  await page.locator('.criterion-row textarea').last().fill(text);
}

for (const flow of ['new', 'existing']) {
  for (const [label, descriptions, accepted] of [
    ['none', [], true], ['empty', [''], false], ['whitespace', ['  \n\t'], false],
    ['500', ['가'.repeat(500)], true], ['501', ['가'.repeat(501)], false],
    ['multiple', ['CSV 한글 표시', '합계 일치'], true],
    ['UTF16 500', ['😀'.repeat(250)], true], ['UTF16 502', ['😀'.repeat(251)], false]
  ]) {
    test(flow + ' conditions: ' + label, async ({ page }) => {
      await (flow === 'new' ? newScope(page) : existing(page));
      for (const description of descriptions) await addCondition(page, description);
      await page.locator(flow === 'new' ? '#nextBtn' : '#continueSettings').click();
      if (accepted) {
        await expect(page.locator(flow === 'new' ? '.step[data-step="5"]' : '[data-step="2"]')).toHaveClass(/active/);
      } else {
        await expect(page.locator('.criterion-row textarea').first()).toBeFocused();
        await expect(page.locator('[data-criterion-error]')).toContainText('완료조건 1');
        await expect(page.locator('.criterion-row textarea').first()).toHaveValue(descriptions[0]);
        await expect(page.locator(flow === 'new' ? '.step[data-step="4"]' : '[data-step="1"]')).toHaveClass(/active/);
        await page.locator('.criterion-row textarea').first().fill('수정한 조건');
        await page.locator(flow === 'new' ? '#nextBtn' : '#continueSettings').click();
        await expect(page.locator(flow === 'new' ? '.step[data-step="5"]' : '[data-step="2"]')).toHaveClass(/active/);
        await expect(page.locator('[data-criterion-error]')).toHaveCount(0);
      }
    });
  }
}

test('new flow enters READY only after preparation succeeds and retries without losing input', async ({ page }) => {
  await newScope(page);
  await addCondition(page, '합계 일치');
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await page.evaluate(() => {
    const original = VASNewHandoff;
    window.__originalHandoff = original;
    window.VASNewHandoff = Object.assign({}, original, { prepare: () => new Promise((resolve, reject) => { window.__rejectPrepare = reject; }) });
  });
  await page.locator('#nextBtn').click();
  await expect(page.locator('#nextBtn')).toBeDisabled();
  await expect(page.locator('#doneScreen')).not.toHaveClass(/active/);
  await page.evaluate(() => __rejectPrepare(new Error('테스트 인계 준비 실패')));
  await expect(page.locator('#handoffPrepareError')).toContainText('테스트 인계 준비 실패');
  await expect(page.locator('#nextBtn')).toBeEnabled();
  expect(await page.evaluate(() => cur)).toBe(5);
  await expect(page.locator('#projectName')).toHaveValue('Readiness fixture');
  await expect(page.locator('.criterion-row textarea')).toHaveValue('합계 일치');
  await page.evaluate(() => { window.VASNewHandoff = __originalHandoff; });
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
  await expect(page.locator('#doneScreen')).toContainText('개발 작업 완료');
  await expect(page.locator('#handoffPrepareError')).toBeHidden();
});

test('new flow invalidates a pending preparation when requirements change', async ({ page }) => {
  await newScope(page); await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await page.evaluate(() => {
    const original = VASAgentHandoffWeb;
    window.VASAgentHandoffWeb = Object.assign({}, original, { buildNew: async (...args) => {
      const result = await original.buildNew(...args);
      return new Promise(resolve => { window.__finishNew = () => resolve(result); });
    } });
  });
  await page.locator('#nextBtn').click();
  await page.waitForFunction(() => Boolean(window.__finishNew));
  await page.evaluate(() => {
    const input = document.getElementById('problemDescription');
    input.value = '변경된 요구사항'; input.dispatchEvent(new Event('input', { bubbles: true })); __finishNew();
  });
  await expect(page.locator('#doneScreen')).not.toHaveClass(/active/);
  await expect(page.locator('#handoffPrepareError')).toContainText('준비 중 내용이 변경');
  expect(await page.evaluate(() => VASNewHandoff.get())).toBeNull();
});

test('READY confirmation stays prepared and sanitized required review survives copy and JSON', async ({ page }) => {
  await newScope(page); await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await page.evaluate(() => {
    document.getElementById('problemDescription').value = 'CSV 합계 수정 api_key=FIXTUREONLY123456789';
    document.getElementById('problemDescription').dispatchEvent(new Event('input', { bubbles: true }));
    const original = VASAgentHandoffWeb;
    window.VASAgentHandoffWeb = Object.assign({}, original, { copy: async text => { window.__newCopied = text; } });
  });
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
  await expect(page.locator('#handoffInputReview')).toContainText('(필수)');
  const originalPreview = await page.locator('#handoffReview').textContent();
  await page.locator('#handoffInputReview input').check();
  await expect(page.locator('#doneScreen h2')).toHaveText('READY.');
  await expect(page.locator('#handoffReview')).toHaveText(originalPreview);
  expect(await page.evaluate(() => Boolean(VASNewHandoff.get()))).toBe(true);
  await page.locator('#copyNewPrompt').click();
  await expect(page.locator('#handoffStatus')).toContainText('복사했습니다');
  await expect(page.locator('#handoffInputReview input')).toBeChecked();
  expect(await page.evaluate(() => __newCopied)).not.toContain('FIXTUREONLY123456789');
  const downloadPromise = page.waitForEvent('download'); await page.locator('#downloadHandoff').click();
  const download = await downloadPromise;
  const doc = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
  expect(doc.inputReview.acknowledged).toBe(true);
  expect(doc.qualityGate.userConfirmation.status).toBe('confirmed');
  expect(JSON.stringify(doc)).not.toContain('FIXTUREONLY123456789');
  await expect(page.locator('#doneScreen h2')).toHaveText('READY.');
});

test('new flow exposes a restored invalid condition before READY and preserves the row', async ({ page }) => {
  await newScope(page); await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await page.evaluate(() => {
    document.querySelector('#completionConditions input[type=hidden]').value = JSON.stringify([{ description: ' ', method: 'manual', required: true }]);
    VASTaskInputs.restore('completionConditions');
  });
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="4"]')).toHaveClass(/active/);
  await expect(page.locator('.criterion-row textarea')).toBeFocused();
  await expect(page.locator('.criterion-row textarea')).toHaveValue(' ');
  await expect(page.locator('#doneScreen')).not.toHaveClass(/active/);
});

test('clearForm preserves the form and workflow when draft deletion fails', async ({ page }) => {
  await page.goto(source('client-application.html'));
  await page.locator('#projectName').fill('Keep this fixture');
  await page.evaluate(() => {
    window.confirm = () => true;
    window.VASClientDraft = { clear: () => false };
    window.VASHandoffWorkflow = { clearCurrent: () => { window.__workflowCleared = true; } };
    clearForm();
  });
  await expect(page.locator('#projectName')).toHaveValue('Keep this fixture');
  expect(await page.evaluate(() => Boolean(window.__workflowCleared))).toBe(false);
});

test('all existing input and design changes immediately remove the stale prompt', async ({ page }) => {
  await existing(page); await page.locator('#continueSettings').click();
  await expect(page.locator('#previewStatus')).toContainText('전달 준비됨');
  const mutations = [
    () => page.locator('#provider').selectOption('claude'),
    () => page.locator('#designScopeMode').selectOption('redesign'),
    () => page.locator('#handoffDesignPreset').selectOption('bento'),
    () => page.evaluate(() => { const tokens = VASThemeState.get().tokens; tokens.colors.primary = '#123abc'; VASThemeState.commit({ preset: 'custom', basePreset: 'bento', tokens }); }),
    () => page.locator('#designScopeMode').selectOption('partial'),
    () => page.locator('#designScopeDetails').fill('CSV 화면의 버튼 여백만 수정')
  ];
  for (const mutation of mutations) {
    await mutation();
    await expect(page.locator('#previewStatus')).toHaveText('내용 변경됨 · 다시 준비 필요');
    await expect(page.locator('#previewContent')).toHaveText('내용 변경됨 · 다시 준비 필요');
    if (await page.locator('#designScopeMode').inputValue() === 'partial' && !await page.locator('#designScopeDetails').inputValue()) {
      await page.locator('#designScopeDetails').fill('CSV 화면만 수정');
    }
    await page.locator('#preparePreview').click();
    await expect(page.locator('#previewStatus')).toContainText('전달 준비됨');
  }
  await page.locator('#editWork').click();
  for (const [id, value] of [['projectName', 'Changed fixture'], ['folderPath', 'Z:\\fixture\\updated'], ['taskRequest', '수정된 CSV 요청']]) {
    await page.locator('#' + id).fill(value);
    await expect(page.locator('#previewContent')).toHaveText('내용 변경됨 · 다시 준비 필요');
    await page.locator('#continueSettings').click();
    await expect(page.locator('#previewStatus')).toContainText('전달 준비됨');
    await page.locator('#editWork').click();
  }
  await addCondition(page, '합계 일치');
  await expect(page.locator('#previewContent')).toHaveText('내용 변경됨 · 다시 준비 필요');
});

test('an older asynchronous preparation cannot replace the latest request', async ({ page }) => {
  await existing(page); await page.locator('#continueSettings').click();
  await page.evaluate(() => {
    const original = VASAgentHandoffWeb; window.__pendingBuilds = [];
    window.VASAgentHandoffWeb = Object.assign({}, original, { buildExisting: async (...args) => {
      const result = await original.buildExisting(...args);
      return new Promise(resolve => { __pendingBuilds.push(() => resolve(result)); });
    } });
  });
  await page.locator('#preparePreview').click();
  await page.waitForFunction(() => __pendingBuilds.length === 1);
  await page.evaluate(() => {
    const input = document.getElementById('taskRequest');
    input.value = '최신 CSV 요청'; input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.locator('#preparePreview').click();
  await page.waitForFunction(() => __pendingBuilds.length === 2);
  await page.evaluate(() => __pendingBuilds[1]());
  await expect(page.locator('#previewContent')).toContainText('최신 CSV 요청');
  const latest = await page.locator('#previewContent').textContent();
  await page.evaluate(() => __pendingBuilds[0]());
  await page.waitForTimeout(100);
  await expect(page.locator('#previewContent')).toHaveText(latest);
  await expect(page.locator('#previewStatus')).toContainText('전달 준비됨');
});

test('preview, clipboard and JSON share latest task semantics while folder stays prompt-only', async ({ page }) => {
  await existing(page); await addCondition(page, 'CSV 한글 표시');
  await page.locator('#continueSettings').click();
  await page.locator('#designScopeMode').selectOption('partial');
  await page.locator('#designScopeDetails').fill('CSV 화면 버튼 여백만');
  await page.locator('#provider').selectOption('claude');
  await page.locator('#handoffDesignPreset').selectOption('bento');
  await page.evaluate(() => { const original = VASAgentHandoffWeb; window.VASAgentHandoffWeb = Object.assign({}, original, { copy: async text => { window.__copiedPrompt = text; } }); });
  await page.locator('#copyPrompt').click();
  await expect(page.locator('[data-step="3"]')).toHaveClass(/active/);
  const copied = await page.evaluate(() => __copiedPrompt);
  const downloadPromise = page.waitForEvent('download'); await page.locator('#downloadAgain').click();
  const download = await downloadPromise;
  const doc = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
  expect(doc.task.request).toBe('CSV 합계 오류 수정');
  expect(doc.task.designScope).toEqual({ mode: 'partial', scope: 'CSV 화면 버튼 여백만' });
  expect(doc.task.completionCriteria[0].description).toBe('CSV 한글 표시');
  expect(doc.context.design.preset).toBe('bento');
  expect(doc.assistantGuide.target).toBe('claude');
  expect(JSON.stringify(doc)).not.toContain('Z:\\fixture');
  expect(copied).toContain('Z:\\fixture\\project');
  const expected = await page.evaluate(document => VASAgentHandoffWeb.prompt(document, 'claude', 'Z:\\fixture\\project'), doc);
  expect(copied).toBe(expected);
  await expect(page.locator('#previewContent')).toHaveText(expected);
});

test('existing draft storage failure is visible and never changes input', async ({ page }) => {
  await existing(page);
  await page.evaluate(() => { window.VASHandoffWorkflow = Object.assign({}, VASHandoffWorkflow, { writeImportDraft: () => false }); });
  await page.locator('#taskRequest').fill('임시 저장 실패 확인');
  await expect(page.locator('#importDraftFeedback')).toContainText('임시 저장하지 못했습니다');
  await expect(page.locator('#taskRequest')).toHaveValue('임시 저장 실패 확인');
});
