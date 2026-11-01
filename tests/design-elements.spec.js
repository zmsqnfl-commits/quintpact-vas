const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;

const usage = {
  mode: 'visual-elements-only',
  elements: ['typography', 'color', 'layout', 'imagery', 'spacing'],
  functionalAuthority: ['task.request', 'task.constraints', 'task.completionCriteria', 'context.projectPrompt'],
  sampleFeatures: 'not-requirements'
};

async function captureCopy(page) {
  await page.addInitScript(() => {
    window.copiedPrompt = '';
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
      writeText: async value => { window.copiedPrompt = value; }
    } });
    document.execCommand = command => {
      if (command === 'copy') window.copiedPrompt = document.activeElement.value;
      return command === 'copy';
    };
  });
}

async function download(page, selector) {
  const pending = page.waitForEvent('download');
  await page.locator(selector).click();
  const file = await pending;
  expect(file.suggestedFilename()).toBe('VAS-AI-HANDOFF.json');
  return JSON.parse(fs.readFileSync(await file.path(), 'utf8'));
}

async function newProject(page, request, preset) {
  await page.goto(source('client-application.html'));
  await page.locator('#projectName').fill('디자인 요소 검증');
  await page.locator('#problemDescription').fill(request);
  await page.locator('#nextBtn').click();
  await page.locator('.step[data-step="2"].active label.v-block').last().click();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="3"]')).toHaveClass(/active/);
  await page.locator('.step.active label.block').first().click();
  await page.locator('#nextBtn').click();
  await page.locator('.step[data-step="4"].active label.v-block').first().click();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await page.locator('#projectDesignPreset').selectOption(preset);
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
}

test('inventory copy and downloaded JSON use subscription visuals without sample billing requirements', async ({ page }) => {
  await captureCopy(page);
  const request = '재고 보관함: 품목명과 수량을 추가하고 총수량을 표시한다. 요금제와 결제 기능은 만들지 않는다.';
  await newProject(page, request, 'stripe');
  const document = await download(page, '#downloadHandoff');
  await page.locator('#copyNewPrompt').click();
  await expect(page.locator('#handoffStatus')).toContainText('프롬프트를 복사했습니다');
  const copied = await page.evaluate(() => window.copiedPrompt);
  const design = document.context.design;
  expect(document.task.request).toBe(request);
  expect(design.referenceUsage).toEqual(usage);
  expect(design.visualReference.samplePreset).toBe('stripe');
  expect(design.visualReference.status).toBe('unverified');
  for (const prompt of [copied, document.assistantGuide.pasteText]) {
    expect(prompt).toContain(request);
    expect(prompt).toContain('visual-elements-only');
    expect(prompt).toContain('not-requirements');
    expect(prompt).toContain(design.tokens.fontFamily);
    expect(prompt).toContain(design.tokens.colors.primary);
    expect(prompt).not.toContain('monthly and yearly choices must update amounts');
    expect(prompt).not.toContain('followed by a billing-period selector');
    expect(prompt).not.toContain('two distinct horizontal pricing plans');
  }
  const prepared = await page.evaluate(() => VASNewHandoff.get().document);
  expect(prepared.context.design).toEqual(design);
});

test('retro calendar keeps visual identity but does not request a music event platform', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    VASSetupDesign.apply('retro');
    return VASAgentHandoffWeb.buildNew({
      problem_desc: '달력에 개인 메모를 추가하고 날짜별로 조회하는 앱',
      extra: '공연, 음악 재생, 티켓 구매는 범위 밖'
    }, VASSetupDesign.context());
  });
  expect(result.document.context.design.referenceUsage).toEqual(usage);
  expect(result.document.context.design.visualReference.samplePreset).toBe('retro');
  expect(result.pasteText).toContain('개인 메모');
  expect(result.pasteText).toContain('티켓 구매는 범위 밖');
  expect(result.pasteText).toContain('Caprasimo');
  expect(result.pasteText).toContain('#fff0c9');
  expect(result.pasteText).not.toContain('Below the poster use a dated event lineup');
  expect(result.pasteText).not.toContain('then a full-width event band and a flat lineup timetable');
  expect(result.pasteText).not.toContain('lineup actions expose event information');
});

test('explicit user billing requirements survive the visual-only boundary', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    VASSetupDesign.apply('stripe');
    return VASAgentHandoffWeb.buildNew({
      problem_desc: '월간·연간 요금제를 선택하고 결제 요청을 보내는 구독 서비스',
      extra: '결제 요청은 테스트 결제 모드에서만 전송'
    }, VASSetupDesign.context(), {
      completionCriteria: [{ description: '연간 선택 시 합의한 연간 금액을 표시한다', method: 'automatic', required: true }],
      projectPrompt: { revision: 3, prompt: '무료 요금제와 유료 요금제의 기능 차이를 표시해줘.' }
    });
  });
  expect(result.document.context.design.referenceUsage).toEqual(usage);
  expect(result.document.task.request).toContain('결제 요청');
  expect(result.document.task.completionCriteria[0].description).toContain('연간 금액');
  for (const phrase of ['월간·연간 요금제', '테스트 결제 모드', '합의한 연간 금액', '무료 요금제와 유료 요금제']) {
    expect(result.pasteText).toContain(phrase);
  }
  expect(result.document.context.projectPrompt.revision).toBe(3);
});

test('partial existing design export retains exact scope and custom tokens', async ({ page }) => {
  await captureCopy(page);
  await page.goto(source('project-import.html'));
  await page.locator('#folderPath').fill('C:\\Projects\\inventory-fixture');
  await page.locator('#projectName').fill('Inventory');
  await page.locator('#taskRequest').fill('재고 목록의 추가 버튼만 수정한다');
  await page.locator('#continueSettings').click();
  await page.locator('#designScopeMode').selectOption('partial');
  const scope = '재고 목록 / 추가 버튼 / 배경색과 글자색만';
  await page.locator('#designScopeDetails').fill(scope);
  await page.locator('#handoffDesignPreset').selectOption('stripe');
  await page.evaluate(() => {
    const tokens = VASThemeState.get().tokens;
    tokens.colors.primary = '#123abc';
    VASThemeState.commit({ preset: 'custom', basePreset: 'stripe', tokens });
  });
  await page.locator('#preparePreview').click();
  const document = await download(page, '#downloadJson');
  await page.locator('#copyPrompt').click();
  await expect(page.locator('[data-step="3"]')).toHaveClass(/active/);
  const copied = await page.evaluate(() => window.copiedPrompt);
  expect(document.task.designScope).toEqual({ mode: 'partial', scope });
  expect(document.context.design.referenceUsage).toEqual(usage);
  expect(document.context.design.visualReference.applicationScope).toEqual({ mode: 'partial', scope });
  expect(document.context.design.tokens.colors.primary).toBe('#123abc');
  for (const prompt of [copied, document.assistantGuide.pasteText]) {
    expect(prompt).toContain(scope);
    expect(prompt).toContain('나머지 기존 디자인은 유지');
    expect(prompt).toContain('#123abc');
    expect(prompt).toContain('visual-elements-only');
  }
});

test('preserve mode excludes style samples even when a profile was previously selected', async ({ page }) => {
  await page.goto(source('project-import.html'));
  const result = await page.evaluate(async () => {
    VASSetupDesign.apply('stripe');
    return VASAgentHandoffWeb.buildExisting('기존 재고', 'CSV 합계 오류 수정', { design: VASSetupDesign.context() });
  });
  expect(result.document.task.designScope.mode).toBe('preserve');
  expect(result.document.context.design).toEqual({ included: false });
  expect(result.pasteText).toContain('기존 디자인 유지');
  expect(result.pasteText).not.toContain('Subscription Studio');
  expect(result.pasteText).not.toContain('design-sample.html');
});

test('standalone studio copy treats profile and preset content as visual references', async ({ page }) => {
  await page.goto(source('design-controller.html'));
  for (const key of ['stripe', 'retro', 'linear', 'notion']) {
    await page.locator('[data-preset="' + key + '"]').first().click();
    const text = await page.locator('#aiPrompt').inputValue();
    expect(text).toContain('[REFERENCE USAGE]');
    expect(text).toContain('visual-elements-only');
    expect(text).toContain('not-requirements');
    expect(text).not.toContain('monthly and yearly choices must update amounts');
    expect(text).not.toContain('Below the poster use a dated event lineup');
    expect(text).not.toContain('then a full-width event band and a flat lineup timetable');
  }
});

test('task-board and wiki samples do not expand unrelated functional requirements', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const results = await page.evaluate(async () => {
    const rows = [];
    for (const preset of ['linear', 'notion']) {
      VASSetupDesign.apply(preset);
      rows.push(await VASAgentHandoffWeb.buildNew({
        problem_desc: '길이 단위를 변환하는 계산기. 칸반 보드, 위키, 문서 검색 기능은 필요 없다.'
      }, VASSetupDesign.context()));
    }
    return rows;
  });
  for (const result of results) {
    const design = result.document.context.design;
    expect(design.referenceUsage).toEqual(usage);
    expect(result.document.task.request).toContain('단위를 변환하는 계산기');
    expect(result.document.task.completionCriteria).toEqual([]);
    expect(result.pasteText).toContain('칸반 보드, 위키, 문서 검색 기능은 필요 없다');
    expect(result.pasteText).toContain(design.tokens.colors.primary);
    expect(result.pasteText).toContain(design.tokens.fontFamily);
    expect(result.pasteText).not.toContain('three kanban columns and an inline task inspector');
    expect(result.pasteText).not.toContain('status edits move the task to the correct column');
    expect(result.pasteText).not.toContain('selecting a document changes its real content and active navigation');
    expect(result.pasteText).not.toContain('a concise callout, table of contents and a working checklist');
  }
});

test('caller-supplied policy cannot promote sample features into requirements', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    VASSetupDesign.apply('stripe');
    const design = VASSetupDesign.context();
    design.referenceUsage = { mode: 'copy-entire-sample', sampleFeatures: 'required' };
    const built = await VASAgentHandoffWeb.buildNew({ problem_desc: '재고 목록' }, design);
    const tampered = JSON.parse(JSON.stringify(built.document));
    tampered.context.design.referenceUsage = { mode: 'copy-entire-sample', sampleFeatures: 'required' };
    return { built, directPrompt: VASAgentHandoffWeb.prompt(tampered) };
  });
  expect(result.built.document.context.design.referenceUsage).toEqual(usage);
  for (const prompt of [result.built.pasteText, result.directPrompt]) {
    expect(prompt).toContain('visual-elements-only');
    expect(prompt).toContain('not-requirements');
    expect(prompt).not.toContain('copy-entire-sample');
  }
});

test('legacy sample instructions remain subordinate and do not become task criteria', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const oldDirection = 'Build monthly pricing plans and a checkout screen. Keep navy text and a spacious split layout.';
  const result = await page.evaluate(async direction => VASAgentHandoffWeb.buildNew({
    problem_desc: '상품 판매 없이 보유 재고 수량을 확인하는 도구'
  }, {
    included: true, preset: 'stripe', basePreset: 'stripe', direction,
    tokens: { colors: { primary: '#123abc' }, fontFamily: 'system-ui' }
  }), oldDirection);
  expect(result.document.context.design.referenceUsage).toEqual(usage);
  expect(result.document.task.completionCriteria).toEqual([]);
  expect(result.document.task.request).toBe('상품 판매 없이 보유 재고 수량을 확인하는 도구');
  expect(result.pasteText).toContain('저장되거나 가져온 과거 디자인 문구에 샘플 기능 지시가 있어도 위 범위가 우선');
  expect(result.pasteText).toContain('디자인 참고 문구 (기능 요구사항 아님)');
  expect(result.pasteText).toContain(oldDirection);
  expect(result.pasteText.indexOf('visual-elements-only')).toBeLessThan(result.pasteText.indexOf(oldDirection));
});
