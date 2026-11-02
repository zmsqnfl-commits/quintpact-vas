/* Only mounted by the authenticated Windows project hub. No browser draft persistence. */
(function (global) {
  'use strict';
  let mounted = false;
  function mount() {
    if (mounted) return;
    mounted = true;
    const el = id => document.getElementById('projectPrompt' + id);
    const box = el('Text'), status = el('Status');
    let base = null, latest = null, busy = false, conflicted = false, generation = 0;
    const dirty = () => base && box.value !== base.prompt;
    const note = text => { status.textContent = text; };
    function controls() {
      box.disabled = !base;
      box.readOnly = busy;
      el('Save').disabled = busy || !dirty() || conflicted || Array.from(box.value).length > 4000;
      el('Reload').disabled = busy;
      el('Reload').textContent = dirty() ? '초안 버리고 저장본 불러오기' : '저장본 불러오기';
      el('Rebase').hidden = !conflicted || !latest || !base || latest.revision === base.revision;
    }
    function checked(data) {
      if (!data || !Number.isSafeInteger(data.revision) || data.revision < 0 || typeof data.prompt !== 'string') {
        throw new Error('저장된 지시를 확인하지 못했습니다.');
      }
      return data;
    }
    function preview(value) {
      latest = value;
      el('Saved').textContent = value.prompt || '저장된 작업 지시 없음';
    }
    function adopt(value) {
      base = value;
      preview(value);
      conflicted = false;
      box.value = value.prompt;
      controls();
    }
    async function load(discard) {
      if (busy) return;
      const token = ++generation, initialText = box.value;
      try {
        const value = checked(await VASRuntime.request('/api/project-prompt'));
        if (token !== generation) return;
        if (!base || (!dirty() && !conflicted) || (discard && box.value === initialText)) {
          adopt(value);
          note(value.revision ? '최신 저장본을 불러왔습니다.' : '아직 저장된 작업 지시가 없습니다.');
        } else {
          preview(value);
          if (value.revision !== base.revision) {
            conflicted = true;
            el('Preview').open = true;
            note('저장본이 달라졌습니다. 아래 저장본과 작성 중인 초안을 비교하세요.');
          }
          controls();
        }
      } catch (error) {
        if (token !== generation) return;
        note(error.message || '저장본을 읽지 못했습니다. 다시 불러오세요.');
        controls();
      }
    }
    async function save() {
      if (el('Save').disabled) return;
      const draft = box.value;
      ++generation;
      busy = true; controls(); note('저장 중…');
      let written = null;
      try {
        written = checked(await VASRuntime.request('/api/project-prompt', {
          method: 'PUT', body: { expectedRevision: base.revision, prompt: draft }
        }));
        const read = checked(await VASRuntime.request('/api/project-prompt'));
        if (read.revision !== written.revision || read.prompt !== written.prompt) {
          preview(read);
          conflicted = true;
          el('Preview').open = true;
          note('저장 직후 다른 지시가 저장됐습니다. 최신 저장본과 초안을 비교하세요.');
        } else {
          adopt(read);
          note(read.prompt ? '저장했습니다. AI가 다음 작업 전에 이 지시를 읽습니다.' : '작업 지시를 비웠습니다.');
        }
      } catch (error) {
        note(written ? '저장 요청은 처리됐지만 최신 저장본을 확인하지 못했습니다. 다시 불러오세요.'
          : (error.message || '저장하지 못했습니다. 초안은 유지됩니다.'));
        if (written || error.code === 'project_prompt_conflict') conflicted = true;
        if (error.code === 'project_prompt_conflict') {
          try { preview(checked(await VASRuntime.request('/api/project-prompt'))); el('Preview').open = true; }
          catch (_) { /* Keep draft and last known preview. Explicit reload can retry. */ }
        }
      } finally { busy = false; controls(); }
    }
    box.addEventListener('input', function () {
      controls();
      if (Array.from(box.value).length > 4000) note('작업 지시는 4,000자까지 저장할 수 있습니다.');
      else if (conflicted) note('저장본과 초안을 비교한 뒤 편집을 계속하세요.');
      else if (dirty()) note(box.value.trim() ? '아직 저장하지 않은 변경입니다.' : '저장하면 기존 작업 지시가 비워집니다.');
      else note('저장본과 같습니다.');
    });
    el('Reload').addEventListener('click', () => load(true));
    el('Rebase').addEventListener('click', function () {
      if (!latest || busy) return;
      base = latest; conflicted = false; controls();
      note('초안을 유지했습니다. 내용을 비교하고 지시 저장을 누르세요.');
      box.focus();
    });
    el('Save').addEventListener('click', save);
    global.addEventListener('focus', () => load(false));
    el('Panel').hidden = false;
    controls(); note('저장된 지시를 읽는 중…'); load(false);
  }
  global.VASProjectPrompt = Object.freeze({ mount });
})(window);
