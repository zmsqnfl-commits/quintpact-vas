/** 페이지 사이에서 현재 프로젝트의 안전한 식별 정보만 이어 줍니다. */
(function (global) {
  'use strict';

  const HASH_KEY = 'vasProject';
  const STORAGE_KEY = 'vasProjectContext';
  const VERSION = 1;
  const ID_PATTERN = /^[A-Za-z0-9._-]{1,100}$/;
  const SOURCES = new Set(['new', 'imported']);
  const GOALS = new Set(['manage', 'improve', 'redesign', 'upgrade']);
  const STAGES = new Set(['design', 'knowledge', 'ready']);
  let current = null;
  let initialized = false;

  function safeEnum(value, values, fallback) {
    return values.has(value) ? value : fallback;
  }

  function normalize(value) {
    const input = value && typeof value === 'object' ? value : {};
    const projectId = String(input.projectId || '').trim();
    if (!ID_PATTERN.test(projectId)) return null;
    return Object.freeze({
      v: VERSION,
      projectId: projectId,
      sourceType: safeEnum(input.sourceType, SOURCES, 'new'),
      goal: safeEnum(input.goal, GOALS, 'manage'),
      stage: safeEnum(input.stage, STAGES, 'design')
    });
  }

  function readHash() {
    try {
      const params = new URLSearchParams(global.location.hash.replace(/^#/, ''));
      const projectId = params.get(HASH_KEY);
      return projectId && ID_PATTERN.test(projectId) ? { projectId: projectId } : null;
    } catch (error) {
      return null;
    }
  }

  function readStored() {
    return VASStorage.readJson(STORAGE_KEY, null, function (value) {
      return Boolean(value && value.v === VERSION && ID_PATTERN.test(String(value.projectId || '')));
    }, 'session');
  }

  function writeStored(value) {
    if (!value) return VASStorage.remove(STORAGE_KEY, 'session');
    return VASStorage.writeJson(STORAGE_KEY, value, 'session');
  }

  function updateLocation(projectId) {
    try {
      const params = new URLSearchParams(global.location.hash.replace(/^#/, ''));
      if (projectId) params.set(HASH_KEY, projectId);
      else params.delete(HASH_KEY);
      const hash = params.toString();
      global.history.replaceState(null, '', global.location.pathname + global.location.search + (hash ? '#' + hash : ''));
    } catch (error) { }
  }

  function init() {
    const stored = normalize(readStored());
    const hash = readHash();
    current = hash ? normalize(Object.assign({}, stored || {}, hash)) : stored;
    initialized = true;
    if (current) writeStored(current);
    return current ? JSON.parse(JSON.stringify(current)) : null;
  }

  function get() {
    if (!initialized) init();
    return current ? JSON.parse(JSON.stringify(current)) : null;
  }

  function set(value) {
    current = normalize(value);
    if (!current) throw new Error('프로젝트 연결 정보가 올바르지 않습니다.');
    initialized = true;
    writeStored(current);
    updateLocation(current.projectId);
    decorateLinks(document);
    global.dispatchEvent(new CustomEvent('vas-project-context', { detail: get() }));
    return get();
  }

  function clear() {
    current = null;
    initialized = true;
    writeStored(null);
    updateLocation('');
    global.dispatchEvent(new CustomEvent('vas-project-context', { detail: null }));
  }

  function decorateLinks(root) {
    const context = get();
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('a[data-vas-project-link]').forEach(function (link) {
      const raw = link.getAttribute('href');
      if (!raw || /^(https?:|mailto:|javascript:)/i.test(raw)) return;
      try {
        const url = new URL(raw, global.location.href);
        const params = new URLSearchParams(url.hash.replace(/^#/, ''));
        if (context) params.set(HASH_KEY, context.projectId);
        else params.delete(HASH_KEY);
        url.hash = params.toString();
        link.setAttribute('href', url.href);
      } catch (error) { }
    });
  }

  function nextHref(value) {
    const project = normalize(value) || get();
    if (!project) return 'vas-hub.html';
    if (project.stage === 'design') return 'design-controller.html';
    if (project.stage === 'knowledge') return 'knowledge-search.html';
    return 'knowledge-search.html';
  }

  global.VASProjectContext = Object.freeze({ init, get, set, clear, decorateLinks, nextHref });
})(window);
