/** Browser memory imports commit all records together, including identity aliases. */
(function (global) {
  'use strict';
  const portableId = global.VASMemoryIdentity || (typeof require === 'function' ? require('./memory-identity.js') : null);
  function clone(value) { return value === undefined ? undefined : JSON.parse(JSON.stringify(value)); }
  function resolveImport(existing, incoming) {
    const aliases = new Map();
    for (const row of existing) { aliases.set(row.id, row.id); aliases.set(portableId(row.id), row.id); }
    return incoming.map(function (event) {
      const key = portableId(event.id), id = aliases.get(event.id) || aliases.get(key) || event.id;
      aliases.set(event.id, id); aliases.set(key, id);
      return Object.assign({}, event, { id });
    });
  }
  function memoryAdapter() {
    let events = new Map();
    const metadata = new Map();
    return {
      init: async function () {},
      importData: async function (data, mode) {
        const next = mode === 'replace' ? new Map() : new Map(events);
        for (const event of resolveImport(Array.from(next.values()), data.events)) next.set(event.id, clone(event));
        events = next;
        if (mode === 'replace') metadata.set('profile', null);
        return { imported: data.events.length };
      },
      list: async function () { return Array.from(events.values()).map(clone); },
      put: async function (event) { events.set(event.id, clone(event)); return clone(event); },
      remove: async function (id) { events.delete(id); },
      clear: async function () { events.clear(); },
      getMeta: async function (key) { return clone(metadata.get(key)); },
      setMeta: async function (key, value) { metadata.set(key, clone(value)); }
    };
  }
  function idbAdapter(DB_NAME) {
    try { if (!global.indexedDB) return null; } catch (error) { return null; }
    let databasePromise;
    function open() {
      if (databasePromise) return databasePromise;
      databasePromise = new Promise(function (resolve, reject) {
        let request;
        try {
          request = global.indexedDB.open(DB_NAME, 1);
        } catch (error) {
          reject(error);
          return;
        }
        request.onupgradeneeded = function () {
          const database = request.result;
          if (!database.objectStoreNames.contains('events')) {
            database.createObjectStore('events', { keyPath: 'id' });
          }
          if (!database.objectStoreNames.contains('meta')) {
            database.createObjectStore('meta', { keyPath: 'key' });
          }
        };
        request.onsuccess = function () { resolve(request.result); };
        request.onerror = function () { reject(request.error || new Error('IndexedDB open failed')); };
        request.onblocked = function () { reject(new Error('IndexedDB blocked')); };
      });
      return databasePromise;
    }
    function request(storeName, mode, operation) {
      return open().then(function (database) {
        return new Promise(function (resolve, reject) {
          const transaction = database.transaction(storeName, mode);
          const result = operation(transaction.objectStore(storeName));
          transaction.oncomplete = function () { resolve(result.result); };
          result.onerror = function () { reject(result.error || new Error('IndexedDB request failed')); };
          transaction.onabort = function () { reject(transaction.error || new Error('IndexedDB transaction aborted')); };
        });
      });
    }
    return {
      init: open,
      importData: function (data, mode) {
        return open().then(function (database) {
          return new Promise(function (resolve, reject) {
            const transaction = database.transaction(['events', 'meta'], 'readwrite');
            let failure = null;
            transaction.oncomplete = function () { resolve({ imported: data.events.length }); };
            transaction.onabort = function () { reject(failure || transaction.error || new Error('IndexedDB transaction aborted')); };
            const store = transaction.objectStore('events');
            const read = store.getAll();
            read.onsuccess = function () {
              try {
                const events = resolveImport(mode === 'replace' ? [] : read.result, data.events);
                if (mode === 'replace') {
                  store.clear();
                  transaction.objectStore('meta').put({ key: 'profile', value: null });
                }
                events.forEach(function (event) { store.put(event); });
              } catch (error) { failure = error; transaction.abort(); }
            };
          });
        });
      },
      list: function () { return request('events', 'readonly', function (store) { return store.getAll(); }); },
      put: function (event) {
        return request('events', 'readwrite', function (store) { return store.put(event); })
          .then(function () { return clone(event); });
      },
      remove: function (id) { return request('events', 'readwrite', function (store) { return store.delete(id); }); },
      clear: function () { return request('events', 'readwrite', function (store) { return store.clear(); }); },
      getMeta: function (key) {
        return request('meta', 'readonly', function (store) { return store.get(key); })
          .then(function (row) { return row ? row.value : undefined; });
      },
      setMeta: function (key, value) {
        return request('meta', 'readwrite', function (store) { return store.put({ key: key, value: value }); });
      }
    };
  }
  const api = Object.freeze({ temporary: memoryAdapter, indexedDB: idbAdapter });
  global.VASMemoryAdapters = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
