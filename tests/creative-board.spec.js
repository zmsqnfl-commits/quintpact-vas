const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '..');
const appUrl = pathToFileURL(path.join(root, 'src/proof-app/index.html')).href;
const storageKey = 'morrow.board.v1';
const rows = page => page.locator('#task-list [data-task-id]');
const rowNamed = (page, name) => rows(page).filter({ has: page.getByRole('button', { name, exact: true }) });
const persisted = page => page.evaluate(key => JSON.parse(localStorage.getItem(key)), storageKey);
const stable = value => Array.isArray(value) ? '[' + value.map(stable).join(',') + ']'
  : value && typeof value === 'object' ? '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + stable(value[key])).join(',') + '}'
    : JSON.stringify(value);

async function seed(page, tasks) {
  await page.addInitScript(({ key, tasks }) => {
    if (!sessionStorage.getItem('proof-seeded')) {
      localStorage.setItem(key, JSON.stringify({ version: 1, tasks }));
      sessionStorage.setItem('proof-seeded', 'yes');
    }
  }, { key: storageKey, tasks });
}

function task(id, title, overrides = {}) {
  return { id, title, note: '', category: 'web', status: 'todo', dueDate: '', archived: false,
    sample: false, createdAt: '2026-09-07T00:00:00.000Z', updatedAt: '2026-09-07T00:00:00.000Z', ...overrides };
}

async function create(page, title, note = '') {
  await page.getByRole('button', { name: '새 작업', exact: true }).first().click();
  await page.getByLabel('제목', { exact: true }).fill(title);
  await page.getByLabel('메모', { exact: true }).fill(note);
  await page.getByRole('button', { name: '작업 추가', exact: true }).click();
  await expect(page.locator('#task-dialog')).not.toBeVisible();
}

test('real exported VAS handoff retains the exact request, full roles and verified payload hash', async () => {
  const folder = path.join(root, 'docs/verification');
  const handoff = JSON.parse(fs.readFileSync(path.join(folder, 'creative-board-handoff.json'), 'utf8'));
  const request = JSON.parse(fs.readFileSync(path.join(folder, 'creative-board-request.json'), 'utf8'));
  expect(handoff.task.request).toBe(request.problem_desc);
  expect(handoff.context.design.preset).toBe('bento');
  for (const role of ['designer', 'implementer', 'reviewer']) {
    const body = fs.readFileSync(path.join(root, '.agents/skills', role, 'SKILL.md'), 'utf8')
      .replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '').trim().replace(/\r\n/g, '\n');
    expect(handoff.assistantGuide.pasteText).toContain(body);
  }
  expect(fs.readFileSync(path.join(folder, 'creative-board-handoff.txt'), 'utf8').replace(/\r\n/g, '\n').trim()).toBe(handoff.assistantGuide.pasteText);
  const payload = structuredClone(handoff);
  delete payload.integrity;
  payload.assistantGuide.pasteText = '';
  expect(crypto.createHash('sha256').update(stable(payload)).digest('hex')).toBe(handoff.integrity.payloadSha256);
});

test('task create, edit, completion and reload persist without altering VAS settings', async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('vas-sentinel')) {
      localStorage.setItem('vasCurrentPreset', 'bento');
      localStorage.setItem('vasFavorites', '["stripe"]');
      sessionStorage.setItem('vas-sentinel', 'yes');
    }
  });
  await page.goto(appUrl);
  await expect(rows(page)).toHaveCount(4);
  await expect(page.getByText('예시 작업이 포함되어 있어요. 직접 수정하거나 지워보세요.')).toBeVisible();
  await create(page, '새 랜딩 페이지', '첫 화면 카피');
  await rowNamed(page, '새 랜딩 페이지').getByRole('button', { name: '새 랜딩 페이지', exact: true }).click();
  await page.getByLabel('제목', { exact: true }).fill('런칭 페이지');
  await page.getByLabel('메모', { exact: true }).fill('수정한 카피');
  await page.locator('#task-category').selectOption('content');
  await page.locator('#task-status').selectOption('doing');
  await page.locator('#task-due').fill('2026-12-31');
  await page.getByRole('button', { name: '변경 저장', exact: true }).click();
  await expect(rowNamed(page, '런칭 페이지')).toContainText('진행 중');
  await rowNamed(page, '런칭 페이지').getByRole('checkbox').check();
  await page.reload();
  await expect(rowNamed(page, '런칭 페이지').getByRole('checkbox')).toBeChecked();
  const data = await persisted(page);
  expect(data.tasks.find(item => item.title === '런칭 페이지')).toMatchObject({ note: '수정한 카피', category: 'content', status: 'done', dueDate: '2026-12-31', sample: false });
  expect(await page.evaluate(() => ({ preset: localStorage.getItem('vasCurrentPreset'), favorites: localStorage.getItem('vasFavorites') })))
    .toEqual({ preset: 'bento', favorites: '["stripe"]' });
});

test('search matches notes and combines status/category filters with a usable reset', async ({ page }) => {
  await seed(page, [task('a', '브랜드 작업', { note: '마포 스튜디오', category: 'branding', status: 'doing' }),
    task('b', '웹 작업', { note: '마포 스튜디오', status: 'doing' }), task('c', '다른 작업')]);
  await page.goto(appUrl);
  await page.locator('#search').fill('마포');
  await expect(rows(page)).toHaveCount(2);
  await page.locator('#category-filter').selectOption('branding');
  await page.locator('[data-status-filter="doing"]').click();
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page)).toContainText('브랜드 작업');
  await page.locator('[data-status-filter="done"]').click();
  await expect(rows(page)).toHaveCount(0);
  await expect(page.getByText('조건에 맞는 작업이 없어요.')).toBeVisible();
  await page.getByRole('button', { name: '필터 초기화', exact: true }).click();
  await expect(rows(page)).toHaveCount(3);
});

test('archive, restore, delete and undo change real tasks; empty storage stays empty after reload', async ({ page }) => {
  await seed(page, [task('only', '실제 한 개 작업', { note: '복원할 메모' })]);
  await page.goto(appUrl);
  await rowNamed(page, '실제 한 개 작업').getByRole('button', { name: '실제 한 개 작업', exact: true }).click();
  await page.getByRole('button', { name: '보관', exact: true }).click();
  await expect(rows(page)).toHaveCount(0);
  await page.locator('[data-view="archive"]').click();
  await rowNamed(page, '실제 한 개 작업').getByRole('button', { name: '실제 한 개 작업', exact: true }).click();
  await page.getByRole('button', { name: '복원', exact: true }).click();
  await page.locator('[data-view="board"]').click();
  const before = (await persisted(page)).tasks[0];
  await rowNamed(page, '실제 한 개 작업').getByRole('button', { name: '실제 한 개 작업', exact: true }).click();
  await page.getByRole('button', { name: '삭제', exact: true }).click();
  await expect(rows(page)).toHaveCount(0);
  await page.getByRole('button', { name: '실행 취소', exact: true }).click();
  expect((await persisted(page)).tasks[0]).toEqual(before);
  await rowNamed(page, '실제 한 개 작업').getByRole('button', { name: '실제 한 개 작업', exact: true }).click();
  await page.getByRole('button', { name: '삭제', exact: true }).click();
  await page.reload();
  await expect(rows(page)).toHaveCount(0);
  await expect(page.getByText('첫 작업을 적어보세요.')).toBeVisible();
  expect((await persisted(page)).tasks).toEqual([]);
});

test('dialog validates blank input, contains keyboard focus and cancels draft changes', async ({ page }) => {
  await page.goto(appUrl);
  const trigger = page.getByRole('button', { name: '새 작업', exact: true }).first();
  await trigger.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('제목', { exact: true })).toBeFocused();
  await page.getByLabel('제목', { exact: true }).fill('   ');
  await page.getByRole('button', { name: '작업 추가', exact: true }).click();
  await expect(page.getByText('제목을 입력해 주세요.')).toBeVisible();
  await expect(page.getByLabel('제목', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  for (let index = 0; index < 15; index += 1) {
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => Boolean(document.activeElement.closest('dialog')))).toBe(true);
  }
  await page.keyboard.press('Escape');
  await expect(page.locator('#task-dialog')).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await expect(rows(page)).toHaveCount(4);
});

test('user HTML remains literal and JSON export contains the actual current records', async ({ page }) => {
  await seed(page, []);
  await page.goto(appUrl);
  const unsafe = '<img src=x onerror="alert(1)">';
  const dialogs = [];
  page.on('dialog', async dialog => { dialogs.push(dialog.message()); await dialog.dismiss(); });
  await create(page, unsafe, '<script>alert(2)</script>');
  await expect(rowNamed(page, unsafe)).toHaveCount(1);
  await expect(page.locator('#task-list img, #task-list script')).toHaveCount(0);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'JSON 내보내기', exact: true }).click();
  const download = await downloadPromise;
  const data = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
  expect(data.version).toBe(1);
  expect(data.tasks).toEqual((await persisted(page)).tasks);
  expect(data.tasks[0]).toMatchObject({ title: unsafe, note: '<script>alert(2)</script>' });
  expect(dialogs).toEqual([]);
});

test('a 5001st saved task remains readable after reload', async ({ page }) => {
  await seed(page, Array.from({ length: 5000 }, (_, index) => task('task-' + index, '보존할 작업 ' + index)));
  await page.goto(appUrl);
  await expect(rows(page)).toHaveCount(5000);
  await create(page, '5001번째 작업');
  expect((await persisted(page)).tasks).toHaveLength(5001);
  await page.reload();
  await expect(rows(page)).toHaveCount(5001);
  await expect(rowNamed(page, '5001번째 작업')).toHaveCount(1);
  await expect(page.locator('#storage-status')).toHaveText('변경 사항은 자동으로 저장돼요.');
});

for (const invalid of ['{broken-json', JSON.stringify({ version: 99, tasks: [] }), JSON.stringify({ version: 1, tasks: [{ id: 'bad' }] })]) {
  test('invalid saved data is disclosed and preserved: ' + invalid.slice(0, 24), async ({ page }) => {
    await page.addInitScript(({ key, invalid }) => { localStorage.setItem(key, invalid); }, { key: storageKey, invalid });
    await page.goto(appUrl);
    await expect(rows(page)).toHaveCount(0);
    await expect(page.getByText(/저장.*(?:읽|손상|확인)|데이터.*(?:읽|손상|확인)/).first()).toBeVisible();
    expect(await page.evaluate(key => localStorage.getItem(key), storageKey)).toBe(invalid);
  });
}

for (const failure of ['read', 'write']) {
  test('storage ' + failure + ' denial keeps edits exportable and never claims saved', async ({ page }) => {
    await page.addInitScript(({ key, failure }) => {
      const method = failure === 'read' ? 'getItem' : 'setItem';
      const original = Storage.prototype[method];
      Storage.prototype[method] = function (name, ...args) {
        if (name === key) throw new DOMException('Test storage denial', failure === 'read' ? 'SecurityError' : 'QuotaExceededError');
        return original.call(this, name, ...args);
      };
    }, { key: storageKey, failure });
    await page.goto(appUrl);
    await create(page, '저장 실패에도 유지할 작업');
    await expect(rowNamed(page, '저장 실패에도 유지할 작업')).toHaveCount(1);
    await expect(page.getByText('브라우저에 저장하지 못했어요. JSON으로 보관해 주세요.')).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'JSON 내보내기', exact: true }).click();
    const download = await downloadPromise;
    const data = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    expect(data.tasks.some(item => item.title === '저장 실패에도 유지할 작업')).toBe(true);
  });
}

for (const width of [1440, 768, 390, 320]) {
  test('rendered board and form fit ' + width + 'px and load only local assets', async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [], remote = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('requestfailed', request => errors.push(request.url()));
    page.on('request', request => { if (/^https?:/.test(request.url())) remote.push(request.url()); });
    await page.goto(appUrl);
    await expect(page).toHaveTitle(/Morrow/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('좋은 생각을,');
    await page.evaluate(async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, image => image.decode())); });
    const tokens = await page.evaluate(() => ({ background: getComputedStyle(document.body).backgroundColor,
      hero: getComputedStyle(document.querySelector('h1')).fontSize,
      font: getComputedStyle(document.body).fontFamily,
      overflow: document.documentElement.scrollWidth > innerWidth + 1 }));
    expect(tokens.background).toBe('rgb(233, 223, 245)');
    expect(tokens.font).toContain('Bricolage Grotesque');
    if (width === 1440) expect(tokens.hero).toBe('56px');
    expect(tokens.overflow).toBe(false);
    await page.screenshot({ path: info.outputPath('morrow-' + width + '.png'), fullPage: true });
    await page.getByRole('button', { name: '새 작업', exact: true }).first().click();
    await page.getByLabel('제목', { exact: true }).fill('반응형에서 긴 제목도 정상 표시됩니다 '.repeat(3));
    const dialog = page.locator('#task-dialog');
    expect(await dialog.evaluate(element => element.scrollWidth > element.clientWidth + 1)).toBe(false);
    const box = await dialog.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
    await page.getByRole('button', { name: '작업 추가', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('morrow-dialog-' + width + '.png'), fullPage: true });
    await page.getByRole('button', { name: '작업 추가', exact: true }).click();
    await expect(rows(page)).toHaveCount(5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
    expect(errors).toEqual([]);
    expect(remote).toEqual([]);
  });
}
