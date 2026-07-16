/** VAS 신청서 로컬 초안 저장·복구 */
(function (global) {
  'use strict';

  const mode = document.body.dataset.mode || 'internal';
  const key = 'vasClientDraft.v1.' + mode;
  const enabledKey = 'vasClientDraftEnabled.v1.' + mode;
  const form = document.getElementById('projectForm');
  let timer = null;
  let suspended = false;
  let enabled = VASStorage.readText(enabledKey, '1') !== '0';
  let pending = VASStorage.readJson(key, null, function (value) {
    return value && value.v === 1 && value.fields && typeof value.fields === 'object';
  });

  function collectFields() {
    const fields = {};
    form.querySelectorAll('input[name], textarea[name], select[name]').forEach(function (element) {
      if (!element.name || element.disabled || element.type === 'file' || element.name === 'attached_files') return;
      if (element.type === 'checkbox' || element.type === 'radio') {
        if (!fields[element.name]) fields[element.name] = [];
        if (element.checked) fields[element.name].push(element.value);
      } else {
        fields[element.name] = element.value;
      }
    });
    return fields;
  }

  function save() {
    if (suspended || !enabled) return;
    pending = {
      v: 1,
      savedAt: new Date().toISOString(),
      step: global.cur || 1,
      language: global.currentLang || 'ko',
      fields: collectFields()
    };
    VASStorage.writeJson(key, pending);
  }

  function schedule() {
    if (!enabled) return;
    suspended = false;
    global.clearTimeout(timer);
    timer = global.setTimeout(save, 200);
  }

  function applyFields(fields) {
    Object.keys(fields).forEach(function (name) {
      const values = Array.isArray(fields[name]) ? fields[name] : [fields[name]];
      form.querySelectorAll('[name="' + CSS.escape(name) + '"]').forEach(function (element) {
        if (element.type === 'checkbox' || element.type === 'radio') {
          element.checked = values.includes(element.value);
        } else if (element.type !== 'file') {
          element.value = values[0] || '';
        }
      });
    });
  }

  function restore() {
    if (!pending) return;
    applyFields(pending.fields);
    global.cur = Math.min(5, Math.max(1, Number(pending.step) || 1));
    global.currentLang = pending.language === 'en' ? 'en' : 'ko';
    document.querySelectorAll('.step').forEach(function (step) {
      step.classList.toggle('active', Number(step.dataset.step) === global.cur);
      step.style.opacity = Number(step.dataset.step) === global.cur ? '1' : '0';
      step.style.transform = Number(step.dataset.step) === global.cur ? 'translateY(0)' : 'translateY(40px)';
    });
    global.setLang(global.currentLang);
    document.getElementById('draftNotice').hidden = true;
  }

  function clear() {
    suspended = true;
    pending = null;
    VASStorage.remove(key);
  }

  function discard() {
    clear();
    suspended = false;
    document.getElementById('draftNotice').hidden = true;
  }

  function renderPolicy() {
    const korean = (global.currentLang || 'ko') === 'ko';
    document.getElementById('draftPolicyText').textContent = enabled
      ? (korean ? '입력 내용은 복구를 위해 이 브라우저에 자동 저장됩니다.' : 'Your entries are auto-saved in this browser for recovery.')
      : (korean ? '초안 자동 저장이 꺼져 있습니다.' : 'Draft auto-save is off.');
    document.getElementById('draftPolicyToggle').textContent = enabled
      ? (korean ? '자동 저장 끄기' : 'Turn off')
      : (korean ? '자동 저장 켜기' : 'Turn on');
  }

  function toggle() {
    enabled = !enabled;
    VASStorage.writeText(enabledKey, enabled ? '1' : '0');
    if (enabled) schedule();
    else clear();
    renderPolicy();
  }

  function showNotice() {
    if (!pending) return;
    const notice = document.getElementById('draftNotice');
    const savedAt = document.getElementById('draftSavedAt');
    savedAt.textContent = pending.savedAt ? ' ' + new Date(pending.savedAt).toLocaleString() : '';
    notice.hidden = false;
  }

  form.addEventListener('input', schedule);
  form.addEventListener('change', schedule);
  global.addEventListener('beforeunload', save);
  if (!enabled) clear();
  renderPolicy();
  showNotice();

  global.VASClientDraft = Object.freeze({ save, restore, clear, discard, toggle, renderPolicy });
})(window);
