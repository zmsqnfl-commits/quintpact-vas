const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;

function once(prompt, skill) {
  expect(typeof skill).toBe('string');
  expect(skill.length).toBeGreaterThan(400);
  expect(prompt.split(skill)).toHaveLength(2);
  expect(prompt.length).toBeLessThanOrEqual(32000);
}

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

async function finishNewProject(page) {
  await page.locator('#nextBtn').click();
  await page.locator('.step[data-step="2"].active label.v-block').last().click();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="3"]')).toHaveClass(/active/);
  await page.locator('.step.active label.block').first().click();
  await page.locator('#nextBtn').click();
  await page.locator('.step[data-step="4"].active label.v-block').first().click();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await page.locator('#projectDesignPreset').selectOption('stripe');
  await page.locator('#nextBtn').click();
  await expect(page.locator('#doneScreen')).toHaveClass(/active/);
}

test('image picker exports only attachment count and analysis instructions, never unseen image evidence', async ({ page }) => {
  const remoteRequests = [];
  page.on('request', request => { if (/^https?:/.test(request.url())) remoteRequests.push(request.url()); });
  await captureCopy(page);
  await page.goto(source('client-application.html'));
  await page.locator('#projectName').fill('참고 이미지 적용');
  const request = '첨부한 이미지의 시각 요소를 참고해 품목과 수량을 관리하는 앱을 만든다.';
  await page.locator('#problemDescription').fill(request);
  const name = 'private-reference-fixture.png';
  const canary = 'IMAGE_BYTES_NOT_EXPORTED_40218';
  const tinyPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9XcAAAAASUVORK5CYII=', 'base64');
  await page.locator('#fileInput').setInputFiles({ name, mimeType: 'image/png', buffer: Buffer.concat([tinyPng, Buffer.from(canary)]) });
  await expect(page.locator('#fileChips')).toContainText(name);
  await finishNewProject(page);
  const pending = page.waitForEvent('download');
  await page.locator('#downloadHandoff').click();
  const file = await pending;
  const document = JSON.parse(fs.readFileSync(await file.path(), 'utf8'));
  await page.locator('#copyNewPrompt').click();
  await expect(page.locator('#handoffStatus')).toContainText('프롬프트를 복사했습니다');
  const result = await page.evaluate(() => ({ copied: window.copiedPrompt, skill: VASAgentResources.designAnalysis }));
  const all = JSON.stringify(document);
  expect(document.context.requirements.value.attachments).toEqual({ contentsIncluded: false, namesIncluded: false,
    transfer: 'attach-in-coding-tool', count: 1 });
  expect(document.context.design.visualReference.status).toBe('unverified');
  expect(document.task.request).toBe(request);
  for (const prompt of [result.copied, document.assistantGuide.pasteText]) {
    once(prompt, result.skill);
    expect(prompt).toContain('별도로 첨부');
    expect(prompt).toContain('파일 이름과 내용을 전송하지 않았습니다');
    expect(prompt).not.toContain(name);
    expect(prompt).not.toContain(canary);
    expect(prompt).not.toContain(tinyPng.toString('base64'));
  }
  expect(all).not.toContain(name);
  expect(all).not.toContain(canary);
  expect(remoteRequests).toEqual([]);
});

test('every preset carries the complete analysis skill once without losing tokens or visual-only scope', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    const records = [];
    for (const key of Object.keys(PRESETS)) {
      VASSetupDesign.apply(key);
      const selected = VASSetupDesign.context();
      const value = await VASAgentHandoffWeb.buildNew({ problem_desc: '사진 참고로 재고 앱의 시각 요소를 적용한다.' }, selected);
      records.push({ key, direction: selected.direction, prompt: value.pasteText,
        tokens: selected.tokens, actualTokens: value.document.context.design.tokens,
        usage: value.document.context.design.referenceUsage });
    }
    return { skill: VASAgentResources.designAnalysis, records };
  });
  expect(result.records).toHaveLength(28);
  for (const row of result.records) {
    once(row.direction, result.skill);
    expect(row.direction.length, row.key).toBeLessThanOrEqual(12000);
    once(row.prompt, result.skill);
    expect(row.actualTokens).toEqual(row.tokens);
    expect(row.usage.mode).toBe('visual-elements-only');
    expect(row.usage.sampleFeatures).toBe('not-requirements');
  }
});

test('custom directions without a built-in sample still receive the full offline analysis skill', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    const tokens = { fontFamily: 'system-ui', colors: { primary: '#123abc' } };
    const document = (await VASAgentHandoffWeb.buildNew({ problem_desc: '내가 가져온 이미지의 배치를 메모 앱에 적용' }, {
      included: true, preset: 'custom', tokens, direction: '사용자 이미지의 넓은 여백을 참고'
    })).document;
    return { document, skill: VASAgentResources.designAnalysis, tokens };
  });
  once(result.document.assistantGuide.pasteText, result.skill);
  expect(result.document.context.design.tokens).toEqual(result.tokens);
  expect(result.document.context.design.visualReference).toMatchObject({ status: 'unverified', samplePreset: null,
    liveSampleUrl: null, versionedSourceUrl: null });
  expect(result.document.assistantGuide.pasteText).not.toContain('preset=awwwards');
});

test('a skill hidden past the rendered direction limit is added back to direct legacy prompts', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const result = await page.evaluate(async () => {
    const skill = VASAgentResources.designAnalysis;
    const built = await VASAgentHandoffWeb.buildNew({ problem_desc: '참고 이미지의 요소를 메모 앱에 적용한다.' }, {
      included: true, preset: 'custom', direction: '원본 이미지 참고', tokens: { fontFamily: 'system-ui' }
    });
    built.document.context.design.direction = 'X'.repeat(12000) + skill;
    return { skill, prompt: VASAgentHandoffWeb.prompt(built.document) };
  });
  once(result.prompt, result.skill);
  expect(result.prompt).toContain('X'.repeat(12000));
});

test('partial scope retains exact limits while preserve does not invoke new reference analysis', async ({ page }) => {
  await page.goto(source('project-import.html'));
  const result = await page.evaluate(async () => {
    VASSetupDesign.apply('bento');
    const active = VASSetupDesign.context();
    const scope = { mode: 'partial', scope: '재고 화면 / 추가 버튼 / 색상만' };
    const partial = await VASAgentHandoffWeb.buildExisting('수정할 앱', '참고 이미지의 강조색을 추가 버튼에만 적용',
      { design: active }, { designScope: scope });
    const preserve = await VASAgentHandoffWeb.buildExisting('수정할 앱', 'CSV 저장 오류만 수정하고 화면은 유지',
      { design: active });
    return { partial, preserve, scope, skill: VASAgentResources.designAnalysis };
  });
  once(result.partial.pasteText, result.skill);
  expect(result.partial.document.task.designScope).toEqual(result.scope);
  expect(result.partial.pasteText).toContain('나머지 기존 디자인은 유지');
  expect(result.preserve.document.context.design).toEqual({ included: false });
  expect(result.preserve.pasteText).not.toContain(result.skill);
  expect(result.preserve.pasteText).toContain('기존 디자인 유지');
});

test('standalone studio copies portable analysis instructions through profile and token edits', async ({ page }) => {
  await captureCopy(page);
  await page.goto(source('design-controller.html'));
  await page.locator('[data-preset="retro"]').first().click();
  await page.locator('#colorPrimary').evaluate(element => {
    element.value = '#123abc'; element.dispatchEvent(new Event('input', { bubbles: true }));
  });
  const before = await page.evaluate(() => ({ prompt: document.getElementById('aiPrompt').value, skill: VASAgentResources.designAnalysis }));
  once(before.prompt, before.skill);
  expect(before.prompt).toContain('#123abc');
  await page.evaluate(() => copyAgentPrompt());
  const copied = await page.evaluate(() => window.copiedPrompt);
  once(copied, before.skill);
  expect(copied).toContain('#123abc');
  await page.locator('#tasteProfileMode').selectOption('dataTool');
  const after = await page.locator('#aiPrompt').inputValue();
  once(after, before.skill);
  expect(after).toContain('#123abc');
});
