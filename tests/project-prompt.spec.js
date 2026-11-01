const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const http = require('http');

const source = path.resolve(__dirname, '../src');
let server, base;
test.beforeAll(async () => {
  server = http.createServer((req, res) => {
    const name = path.basename(new URL(req.url, 'http://localhost').pathname);
    const file = path.join(source, name);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
    const type = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' }[path.extname(file)] || 'application/octet-stream';
    res.setHeader('Content-Type', type + '; charset=utf-8');
    res.end(fs.readFileSync(file));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = 'http://127.0.0.1:' + server.address().port;
});
test.afterAll(() => new Promise(resolve => server.close(resolve)));

async function fixture(context, layout = 'project') {
  const state = { current: { revision: 0, prompt: '' }, puts: 0, failSave: false, failRead: false };
  await context.route('**/api/**', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname === '/api/status') return route.fulfill({ json: { layout } });
    if (url.pathname !== '/api/project-prompt') return route.fulfill({ json: {} });
    if (req.method() === 'GET') {
      if (state.failRead) return route.fulfill({ status: 503, json: { code: 'project_prompt_unavailable', error: '저장본 조회 실패' } });
      return route.fulfill({ json: state.current });
    }
    state.puts++;
    if (state.failSave) return route.fulfill({ status: 503, json: { code: 'project_prompt_unavailable', error: '저장 실패 · 초안 유지' } });
    const value = req.postDataJSON();
    if (value.expectedRevision !== state.current.revision) return route.fulfill({
      status: 409, json: { code: 'project_prompt_conflict', error: '다른 탭에서 변경했습니다.' }
    });
    state.current = { revision: state.current.revision + 1, prompt: value.prompt };
    return route.fulfill({ json: state.current });
  });
  return state;
}
async function open(page) {
  await page.goto(base + '/vas-hub.html?vasToken=' + 'x'.repeat(32));
  await expect(page.locator('#projectPromptText')).toBeEnabled();
}

test('saved prompt preview comes from readback; literal input and explicit clearing work', async ({ context, page }) => {
  const state = await fixture(context);
  await open(page);
  const value = '<img src=x onerror=alert(1)> 결제 없이 재고만';
  await page.locator('#projectPromptText').fill(value);
  await expect(page.locator('#projectPromptStatus')).toContainText('아직 저장하지');
  await expect(page.locator('#projectPromptSaved')).not.toContainText(value);
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptStatus')).toContainText('저장했습니다');
  await expect(page.locator('#projectPromptSaved')).toHaveText(value);
  await expect(page.locator('#projectPromptSaved img')).toHaveCount(0);
  expect(state.current).toEqual({ revision: 1, prompt: value });
  await page.reload();
  await expect(page.locator('#projectPromptText')).toHaveValue(value);
  await page.locator('#projectPromptText').fill('');
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptStatus')).toHaveText('작업 지시를 비웠습니다.');
  expect(state.current).toEqual({ revision: 2, prompt: '' });
});

test('a stale tab preserves its draft and cannot silently replace the newer prompt', async ({ context, page }) => {
  const state = await fixture(context);
  await open(page);
  await page.locator('#projectPromptText').fill('첫 화면의 편집');
  const other = await context.newPage();
  await open(other);
  await other.locator('#projectPromptText').fill('다른 화면에서 먼저 저장');
  await other.locator('#projectPromptSave').click();
  await expect(other.locator('#projectPromptStatus')).toContainText('저장했습니다');
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptRebase')).toBeVisible();
  await expect(page.locator('#projectPromptText')).toHaveValue('첫 화면의 편집');
  await expect(page.locator('#projectPromptSaved')).toHaveText('다른 화면에서 먼저 저장');
  expect(state.current.prompt).toBe('다른 화면에서 먼저 저장');
  await page.locator('#projectPromptRebase').click();
  await page.locator('#projectPromptText').fill('두 화면의 요청을 비교한 새 지시');
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptStatus')).toContainText('저장했습니다');
  expect(state.current).toEqual({ revision: 2, prompt: '두 화면의 요청을 비교한 새 지시' });
});

test('failed saves and failed readback keep the draft without claiming verified save', async ({ context, page }) => {
  const state = await fixture(context);
  await open(page);
  await page.locator('#projectPromptText').fill('소수점 없이 표시');
  state.failSave = true;
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptStatus')).toContainText('저장 실패');
  await expect(page.locator('#projectPromptText')).toHaveValue('소수점 없이 표시');
  expect(state.current.revision).toBe(0);
  state.failSave = false; state.failRead = true;
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptStatus')).toContainText('최신 저장본을 확인하지 못했습니다');
  await expect(page.locator('#projectPromptText')).toHaveValue('소수점 없이 표시');
  await expect(page.locator('#projectPromptSave')).toBeDisabled();
  state.failRead = false;
  await page.locator('#projectPromptReload').click();
  await expect(page.locator('#projectPromptStatus')).toHaveText('최신 저장본을 불러왔습니다.');
  await expect(page.locator('#projectPromptSaved')).toHaveText('소수점 없이 표시');
});

test('the editor stays hidden on a tool installation and fits a narrow project screen', async ({ context, page }) => {
  await fixture(context, 'tool');
  await page.goto(base + '/vas-hub.html?vasToken=' + 'x'.repeat(32));
  await expect(page.locator('#projectPromptPanel')).toBeHidden();
  await context.unroute('**/api/**');
  await fixture(context);
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  await page.locator('#projectPromptText').fill('모바일에서도 내용을 읽고 저장할 수 있어야 합니다.');
  await page.locator('#projectPromptSave').click();
  await expect(page.locator('#projectPromptStatus')).toContainText('저장했습니다');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
