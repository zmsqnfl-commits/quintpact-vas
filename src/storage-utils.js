/**
 * VAS 로컬 저장소 안전 접근 유틸리티
 * 손상된 JSON이나 저장소 접근 제한이 있어도 화면 실행을 유지합니다.
 */
(function (global) {
  'use strict';

  const SYSTEM_SANS = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif";
  const SYSTEM_MONO = "ui-monospace, 'Cascadia Code', 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace";

  function getStorage(kind) {
    try {
      return kind === 'session' ? global.sessionStorage : global.localStorage;
    } catch (error) {
      return null;
    }
  }

  function writeJson(key, value, kind) {
    const storage = getStorage(kind);
    if (!storage) return false;
    try {
      storage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function readJson(key, fallback, validator, kind) {
    const storage = getStorage(kind);
    if (!storage) return fallback;
    try {
      const raw = storage.getItem(key);
      if (raw === null) return fallback;
      const value = JSON.parse(raw);
      if (validator && !validator(value)) throw new Error('저장 데이터 형식 오류');
      return value;
    } catch (error) {
      writeJson(key, fallback, kind);
      return fallback;
    }
  }

  function writeText(key, value, kind) {
    const storage = getStorage(kind);
    if (!storage) return false;
    try {
      storage.setItem(key, String(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function readText(key, fallback, kind) {
    const storage = getStorage(kind);
    if (!storage) return fallback;
    try {
      const value = storage.getItem(key);
      return value === null ? fallback : value;
    } catch (error) {
      return fallback;
    }
  }

  function normalizeFontFamily(value) {
    if (typeof value !== 'string' || !value.trim()) return SYSTEM_SANS;
    if (!/(Pretendard|Geist|Inter|JetBrains)/i.test(value)) return value;
    return /(Mono|JetBrains)/i.test(value) ? SYSTEM_MONO : SYSTEM_SANS;
  }

  function remove(key, kind) {
    const storage = getStorage(kind);
    if (!storage) return false;
    try {
      storage.removeItem(key);
      return true;
    } catch (error) {
      return false;
    }
  }

  function clamp(value, min, max, fallback) {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.min(max, Math.max(min, number));
  }

  function normalizeColor(value, fallback) {
    return typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value)
      ? value.toLowerCase()
      : fallback;
  }

  function getDefaultTheme() {
    return {
      fontFamily: SYSTEM_SANS,
      fontSize: 16,
      fsHero: '56px',
      fsH2: '35.2px',
      fsH3: '24px',
      fsBody: '16px',
      fsSm: '12.8px',
      letterSpacing: -0.05,
      padding: 24,
      radius: 0,
      borderWidth: 2,
      shadow: 0,
      speed: 0.1,
      colors: {
        primary: '#000000',
        background: '#f0f0f0',
        surface: '#ffcc00',
        text: '#000000',
        border: '#000000',
        success: '#10b981'
      }
    };
  }

  function normalizeTheme(value) {
    const fallback = getDefaultTheme();
    const input = value && typeof value === 'object' ? value : {};
    const colors = input.colors && typeof input.colors === 'object' ? input.colors : {};
    const fontSize = clamp(input.fontSize, 12, 24, fallback.fontSize);
    return {
      fontFamily: normalizeFontFamily(input.fontFamily),
      fontSize,
      fsHero: (fontSize * 3.5) + 'px',
      fsH2: (fontSize * 2.2) + 'px',
      fsH3: (fontSize * 1.5) + 'px',
      fsBody: fontSize + 'px',
      fsSm: (fontSize * 0.8) + 'px',
      letterSpacing: clamp(input.letterSpacing, -0.1, 0.2, fallback.letterSpacing),
      padding: clamp(input.padding, 12, 64, fallback.padding),
      radius: clamp(input.radius, 0, 40, fallback.radius),
      borderWidth: clamp(input.borderWidth, 0, 8, fallback.borderWidth),
      shadow: clamp(input.shadow, 0, 80, fallback.shadow),
      speed: clamp(input.speed, 0.1, 1, fallback.speed),
      colors: {
        primary: normalizeColor(colors.primary, fallback.colors.primary),
        background: normalizeColor(colors.background, fallback.colors.background),
        surface: normalizeColor(colors.surface, fallback.colors.surface),
        text: normalizeColor(colors.text, fallback.colors.text),
        border: normalizeColor(colors.border, fallback.colors.border),
        success: normalizeColor(colors.success, fallback.colors.success)
      }
    };
  }

  function isTheme(value) {
    if (!value || typeof value !== 'object' || !value.colors || typeof value.colors !== 'object') return false;
    const colorKeys = ['primary', 'background', 'surface', 'text', 'border'];
    return colorKeys.every(function (key) { return typeof value.colors[key] === 'string'; });
  }

  global.VASStorage = Object.freeze({
    SYSTEM_SANS,
    SYSTEM_MONO,
    isTheme,
    getDefaultTheme,
    normalizeTheme,
    normalizeFontFamily,
    remove,
    readJson,
    readText,
    writeJson,
    writeText
  });
})(window);
