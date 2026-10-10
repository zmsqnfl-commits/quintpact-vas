/** Real Windows runtime + Chromium + separate CLI processes; no mocked session API. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const { spawn, spawnSync } = require('node:child_process');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const copy = value => JSON.parse(JSON.stringify(value));
const results = [], consoleMessages = [], pageErrors = [], requests = [];
let task, runtimeRoot, env, runtime, server, browser, python, serverOutput = '';
const secret = 'Stage3FixturePassword_47';
const staleContext = { v: 1, projectId: 'stale-project-canary', sourceType: 'imported', goal: 'redesign', stage: 'design' };
const globalTheme = JSON.stringify({ colors: { primary: '#aa1177' }, radius: 27 });

async function bounded(promise, message) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(message)), 15000);
    })]);
  } finally { clearTimeout(timer); }
}

function cli(args, settings) {
  const result = spawnSync(python, ['-B', path.join(root, 'scripts/vas-session.py'), '--vas-root', runtimeRoot, ...args], {
    cwd: root, env, windowsHide: true, encoding: 'utf8', timeout: 30000,
    input: settings === undefined ? undefined : JSON.stringify(settings)
  });
  assert.equal(result.status, 0, result.error?.message || result.stderr || result.stdout);
  return JSON.parse(result.stdout.replace(/^\uFEFF/, ''));
}
const resume = id => cli(['resume', '--session', id]).session;
function save(id, update) {
  const current = resume(id), next = copy(current.settings);
  update(next);
  return cli(['save', '--session', id, '--expected-revision', String(current.revision)], next).session;
}
function settings(name, primary, existing = false) {
  return {
    project: { name, sourceType: existing ? 'existing' : 'new' },
    task: { request: '예약 CSV 내보내기', constraints: ['로그인 제외'],
      designScope: { mode: existing ? 'preserve' : 'new', scope: existing ? '' : '예약 화면' },
      completionCriteria: [{ description: 'CSV의 한글과 쉼표 보존', method: 'automatic', required: true }] },
    design: { profileId: 'editorial', preset: 'custom', basePreset: 'awwwards', tasteProfileMode: 'editorial',
      direction: '차분한 예약 화면', tokens: { fontFamily: 'system-ui', fontSize: 16, radius: 8,
        padding: 24, borderWidth: 1, shadow: 0, speed: 0.3, letterSpacing: 0,
        colors: { primary, background: '#f5f4f0', surface: '#ffffff', text: '#182028', border: '#d7dadc', success: '#228844' } } },
    questions: ['예약 단위 확인'], nextStep: '예약 입력 항목 확정'
  };
}
function create(name, primary, existing = false) {
  const target = path.join(runtimeRoot, 'workspace', name);
  fs.mkdirSync(target, { recursive: true });
  fs.writeFileSync(path.join(target, 'app.txt'), 'fixture app must never be edited\n');
  const data = settings(name, primary, existing);
  return { target, document: cli(['create', '--target', target], data).session };
}
async function api(route, method = 'GET', body, headers) {
  const response = await fetch(runtime.baseUrl + route, {
    method, headers: headers || { Origin: runtime.baseUrl, 'X-VAS-Token': runtime.token, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000)
  });
  return { status: response.status, data: await response.json() };
}
async function check(name, action) {
  await action(); results.push(name); process.stdout.write('PASS ' + name + '\n');
}
async function freePort() {
  const probe = net.createServer();
  await new Promise((resolve, reject) => { probe.once('error', reject); probe.listen(0, '127.0.0.1', resolve); });
  const port = probe.address().port;
  await new Promise(resolve => probe.close(resolve));
  return Math.min(port, 65526);
}
async function start() {
  task = fs.mkdtempSync(path.join(os.tmpdir(), 'vas-session-design-'));
  runtimeRoot = path.join(task, 'runtime');
  fs.mkdirSync(runtimeRoot);
  fs.cpSync(path.join(root, 'src'), path.join(runtimeRoot, 'src'), { recursive: true });
  fs.copyFileSync(path.join(root, 'Run-VAS-System.bat'), path.join(runtimeRoot, 'Run-VAS-System.bat'));
  const probe = spawnSync(process.env.VAS_PYTHON || 'python.exe', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8', windowsHide: true });
  assert.equal(probe.status, 0, 'Python 3.10+ is required');
  python = probe.stdout.trim();
  env = { ...process.env, LOCALAPPDATA: path.join(task, 'local-appdata'), VAS_PYTHON: python, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' };
  const state = path.join(task, 'runtime-state');
  fs.mkdirSync(state);
  server = spawn('powershell.exe', ['-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    path.join(root, 'scripts/Start-VAS.ps1'), '-Server', '-NoBrowser', '-RootPath', runtimeRoot,
    '-StateRoot', state, '-Port', String(await freePort()), '-IdleTimeoutSeconds', '600'],
  { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.on('data', value => { serverOutput += value; });
  server.stderr.on('data', value => { serverOutput += value; });
  for (let attempt = 0; attempt < 100; attempt++) {
    const file = fs.readdirSync(state).find(name => /^runtime-.*\.json$/.test(name));
    if (file) { runtime = JSON.parse(fs.readFileSync(path.join(state, file), 'utf8').replace(/^\uFEFF/, '')); break; }
    if (server.exitCode !== null) throw new Error('Runtime exited: ' + serverOutput);
    await delay(200);
  }
  assert.ok(runtime, 'runtime did not start');
  const chrome = process.env.VAS_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  browser = await chromium.launch({ headless: true, ...(fs.existsSync(chrome) ? { executablePath: chrome } : {}) });
}
function observe(page) {
  page.on('console', item => consoleMessages.push({ type: item.type(), text: item.text(), url: item.location().url }));
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', request => requests.push({ method: request.method(), path: new URL(request.url()).pathname }));
  page.on('dialog', dialog => dialog.accept());
}
async function revision(page, number) {
  await page.waitForFunction(expected => document.getElementById('chatDesignPanel')?.dataset.revision === String(expected), number, { timeout: 15000 });
}
async function state(page, name) {
  await page.waitForFunction(expected => document.getElementById('chatDesignPanel')?.dataset.state === expected, name, { timeout: 15000 });
}
async function focus(page) {
  await page.bringToFront(); await page.evaluate(() => window.dispatchEvent(new Event('focus')));
}
async function open(context, id) {
  const page = await context.newPage();
  await page.goto(runtime.baseUrl + '/src/design-controller.html?session=' + id + '&vasToken=' + runtime.token);
  return page;
}
function noPrivate(value, targets) {
  const text = JSON.stringify(value);
  for (const forbidden of [secret, runtimeRoot, ...targets]) {
    assert.ok(!text.includes(forbidden) && !text.includes(JSON.stringify(forbidden).slice(1, -1)), 'private value in public response');
  }
}
async function main() {
  await start();
  const first = create('예약 작업', '#125678'), second = create('재고 작업', '#8b4513'), preserved = create('기존 작업', '#456789', true);
  const legacy = create('이전 토큰 작업', '#123456');
  const id = first.document.sessionId, other = second.document.sessionId, preserveId = preserved.document.sessionId;
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  context.on('page', observe);
  await context.addInitScript(({ globalTheme, staleContext, origin }) => {
    if (location.origin !== origin) return;
    localStorage.setItem('vasThemeTokens', globalTheme);
    localStorage.setItem('vasCurrentPreset', 'clay');
    sessionStorage.setItem('vasProjectContext', JSON.stringify(staleContext));
  }, { globalTheme, staleContext, origin: runtime.baseUrl });
  const page = await open(context, id);
  await check('CLI design is displayed in the real design studio', async () => {
    await revision(page, first.document.revision); await state(page, 'saved');
    assert.equal(await page.locator('#colorPrimary').inputValue(), '#125678');
    assert.equal(await page.locator('#radius').inputValue(), '8');
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), '차분한 예약 화면');
    assert.equal(await page.locator('#chatDesignScope').inputValue(), 'new');
    assert.equal((await page.locator('#applyProjectTheme').textContent()).trim(), '대화 설정에 저장');
    assert.equal(await page.locator('#applyProjectTheme').isDisabled(), true);
    assert.deepEqual(resume(id), first.document, 'opening the UI must not rewrite the document');
  });
  let expected = first.document;
  await check('browser save is restored by an independent CLI process without changing the task', async () => {
    await page.locator('#chatDesignDirection').fill('화면에서 선택한 올리브색 예약 화면');
    await page.locator('#colorPrimary').fill('#337755');
    await page.locator('#applyProjectTheme').click();
    await revision(page, expected.revision + 1); await state(page, 'saved');
    const saved = resume(id);
    assert.equal(saved.settings.design.tokens.colors.primary, '#337755');
    assert.equal(saved.settings.design.direction, '화면에서 선택한 올리브색 예약 화면');
    for (const field of ['project', 'task', 'questions', 'nextStep']) assert.deepEqual(saved.settings[field], expected.settings[field]);
    expected = saved;
  });
  await check('a clean studio refreshes when a separate CLI changes design and requirements', async () => {
    expected = save(id, data => { data.design.direction = '채팅에서 바꾼 차분한 파란색'; data.design.tokens.colors.primary = '#2244bb'; data.task.request = '예약 CSV와 날짜 필터'; });
    await focus(page); await revision(page, expected.revision);
    assert.equal(await page.locator('#colorPrimary').inputValue(), '#2244bb');
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), expected.settings.design.direction);
    assert.equal(await page.locator('#chatDesignRequest').textContent(), expected.settings.task.request);
    assert.equal(await page.locator('#applyProjectTheme').isDisabled(), true);
  });
  await check('a stale browser save conflicts without overwriting either draft or CLI updates', async () => {
    await page.locator('#chatDesignDirection').fill('저장 전 화면 초안');
    await page.route('**/api/chat/session/design', async route => {
      expected = save(id, data => { data.design.direction = '동시에 확정한 채팅 디자인'; data.questions = ['동시 편집 후 확인']; });
      await route.continue();
    }, { times: 1 });
    await page.locator('#applyProjectTheme').click(); await state(page, 'conflict');
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), '저장 전 화면 초안');
    assert.equal(await page.locator('#applyProjectTheme').isDisabled(), true);
    assert.deepEqual(resume(id), expected);
    await page.locator('#chatDesignReload').click(); await revision(page, expected.revision); await state(page, 'saved');
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), expected.settings.design.direction);
  });
  await check('dirty polling keeps the local draft until explicit reload', async () => {
    await page.locator('#chatDesignDirection').fill('두 번째 저장 전 초안');
    expected = save(id, data => { data.design.direction = '새 대화의 최종 방향'; });
    await focus(page); await state(page, 'conflict');
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), '두 번째 저장 전 초안');
    await page.locator('#chatDesignReload').click(); await revision(page, expected.revision);
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), '새 대화의 최종 방향');
  });
  await check('a delayed real GET cannot roll back a successful browser save', async () => {
    let release, captured;
    const releaseOldResponse = new Promise(resolve => { release = resolve; });
    const oldResponseCaptured = new Promise(resolve => { captured = resolve; });
    await page.route('**/api/chat/session?sessionId=' + id, async route => {
      const response = await route.fetch(); captured();
      await releaseOldResponse; await route.fulfill({ response });
    }, { times: 1 });
    try {
      await focus(page); await bounded(oldResponseCaptured, 'No refresh response arrived for the delayed GET check');
      await page.locator('#chatDesignDirection').fill('지연 조회보다 새로운 화면 저장');
      await page.locator('#applyProjectTheme').click(); await revision(page, expected.revision + 1);
      expected = resume(id);
    } finally { release(); }
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#chatDesignPanel').getAttribute('data-revision'), String(expected.revision));
    assert.equal(await page.locator('#chatDesignDirection').inputValue(), '지연 조회보다 새로운 화면 저장');
    assert.deepEqual(resume(id), expected);
  });
  const otherPage = await open(context, other);
  await check('two sessions stay isolated from each other and legacy global theme storage', async () => {
    await revision(otherPage, second.document.revision);
    assert.equal(await otherPage.locator('#colorPrimary').inputValue(), '#8b4513');
    await otherPage.locator('#colorPrimary').fill('#663399');
    await otherPage.locator('#applyProjectTheme').click(); await revision(otherPage, second.document.revision + 1);
    await focus(page);
    assert.equal(await page.locator('#colorPrimary').inputValue(), '#2244bb');
    assert.deepEqual(resume(id), expected);
    assert.equal(await page.evaluate(() => localStorage.getItem('vasThemeTokens')), globalTheme);
    assert.equal(await otherPage.evaluate(() => localStorage.getItem('vasCurrentPreset')), 'clay');
    assert.ok(!requests.some(item => item.path === '/api/projects/theme'), 'stale project context triggered legacy writes');
  });
  const preservePage = await open(context, preserveId);
  await check('existing design stays preserved until a change scope is explicitly selected', async () => {
    await revision(preservePage, preserved.document.revision);
    assert.equal(await preservePage.locator('#chatDesignScope').inputValue(), 'preserve');
    assert.equal(await preservePage.locator('#colorPrimary').isDisabled(), true);
    assert.equal(await preservePage.locator('#chatDesignDirection').isDisabled(), true);
    assert.deepEqual(resume(preserveId), preserved.document);
    await preservePage.locator('#chatDesignScope').selectOption('partial');
    assert.equal(await preservePage.locator('#applyProjectTheme').isDisabled(), true, 'partial changes require a named scope');
    await preservePage.locator('#chatDesignScopeText').fill('예약 목록의 필터 영역');
    await preservePage.locator('#chatDesignDirection').fill('필터 영역만 간결하게');
    await preservePage.locator('#applyProjectTheme').click(); await revision(preservePage, preserved.document.revision + 1);
    const saved = resume(preserveId);
    assert.deepEqual(saved.settings.task.designScope, { mode: 'partial', scope: '예약 목록의 필터 영역' });
    assert.deepEqual(saved.settings.task.completionCriteria, preserved.document.settings.task.completionCriteria);
    assert.equal(saved.settings.design.direction, '필터 영역만 간결하게');
  });
  await check('editing direction alone preserves legacy version-one arbitrary tokens', async () => {
    const legacyDoc = save(legacy.document.sessionId, data => {
      data.design = { profileId: 'editorial', direction: '이전 설정 방향',
        tokens: { color: '#112233', radius: '8px', spacing: { gutter: 12 }, customFlag: true } };
    });
    const legacyPage = await open(context, legacyDoc.sessionId); await revision(legacyPage, legacyDoc.revision);
    await legacyPage.locator('#chatDesignDirection').fill('방향 문장만 수정');
    await legacyPage.locator('#applyProjectTheme').click(); await revision(legacyPage, legacyDoc.revision + 1);
    const after = resume(legacyDoc.sessionId);
    assert.deepEqual(after.settings.design.tokens, legacyDoc.settings.design.tokens);
    assert.equal(after.settings.design.direction, '방향 문장만 수정');
    assert.deepEqual(Object.keys(after.settings.design).sort(), ['direction', 'profileId', 'tokens']);
    assert.deepEqual(after.settings.task, legacyDoc.settings.task); await legacyPage.close();
  });
  await check('reload and sample-site round trip retain the selected session and saved design', async () => {
    await page.reload(); await revision(page, expected.revision);
    const opened = context.waitForEvent('page'); await page.locator('#openDesignSample').click();
    const sample = await opened; await sample.waitForLoadState();
    assert.equal(new URL(sample.url()).searchParams.get('session'), id);
    assert.equal(new URL(await sample.locator('#sampleBack').getAttribute('href'), sample.url()).searchParams.get('session'), id);
    await sample.locator('#sampleBack').click(); await revision(sample, expected.revision);
    assert.equal(await sample.locator('#colorPrimary').inputValue(), expected.settings.design.tokens.colors.primary);
    assert.deepEqual(resume(id), expected); await sample.close();
  });
  await check('desktop and narrow-screen controls remain within the viewport', async () => {
    await focus(page); await page.screenshot({ path: path.join(task, 'desktop.png'), fullPage: false });
    await page.screenshot({ path: path.join(task, 'desktop-full.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('[data-studio-view="settings"]').click();
    assert.ok(await page.locator('#chatDesignPanel').isVisible());
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'horizontal page overflow');
    await page.screenshot({ path: path.join(task, 'mobile.png'), fullPage: false });
    await page.screenshot({ path: path.join(task, 'mobile-full.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
  });
  await check('public API excludes bindings and secrets and rejects missing authentication', async () => {
    expected = save(id, data => { data.design.direction = '차분한 디자인 {"password":"' + secret + '"}'; });
    for (const route of ['/api/chat/sessions', '/api/chat/session?sessionId=' + id]) {
      const response = await api(route); assert.equal(response.status, 200); noPrivate(response.data, [first.target, second.target, preserved.target]);
      if (response.data.target) assert.deepEqual(Object.keys(response.data.target), ['status']);
    }
    assert.equal((await api('/api/chat/sessions', 'GET', undefined, { Origin: runtime.baseUrl })).status, 401);
    assert.equal((await api('/api/chat/sessions', 'GET', undefined, { 'X-VAS-Token': runtime.token })).status, 403);
    await focus(page); await revision(page, expected.revision);
    assert.ok(!(await page.locator('body').textContent()).includes(secret));
  });
  await check('unknown sessions show an error and cannot save', async () => {
    const missing = await open(context, 'f'.repeat(32)); await state(missing, 'error');
    assert.equal(await missing.locator('#applyProjectTheme').isDisabled(), true);
    assert.equal((await api('/api/chat/session?sessionId=' + 'f'.repeat(32))).status, 404);
    await missing.close();
  });
  await check('deleted target is read-only until the CLI explicitly rebinds it', async () => {
    const moved = path.join(runtimeRoot, 'workspace', 'moved-inventory');
    assert.ok(second.target.startsWith(runtimeRoot + path.sep) && moved.startsWith(runtimeRoot + path.sep));
    fs.renameSync(second.target, moved);
    await focus(otherPage); await state(otherPage, 'error');
    assert.equal(await otherPage.locator('#applyProjectTheme').isDisabled(), true);
    assert.equal(await otherPage.locator('#colorPrimary').isDisabled(), true);
    const doc = resume(other), before = copy(doc);
    const rejected = await api('/api/chat/session/design', 'POST', { sessionId: other, expectedRevision: doc.revision,
      designScope: doc.settings.task.designScope, design: doc.settings.design });
    assert.equal(rejected.status, 409); assert.equal(rejected.data.code, 'target_unavailable');
    assert.deepEqual(resume(other), before);
    assert.equal(fs.readFileSync(path.join(moved, 'app.txt'), 'utf8'), 'fixture app must never be edited\n');
  });
  await check('session removal stops an already open studio from saving', async () => {
    const current = resume(preserveId);
    cli(['forget', '--session', preserveId, '--expected-revision', String(current.revision)]);
    await focus(preservePage); await state(preservePage, 'error');
    assert.equal(await preservePage.locator('#applyProjectTheme').isDisabled(), true);
    assert.equal((await api('/api/chat/session?sessionId=' + preserveId)).status, 404);
  });
  await check('no app files or unrelated project writes and no unexpected browser errors', async () => {
    for (const target of [first.target, preserved.target, legacy.target]) {
      assert.deepEqual(fs.readdirSync(target), ['app.txt']);
      assert.equal(fs.readFileSync(path.join(target, 'app.txt'), 'utf8'), 'fixture app must never be edited\n');
    }
    assert.ok(!requests.some(item => item.method === 'POST' && item.path === '/api/projects/theme'));
    assert.deepEqual(pageErrors, []);
    const unexpected = consoleMessages.filter(item => item.type === 'error' &&
      !(/\/api\/chat\/session/.test(item.url) && /(?:404|409)/.test(item.text)));
    assert.deepEqual(unexpected, []);
  });
  await context.close();
}
function scrub(value) {
  let text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  if (runtime?.token) text = text.replaceAll(runtime.token, '[runtime-token]');
  return text;
}
(async () => {
  if (process.platform !== 'win32') {
    process.stdout.write('SKIP session-design integration: Windows PowerShell runtime is required.\n');
    return;
  }
  let failure;
  try { await main(); } catch (error) { failure = scrub(error.stack || error); process.exitCode = 1; }
  finally {
    if (failure && browser) {
      const pages = browser.contexts().flatMap(context => context.pages());
      const states = [];
      for (const page of pages) {
        states.push(await page.evaluate(() => ({ path: location.pathname,
          state: document.getElementById('chatDesignPanel')?.dataset.state,
          revision: document.getElementById('chatDesignPanel')?.dataset.revision,
          status: document.getElementById('chatDesignStatus')?.textContent,
          direction: document.getElementById('chatDesignDirection')?.value })).catch(() => ({})));
      }
      fs.writeFileSync(path.join(task, 'failure-ui.json'), scrub(states));
      if (pages.length) await pages[0].screenshot({ path: path.join(task, 'failure.png'), timeout: 5000 }).catch(() => {});
    }
    if (browser) await browser.close().catch(() => {});
    if (runtime) await api('/api/shutdown', 'POST', {}).catch(() => {});
    if (server && server.exitCode === null) {
      await Promise.race([new Promise(resolve => server.once('exit', resolve)), delay(3000)]);
      if (server.exitCode === null) server.kill();
    }
    if (task) fs.writeFileSync(path.join(task, 'results.json'), scrub({ status: failure ? 'failed' : 'passed',
      checks: results, failure, pageErrors, consoleMessages, requests, serverOutput }));
    if (failure) process.stderr.write(failure + '\n');
    process.stdout.write(`${results.length} session-design checks passed. Artifacts: ${task || 'not created'}\n`);
  }
})();
