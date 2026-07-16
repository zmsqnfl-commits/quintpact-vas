/** 동의 기반 개인화 이벤트 저장소입니다. IndexedDB 실패 시 메모리로 안전 전환합니다. */
(function (global) {
  'use strict';

  const config = global.VASConfig || {};
  const SCHEMA = config.personalizationSchema || 1;
  const DB_NAME = config.personalizationDbName || 'vas-personalization';
  const WARNING_EVENTS = config.memoryWarningEvents || 2000;
  const EVENT_TYPES = Object.freeze([
    'theme_selected', 'search', 'navigation', 'form_completed', 'export',
    'feedback', 'project_opened', 'project_imported', 'project_created',
    'recommendation_used', 'workflow_completed'
  ]);
  const TYPE_SET = new Set(EVENT_TYPES);
  const BLOCKED_KEY = /(pass(word|phrase)?|secret|credential|api.?key|auth|token|database.?url|db.?pass|aws.?access|file|path|folder|directory|attachment|upload|(project|client).?name|contact|phone|e.?mail)/i;
  const SECRET_VALUE = /(?:\b(?:password|passwd|secret|api[_ -]?key|authorization|client[_ -]?secret|database[_ -]?url|aws[_ -]?(?:access[_ -]?key[_ -]?id|secret[_ -]?access[_ -]?key))\s*[:=]|\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{12,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}|bearer\s+[a-z0-9._~-]{12,}|\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}|\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql):\/\/\S+)/i;
  const PATH_VALUE = /(?:^|[\s"'(])(?:[a-z]:[\\/]|\\\\|\/(?:users|home|etc|var|tmp|mnt|volumes)\/|\.{1,2}[\\/])|[\\/][\w .-]+\.[a-z0-9]{1,8}(?:$|[\s"',)])/i;
  const FILE_VALUE = /(?:^|[\s"'(])[^<>:"/\\|?*\r\n]{1,100}\.[a-z0-9]{1,8}(?:$|[\s"',)])/i;
  let activeAdapter = null;
  let initialization = null;
  let consentState = null;
  let pauseState = false;
  let sequence = 0;
  const projectKnowledgeCache = new Map();

  function clone(value) {
    if (value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
  }

  function memoryAdapter() {
    const events = new Map();
    const metadata = new Map();
    return {
      init: async function () {},
      list: async function () { return Array.from(events.values()).map(clone); },
      put: async function (event) { events.set(event.id, clone(event)); return clone(event); },
      remove: async function (id) { events.delete(id); },
      clear: async function () { events.clear(); },
      getMeta: async function (key) { return clone(metadata.get(key)); },
      setMeta: async function (key, value) { metadata.set(key, clone(value)); }
    };
  }

  function idbAdapter() {
    if (!global.indexedDB) return null;
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
          result.onsuccess = function () { resolve(result.result); };
          result.onerror = function () { reject(result.error || new Error('IndexedDB request failed')); };
          transaction.onabort = function () { reject(transaction.error || new Error('IndexedDB transaction aborted')); };
        });
      });
    }
    return {
      init: open,
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

  function runtimeAdapter() {
    const runtime = global.VASRuntime;
    if (!runtime || typeof runtime.isAvailable !== 'function' || !runtime.isAvailable()) return null;
    let metadata = idbAdapter() || memoryAdapter();
    let statusCache = null;
    async function metaCall(method, key, value) {
      try {
        return await metadata[method](key, value);
      } catch (error) {
        metadata = memoryAdapter();
        await metadata.init();
        return metadata[method](key, value);
      }
    }
    return {
      init: async function () {
        statusCache = await runtime.request('/api/memory/status');
        try { await metadata.init(); } catch (error) { metadata = memoryAdapter(); await metadata.init(); }
      },
      list: async function () {
        const response = await runtime.request('/api/memory/events');
        return response && Array.isArray(response.events) ? response.events : [];
      },
      put: async function (event) {
        const response = await runtime.request('/api/memory/events', { method: 'POST', body: event });
        return response && response.accepted ? response.event : null;
      },
      remove: function (id) {
        return runtime.request('/api/memory/events/' + encodeURIComponent(id), { method: 'DELETE' });
      },
      clear: function () { return runtime.request('/api/memory/events', { method: 'DELETE' }); },
      getMeta: async function (key) {
        if (key === 'paused') {
          statusCache = await runtime.request('/api/memory/status');
          return Boolean(statusCache.paused);
        }
        return metaCall('getMeta', key);
      },
      setMeta: async function (key, value) {
        if (key === 'paused') {
          const response = await runtime.request('/api/memory/pause', { method: 'POST', body: { paused: Boolean(value) } });
          if (statusCache) statusCache.paused = Boolean(response.paused);
          return;
        }
        return metaCall('setMeta', key, value);
      },
      status: async function () {
        statusCache = await runtime.request('/api/memory/status');
        return statusCache;
      },
      importData: function (data, mode) {
        return runtime.request('/api/memory/import', {
          method: 'POST',
          body: { mode: mode, data: data }
        });
      }
    };
  }

  function isAdapter(value) {
    return value && ['init', 'list', 'put', 'remove', 'clear', 'getMeta', 'setMeta']
      .every(function (name) { return typeof value[name] === 'function'; });
  }

  async function fallback() {
    activeAdapter = memoryAdapter();
    await activeAdapter.init();
    await activeAdapter.setMeta('consent', consentState);
    await activeAdapter.setMeta('paused', pauseState);
  }

  async function call(method) {
    await init();
    const args = Array.prototype.slice.call(arguments, 1);
    try {
      return await activeAdapter[method].apply(activeAdapter, args);
    } catch (error) {
      await fallback();
      return activeAdapter[method].apply(activeAdapter, args);
    }
  }

  async function init(options) {
    if (initialization) return initialization;
    initialization = (async function () {
      const settings = options || {};
      const supplied = settings.adapter || global.VASLocalMemoryAdapter;
      activeAdapter = isAdapter(supplied) ? supplied : runtimeAdapter() || idbAdapter();
      if (!activeAdapter) activeAdapter = memoryAdapter();
      try {
        await activeAdapter.init();
        const storedConsent = await activeAdapter.getMeta('consent');
        consentState = storedConsent === true ? true : storedConsent === false ? false : null;
        pauseState = Boolean(await activeAdapter.getMeta('paused'));
      } catch (error) {
        await fallback();
      }
      return api;
    })();
    return initialization;
  }

  function safeIdentifier(value, fallbackValue) {
    const text = String(value == null ? '' : value).trim();
    return /^[a-z0-9_-]{1,64}$/i.test(text) ? text : fallbackValue;
  }

  function sanitizeString(value) {
    const text = String(value).replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!text || SECRET_VALUE.test(text) || PATH_VALUE.test(text) || FILE_VALUE.test(text)) return undefined;
    return text.slice(0, 500);
  }

  function sanitizeValue(value, key, depth) {
    if (depth > 5 || (key && BLOCKED_KEY.test(key))) return undefined;
    if (typeof value === 'string') return sanitizeString(value);
    if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
    if (typeof value === 'boolean' || value === null) return value;
    if (Array.isArray(value)) {
      return value.slice(0, 20).map(function (item) {
        return sanitizeValue(item, '', depth + 1);
      }).filter(function (item) { return item !== undefined; });
    }
    if (value && Object.getPrototypeOf(value) === Object.prototype) {
      const result = {};
      Object.keys(value).sort().slice(0, 40).forEach(function (childKey) {
        const clean = sanitizeValue(value[childKey], childKey, depth + 1);
        if (clean !== undefined) result[childKey] = clean;
      });
      return result;
    }
    return undefined;
  }

  function hasContent(value) {
    if (value === null || typeof value === 'boolean' || typeof value === 'number') return true;
    if (typeof value === 'string') return Boolean(value);
    if (Array.isArray(value)) return value.some(hasContent);
    return value && Object.keys(value).some(function (key) { return hasContent(value[key]); });
  }

  function eventId() {
    if (global.crypto && typeof global.crypto.randomUUID === 'function') return global.crypto.randomUUID();
    sequence += 1;
    return 'event-' + Date.now().toString(36) + '-' + sequence.toString(36);
  }

  function normalizeFeedback(value) {
    if (value === 1 || value === 'like' || value === 'positive') return 1;
    if (value === -1 || value === 'dislike' || value === 'negative') return -1;
    return 0;
  }

  function buildEvent(input, imported) {
    if (!input || !TYPE_SET.has(input.type)) return null;
    const payload = sanitizeValue(input.payload || {}, '', 0);
    if (!hasContent(payload)) return null;
    const parsedTime = Date.parse(input.timestamp || '');
    const timestamp = imported && Number.isFinite(parsedTime)
      ? new Date(parsedTime).toISOString() : new Date().toISOString();
    return Object.freeze({
      v: SCHEMA,
      id: imported ? safeIdentifier(input.id, eventId()) : eventId(),
      type: input.type,
      source: safeIdentifier(input.source, 'ui'),
      projectId: safeIdentifier(input.projectId, null),
      timestamp: timestamp,
      payload: payload,
      feedback: normalizeFeedback(input.feedback)
    });
  }

  function collectStrings(value, output) {
    if (typeof value === 'string') output.push(value);
    else if (Array.isArray(value)) value.forEach(function (item) { collectStrings(item, output); });
    else if (value && typeof value === 'object') {
      Object.keys(value).forEach(function (key) { collectStrings(value[key], output); });
    }
  }

  function profileTokens(value) {
    if (global.VASRagLite) return global.VASRagLite.tokenize(value);
    const matches = String(value).toLowerCase().match(/[가-힣]{2,}|[a-z0-9]{2,}/g) || [];
    return Array.from(new Set(matches)).slice(0, 80);
  }

  async function recomputeProfile() {
    const events = await call('list');
    const scores = new Map();
    const counts = {};
    events.forEach(function (event) {
      counts[event.type] = (counts[event.type] || 0) + 1;
      const strings = [];
      collectStrings(event.payload, strings);
      const terms = profileTokens(strings.join(' '));
      const weight = event.feedback === -1 ? -1 : event.feedback === 1 ? 2 : 1;
      terms.forEach(function (term) { scores.set(term, (scores.get(term) || 0) + weight); });
    });
    const terms = Array.from(scores.entries()).filter(function (row) { return row[1] > 0; })
      .sort(function (left, right) { return right[1] - left[1] || left[0].localeCompare(right[0]); })
      .slice(0, 20).map(function (row) { return row[0]; });
    const profile = { schema: SCHEMA, terms: terms, eventCounts: counts };
    await call('setMeta', 'profile', profile);
    return profile;
  }

  async function consent(enabled) {
    await init();
    if (enabled === undefined) return consentState;
    consentState = enabled === true;
    await call('setMeta', 'consent', consentState);
    return consentState;
  }

  async function pause(paused) {
    await init();
    if (paused === undefined) return pauseState;
    pauseState = paused !== false;
    await call('setMeta', 'paused', pauseState);
    return pauseState;
  }

  async function record(typeOrEvent, payload, options) {
    await init();
    if (consentState !== true || pauseState) return null;
    const input = typeof typeOrEvent === 'object' ? Object.assign({}, typeOrEvent) : Object.assign({}, options || {}, {
      type: typeOrEvent,
      payload: payload
    });
    const context = global.VASProjectContext && global.VASProjectContext.get
      ? global.VASProjectContext.get() : null;
    if (!input.projectId && context) input.projectId = context.projectId;
    const event = buildEvent(input, false);
    if (!event) return null;
    const stored = await call('put', event);
    if (!stored) return null;
    await recomputeProfile();
    return stored;
  }

  async function list(filter) {
    const settings = filter || {};
    let events = await call('list');
    if (settings.type) events = events.filter(function (event) { return event.type === settings.type; });
    if (settings.projectId) events = events.filter(function (event) { return event.projectId === settings.projectId; });
    events.sort(function (a, b) {
      const direction = settings.order === 'asc' ? 1 : -1;
      return direction * (a.timestamp.localeCompare(b.timestamp) || a.id.localeCompare(b.id));
    });
    const limit = Math.max(0, Number(settings.limit) || events.length);
    return events.slice(0, limit).map(clone);
  }

  async function remove(id) {
    await call('remove', safeIdentifier(id, ''));
    await recomputeProfile();
    return true;
  }

  async function clear() {
    await call('clear');
    await recomputeProfile();
    return true;
  }

  async function exportData() {
    const events = await list({ order: 'asc' });
    return JSON.stringify({ schema: SCHEMA, exportedAt: new Date().toISOString(), events: events }, null, 2);
  }

  async function importData(input, options) {
    await init();
    if (consentState !== true) return 0;
    let data;
    try {
      data = typeof input === 'string' ? JSON.parse(input) : input;
    } catch (error) {
      return 0;
    }
    if (!data || data.schema !== SCHEMA || !Array.isArray(data.events)) return 0;
    const mode = options && options.replace === true ? 'replace' : 'merge';
    const safeEvents = [];
    let imported = 0;
    for (const raw of data.events) {
      const event = buildEvent(raw, true);
      if (event) {
        safeEvents.push(event);
        imported += 1;
      }
    }
    if (typeof activeAdapter.importData === 'function') {
      try {
        const response = await activeAdapter.importData({ schema: SCHEMA, events: safeEvents }, mode);
        imported = response && Number.isFinite(Number(response.imported)) ? Number(response.imported) : imported;
      } catch (error) {
        await fallback();
        if (mode === 'replace') await call('clear');
        for (const event of safeEvents) await call('put', event);
      }
    } else {
      if (mode === 'replace') await call('clear');
      for (const event of safeEvents) await call('put', event);
    }
    await recomputeProfile();
    return imported;
  }

  async function status() {
    await init();
    let runtimeStatus = null;
    if (typeof activeAdapter.status === 'function') {
      try { runtimeStatus = await activeAdapter.status(); } catch (error) { runtimeStatus = null; }
    }
    const count = runtimeStatus ? Number(runtimeStatus.count) || 0 : (await call('list')).length;
    if (runtimeStatus) pauseState = Boolean(runtimeStatus.paused);
    return Object.freeze({
      count: count,
      paused: pauseState,
      consent: consentState,
      storageWarning: count >= WARNING_EVENTS,
      bytes: runtimeStatus ? Number(runtimeStatus.bytes) || 0 : null,
      retention: runtimeStatus ? runtimeStatus.retention : 'until-explicit-delete'
    });
  }

  async function projectKnowledge(projectId) {
    const runtime = global.VASRuntime;
    if (!projectId || !/^[A-Za-z0-9._-]{1,100}$/.test(projectId)) return [];
    if (!runtime || !runtime.isAvailable || !runtime.isAvailable()) return [];
    const cached = projectKnowledgeCache.get(projectId);
    if (cached && Date.now() - cached.at < 30000) return cached.entries;
    try {
      const response = await runtime.request('/api/knowledge/projects?projectId=' + encodeURIComponent(projectId));
      projectKnowledgeCache.set(projectId, {
        at: Date.now(),
        entries: response && Array.isArray(response.entries) ? response.entries : []
      });
    } catch (error) {
      projectKnowledgeCache.set(projectId, { at: Date.now(), entries: [] });
    }
    return projectKnowledgeCache.get(projectId).entries;
  }

  async function ragCall(method, query, options, prompt) {
    await init();
    if (!global.VASRagLite) return method === 'augmentPrompt' ? String(prompt || '') : method === 'recommend' ? { query: query, preferences: [], results: [] } : [];
    const context = global.VASProjectContext && global.VASProjectContext.get
      ? global.VASProjectContext.get() : null;
    const requestedProject = options && options.projectId;
    const projectId = /^[A-Za-z0-9._-]{1,100}$/.test(String(requestedProject || ''))
      ? String(requestedProject) : context && context.projectId;
    const memory = consentState === true
      ? await list({ order: 'asc', projectId: projectId || undefined }) : [];
    let profile = { terms: [] };
    if (consentState === true && projectId) {
      const values = [];
      memory.forEach(function (event) { collectStrings(event.payload, values); });
      profile = { terms: profileTokens(values.join(' ')).slice(0, 20) };
    } else if (consentState === true) {
      profile = await call('getMeta', 'profile') || profile;
    }
    const settings = Object.assign({}, options || {}, {
      memory: memory,
      profile: profile,
      projectId: projectId || null,
      knowledgeEntries: consentState === true ? await projectKnowledge(projectId) : []
    });
    return method === 'augmentPrompt'
      ? global.VASRagLite.augmentPrompt(prompt, query, settings)
      : global.VASRagLite[method](query, settings);
  }

  const api = Object.freeze({
    eventTypes: EVENT_TYPES,
    init: init,
    consent: consent,
    getConsent: function () { return consent(); },
    record: record,
    retrieve: function (query, options) { return ragCall('retrieve', query, options); },
    recommend: function (query, options) { return ragCall('recommend', query, options); },
    augmentPrompt: function (prompt, query, options) { return ragCall('augmentPrompt', query, options, prompt); },
    list: list,
    delete: remove,
    clear: clear,
    export: exportData,
    import: importData,
    pause: pause,
    status: status
  });

  global.VASPersonalization = api;
})(typeof window !== 'undefined' ? window : globalThis);
