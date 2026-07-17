/** VAS 페이지와 디자인 스튜디오 사이의 안전한 테마 상태 브리지. */
(function (global) {
  'use strict';

  const HASH_KEY = 'vas';
  const HASH_LIMIT = 4096;
  const STATE_VERSION = 1;
  const DEFAULT_PRESET = 'awwwards';
  const CHANNEL_NAME = 'vas-theme-state';
  let currentState = null;
  let channel = null;

  function normalizePreset(value) {
    if (value === 'custom') return value;
    return typeof value === 'string' && /^[a-z0-9-]{1,32}$/i.test(value)
      ? value.toLowerCase() : DEFAULT_PRESET;
  }

  function normalizeTasteMode(value) {
    return typeof value === 'string' && /^[a-z0-9-]{1,48}$/i.test(value) ? value : 'auto';
  }

  function normalizeRevision(value) {
    const revision = Number(value);
    return Number.isSafeInteger(revision) && revision >= 0 ? revision : 0;
  }

  function normalizeUpdatedAt(value) {
    const updatedAt = Number(value);
    return Number.isSafeInteger(updatedAt) && updatedAt >= 0 ? updatedAt : 0;
  }

  function normalizeState(value) {
    const input = value && typeof value === 'object' ? value : {};
    return {
      v: STATE_VERSION,
      revision: normalizeRevision(input.revision),
      updatedAt: normalizeUpdatedAt(input.updatedAt),
      preset: normalizePreset(input.preset),
      tasteProfileMode: normalizeTasteMode(input.tasteProfileMode),
      tokens: VASStorage.normalizeTheme(input.tokens)
    };
  }

  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function bytesToBase64(bytes) {
    let binary = '';
    bytes.forEach(function (byte) { binary += String.fromCharCode(byte); });
    return global.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }

  function base64ToBytes(value) {
    const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
    const binary = global.atob(padded);
    return Uint8Array.from(binary, function (char) { return char.charCodeAt(0); });
  }

  function encodeNavigationState(state) {
    return bytesToBase64(new TextEncoder().encode(JSON.stringify(normalizeState(state))));
  }

  function decodeNavigationState(value) {
    if (!value || value.length > HASH_LIMIT || !/^[A-Za-z0-9_-]+$/.test(value)) return null;
    try {
      const parsed = JSON.parse(new TextDecoder().decode(base64ToBytes(value)));
      return parsed && parsed.v === STATE_VERSION ? normalizeState(parsed) : null;
    } catch (error) { return null; }
  }

  function readHashState() {
    const match = global.location.hash.match(/(?:^#|&)vas=([^&]+)/);
    return match ? decodeNavigationState(match[1]) : null;
  }

  function readStoredState() {
    const tokens = VASStorage.readJson('vasThemeTokens', null, VASStorage.isTheme);
    if (!tokens) return null;
    const meta = VASStorage.readJson('vasThemeStateMeta', {}, function (value) {
      return value && typeof value === 'object';
    }) || {};
    return normalizeState({
      revision: meta.revision,
      updatedAt: meta.updatedAt,
      preset: VASStorage.readText('vasCurrentPreset', DEFAULT_PRESET),
      tasteProfileMode: VASStorage.readText('vasTasteProfileMode', 'auto'),
      tokens: tokens
    });
  }

  function newest() {
    const states = Array.prototype.slice.call(arguments).filter(Boolean).map(normalizeState);
    return states.reduce(function (best, candidate) {
      if (!best || candidate.revision > best.revision) return candidate;
      if (candidate.revision < best.revision) return best;
      if (candidate.updatedAt > best.updatedAt) return candidate;
      if (candidate.updatedAt < best.updatedAt) return best;
      return JSON.stringify(candidate) > JSON.stringify(best) ? candidate : best;
    }, null);
  }

  function persist(state) {
    VASStorage.writeJson('vasThemeTokens', state.tokens);
    VASStorage.writeText('vasCurrentPreset', state.preset);
    VASStorage.writeText('vasTasteProfileMode', state.tasteProfileMode);
    VASStorage.writeText('vasThemeTokensVersion', global.VASConfig ? global.VASConfig.version : '2.6.4');
    VASStorage.writeJson('vasThemeStateMeta', {
      v: STATE_VERSION, preset: state.preset, revision: state.revision, updatedAt: state.updatedAt
    });
  }

  function linksIn(root) {
    const selector = 'a[data-vas-link], a[href$=".html"], a[href*=".html?"]';
    const links = [];
    if (root && root.matches && root.matches(selector)) links.push(root);
    const scope = root && root.querySelectorAll ? root : document;
    return links.concat(Array.from(scope.querySelectorAll(selector)));
  }

  function decorateLinks(root) {
    const encoded = encodeNavigationState(get());
    linksIn(root).forEach(function (link) {
      const raw = link.getAttribute('href');
      if (!raw || /^(mailto:|javascript:)/i.test(raw)) return;
      try {
        const url = new URL(raw, global.location.href);
        if (/^https?:$/.test(url.protocol) && url.origin !== global.location.origin) return;
        const fragments = new URLSearchParams(url.hash.replace(/^#/, ''));
        fragments.set(HASH_KEY, encoded);
        url.hash = fragments.toString();
        link.setAttribute('href', url.href);
      } catch (error) { }
    });
  }

  function announce() {
    const state = get();
    global.dispatchEvent(new CustomEvent('vas-theme-state', { detail: state }));
    try { if (channel) channel.postMessage(state); } catch (error) { }
  }

  function accept(state, notify) {
    const next = normalizeState(state);
    const changed = !currentState || JSON.stringify(currentState) !== JSON.stringify(next);
    currentState = next;
    persist(currentState);
    decorateLinks(document);
    if (changed && notify) global.dispatchEvent(new CustomEvent('vas-theme-state', { detail: get() }));
    return get();
  }

  function ensureChannel() {
    if (channel || typeof global.BroadcastChannel !== 'function') return;
    try {
      channel = new global.BroadcastChannel(CHANNEL_NAME);
      channel.addEventListener('message', function (event) {
        const incoming = normalizeState(event.data);
        const next = newest(currentState, incoming);
        if (!currentState || JSON.stringify(next) !== JSON.stringify(currentState)) accept(next, true);
      });
    } catch (error) { channel = null; }
  }

  function init() {
    ensureChannel();
    if (currentState) return sync();
    currentState = newest(readHashState(), readStoredState()) || normalizeState({});
    persist(currentState);
    decorateLinks(document);
    return get();
  }

  function get() {
    if (!currentState) return init();
    return clone(currentState);
  }

  function sync() {
    if (!currentState) return init();
    const next = newest(currentState, readHashState(), readStoredState());
    return next && JSON.stringify(next) !== JSON.stringify(currentState) ? accept(next, true) : get();
  }

  function commit(partial) {
    const input = partial && typeof partial === 'object' ? partial : {};
    const base = newest(currentState || normalizeState({}), readStoredState(), readHashState());
    currentState = normalizeState({
      revision: (base ? base.revision : 0) + 1,
      updatedAt: Date.now(),
      preset: input.preset === undefined ? base.preset : input.preset,
      tasteProfileMode: input.tasteProfileMode === undefined ? base.tasteProfileMode : input.tasteProfileMode,
      tokens: input.tokens === undefined ? base.tokens : input.tokens
    });
    persist(currentState);
    decorateLinks(document);
    announce();
    return get();
  }

  global.VASThemeState = Object.freeze({
    init: init, get: get, sync: sync, commit: commit, decorateLinks: decorateLinks,
    encodeNavigationState: encodeNavigationState, decodeNavigationState: decodeNavigationState
  });

  global.addEventListener('storage', function (event) {
    if (!event.key || /^vas(?:Theme|Current|Taste)/.test(event.key)) sync();
  });
  global.addEventListener('focus', sync);
  global.addEventListener('pageshow', sync);
})(window);
