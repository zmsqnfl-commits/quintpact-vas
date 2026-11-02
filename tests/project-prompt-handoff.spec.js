const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const http = require('http');

const source = path.resolve(__dirname, '../ui');
let server, base;
test.beforeAll(async () => {
  server = http.createServer((req, res) => {
    const file = path.join(source, path.basename(new URL(req.url, 'http://localhost').pathname));
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
    const type = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' }[path.extname(file)] || 'application/octet-stream';
    res.setHeader('Content-Type', type + '; charset=utf-8');
    res.end(fs.readFileSync(file));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = 'http://127.0.0.1:' + server.address().port;
});
test.afterAll(() => new Promise(resolve => server.close(resolve)));

function gate() { let release; const waiting = new Promise(resolve => { release = resolve; }); return { waiting, release }; }
async function setup(page, options = {}) {
  const state = { current: options.current || { revision: 1, prompt: 'ROOT ONLY saved instructions' }, reads: 0 };
  await page.addInitScript(() => {
    window.copiedPrompt = '';
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async value => { window.copiedPrompt = value; } } });
  });
  await page.route('**/api/**', async route => {
    const endpoint = new URL(route.request().url()).pathname;
    if (endpoint === '/api/status') {
      if (options.status) await options.status.waiting;
      return route.fulfill({ json: { layout: 'project' } });
    }
    if (endpoint === '/api/project-prompt') {
      state.reads++;
      if (options.onRead) await options.onRead(state.reads);
      return route.fulfill({ json: state.current });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto(base + '/project-import.html?vasToken=' + 'x'.repeat(32));
  await page.locator('#projectName').fill('Inventory app');
  await page.locator('#taskRequest').fill('Show the inventory total.');
  return state;
}

test('editing an external target while initial layout is pending cannot inherit the root prompt', async ({ page }) => {
  const status = gate();
  const state = await setup(page, { status });
  await page.locator('#continueSettings').click();
  await page.locator('#folderPath').fill('C:\\OtherProject');
  const response = page.waitForResponse('**/api/status');
  status.release();
  await response;
  await expect(page.locator('#folderPath')).not.toHaveAttribute('required', '');
  await expect(page.locator('[data-step="1"]')).toHaveClass(/active/);
  await expect(page.locator('#previewStatus')).toContainText('다시 준비');
  expect(state.reads).toBe(0);
  await page.locator('#continueSettings').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await expect(page.locator('#previewContent')).toContainText('C:\\OtherProject');
  await expect(page.locator('#previewContent')).not.toContainText('ROOT ONLY');
  await page.locator('#copyPrompt').click();
  await expect.poll(() => page.evaluate(() => window.copiedPrompt)).toContain('C:\\OtherProject');
  expect(await page.evaluate(() => window.copiedPrompt)).not.toContain('ROOT ONLY');
  const portable = await page.evaluate(() => ({ copied: window.copiedPrompt, roles: VASAgentResources.portableRoles }));
  for (const [role, instructions] of Object.entries(portable.roles)) {
    expect(portable.copied).toContain('[ROLE INSTRUCTIONS: ' + role + ']\n' + instructions);
  }
  expect(portable.copied).not.toMatch(/scripts\/|\.agents\/|ui\/|모두 최상위 src\//);
  expect(state.reads).toBe(0);
});

test('copy and JSON re-read newer canonical saved instructions after an older preview', async ({ page }) => {
  const state = await setup(page);
  await page.locator('#continueSettings').click();
  await expect(page.locator('#previewContent')).toContainText('ROOT ONLY');
  const latest = '합계 표시\n\n  들여쓰기 유지\n' + '🟢'.repeat(1200);
  state.current = { revision: 2, prompt: latest };
  await page.locator('#copyPrompt').click();
  await expect.poll(() => page.evaluate(() => window.copiedPrompt)).toContain(latest);
  await expect(page.locator('#previewContent')).toContainText('revision 2');
  const pending = page.waitForEvent('download');
  await page.locator('#downloadAgain').click();
  const document = JSON.parse(fs.readFileSync(await (await pending).path(), 'utf8'));
  expect(document.context.projectPrompt).toEqual(state.current);
  expect(document.assistantGuide.pasteText).toContain(latest);
  expect(document.assistantGuide.pasteText).not.toContain('ROOT ONLY');
});

test('a first save after the absent-file snapshot blocks an older copy', async ({ page }) => {
  const finalRead = gate(), reached = gate();
  const state = await setup(page, {
    current: { revision: 0, prompt: '' },
    onRead: async count => { if (count === 5) { reached.release(); await finalRead.waiting; } }
  });
  await page.locator('#continueSettings').click();
  await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  await page.locator('#copyPrompt').click();
  await reached.waiting;
  state.current = { revision: 1, prompt: 'NEW first saved instruction' };
  finalRead.release();
  await expect(page.locator('#errorBox')).toContainText('프로젝트 지시가 변경됐습니다');
  expect(await page.evaluate(() => window.copiedPrompt)).toBe('');
  await page.locator('#copyPrompt').click();
  await expect.poll(() => page.evaluate(() => window.copiedPrompt)).toContain('NEW first saved instruction');
});

for (const action of ['copyPrompt', 'downloadJson']) {
  test('form edits during the final saved-prompt read abort ' + action, async ({ page }) => {
    const finalRead = gate(), reached = gate();
    let downloads = 0;
    page.on('download', () => { downloads++; });
    await setup(page, { onRead: async count => { if (count === 5) { reached.release(); await finalRead.waiting; } } });
    await page.locator('#continueSettings').click();
    await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
    await page.locator('#' + action).click();
    await reached.waiting;
    await page.locator('#provider').selectOption('claude');
    finalRead.release();
    await expect(page.locator('#errorBox')).toContainText('내용이 변경되었습니다');
    expect(await page.evaluate(() => window.copiedPrompt)).toBe('');
    expect(downloads).toBe(0);
  });
}

test('the open project keeps the app and its VAS workflow together even before the first saved prompt', async ({ page }) => {
  await setup(page, { current: { revision: 0, prompt: '' } });
  await page.locator('#continueSettings').click();
  await page.locator('#copyPrompt').click();
  await expect.poll(() => page.evaluate(() => window.copiedPrompt)).toContain('프로젝트 폴더 전체');
  const copied = await page.evaluate(() => window.copiedPrompt);
  for (const text of ['프로젝트 폴더 전체', '최상위 src/', 'ui/', 'python -B scripts/vas.py start', 'prepared', 'python -B scripts/vas.py finish', '재조회']) {
    expect(copied).toContain(text);
  }
  expect(copied).not.toContain('.vas/');
});
