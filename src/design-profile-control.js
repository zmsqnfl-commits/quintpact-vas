/**
 * VAS 디자인 스튜디오 — Taste Profile 수동 선택 제어
 */
(function () {
  'use strict';

  const AUTO_PROFILE = 'auto';
  const STORAGE_KEY = 'vasTasteProfileMode';

  function getProfiles() {
    return window.VAS_TASTE_PROFILES || {};
  }

  function normalizeMode(value) {
    return value === AUTO_PROFILE || getProfiles()[value] ? value : AUTO_PROFILE;
  }

  function getSelectedMode() {
    const select = document.getElementById('tasteProfileMode');
    const stored = VASStorage.readText(STORAGE_KEY, AUTO_PROFILE);
    return normalizeMode(select && select.value ? select.value : stored);
  }

  function getStoredMode() {
    return normalizeMode(VASStorage.readText(STORAGE_KEY, AUTO_PROFILE));
  }

  function getManualTasteProfileKey() {
    const mode = getSelectedMode();
    return mode === AUTO_PROFILE ? null : mode;
  }

  function getCurrentPresetKey() {
    return VASStorage.readText('vasCurrentPreset', 'awwwards');
  }

  function refreshAgentPrompt() {
    if (window.refreshDesignPrompt) {
      window.refreshDesignPrompt();
      return;
    }
    const presetKey = getCurrentPresetKey();
    const preset = typeof PRESETS !== 'undefined' ? PRESETS[presetKey] : null;
    const promptBox = document.getElementById('aiPrompt');
    if (!preset || !promptBox) return;
    promptBox.value = window.composeAgentPrompt
      ? window.composeAgentPrompt(presetKey, preset, getManualTasteProfileKey())
      : preset.prompt;
  }

  function setTasteProfileMode(value) {
    const mode = normalizeMode(value);
    const select = document.getElementById('tasteProfileMode');
    if (select) select.value = mode;
    VASStorage.writeText(STORAGE_KEY, mode);
    if (window.VASThemeState) window.VASThemeState.commit({ tasteProfileMode: mode });
    refreshAgentPrompt();
  }

  function renderTasteProfileOptions() {
    const select = document.getElementById('tasteProfileMode');
    if (!select) return;

    select.innerHTML = '<option value="auto">프리셋 기준 자동</option>';
    Object.keys(getProfiles()).forEach(function (key) {
      const profile = getProfiles()[key];
      const option = document.createElement('option');
      option.value = key;
      option.textContent = profile.label;
      select.appendChild(option);
    });
    select.value = getStoredMode();
  }

  window.getManualTasteProfileKey = getManualTasteProfileKey;
  window.setTasteProfileMode = setTasteProfileMode;
  window.refreshAgentPrompt = refreshAgentPrompt;

  renderTasteProfileOptions();
})();
