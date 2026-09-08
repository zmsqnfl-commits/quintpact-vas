/** 동의 기반 저장소. 초기 브라우저 저장소 차단만 임시 저장으로 전환합니다. */
(function (global) {
  'use strict';
  const config = global.VASConfig || {};
  const portableId = global.VASMemoryIdentity || (typeof require === 'function' ? require('./memory-identity.js') : null);
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
  const SECRET_VALUE = new RegExp("(?:\\b(?:[a-z0-9]+[_-])*(?:password|pgpassword|passwd|pwd|passphrase|secret|secrets|credential|credentials|api[_ -]?key|(?:access|refresh|auth|session)[_ -]?token|token|client[_ -]?secret|authorization|private[_ -]?key|database[_ -]?url|db[_ -]?(?:url|password|pass)|(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|aws[_ -]?(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|connection[_ -]?string|github[_ -]?pat)\\b[\"']?\\s*(?:(?:/\\*[\\s\\S]*?\\*/|//[^\\r\\n]*)\\s*)*(?:\\]\\s*(?:(?:/\\*[\\s\\S]*?\\*/|//[^\\r\\n]*)\\s*)*)?[:=]|(?:\\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{12,}|\\b(?:AKIA|ASIA)[A-Z0-9]{16}|\\b(?:Bearer|Basic)\\s+[a-z0-9._~+/=-]{10,}|\\beyJ[a-z0-9_-]{8,}\\.[a-z0-9_-]{8,}\\.[a-z0-9_-]{8,}|-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|\\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|rediss?|mssql)(?:\\+[a-z0-9_.-]+)?://\\S+|\\b[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}|\\b(?:\\+?82[- ]?0?1[016789]|01[016789])[- ]?\\d{3,4}[- ]?\\d{4}))", 'i');
  const PATH_VALUE = /(?:^|[\s"'(])(?:[a-z]:[\\/]|\\\\|\/(?:users|home|etc|var|tmp|mnt|volumes)\/|\.{1,2}[\\/])|[\\/][\w .-]+\.[a-z0-9]{1,8}(?:$|[\s"',)])/i;
  const FILE_VALUE = /(?:^|[\s"'(])[^<>:"/\\|?*\r\n]{1,100}\.[a-z0-9]{1,8}(?:$|[\s"',)])/i;
  let activeAdapter = null;
  let initialization = null;
  let consentState = null;
  let pauseState = false;
  let sequence = 0;
  let storageMode = 'temporary';
  let memoryChannel = null;
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
      return metadata[method](key, value);
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
    storageMode = 'temporary';
    activeAdapter = memoryAdapter();
    await activeAdapter.init();
    await activeAdapter.setMeta('consent', consentState);
    await activeAdapter.setMeta('paused', pauseState);
  }
  async function call(method) {
    await init();
    const args = Array.prototype.slice.call(arguments, 1);
    return activeAdapter[method].apply(activeAdapter, args);
  }
  async function init(options) {
    if (initialization) return initialization;
    initialization = (async function () {
      const settings = options || {};
      const supplied = settings.adapter || global.VASLocalMemoryAdapter;
      const runtime = runtimeAdapter();
      activeAdapter = isAdapter(supplied) ? supplied : runtime || idbAdapter();
      storageMode = isAdapter(supplied) ? 'adapter' : runtime ? 'windows' : activeAdapter ? 'browser' : 'temporary';
      if (!activeAdapter) activeAdapter = memoryAdapter();
      try {
        await activeAdapter.init();
        const storedConsent = await activeAdapter.getMeta('consent');
        consentState = storedConsent === true ? true : storedConsent === false ? false : null;
        pauseState = Boolean(await activeAdapter.getMeta('paused'));
      } catch (error) {
        if (runtime || isAdapter(supplied)) throw error;
        await fallback();
      }
      return api;
    })().catch(function (error) { initialization = null; throw error; });
    return initialization;
  }
  function safeIdentifier(value, fallbackValue) {
    const text = String(value == null ? '' : value).trim();
    return /^[a-z0-9_-]{1,64}$/i.test(text) && !SECRET_VALUE.test(text) ? text : fallbackValue;
  }
  function privateText(value) {
    let decoded = String(value).replace(/\\(?:u([a-f0-9]{4})|x([a-f0-9]{2}))/gi, (_, u, x) => String.fromCharCode(parseInt(u || x, 16)));
    for (let i = 0; i < 4; i += 1) {
      const next = decoded.replace(/"(?:\\.|[^"\\])*"/g, function (token) { try { return ' ' + JSON.parse(token) + ' '; } catch (error) { return token; } });
      if (next === decoded) break; if (i === 3) return true;
      decoded = next;
    }
    const xmlLabels = decoded.replace(/<(?:[^\s<>\/=:]+:)?([a-z0-9_-]+)(?=[\s/>])/gi, ' $1=');
    const indexedLabels = decoded.replace(/["'`]?\s*(?:(?:\/\*[\s\S]*?\*\/|\/\/[^\r\n]*)\s*)*\]/g, '=');
    return SECRET_VALUE.test(indexedLabels) || SECRET_VALUE.test(xmlLabels) || PATH_VALUE.test(decoded) || FILE_VALUE.test(decoded);
  }
  function sanitizeString(value) {
    if (privateText(value)) return undefined;
    return String(value).replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 500) || undefined;
  }
  function sanitizeValue(value, key, depth) {
    if (depth > 5 || (key && (BLOCKED_KEY.test(key) || privateText(key) || SECRET_VALUE.test(key + '=') || ['__proto__', 'constructor', 'prototype'].includes(key)))) return undefined;
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
    if (global.crypto && typeof global.crypto.randomUUID === 'function') return global.crypto.randomUUID().replace(/-/g, '');
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
  function profileFor(events) {
    const scores = new Map();
    const counts = Object.create(null);
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
    return { schema: SCHEMA, terms: terms, eventCounts: counts };
  }
  async function consent(enabled) {
    await init();
    if (enabled === undefined) {
      const stored = await call('getMeta', 'consent');
      consentState = stored === true ? true : stored === false ? false : null;
      return consentState;
    }
    await call('setMeta', 'consent', enabled === true);
    consentState = enabled === true;
    changed('consent');
    return consentState;
  }
  async function pause(paused) {
    await init();
    if (paused === undefined) { pauseState = Boolean(await call('getMeta', 'paused')); return pauseState; }
    await call('setMeta', 'paused', paused !== false);
    pauseState = paused !== false;
    changed('pause');
    return pauseState;
  }
  async function record(typeOrEvent, payload, options) {
    await init();
    if (await consent() !== true || await pause()) return null;
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
    changed('record');
    return stored;
  }
  async function list(filter) {
    const settings = filter || {};
    let events = (await call('list')).map(function (event) {
      return { v: SCHEMA, id: safeIdentifier(event.id, ''), type: TYPE_SET.has(event.type) ? event.type : 'navigation', source: safeIdentifier(event.source, 'ui'), projectId: safeIdentifier(event.projectId, null), timestamp: new Date(Number.isFinite(Date.parse(event.timestamp)) ? Date.parse(event.timestamp) : 0).toISOString(), payload: sanitizeValue(event.payload, '', 0) || {}, feedback: normalizeFeedback(event.feedback) };
    });
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
    await call('setMeta', 'profile', null);
    await call('remove', safeIdentifier(id, ''));
    changed('delete');
    return true;
  }
  async function clear() {
    await call('setMeta', 'profile', null);
    await call('clear');
    changed('clear');
    return true;
  }
  async function exportData() {
    const events = await list({ order: 'asc' });
    return JSON.stringify({ schema: SCHEMA, exportedAt: new Date().toISOString(), events: events }, null, 2);
  }
  async function importData(input, options) {
    await init();
    if (await consent() !== true) return 0;
    let data;
    try {
      data = typeof input === 'string' ? JSON.parse(input) : input;
    } catch (error) {
      return 0;
    }
    const legacy = data && !Object.hasOwn(data, 'schema') && data.format === 'vas-personalization-memory' && data.version === SCHEMA;
    if (!data || (data.schema !== SCHEMA && !legacy) || !Array.isArray(data.events)) return 0;
    const mode = options && options.replace === true ? 'replace' : 'merge';
    if (mode === 'replace') await call('setMeta', 'profile', null);
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
      const response = await activeAdapter.importData({ schema: SCHEMA, events: safeEvents }, mode);
      imported = response && Number.isFinite(Number(response.imported)) ? Number(response.imported) : imported;
    } else {
      if (mode === 'replace') await call('clear');
      const aliases = new Map();
      for (const row of mode === 'merge' ? await list() : []) {
        aliases.set(row.id, row.id); aliases.set(await portableId(row.id), row.id);
      }
      for (const event of safeEvents) {
        const key = await portableId(event.id), id = aliases.get(event.id) || aliases.get(key) || event.id;
        await call('put', Object.assign({}, event, { id }));
        aliases.set(event.id, id); aliases.set(key, id);
      }
    }
    changed('import');
    return imported;
  }
  async function status() {
    await init();
    await consent();
    let runtimeStatus = null;
    if (typeof activeAdapter.status === 'function') {
      runtimeStatus = await activeAdapter.status();
    }
    const count = runtimeStatus ? Number(runtimeStatus.count) || 0 : (await call('list')).length;
    if (runtimeStatus) pauseState = Boolean(runtimeStatus.paused);
    else await pause();
    return Object.freeze({
      storageMode: storageMode,
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
      if (response && response.warning && global.dispatchEvent && global.CustomEvent) {
        global.dispatchEvent(new CustomEvent('vas-knowledge-warning', { detail: { code: response.warning } }));
      }
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
    await consent();
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
      profile = profileFor(memory);
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
  function changed(action) {
    if (global.dispatchEvent && global.CustomEvent) global.dispatchEvent(new CustomEvent('vas-memory-change', { detail: { action: action } }));
    try { if (memoryChannel) memoryChannel.postMessage(action); } catch (error) { }
  }
  if (global.document && global.BroadcastChannel) {
    try {
      memoryChannel = new global.BroadcastChannel('vas-work-memory');
      memoryChannel.onmessage = function (event) {
        global.dispatchEvent(new CustomEvent('vas-memory-change', { detail: { action: event.data } }));
      };
    } catch (error) { }
  }
  const api = Object.freeze({
    eventTypes: EVENT_TYPES,
    init: init, consent: consent,
    getConsent: function () { return consent(); },
    record: record,
    retrieve: function (query, options) { return ragCall('retrieve', query, options); },
    recommend: function (query, options) { return ragCall('recommend', query, options); },
    augmentPrompt: function (prompt, query, options) { return ragCall('augmentPrompt', query, options, prompt); },
    list: list, delete: remove, clear: clear,
    export: exportData, import: importData,
    pause: pause, status: status
  });
  global.VASPersonalization = api;
})(typeof window !== 'undefined' ? window : globalThis);
