const { test, expect } = require('@playwright/test');
const fs = require('fs');
const os = require('os');
const path = require('path');
const net = require('net');
const { spawn, spawnSync } = require('child_process');
const root = path.resolve(__dirname, '..');
let directory, state, base, token, runtimeRoot;

test.skip(process.platform !== 'win32', 'Requires the actual Windows PowerShell runtime');
test.setTimeout(45000);
test.beforeAll(async () => {
  directory = fs.mkdtempSync(path.join(os.tmpdir(), 'vas-connected-'));
  runtimeRoot = path.join(directory, '검증 원본'); state = path.join(directory, 'isolated state');
  fs.mkdirSync(runtimeRoot, { recursive: true });
  const copied = spawnSync('python', ['-c', 'import shutil,sys; shutil.copytree(sys.argv[1],sys.argv[2])', path.join(root, 'src'), path.join(runtimeRoot, 'src')], { windowsHide: true, cwd: directory });
  if (copied.status !== 0) throw new Error('Synthetic source copy failed');
  fs.mkdirSync(path.join(runtimeRoot, 'docs'));
  const port = await new Promise(resolve => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)); }); });
  const launch = spawnSync('powershell.exe', ['-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path.join(root, 'scripts/Start-VAS.ps1'), '-NoBrowser', '-RootPath', runtimeRoot, '-StateRoot', state, '-Port', String(port), '-IdleTimeoutSeconds', '180'], { windowsHide: true, cwd: directory, timeout: 25000 });
  if (launch.status !== 0) throw new Error('Synthetic Windows runtime launch failed: ' + launch.status);
  const name = fs.readdirSync(state).find(n => /^runtime-.*\.json$/.test(n));
  const details = JSON.parse(fs.readFileSync(path.join(state, name), 'utf8').replace(/^\uFEFF/, ''));
  base = 'http://127.0.0.1:' + details.port; token = details.token;
});
test.afterAll(async () => {
  if (base) await fetch(base + '/api/shutdown', { method: 'POST', headers: { Origin: base, 'X-VAS-Token': token } }).catch(() => {});
  // Keep isolated evidence under OS Temp; never delete user or workspace directories.
});
test.beforeEach(async ({ page }) => {
  await fetch(base + '/api/memory/events', { method: 'DELETE', headers: { Origin: base, 'X-VAS-Token': token } });
  await fetch(base + '/api/memory/pause', { method: 'POST', headers: { Origin: base, 'X-VAS-Token': token, 'Content-Type': 'application/json' }, body: '{"paused":false}' });
  page.on('dialog', d => d.accept());
});
async function open(page, name = 'project-import.html') { await page.goto(base + '/src/' + name + '?vasToken=' + token); }
async function downloaded(page, button) {
  const pending = page.waitForEvent('download'); await page.locator(button).click();
  return fs.readFileSync(await (await pending).path(), 'utf8');
}

test('failed disk erasure remains visible, retry deletes history, and reload agrees', async ({ page }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await open(page);
  await page.evaluate(async () => { await VASPersonalization.consent(true); await VASPersonalization.record('theme_selected', { preset: 'bento' }); });
  const before = fs.readFileSync(path.join(state, 'memory.json'));
  const backup = path.join(state, 'memory.previous.json'); fs.writeFileSync(backup, before);
  const lockScript = path.join(directory, 'lock-backup.ps1');
  fs.writeFileSync(lockScript, '$f=[IO.File]::Open($args[0],[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None); try { [Console]::WriteLine("ready"); [Console]::ReadLine() | Out-Null } finally { $f.Dispose() }');
  const lock = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', lockScript, backup], { windowsHide: true, cwd: directory });
  const exited = new Promise(resolve => lock.once('exit', resolve));
  try {
    await Promise.race([new Promise((resolve, reject) => { lock.stdout.once('data', resolve); lock.once('error', reject); }), exited.then(() => { throw new Error('Backup lock helper exited before readiness'); })]);
    await page.locator('[data-setup-settings]').first().click();
    await page.locator('#vasSetupDeleteMemory').click();
    await expect(page.locator('#vasSetupFeedback')).toContainText('삭제하지 못했습니다');
    expect(fs.readFileSync(path.join(state, 'memory.json')).equals(before)).toBe(true);
    expect(await page.evaluate(async () => (await VASPersonalization.status()).count)).toBe(1);
  } finally { if (lock.exitCode === null) lock.stdin.end('\n'); await exited; }
  await page.locator('#vasSetupDeleteMemory').click();
  await expect(page.locator('#vasSetupFeedback')).toContainText('삭제했습니다');
  expect(fs.existsSync(backup)).toBe(false);
  await page.reload();
  expect(await page.evaluate(async () => (await VASPersonalization.status()).count)).toBe(0);
  expect(errors).toEqual([]);
});

test('reset reaches open tabs, navigation, downloads and recommendations', async ({ page, context }) => {
  await open(page);
  await page.evaluate(async () => { VASSetupDesign.apply('bento'); await VASPersonalization.consent(true); await VASSetupDesign.confirm(); });
  const other = await context.newPage(); await open(other, 'client-application.html');
  await expect(other.locator('#projectDesignPreset')).toHaveValue('bento');
  await page.locator('[data-setup-settings]').first().click(); await page.locator('#vasSetupReset').click();
  await expect(page.locator('#vasSetupFeedback')).toContainText('기본 디자인');
  await expect(other.locator('#projectDesignPreset')).toHaveValue('awwwards');
  await expect(other.locator('[data-design-memory-suggestion]')).toBeHidden();
  await page.reload();
  await page.locator('#folderPath').fill('C:\\synthetic\\original'); await page.locator('#projectName').fill('Demo');
  await page.locator('#taskRequest').fill('Preserve working features'); await page.locator('#continueSettings').click();
  const doc = JSON.parse(await downloaded(page, '#downloadJson'));
  expect(doc.context.design.preset).toBe('awwwards');
  expect(await page.evaluate(async () => (await VASPersonalization.status()).count)).toBe(0);
  await other.close();
});

for (const width of [1440, 390]) test('new-project copy and JSON agree with all confirmed inputs at ' + width, async ({ page }) => {
  await page.setViewportSize({ width, height: 960 });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.addInitScript(() => { window.copiedPrompt = ''; Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async t => { window.copiedPrompt = t; } } }); });
  await open(page, 'vas-hub.html');
  await page.locator('.start-card:not(.import)').click(); await page.locator('#vasStartWithMemory').click();
  await page.locator('#projectName').fill('Integrated brief');
  await page.locator('#problemDescription').fill('Build a task board. DATABASE_URL=postgresql://demo:FullFlowSecretCanary@localhost/app');
  await page.locator('#fileInput').setInputFiles({ name: 'Confidential-Acquisition.pdf', mimeType: 'application/pdf', buffer: Buffer.from('synthetic attachment') });
  await page.locator('#nextBtn').click(); await page.locator('input[name="data_status"][value="none"]').check();
  await page.locator('#nextBtn').click(); await page.locator('input[name="env_web"]').check();
  await page.locator('#nextBtn').click(); await page.locator('input[name="budget"][value="unknown"]').check();
  await page.locator('[name="extra"]').fill('a'.repeat(1100) + ' KeepLateRestrictionCanary');
  await page.locator('#nextBtn').click();
  await page.locator('#projectDesignPreset').selectOption('bento');
  expect(await page.evaluate(async () => (await VASPersonalization.list()).length)).toBe(0);
  await page.locator('#nextBtn').click(); await expect(page.locator('#doneScreen')).toHaveClass(/active/);
  await page.locator('[onclick="copyNewProjectPrompt()"]').click();
  await expect.poll(() => page.evaluate(() => window.copiedPrompt)).toContain('KeepLateRestrictionCanary');
  const raw = await downloaded(page, '#downloadHandoff');
  const copied = await page.evaluate(() => window.copiedPrompt);
  for (const output of [raw, copied]) {
    expect(output).not.toContain('Confidential-Acquisition.pdf'); expect(output).not.toContain('FullFlowSecretCanary');
    expect(output).toContain('KeepLateRestrictionCanary'); expect(output).toContain('[ROLE INSTRUCTIONS: reviewer]');
  }
  expect(JSON.parse(raw).context.design.preset).toBe('bento');
  const events = await page.evaluate(() => VASPersonalization.list());
  expect(events).toHaveLength(1); expect(events[0].type).toBe('theme_selected'); expect(events[0].payload.preset).toBe('bento');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  if (process.env.VAS_PROOF_DIR) await page.screenshot({ path: path.join(process.env.VAS_PROOF_DIR, 'connected-' + width + '.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('server rejects old knowledge indexes and compatibility ZIP strips credential content', async ({ page }) => {
  const project = path.join(runtimeRoot, 'workspace/projects/demo'), registry = path.join(runtimeRoot, 'workspace/.vas');
  fs.mkdirSync(project, { recursive: true }); fs.mkdirSync(registry, { recursive: true });
  fs.writeFileSync(path.join(registry, 'projects.json'), JSON.stringify({ version: 2, projects: [{ projectId: 'synthetic', path: project, name: 'demo', sourceType: 'new', goal: 'manage', stage: 'ready', createIndex: true }] }));
  fs.writeFileSync(path.join(project, 'rag-context.json'), '{"request":"Preserve React","password":"LegacyPasswordCanary"}');
  fs.writeFileSync(path.join(project, 'design-tokens.json'), '{"colors":{"primary":"#123abc"},"AWS_SECRET_ACCESS_KEY":"LegacyAwsCanary"}');
  fs.writeFileSync(path.join(registry, 'project-knowledge.json'), JSON.stringify({ schema: 1, entries: [{ projectId: 'synthetic', text: '[redacted] OldTrailingSecretCanary' }] }));
  await open(page);
  const old = await page.evaluate(() => VASRuntime.request('/api/knowledge/projects?projectId=synthetic'));
  expect(old.entries).toEqual([]); expect(old.warning).toBe('knowledge_rebuild_required');
  const response = await fetch(base + '/api/projects/export', { method: 'POST', headers: { Origin: base, 'X-VAS-Token': token, 'Content-Type': 'application/json' }, body: '{"projectId":"synthetic"}' });
  expect(response.status).toBe(200);
  const zip = path.join(directory, 'safe-handoff.zip'); fs.writeFileSync(zip, Buffer.from(await response.arrayBuffer()));
  const verify = spawnSync('python', ['-c', 'import zipfile,json,sys; z=zipfile.ZipFile(sys.argv[1]); raw=b"\\n".join(z.read(n) for n in z.namelist()); assert b"LegacyPasswordCanary" not in raw and b"LegacyAwsCanary" not in raw and b"OldTrailingSecretCanary" not in raw; assert b"#123abc" in raw and b"Preserve React" in raw', zip], { windowsHide: true });
  expect(verify.status).toBe(0);
});

