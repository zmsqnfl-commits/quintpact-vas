const { test, expect } = require('@playwright/test');
const path = require('path');
const { pathToFileURL } = require('url');

const clientUrl = pathToFileURL(path.join(__dirname, '..', 'src', 'client-application.html')).href;
const key = 'vasClientDraft.v1.internal';
const enabledKey = 'vasClientDraftEnabled.v1.internal';
const originalDraft = {
  v: 1, savedAt: '2026-10-01T00:00:00.000Z', step: 1, language: 'ko',
  fields: { project_name: 'Synthetic recovery draft', problem_desc: 'Original synthetic request' }
};

async function openPending(page) {
  await page.addInitScript(({ key, enabledKey, originalDraft }) => {
    if (sessionStorage.getItem('draft-recovery-fixture')) return;
    localStorage.setItem(key, JSON.stringify(originalDraft));
    localStorage.setItem(enabledKey, '1');
    sessionStorage.setItem('draft-recovery-fixture', '1');
  }, { key, enabledKey, originalDraft });
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#draftNotice')).toBeVisible();
  return readRaw(page);
}

const readRaw = page => page.evaluate(key => localStorage.getItem(key), key);
const readDraft = async page => JSON.parse(await readRaw(page));

test('saved draft survives reopening and closing without a recovery choice', async ({ page, context }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#projectName').fill(originalDraft.fields.project_name);
  await page.locator('#problemDescription').fill(originalDraft.fields.problem_desc);
  await page.evaluate(() => VASClientDraft.save());
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#draftNotice')).toBeVisible();
  await expect(page.locator('#projectName')).toHaveValue('');
  const before = await readRaw(page);
  await page.close();
  const reopened = await context.newPage();
  await reopened.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await expect(reopened.locator('#draftNotice')).toBeVisible();
  expect(await readRaw(reopened)).toBe(before);
  await reopened.reload({ waitUntil: 'domcontentloaded' });
  expect(await readRaw(reopened)).toBe(before);
});

test('inputs, direct saves and navigation saves cannot unlock a pending recovery', async ({ page }) => {
  const before = await openPending(page);
  await page.locator('#projectName').fill('New unconfirmed input');
  await page.locator('#problemDescription').fill('New unconfirmed request');
  await page.evaluate(() => {
    VASClientDraft.save();
    setLang('en');
    window.dispatchEvent(new Event('beforeunload'));
  });
  await page.waitForTimeout(300);
  expect(await readRaw(page)).toBe(before);
  await expect(page.locator('#draftNotice')).toBeVisible();
});

test('successful restore unlocks subsequent edits and autosave', async ({ page }) => {
  const before = await openPending(page);
  await page.locator('#draftNotice').getByRole('button', { name: '복원', exact: true }).click();
  await expect(page.locator('#draftNotice')).toBeHidden();
  await expect(page.locator('#projectName')).toHaveValue(originalDraft.fields.project_name);
  expect(await readRaw(page)).toBe(before);
  await page.locator('#projectName').fill('Edited restored draft');
  await expect.poll(async () => (await readDraft(page)).fields.project_name).toBe('Edited restored draft');
  expect((await readDraft(page)).fields.problem_desc).toBe(originalDraft.fields.problem_desc);
});

test('failed restore does not permit replacing the recoverable draft', async ({ page }) => {
  const before = await openPending(page);
  const failure = await page.evaluate(() => {
    const setLanguage = window.setLang;
    window.setLang = () => { throw new Error('Synthetic restore failure'); };
    try { VASClientDraft.restore(); } catch (error) { return error.message; }
    finally { window.setLang = setLanguage; }
  });
  expect(failure).toBe('Synthetic restore failure');
  await page.locator('#projectName').fill('Edit after restore failure');
  await page.evaluate(() => VASClientDraft.save());
  await page.waitForTimeout(300);
  expect(await readRaw(page)).toBe(before);
  await expect(page.locator('#draftNotice')).toBeVisible();
  await page.locator('#draftNotice').getByRole('button', { name: '복원', exact: true }).click();
  await expect(page.locator('#projectName')).toHaveValue(originalDraft.fields.project_name);
});

test('successful discard allows a new draft while failed deletion preserves the old one', async ({ page }) => {
  const before = await openPending(page);
  await page.evaluate(key => {
    const remove = Storage.prototype.removeItem;
    Storage.prototype.removeItem = function (name) {
      if (name === key) throw new Error('Synthetic deletion failure');
      return remove.call(this, name);
    };
    window.restoreDraftRemoval = () => { Storage.prototype.removeItem = remove; };
  }, key);
  await page.locator('#draftNotice').getByRole('button', { name: '삭제', exact: true }).click();
  await expect(page.locator('#draftFeedback')).toContainText('초안을 삭제하지 못했습니다');
  await expect(page.locator('#draftNotice')).toBeVisible();
  await page.locator('#projectName').fill('New input after failed deletion');
  await page.evaluate(() => {
    VASClientDraft.save();
    window.dispatchEvent(new Event('beforeunload'));
  });
  await page.waitForTimeout(300);
  expect(await readRaw(page)).toBe(before);
  await page.evaluate(() => window.restoreDraftRemoval());
  await page.locator('#draftNotice').getByRole('button', { name: '삭제', exact: true }).click();
  expect(await readRaw(page)).toBeNull();
  await expect(page.locator('#draftNotice')).toBeHidden();
  await page.locator('#projectName').fill('New draft after successful discard');
  await expect.poll(async () => (await readDraft(page))?.fields.project_name).toBe('New draft after successful discard');
});

test('a previously scheduled save is canceled and remains blocked even if its callback runs', async ({ page }) => {
  await page.goto(clientUrl, { waitUntil: 'domcontentloaded' });
  await page.locator('#projectName').fill('Synthetic draft before queued save');
  await page.evaluate(() => VASClientDraft.save());
  const before = await readRaw(page);
  const result = await page.evaluate(key => {
    const setTimeout = window.setTimeout;
    const clearTimeout = window.clearTimeout;
    const remove = Storage.prototype.removeItem;
    let canceled = false;
    let queued;
    const timerId = 987654321;
    window.setTimeout = function (callback, delay) {
      if (delay === 200) { queued = callback; return timerId; }
      return setTimeout.apply(this, arguments);
    };
    window.clearTimeout = function (id) {
      if (id === timerId) canceled = true;
      return clearTimeout.call(this, id);
    };
    const input = document.getElementById('projectName');
    input.value = 'Replacement from queued save';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    Storage.prototype.removeItem = function (name) {
      if (name === key) throw new Error('Synthetic deletion failure');
      return remove.call(this, name);
    };
    const cleared = VASClientDraft.clear();
    queued();
    VASClientDraft.save();
    window.setTimeout = setTimeout;
    window.clearTimeout = clearTimeout;
    Storage.prototype.removeItem = remove;
    return { cleared, canceled, hadQueuedSave: typeof queued === 'function' };
  }, key);
  expect(result).toEqual({ cleared: false, canceled: true, hadQueuedSave: true });
  expect(await readRaw(page)).toBe(before);
  await page.locator('#projectName').fill('Further input after failed deletion');
  await page.waitForTimeout(300);
  expect(await readRaw(page)).toBe(before);
  await expect(page.locator('#draftNotice')).toBeVisible();
});

test('autosave off still removes the draft and blocks every save path until turned on', async ({ page }) => {
  await openPending(page);
  await page.locator('#draftPolicyToggle').click();
  expect(await page.evaluate(key => localStorage.getItem(key), enabledKey)).toBe('0');
  expect(await readRaw(page)).toBeNull();
  await expect(page.locator('#draftNotice')).toBeHidden();
  await expect(page.locator('#draftPolicyText')).toContainText('꺼져');
  await page.locator('#projectName').fill('Autosave disabled input');
  await page.evaluate(() => {
    VASClientDraft.save();
    window.dispatchEvent(new Event('beforeunload'));
  });
  await page.waitForTimeout(300);
  expect(await readRaw(page)).toBeNull();
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('#draftPolicyText')).toContainText('꺼져');
  await page.locator('#projectName').fill('New enabled draft');
  expect(await readRaw(page)).toBeNull();
  await page.locator('#draftPolicyToggle').click();
  await expect.poll(async () => (await readDraft(page))?.fields.project_name).toBe('New enabled draft');
});

test('turning autosave back on cannot release a failed-deletion recovery lock', async ({ page }) => {
  const before = await openPending(page);
  await page.evaluate(key => {
    const remove = Storage.prototype.removeItem;
    Storage.prototype.removeItem = function (name) {
      if (name === key) throw new Error('Synthetic deletion failure');
      return remove.call(this, name);
    };
  }, key);
  await page.locator('#draftPolicyToggle').click();
  await expect(page.locator('#draftFeedback')).toContainText('초안을 삭제하지 못했습니다');
  await page.locator('#draftPolicyToggle').click();
  await page.locator('#projectName').fill('New input after re-enabling autosave');
  await page.evaluate(() => VASClientDraft.save());
  await page.waitForTimeout(300);
  expect(await readRaw(page)).toBe(before);
  await expect(page.locator('#draftNotice')).toBeVisible();
});
