/**
 * VAS 페이지 간 테마 상태 브리지
 * file:// 저장소가 페이지별로 분리되어도 URL 해시로 안전한 테마만 전달합니다.
 */
(function (global) {
  'use strict';

  const HASH_KEY = 'vas';
  const HASH_LIMIT = 4096;
  const STATE_VERSION = 1;
  const DEFAULT_PRESET = 'awwwards';
  let currentState = null;

  function normalizePreset(value) {
    if (value === 'custom') return value;
    return typeof value === 'string' && /^[a-z0-9-]{1,32}$/i.test(value)
      ? value.toLowerCase()
      : DEFAULT_PRESET;
  }

  function normalizeTasteMode(value) {
    return typeof value === 'string' && /^[a-z0-9-]{1,48}$/i.test(value)
      ? value
      : 'auto';
  }

  function normalizeState(value) {
    const input = value && typeof value === 'object' ? value : {};
    return {
      v: STATE_VERSION,
      preset: normalizePreset(input.preset),
      tasteProfileMode: normalizeTasteMode(input.tasteProfileMode),
      tokens: VASStorage.normalizeTheme(input.tokens)
    };
  }

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
    const json = JSON.stringify(normalizeState(state));
    return bytesToBase64(new TextEncoder().encode(json));
  }

  function decodeNavigationState(value) {
    if (!value || value.length > HASH_LIMIT || !/^[A-Za-z0-9_-]+$/.test(value)) return null;
    try {
      const parsed = JSON.parse(new TextDecoder().decode(base64ToBytes(value)));
      if (!parsed || parsed.v !== STATE_VERSION) return null;
      return normalizeState(parsed);
    } catch (error) {
      return null;
    }
  }

  function readHashState() {
    const match = global.location.hash.match(/(?:^#|&)vas=([^&]+)/);
    return match ? decodeNavigationState(match[1]) : null;
  }

  function readStoredState() {
    const tokens = VASStorage.readJson('vasThemeTokens', null, VASStorage.isTheme);
    if (!tokens) return null;
    return normalizeState({
      preset: VASStorage.readText('vasCurrentPreset', DEFAULT_PRESET),
      tasteProfileMode: VASStorage.readText('vasTasteProfileMode', 'auto'),
      tokens
    });
  }

  function persist(state) {
    VASStorage.writeJson('vasThemeTokens', state.tokens);
    VASStorage.writeText('vasCurrentPreset', state.preset);
    VASStorage.writeText('vasTasteProfileMode', state.tasteProfileMode);
    VASStorage.writeText('vasThemeTokensVersion', global.VASConfig ? global.VASConfig.version : '2.6.0');
    VASStorage.writeJson('vasThemeStateMeta', { v: STATE_VERSION, preset: state.preset });
  }

  function init() {
    const navigationState = readHashState();
    const storedState = navigationState ? null : readStoredState();
    currentState = normalizeState(navigationState || storedState || {});
    persist(currentState);
    return get();
  }

  function get() {
    if (!currentState) return init();
    return JSON.parse(JSON.stringify(currentState));
  }

  function commit(partial) {
    const input = partial && typeof partial === 'object' ? partial : {};
    currentState = normalizeState({
      preset: input.preset === undefined ? get().preset : input.preset,
      tasteProfileMode: input.tasteProfileMode === undefined ? get().tasteProfileMode : input.tasteProfileMode,
      tokens: input.tokens === undefined ? get().tokens : input.tokens
    });
    persist(currentState);
    decorateLinks(document);
    global.dispatchEvent(new CustomEvent('vas-theme-state', { detail: get() }));
    return get();
  }

  function decorateLinks(root) {
    const state = encodeNavigationState(get());
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('a[data-vas-link], a[href$=".html"]').forEach(function (link) {
      const raw = link.getAttribute('href');
      if (!raw || /^(https?:|mailto:|javascript:)/i.test(raw)) return;
      try {
        const url = new URL(raw, global.location.href);
        const fragments = new URLSearchParams(url.hash.replace(/^#/, ''));
        fragments.set(HASH_KEY, state);
        url.hash = fragments.toString();
        link.setAttribute('href', url.href);
      } catch (error) {
        // 잘못된 링크는 원래 값을 유지합니다.
      }
    });
  }

  global.VASThemeState = Object.freeze({
    init,
    get,
    commit,
    decorateLinks,
    encodeNavigationState,
    decodeNavigationState
  });
})(window);
