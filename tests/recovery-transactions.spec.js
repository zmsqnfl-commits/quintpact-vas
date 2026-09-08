const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const source = name => pathToFileURL(path.join(__dirname, '..', 'src', name)).href;

for (const replace of [false, true]) for (const failure of ['quota', 'abort']) {
  test(`memory ${replace ? 'replace' : 'merge'} rolls back ${failure} and retries intact`, async ({ page }) => {
    await page.goto(source('memory-center.html'));
    const result = await page.evaluate(async ({ replace, failure }) => {
      const api = VASPersonalization;
      const item = (id, preset) => ({ id, type: 'theme_selected', timestamp: '2026-09-09T00:00:00Z', payload: { preset } });
      await api.consent(true); await api.clear();
      await api.import({ schema: 1, events: [item('original', 'bento'), item('retained', 'botanical')] });
      const before = await api.export();
      const original = IDBObjectStore.prototype.put;
      const incoming = { schema: 1, events: [item('original', 'linear'), item('second', 'noir')] };
      let attempts = 0, error = null;
      const changes = [];
      addEventListener('vas-memory-change', event => changes.push(event.detail.action));
      IDBObjectStore.prototype.put = function (...args) {
        if (this.name === 'events' && ++attempts === 2) {
          if (failure === 'quota') throw new DOMException('Synthetic quota failure', 'QuotaExceededError');
          this.transaction.abort(); return {};
        }
        return original.apply(this, args);
      };
      try { await api.import(incoming, { replace }); } catch (caught) { error = caught.name; }
      finally { IDBObjectStore.prototype.put = original; }
      const after = await api.export(), failedChanges = changes.slice();
      const imported = await api.import(incoming, { replace });
      return { error, before: JSON.parse(before).events, after: JSON.parse(after).events, failedChanges, imported, rows: await api.list(), changes };
    }, { replace, failure });
    expect(result.error).toBeTruthy();
    expect(result.after).toEqual(result.before);
    expect(result.failedChanges).toEqual([]);
    expect(result.imported).toBe(2);
    expect(result.rows).toHaveLength(replace ? 2 : 3);
    expect(result.rows.find(row => row.id === 'original').payload.preset).toBe('linear');
    expect(result.rows.find(row => row.id === 'second').payload.preset).toBe('noir');
    expect(result.changes).toEqual(['import']);
  });
}

test('failed file import leaves the same file selectable for a successful retry', async ({ page }) => {
  await page.goto(source('memory-center.html'));
  await page.evaluate(async () => {
    await VASPersonalization.consent(true);
    window.realPut = IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put = function (...args) {
      if (this.name === 'events') throw new DOMException('Synthetic quota', 'QuotaExceededError');
      return realPut.apply(this, args);
    };
  });
  const file = { name: 'memory.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify({ schema: 1, events: [{ id: 'retry', type: 'theme_selected', payload: { preset: 'bento' } }] })) };
  await page.locator('#importMemory').setInputFiles(file);
  await expect(page.locator('#memoryFeedback')).toContainText('확인하지 못했습니다');
  await expect(page.locator('#importMemory')).toHaveValue('');
  await expect(page.locator('#importMemory')).toBeEnabled();
  await page.evaluate(() => { IDBObjectStore.prototype.put = realPut; });
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#importMemory').setInputFiles(file);
  await expect(page.locator('#eventCount')).toHaveText('1');
  await expect(page.locator('#importMemory')).toHaveValue('');
});

async function savedDraft(page) {
  await page.goto(source('client-application.html'));
  await page.locator('[name="problem_desc"]').fill('Synthetic recovery control');
  await page.evaluate(() => VASClientDraft.save());
  await page.reload();
  await expect(page.locator('#draftNotice')).toBeVisible();
}

test('failed draft deletion stays visible and can be retried', async ({ page }) => {
  await savedDraft(page);
  await page.evaluate(() => {
    window.realRemove = Storage.prototype.removeItem;
    Storage.prototype.removeItem = function () { throw new DOMException('Synthetic denied', 'SecurityError'); };
  });
  await page.locator('#draftNotice').getByRole('button', { name: '삭제', exact: true }).click();
  await expect(page.locator('#draftFeedback')).toContainText('삭제하지 못했습니다');
  await expect(page.locator('#draftNotice')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('vasClientDraft.v1.internal'))).toContain('Synthetic recovery control');
  await page.evaluate(() => { Storage.prototype.removeItem = realRemove; });
  await page.locator('#draftNotice').getByRole('button', { name: '삭제', exact: true }).click();
  await expect(page.locator('#draftNotice')).toBeHidden();
  expect(await page.evaluate(() => localStorage.getItem('vasClientDraft.v1.internal'))).toBeNull();
});

test('failed autosave policy change retains the persisted setting and explains failure', async ({ page }) => {
  await savedDraft(page);
  await page.clock.install();
  await page.evaluate(() => {
    window.realSet = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith('vasClientDraftEnabled')) throw new DOMException('Synthetic denied', 'SecurityError');
      return realSet.call(this, key, value);
    };
    document.querySelector('[name="problem_desc"]').dispatchEvent(new Event('input', { bubbles: true }));
    VASClientDraft.toggle();
  });
  await page.clock.runFor(250);
  await expect(page.locator('#draftPolicyText')).toContainText('자동 저장됩니다');
  await expect(page.locator('#draftFeedback')).toContainText('설정을 변경하지 못했습니다');
  await page.evaluate(() => { Storage.prototype.setItem = realSet; VASClientDraft.toggle(); });
  await expect(page.locator('#draftPolicyText')).toContainText('꺼져 있습니다');
  await expect(page.locator('#draftFeedback')).toBeHidden();
  await page.reload();
  await expect(page.locator('#draftPolicyText')).toContainText('꺼져 있습니다');
});

test('JSON download remains successful while draft cleanup failure is disclosed', async ({ page }) => {
  await savedDraft(page);
  await page.evaluate(() => {
    VASClientDraft.restore();
    Storage.prototype.removeItem = function () { throw new DOMException('Synthetic denied', 'SecurityError'); };
  });
  const downloadPromise = page.waitForEvent('download');
  await page.evaluate(() => exportJson());
  const download = await downloadPromise;
  expect(JSON.parse(fs.readFileSync(await download.path(), 'utf8')).task.request).toContain('Synthetic recovery control');
  expect(await page.locator('#handoffStatus').textContent()).toContain('JSON을 저장했습니다');
  expect(await page.locator('#handoffStatus').textContent()).toContain('초안은 삭제하지 못했습니다');
  expect(await page.evaluate(() => localStorage.getItem('vasClientDraft.v1.internal'))).toContain('Synthetic recovery control');
});
