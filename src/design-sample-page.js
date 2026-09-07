/** Isolated sample viewer: never commits or broadcasts the user's design state. */
(function () {
  'use strict';
  function readSnapshot() {
    const encoded = new URLSearchParams(location.hash.slice(1)).get('vas');
    if (!encoded || encoded.length > 4096 || !/^[A-Za-z0-9_-]+$/.test(encoded)) return null;
    try {
      const value = JSON.parse(new TextDecoder().decode(Uint8Array.from(
        atob(encoded.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))));
      return value?.v === 1 && VASStorage.isTheme(value.tokens) ? value : null;
    } catch (error) { return null; }
  }
  const snapshot = readSnapshot();
  const requested = new URLSearchParams(location.search).get('preset');
  const key = Object.hasOwn(PRESETS, requested) || (requested === 'custom' && snapshot?.basePreset === 'custom') ? requested : 'awwwards';
  const preset = PRESETS[key] || { label: 'Custom' };
  const tokens = snapshot && snapshot.basePreset === key ? VASStorage.normalizeTheme(snapshot.tokens) : VASStorage.normalizeTheme({
    fontFamily: preset.font, fontSize: 16, letterSpacing: preset.ls, radius: preset.rad,
    padding: preset.pad, borderWidth: preset.bw, shadow: preset.shadow, speed: preset.speed,
    colors: { background: preset.bg, surface: preset.surface, primary: preset.primary,
      text: preset.text, border: preset.border, success: '#10b981' }
  });
  const mode = snapshot?.basePreset === key && typeof snapshot.tasteProfileMode === 'string' && Object.hasOwn(VAS_TASTE_PROFILES, snapshot.tasteProfileMode) ? snapshot.tasteProfileMode : null;
  const profile = getTasteProfileKey(key, preset, mode);
  const root = document.getElementById('advPreview');
  root.dataset.tasteProfile = profile;
  VASDesignPreview.applyTokens(root, tokens);
  VASDesignPreview.render(profile, key, tokens.colors);
  document.body.style.background = tokens.colors.background;
  document.body.style.color = tokens.colors.text;
  const title = preset.label || key.charAt(0).toUpperCase() + key.slice(1);
  document.title = title + ' 샘플 사이트 · VAS';
  document.getElementById('sampleLabel').textContent = title + ' · 샘플 사이트';
  const select = document.getElementById('samplePreset');
  const keys = VAS_PRESET_KEYS.includes(key) ? VAS_PRESET_KEYS : VAS_PRESET_KEYS.concat(key);
  keys.forEach(name => select.add(new Option(PRESETS[name]?.label || name.charAt(0).toUpperCase() + name.slice(1), name)));
  select.value = key;
  select.addEventListener('change', () => { location.href = 'design-sample.html?preset=' + encodeURIComponent(select.value); });
})();
