const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const existing = pathToFileURL(path.join(__dirname, '..', 'src', 'project-import.html')).href;
const fresh = pathToFileURL(path.join(__dirname, '..', 'src', 'client-application.html')).href;

async function start(page, request = 'CSV 내보내기를 추가하세요.') {
  await page.goto(existing);
  await page.locator('#folderPath').fill('C:\\fixture\\sample');
  await page.locator('#projectName').fill('합성 예제');
  await page.locator('#taskRequest').fill(request);
}
async function condition(page, description, method = 'manual') {
  await page.locator('[data-add-criterion]').click();
  const row = page.locator('.criterion-row').last();
  await row.locator('textarea').fill(description);
  await row.locator('select').selectOption(method);
}
async function download(page) {
  const pending = page.waitForEvent('download');
  await page.locator('#downloadJson').click();
  return JSON.parse(fs.readFileSync(await (await pending).path(), 'utf8'));
}

test('existing default preserves saved preset without activating it; conditions round-trip through prompt and JSON', async ({ page }) => {
  await start(page);
  const stored = await page.evaluate(() => VASSetupDesign.context());
  await condition(page, 'CSV 한글과 합계가 원본과 일치한다.');
  await page.locator('#continueSettings').click();
  await expect(page.locator('#activeDesignSettings')).toBeHidden();
  await expect(page.locator('#previewContent')).toContainText('기존 화면과 비교');
  await expect(page.locator('#previewContent')).not.toContainText('확정 디자인 토큰(JSON)');
  const result = await download(page);
  expect(result.task.designScope).toEqual({ mode: 'preserve', scope: '' });
  expect(result.context.design).toEqual({ included: false });
  expect(result.task.completionCriteria).toEqual([{ id: 'C1', description: 'CSV 한글과 합계가 원본과 일치한다.', method: 'manual', required: true }]);
  expect(result.assistantGuide.pasteText).toContain('[C1 · 필수 · 수동 확인]');
  expect(result.qualityGate.requirementsConfirmed).toBe(false);
  expect(result.qualityGate.privacyChecked).toBe(false);
  expect(result.qualityGate.independentSecurityVerification.status).toBe('not-performed');
  expect(await page.evaluate(() => VASSetupDesign.context())).toEqual(stored);
});

test('partial design needs explicit scope and applies preset only inside that scope', async ({ page }) => {
  await start(page);
  await page.locator('#continueSettings').click();
  await page.locator('#designScopeMode').selectOption('partial');
  await page.locator('#downloadJson').click();
  await expect(page.locator('#errorBox')).toContainText('화면·요소·속성');
  await page.locator('#designScopeDetails').fill('주문 화면의 결제 버튼: 배경색과 여백');
  await page.locator('#designScopeDetails').blur();
  const result = await download(page);
  expect(result.context.design.included).toBe(true);
  expect(result.task.designScope.mode).toBe('partial');
  expect(result.assistantGuide.pasteText).toContain('나머지 기존 디자인은 유지');
  expect(result.assistantGuide.pasteText).toContain('데이터 삭제나 요청 밖 기능 변경 권한을 포함하지 않습니다');
});

test('redaction requires review and checking one payload cannot approve later changed conditions', async ({ page }) => {
  await start(page, '담당자 contact@example.com 표기를 정리하세요.');
  await condition(page, 'CSV 합계 확인', 'automatic');
  await page.locator('#continueSettings').click();
  await page.locator('#downloadJson').click();
  await expect(page.locator('#errorBox')).toContainText('확인란');
  await expect(page.locator('#handoffInputReview')).toContainText('필수');
  await page.locator('#handoffInputReview input').check();
  let result = await download(page);
  expect(result.inputReview.acknowledged).toBe(true);
  expect(JSON.stringify(result)).not.toContain('contact@example.com');
  expect(result.qualityGate.userConfirmation.status).toBe('confirmed');
  expect(result.qualityGate.privacyChecked).toBe(false);
  await page.locator('#editWork').click();
  await page.locator('.criterion-row textarea').fill('CSV 행 수와 합계를 확인');
  await page.locator('#continueSettings').click();
  await expect(page.locator('#handoffInputReview input')).not.toBeChecked();
});

test('new project retains its design, empty criteria stay empty, and overflowing conditions are rejected', async ({ page }) => {
  await page.goto(fresh);
  const result = await page.evaluate(async () => {
    const good = await VASAgentHandoffWeb.buildNew({ project_name: '새 예제', problem_desc: '문서 보기' }, VASSetupDesign.context());
    let message = '';
    try { await VASAgentHandoffWeb.buildNew({}, VASSetupDesign.context(), { completionCriteria: [{ description: 'x'.repeat(501), method: 'static', required: true }] }); } catch (error) { message = error.message; }
    return { document: good.document, message };
  });
  expect(result.document.task.designScope.mode).toBe('new');
  expect(result.document.context.design.included).toBe(true);
  expect(result.document.task.completionCriteria).toEqual([]);
  expect(result.document.task.acceptanceCriteria).toEqual([]);
  expect(result.message).toContain('500');
});

test('new project condition editor survives local draft restore with method and optionality', async ({ page }) => {
  await page.goto(fresh);
  await page.evaluate(() => { cur = 4; document.querySelectorAll('.step').forEach(el => el.classList.toggle('active', el.dataset.step === '4')); });
  await condition(page, '도움말 문구 대조', 'static');
  await page.locator('.criterion-row input[type=checkbox]').uncheck();
  await page.evaluate(() => VASClientDraft.save());
  await page.reload();
  await page.evaluate(() => VASClientDraft.restore());
  expect(await page.evaluate(() => VASTaskInputs.read('completionConditions'))).toEqual([{ description: '도움말 문구 대조', method: 'static', required: false }]);
  const result = await page.evaluate(() => VASNewHandoff.prepare());
  expect(result.document.task.completionCriteria[0]).toEqual({ id: 'C1', description: '도움말 문구 대조', method: 'static', required: false });
});

test('scope and condition controls fit desktop and mobile screens', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await start(page);
    await condition(page, '키보드로 내보내기 버튼을 실행한다.');
    // Commit the focused textarea before full-page capture changes the scroll position.
    await page.locator('.criterion-row textarea').last().blur();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: path.join(process.env.TEMP || '.', 'vas-existing-criteria-' + width + '.png'), fullPage: true });
    await page.locator('#continueSettings').click();
    await page.locator('#designScopeMode').selectOption('partial');
    await page.locator('#designScopeDetails').fill('주문 화면 / 내보내기 버튼 / 레이블과 키보드 조작');
    await page.locator('#designScopeDetails').blur();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: path.join(process.env.TEMP || '.', 'vas-existing-scope-' + width + '.png'), fullPage: true });
    await page.goto(fresh);
    await page.evaluate(() => { cur = 4; document.querySelectorAll('.step').forEach(el => el.classList.toggle('active', el.dataset.step === '4')); });
    await condition(page, '문서 검색 결과가 제목순으로 정렬된다.', 'automatic');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: path.join(process.env.TEMP || '.', 'vas-new-criteria-' + width + '.png'), fullPage: true });
  }
});
