const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;

test('public presets hand off version-labelled source, live sample and unverified state without loading URLs', async ({ page }) => {
  const remoteRequests = [];
  page.on('request', request => { if (/^https?:/.test(request.url())) remoteRequests.push(request.url()); });
  await page.goto(source('client-application.html'));
  const results = await page.evaluate(async () => {
    const rows = [];
    for (const key of VAS_PRESET_KEYS) {
      VASSetupDesign.apply(key);
      const design = VASSetupDesign.context();
      const built = await VASAgentHandoffWeb.buildNew({ project_name: 'Reference fixture', problem_desc: 'Build a portfolio' }, design);
      rows.push({ key, version: VASConfig.version, setup: design.visualReference,
        reference: built.document.context.design.visualReference, tokens: built.document.context.design.tokens,
        prompt: built.pasteText, inputReview: built.document.inputReview });
    }
    return rows;
  });
  expect(results).toHaveLength(14);
  for (const item of results) {
    expect(item.reference).toEqual(item.setup);
    expect(item.reference).toMatchObject({ status: 'unverified', sampleKind: 'base-preset', samplePreset: item.key,
      userModified: false, valueAuthority: 'confirmed-design-tokens', vasVersion: item.version,
      sourceRef: 'v' + item.version, liveSampleVersion: 'not-verified', applicationScope: { mode: 'new', scope: '' } });
    expect(item.reference.versionedSourceUrl).toBe('https://github.com/zmsqnfl-commits/quintpact-vas/blob/v' + item.version + '/src/design-sample.html');
    expect(item.reference.liveSampleUrl).toBe('https://zmsqnfl-commits.github.io/quintpact-vas/src/design-sample.html?preset=' + item.key);
    expect(item.prompt).toContain(item.reference.liveSampleUrl);
    expect(item.prompt).toContain(item.tokens.fontFamily);
    expect(item.prompt).toContain('시각 참조 미확인');
    expect(item.prompt).toContain('최신 Pages');
    expect(item.prompt).toContain('외부 CDN·원격 폰트를 추가하지 마세요');
    expect(item.inputReview.required).toBe(false);
  }
  expect(remoteRequests).toEqual([]);
});

test('custom tokens use their known base sample and partial permission remains exact', async ({ page }) => {
  await page.goto(source('project-import.html'));
  const value = await page.evaluate(async () => {
    VASSetupDesign.apply('bento');
    const tokens = VASThemeState.get().tokens;
    tokens.colors.primary = '#123abc';
    VASThemeState.commit({ preset: 'custom', basePreset: 'bento', tokens });
    const scope = { mode: 'partial', scope: '주문 화면 / 확인 버튼 / 배경색' };
    const setup = VASSetupDesign.context(scope);
    const built = await VASAgentHandoffWeb.buildExisting('Partial fixture', '확인 버튼 색상만 변경', { design: setup }, { designScope: scope });
    return { document: built.document, prompt: built.pasteText, setup };
  });
  const design = value.document.context.design;
  expect(design.preset).toBe('custom');
  expect(design.basePreset).toBe('bento');
  expect(design.tokens.colors.primary).toBe('#123abc');
  expect(design.visualReference).toMatchObject({ samplePreset: 'bento', userModified: true,
    applicationScope: { mode: 'partial', scope: '주문 화면 / 확인 버튼 / 배경색' } });
  expect(value.prompt).toContain('샘플과 달라도 확정 디자인 토큰을 따르세요');
  expect(value.prompt).toContain('#123abc');
  expect(value.prompt).toContain('나머지 기존 디자인은 유지');
  expect(value.document.inputReview.required).toBe(false);
});

test('preserve removes sample, token and style directions even with supplied active metadata', async ({ page }) => {
  await page.goto(source('project-import.html'));
  const value = await page.evaluate(async () => {
    VASSetupDesign.apply('bento');
    const setup = VASSetupDesign.context({ mode: 'preserve', scope: '' });
    const active = VASSetupDesign.context();
    active.direction = 'REPLACE ALL COLORS';
    const result = await VASAgentHandoffWeb.buildExisting('Preserve fixture', 'CSV 고치기', { design: active });
    return { setup, document: result.document, prompt: result.pasteText };
  });
  expect(value.setup).toEqual({ included: false });
  expect(value.document.context.design).toEqual({ included: false });
  expect(value.prompt).toContain('기존 디자인 유지');
  for (const text of ['REPLACE ALL COLORS', '디자인 시각 참조', '확정 디자인 토큰', 'design-sample.html']) expect(value.prompt).not.toContain(text);
});

test('unknown or unbased custom styles do not invent working sample links', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const rows = await page.evaluate(async () => {
    const output = [];
    for (const preset of ['custom', 'legacy-unknown', 'vercel']) {
      const built = await VASAgentHandoffWeb.buildNew({ problem_desc: 'Custom UI' }, {
        included: true, preset, tokens: { fontFamily: 'system-ui', colors: { primary: '#123abc' } }, direction: 'Use confirmed values'
      });
      output.push({ reference: built.document.context.design.visualReference, prompt: built.pasteText });
    }
    return output;
  });
  for (const row of rows) {
    expect(row.reference).toMatchObject({ status: 'unverified', samplePreset: null, versionedSourceUrl: null, liveSampleUrl: null });
    expect(row.prompt).toContain('다른 스타일의 샘플로 대체하지 말고');
    expect(row.prompt).not.toContain('preset=awwwards');
  }
});

test('reference metadata and confirmed values survive v3 normalization and enter integrity hashes', async ({ page }) => {
  await page.goto(source('client-application.html'));
  const value = await page.evaluate(async () => {
    VASSetupDesign.apply('linear');
    const initial = (await VASAgentHandoffWeb.buildNew({ problem_desc: 'A task board' }, VASSetupDesign.context())).document;
    const normalized = await VASAgentContract.normalizeHandoff(JSON.parse(JSON.stringify(initial)));
    const changed = JSON.parse(JSON.stringify(initial));
    changed.context.design.visualReference.sourceRef = 'v0.0.1';
    await VASAgentHandoffWeb.refreshIntegrity(changed);
    return { initial, normalized, changed };
  });
  expect(value.initial.schemaVersion).toBe(3);
  expect(value.normalized.context.design).toEqual(value.initial.context.design);
  expect(value.normalized.integrity.payloadSha256).toBe(value.initial.integrity.payloadSha256);
  expect(value.changed.integrity.payloadSha256).not.toBe(value.initial.integrity.payloadSha256);
});
