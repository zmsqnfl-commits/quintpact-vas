const { test, expect } = require('@playwright/test');
const path = require('path');
const script = path.join(__dirname, '..', 'src', 'personalization-store.js');

test('persistent mutation failures retain the adapter, consent and visible records', async ({ page }) => {
  await page.evaluate(() => {
    const events = [{ id: 'control', type: 'theme_selected', timestamp: '2026-09-08T00:00:00Z', payload: { preset: 'bento' } }];
    const meta = { consent: true, paused: false };
    const fail = async () => { throw Error('synthetic disk failure'); };
    window.VASLocalMemoryAdapter = { init: async () => {}, list: async () => events, getMeta: async k => meta[k], setMeta: fail, put: fail, clear: fail, remove: fail, importData: fail };
  });
  await page.addScriptTag({ path: script });
  const result = await page.evaluate(async () => {
    const api = VASPersonalization, rejected = [];
    for (const action of [() => api.delete('control'), () => api.clear(), () => api.consent(false), () => api.pause(true), () => api.record('theme_selected', { preset: 'linear' }), () => api.import({ schema: 1, events: [] }, { replace: true })]) {
      try { await action(); rejected.push(false); } catch (error) { rejected.push(error.message === 'synthetic disk failure'); }
    }
    return { rejected, state: await api.status(), records: await api.list() };
  });
  expect(result.rejected).toEqual([true, true, true, true, true, true]);
  expect(result.state).toMatchObject({ count: 1, consent: true, paused: false, storageMode: 'adapter' });
  expect(result.records[0].id).toBe('control');
});

test('IndexedDB request success followed by transaction abort is a failure', async ({ page }) => {
  await page.evaluate(() => {
    const database = { transaction(storeName) {
      const transaction = { objectStore() {
        const request = (value, abort) => { const r = { result: value }; setTimeout(() => { if (r.onsuccess) r.onsuccess(); if (abort) transaction.onabort(); else transaction.oncomplete(); }, 0); return r; };
        return { get: key => request({ value: key === 'consent' }), getAll: () => request([{ id: 'control', timestamp: '2026-09-08' }]), clear: () => request(undefined, true) };
      } }; return transaction;
    } };
    Object.defineProperty(window, 'indexedDB', { configurable: true, value: { open() { const r = { result: database }; setTimeout(() => r.onsuccess(), 0); return r; } } });
  });
  await page.addScriptTag({ path: script });
  const result = await page.evaluate(async () => {
    await VASPersonalization.init(); let rejected = false;
    try { await VASPersonalization.clear(); } catch (error) { rejected = /aborted/.test(error.message); }
    return { rejected, records: await VASPersonalization.list() };
  });
  expect(result.rejected).toBe(true); expect(result.records).toHaveLength(1);
});
