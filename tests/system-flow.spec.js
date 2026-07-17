const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;
const hubUrl = source('vas-hub.html');
const clientUrl = source('client-application.html');
const designUrl = source('design-controller.html');
const importUrl = source('project-import.html');
const knowledgeUrl = source('knowledge-search.html');

test('start screen only shows the two choices and never asks for memory automatically', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.hero')).toBeVisible();
  await expect(page.locator('.start-card')).toHaveCount(2);
  await expect(page.locator('.start-card').first()).toContainText('새 프로젝트 만들기');
  await expect(page.locator('.start-card').first()).toContainText('코딩 AI용 프롬프트');
  await expect(page.locator('.start-card').last()).toContainText('기존 프로그램 AI로 연결');
  await expect(page.locator('#privacyRail, #onboarding, .tools-section, .projects-section, #nextRecommendation')).toHaveCount(0);
  expect(await page.evaluate(() => VASPersonalization.getConsent())).toBeNull();
});

test('declining work memory does not record the start navigation', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('.start-card:not(.import)').click();
  await page.locator('#vasStartWithoutMemory').click();
  await page.waitForFunction(() => typeof VASPersonalization !== 'undefined');
  const events = await page.evaluate(async () => VASPersonalization.list());
  expect(events).toEqual([]);
});

test('both start choices require an explicit work-memory decision', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('.start-card:not(.import)').click();
  await expect(page.locator('#vasStartMemory')).toBeVisible();
  await expect(page.locator('#vasStartMemoryTitle')).toHaveText('이번 작업을 기억할까요?');
  expect(await page.evaluate(() => VASPersonalization.getConsent())).toBeNull();
  await page.locator('#vasStartWithoutMemory').click();
  await expect(page).toHaveURL(/client-application\.html/);
  await page.waitForFunction(() => typeof VASPersonalization !== 'undefined');
  expect(await page.evaluate(() => VASPersonalization.getConsent())).toBe(false);

  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('.start-card.import').click();
  await expect(page.locator('#vasStartMemoryState')).toHaveText('사용 안 함');
  await page.locator('#vasStartWithMemory').click();
  await expect(page).toHaveURL(/project-import\.html/);
  await page.waitForFunction(() => typeof VASPersonalization !== 'undefined');
  expect(await page.evaluate(() => VASPersonalization.getConsent())).toBe(true);
});

test('hub keeps only help while work screens keep memory settings', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const header = page.locator('.site-header');
  await expect(header.getByRole('button', { name: '설정' })).toHaveCount(0);
  await header.getByRole('button', { name: '사용 방법' }).click();
  await expect(page.locator('#vasSetupHelp')).toBeVisible();
  await expect(page.locator('#vasSetupHelp')).toContainText('프롬프트를 코딩 도구에 붙여넣습니다');
  await page.locator('#vasSetupHelp [data-setup-close]').click();
  await header.getByRole('button', { name: '사용 방법' }).click();
  await expect(page.locator('#vasSetupHelp')).toBeVisible();
  await page.locator('#vasSetupHelp [data-setup-close]').click();

  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  const workHeader = page.locator('.client-topline');
  await workHeader.getByRole('button', { name: '설정' }).click();
  await expect(page.locator('#vasSetupSettingsTitle')).toHaveText('설정을 바꿔보세요.');
  const titleLayout = await page.locator('#vasSetupSettingsTitle').evaluate(element => {
    const style = getComputedStyle(element);
    return {
      fontSize: parseFloat(style.fontSize),
      lineCount: Math.round(element.getBoundingClientRect().height / parseFloat(style.lineHeight)),
      wordBreak: style.wordBreak
    };
  });
  expect(titleLayout.fontSize).toBeLessThanOrEqual(40);
  expect(titleLayout.lineCount).toBeLessThanOrEqual(2);
  expect(titleLayout.wordBreak).toBe('keep-all');
  await expect(page.locator('#vasSetupMemoryState')).toHaveText('사용 안 함');
  await page.locator('#vasSetupToggleMemory').click();
  await expect(page.locator('#vasSetupMemoryState')).toContainText('사용 중');
  await page.locator('#vasSetupTogglePause').click();
  await expect(page.locator('#vasSetupMemoryState')).toContainText('잠시 중지됨');
  await page.locator('#vasSetupSettings [data-setup-close]').click();
  await workHeader.getByRole('button', { name: '설정' }).click();
  await expect(page.locator('#vasSetupMemoryState')).toContainText('잠시 중지됨');
});

test('consented work memory offers a user-confirmed RAG design recommendation', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  const recommendation = await page.evaluate(async () => {
    VASSetupDesign.apply('awwwards');
    await VASPersonalization.consent(true);
    await VASPersonalization.clear();
    await VASPersonalization.record({
      type: 'theme_selected', source: 'design-studio', payload: { preset: 'linear' }
    });
    await VASSetupDesign.refresh();
    const button = document.querySelector('[data-design-memory-suggestion]');
    return {
      text: button && button.textContent,
      hidden: button && button.hidden,
      runtimeConnected: typeof VASRuntime !== 'undefined',
      ragConnected: typeof VASRagLite !== 'undefined'
    };
  });
  expect(recommendation).toEqual({
    text: '작업 기억 추천: Linear 적용', hidden: false,
    runtimeConnected: true, ragConnected: true
  });
  await page.locator('#projectName').fill('RAG 추천 확인');
  await page.locator('#problemDescription').fill('작업 기억이 디자인 설정에 연결되는지 확인합니다.');
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="2"]')).toHaveClass(/active/);
  await page.locator('input[name="data_status"][value="none"]').check();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="3"]')).toHaveClass(/active/);
  await page.locator('input[name="env_web"]').check();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="4"]')).toHaveClass(/active/);
  await page.locator('input[name="budget"][value="unknown"]').check();
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="5"]')).toHaveClass(/active/);
  await expect(page.locator('#nextBtn')).toHaveText('내용 확인');
  const actionContrast = await page.locator('#nextBtn, .design-reference-link').evaluateAll(elements => {
    const luminance = color => {
      const channels = color.match(/[\d.]+/g).slice(0, 3).map(value => {
        const channel = Number(value) / 255;
        return channel <= .03928 ? channel / 12.92 : Math.pow((channel + .055) / 1.055, 2.4);
      });
      return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
    };
    return elements.map(element => {
      const style = getComputedStyle(element);
      const light = Math.max(luminance(style.color), luminance(style.backgroundColor));
      const dark = Math.min(luminance(style.color), luminance(style.backgroundColor));
      return (light + .05) / (dark + .05);
    });
  });
  actionContrast.forEach(ratio => expect(ratio).toBeGreaterThanOrEqual(4.5));
  const designActionLayout = await page.evaluate(() => {
    const recommendation = document.querySelector('[data-design-memory-suggestion]');
    const reference = document.querySelector('.design-reference-link');
    const next = document.querySelector('#nextBtn');
    const recommendationRect = recommendation.getBoundingClientRect();
    const referenceRect = reference.getBoundingClientRect();
    return {
      separated: recommendationRect.bottom <= referenceRect.top,
      referenceBackground: getComputedStyle(reference).backgroundColor,
      nextBackground: getComputedStyle(next).backgroundColor
    };
  });
  expect(designActionLayout).toEqual({
    separated: true,
    referenceBackground: 'rgb(17, 17, 17)',
    nextBackground: 'rgb(17, 17, 17)'
  });
  await page.locator('[data-design-memory-suggestion]').click();
  await expect(page.locator('#projectDesignPreset')).toHaveValue('linear');
  await expect(page.locator('[data-design-memory-suggestion]')).toContainText('추천 적용됨: Linear');
});

test('theme state reaches the new project contract without recoloring the setup form', async ({ page }) => {
  await page.goto(designUrl, { waitUntil: 'domcontentloaded' });
  const expected = await page.evaluate(() => {
    applyPreset('stripe');
    return { primary: PRESETS.stripe.primary, href: document.querySelector('a[data-vas-link]').href };
  });
  expect(expected.href).toContain('#vas=');
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  const state = await page.evaluate(() => ({
    primary: VASThemeState.get().tokens.colors.primary,
    shellAccent: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
    shellFocusAccent: getComputedStyle(document.documentElement).getPropertyValue('--vas-accent').trim()
  }));
  expect(state.primary).toBe(expected.primary);
  expect(state.shellAccent).toBe('#ffd200');
  expect(state.shellFocusAccent).toBe('#ffd200');
});

test('studio changes update the open form badge and survive reload', async ({ page, context }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'domcontentloaded' });
  const studio = await context.newPage();
  await studio.goto(designUrl + '?return=client-application.html', { waitUntil: 'domcontentloaded' });
  await studio.evaluate(() => applyPreset('linear'));
  await expect(page.locator('#projectDesignPreset')).toHaveValue('linear');
  await expect(page.locator('#themeNameSpan')).toHaveText('Linear');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#projectDesignPreset')).toHaveValue('linear');
  await expect(page.locator('#themeNameSpan')).toHaveText('Linear');
  await studio.close();
});

test('project context remains minimal for compatibility', async ({ page }) => {
  await page.goto(designUrl, { waitUntil: 'domcontentloaded' });
  const result = await page.evaluate(() => {
    VASProjectContext.set({ projectId: 'project-123', sourceType: 'imported', goal: 'redesign', stage: 'design', name: 'private', path: 'C:\\private' });
    const wrapper = document.createElement('div');
    wrapper.innerHTML = '<a data-vas-project-link href="design-controller.html">계속</a>';
    VASProjectContext.decorateLinks(wrapper);
    return { context: VASProjectContext.get(), href: wrapper.querySelector('a').href, stored: sessionStorage.getItem('vasProjectContext') };
  });
  expect(result.context.projectId).toBe('project-123');
  expect(result.href).toContain('vasProject=project-123');
  expect(result.href).not.toContain('private');
  expect(result.stored).not.toContain('C:\\private');
});

test('form draft is explicit and restorable without contact details', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.hero-title h1 > span')).toHaveCount(2);
  await expect(page.locator('.hero-title h1 > span').first()).toHaveText('새 프로젝트');
  expect(await page.locator('.hero-title h1 > span').first().evaluate(node => getComputedStyle(node).whiteSpace)).toBe('nowrap');
  await expect(page.locator('.draft-policy')).toContainText('자동 저장');
  await page.locator('input[name="project_name"]').fill('Restore Test');
  await page.locator('textarea[name="problem_desc"]').fill('복원할 요구사항');
  await page.locator('#nextBtn').click();
  await expect(page.locator('.step[data-step="2"]')).toHaveClass(/active/);
  await page.waitForTimeout(350);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#draftNotice')).toBeVisible();
  await page.getByRole('button', { name: '복원' }).click();
  await expect(page.locator('input[name="project_name"]')).toHaveValue('Restore Test');
  await expect(page.locator('.step[data-step="2"]')).toHaveClass(/active/);
});

test('required fields expose an accessible error and focus the first problem', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#nextBtn').click();
  await expect(page.locator('#projectName')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.locator('[role="alert"]')).toBeVisible();
  await expect(page.locator('#projectName')).toBeFocused();

  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#continueSettings').click();
  await expect(page.locator('#folderPath')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.locator('#folderPath')).toBeFocused();
});

test('new project fields and choices remain visually explicit', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#prevBtn')).toBeHidden();
  await expect(page.locator('#navWrap')).toHaveClass(/only-next/);

  const fieldStyle = await page.locator('#projectName').evaluate(element => {
    const style = getComputedStyle(element);
    return { border: style.borderTopStyle, background: style.backgroundColor };
  });
  expect(fieldStyle.border).toBe('solid');
  expect(fieldStyle.background).not.toBe('rgba(0, 0, 0, 0)');

  await page.locator('#projectName').fill('가독성 확인');
  await page.locator('#problemDescription').fill('선택 항목이 분명하게 보여야 합니다.');
  await page.locator('#nextBtn').click();

  await expect(page.locator('.step[data-step="2"] .block')).toHaveCount(4);
  await expect(page.locator('.step[data-step="2"] .v-block')).toHaveCount(3);
  await expect(page.locator('.step[data-step="2"] .bl-content').first()).toHaveCSS('border-top-style', 'solid');
  await expect(page.locator('.step[data-step="2"] .vl-content').first()).toHaveCSS('border-top-style', 'solid');

  const firstChoice = page.locator('.step[data-step="2"] .block').first();
  await firstChoice.click();
  await expect(firstChoice.locator('input')).toBeChecked();
  expect(await firstChoice.locator('.bl-content').evaluate(element => getComputedStyle(element, '::after').content)).toContain('선택됨');
});

test('local memory sanitizes secrets and absolute paths', async ({ page }) => {
  await page.goto(hubUrl, { waitUntil: 'domcontentloaded' });
  const payload = await page.evaluate(async () => {
    await VASPersonalization.init();
    await VASPersonalization.consent(true);
    await VASPersonalization.record({ type: 'navigation', source: 'test', payload: { topic: '마이그레이션', path: 'C:\\Users\\name\\secret.txt', note: 'api_key=sk-test-secret-1234567890' } });
    return (await VASPersonalization.list())[0].payload;
  });
  expect(JSON.stringify(payload)).not.toContain('C:\\Users');
  expect(JSON.stringify(payload)).not.toContain('sk-test');
});

test('blocked session storage keeps runtime token in memory and URL fragment', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'sessionStorage', { configurable: true, get() { throw new Error('blocked'); } }); });
  const token = 'runtime_token_12345678901234567890';
  await page.goto(knowledgeUrl + '?vasToken=' + token, { waitUntil: 'domcontentloaded' });
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
  expect(page.url()).not.toContain('vasToken=');
  expect(page.url()).toContain('vasRuntime=');
});

test('runtime token decorates links inside a detached wrapper', async ({ page }) => {
  const token = 'runtime_token_12345678901234567890';
  await page.goto(hubUrl + '?vasToken=' + token, { waitUntil: 'domcontentloaded' });
  const href = await page.evaluate(() => {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = '<a href="project-import.html">계속</a>';
    VASRuntime.preserveTokenInLinks(wrapper);
    return wrapper.querySelector('a').href;
  });
  expect(href).toContain('vasRuntime=' + token);
});

test('start screen carries the BAT runtime into the folder picker flow', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'sessionStorage', { configurable: true, get() { throw new Error('blocked'); } }); });
  const token = 'runtime_token_12345678901234567890';
  await page.goto(hubUrl + '?vasToken=' + token, { waitUntil: 'domcontentloaded' });
  const target = await page.locator('.start-card.import').getAttribute('href');
  expect(target).toContain('vasRuntime=' + token);
  await page.goto(target, { waitUntil: 'domcontentloaded' });
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
});

test('BAT runtime survives internal navigation back and forward', async ({ page }) => {
  const token = 'runtime_token_12345678901234567890';
  await page.goto(hubUrl + '?vasToken=' + token, { waitUntil: 'domcontentloaded' });
  await page.locator('.start-card.import').click();
  await page.locator('#vasStartWithoutMemory').click();
  await expect(page).toHaveURL(/project-import\.html/);
  await page.waitForFunction(() => typeof VASRuntime !== 'undefined');
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
  await page.goBack({ waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/vas-hub\.html/);
  await page.waitForFunction(() => typeof VASRuntime !== 'undefined');
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
  await page.goForward({ waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/project-import\.html/);
  await page.waitForFunction(() => typeof VASRuntime !== 'undefined');
  expect(await page.evaluate(() => VASRuntime.getToken())).toBe(token);
});

test('existing flow asks for intent and leaves source discovery to the coding AI', async ({ page }) => {
  await page.goto(importUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#selectFolder')).toHaveText('폴더 위치');
  await expect(page.locator('#modeLabel, [data-preview], #analyzeButton, #analysisGrid')).toHaveCount(0);
  await page.locator('#folderPath').fill('Z:\\work\\legacy-app');
  await page.locator('#projectName').fill('legacy-app');
  await page.locator('#taskRequest').fill('오류를 고쳐 주세요.');
  await page.locator('#continueSettings').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await expect(page.locator('#handoffDesignSummary')).toContainText('잡지처럼 큰 제목과 비대칭 구성');
  await expect(page.locator('[data-design-reference]')).toContainText('Awwwards 디자인 예시·설정 보기');
  await expect(page.locator('[data-design-reference]')).toHaveAttribute('href', /design-controller\.html/);
  await page.locator('#handoffDesignPreset').selectOption('linear');
  await expect(page.locator('#handoffDesignSummary')).toContainText('차분한 어두운 화면');
  await expect(page.locator('[data-design-reference]')).toContainText('Linear 디자인 예시·설정 보기');
  await expect(page.locator('#previewContent')).toContainText('Z:\\work\\legacy-app');
  await expect(page.locator('#previewContent')).toContainText('실제 파일을 직접 읽어 판단하세요');
  await expect(page.locator('#advancedMigration, #createIndex, #configureButton')).toHaveCount(0);
});
