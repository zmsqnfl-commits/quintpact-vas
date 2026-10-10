/** One explicitly selected chat session; edits stay local until the user saves. */
(function (global) {
  'use strict';
  const params = new URLSearchParams(global.location.search);
  const selected = params.get('session');
  const connected = params.has('session');
  const validId = /^[a-f0-9]{32}$/;
  let documentState = null, baseline = '', dirty = false, conflict = false;
  let busy = false, fetching = false, healthy = false, targetAvailable = false, suspended = false;
  let reloadRequested = false;
  let visualChanged = false, previewDiffers = false;
  const el = id => document.getElementById(id);
  const adapter = () => global.VASDesignSessionAdapter;
  const copy = value => JSON.parse(JSON.stringify(value));

  function message(text, state) {
    el('chatDesignStatus').textContent = text;
    el('chatDesignPanel').dataset.state = state || 'idle';
    const badges = { saved: '저장됨', draft: '수정 중', conflict: '변경 확인', error: '연결 확인', loading: '확인 중' };
    el('chatDesignBadge').textContent = badges[state] || (connected ? '채팅 연결' : '선택 가능');
  }

  function draft() {
    const selection = visualChanged ? adapter().read() : {};
    const design = Object.assign({}, copy(documentState.settings.design), selection,
      { direction: el('chatDesignDirection').value });
    const mode = el('chatDesignScope').value;
    return {
      designScope: { mode: mode, scope: mode === 'preserve' ? '' : el('chatDesignScopeText').value },
      design: mode === 'preserve' ? { profileId: '', direction: '', tokens: {} } : design
    };
  }

  function toggleEditing() {
    const available = Boolean(documentState && healthy && targetAvailable && !busy);
    const preserve = el('chatDesignScope').value === 'preserve';
    document.querySelectorAll('#controlsPanel .group:not(#chatDesignPanel) input, #controlsPanel .group:not(#chatDesignPanel) select, #controlsPanel .group:not(#chatDesignPanel) button').forEach(node => {
      node.disabled = !available || preserve;
    });
    document.querySelectorAll('[onclick="undoTheme()"]').forEach(node => { node.disabled = !available || preserve; });
    el('chatDesignScope').disabled = !available || (documentState && documentState.settings.project.sourceType === 'new');
    el('chatDesignScopeText').disabled = !available || preserve;
    el('chatDesignDirection').disabled = !available || preserve;
    el('chatDesignPreserve').hidden = !preserve;
    el('chatDesignPreviewNote').hidden = preserve || !previewDiffers || visualChanged;
    el('chatDesignScopeLabel').hidden = preserve;
    el('chatDesignScopeText').hidden = preserve;
    const validScope = el('chatDesignScope').value !== 'partial' || Boolean(el('chatDesignScopeText').value.trim());
    el('applyProjectTheme').disabled = !available || !dirty || conflict || !validScope;
    el('chatDesignReload').hidden = !conflict;
    el('chatDesignReload').disabled = busy || fetching;
    el('chatDesignRetry').hidden = healthy || busy;
  }

  function edited() {
    if (!documentState || suspended || busy) return;
    dirty = JSON.stringify(draft()) !== baseline;
    if (!conflict && healthy) message(dirty ? '화면의 변경은 아직 저장하지 않았습니다.' : '채팅과 같은 설정입니다.', dirty ? 'draft' : 'saved');
    toggleEditing();
  }

  function matchesPreview(saved, shown) {
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
      return shown && typeof shown === 'object' && Object.keys(saved).every(key => matchesPreview(saved[key], shown[key]));
    }
    return saved === shown;
  }

  function adopt(response) {
    suspended = true;
    documentState = response.session;
    targetAvailable = response.target && response.target.status === 'available';
    const settings = documentState.settings;
    el('chatDesignDetails').hidden = false;
    el('chatDesignName').textContent = settings.project.name;
    el('chatDesignRequest').textContent = settings.task.request;
    el('chatDesignCriteria').replaceChildren();
    settings.task.completionCriteria.forEach(item => {
      const row = document.createElement('li'); row.textContent = item.description;
      el('chatDesignCriteria').append(row);
    });
    Array.from(el('chatDesignScope').options).forEach(option => {
      option.hidden = (settings.project.sourceType === 'new') !== (option.value === 'new');
    });
    el('chatDesignScope').value = settings.task.designScope.mode;
    el('chatDesignScopeText').value = settings.task.designScope.scope;
    el('chatDesignDirection').value = settings.design.direction;
    adapter().hydrate(settings.design);
    const shown = adapter().read();
    visualChanged = false;
    previewDiffers = ['profileId', 'preset', 'basePreset', 'tasteProfileMode', 'tokens'].some(key =>
      settings.design[key] && !matchesPreview(settings.design[key], shown[key]));
    baseline = JSON.stringify(draft()); dirty = false; conflict = false;
    healthy = true; suspended = false;
    message(targetAvailable ? '채팅과 같은 설정입니다. 저장하면 다음 대화에서 이어집니다.' : '작업 폴더를 확인해야 합니다. 채팅에서 대상을 다시 연결하세요.', targetAvailable ? 'saved' : 'error');
    el('chatDesignPanel').dataset.revision = String(documentState.revision);
    toggleEditing();
  }

  async function refresh(discard) {
    if (busy || !validId.test(selected || '')) return;
    if (fetching) { reloadRequested = reloadRequested || Boolean(discard); return; }
    fetching = true;
    try {
      const response = await VASRuntime.request('/api/chat/session?sessionId=' + selected);
      const incoming = response.session;
      if (!incoming || incoming.sessionId !== selected) throw new Error('선택한 작업을 확인할 수 없습니다.');
      // A read started before a successful save must never roll the screen back.
      if (documentState && incoming.revision < documentState.revision) return;
      healthy = true;
      targetAvailable = response.target && response.target.status === 'available';
      if (!documentState || discard || (!dirty && incoming.revision !== documentState.revision)) {
        adopt(response);
      } else if (incoming.revision !== documentState.revision) {
        conflict = true;
        message('채팅이나 다른 화면에서 설정이 바뀌었습니다. 내 변경을 버리고 최신 설정을 불러온 뒤 다시 선택하세요.', 'conflict');
      } else if (!targetAvailable) {
        message('작업 폴더를 확인해야 합니다. 채팅에서 대상을 다시 연결하세요.', 'error');
      } else if (!conflict) {
        message(dirty ? '화면의 변경은 아직 저장하지 않았습니다.' : '채팅과 같은 설정입니다.', dirty ? 'draft' : 'saved');
      }
    } catch (error) {
      healthy = false;
      message(error.status === 404 ? '저장된 작업을 찾을 수 없습니다. 채팅에서 작업을 확인하세요.' : '연결을 확인하지 못했습니다. 화면의 변경은 유지됩니다. 다시 확인하세요.', 'error');
    } finally {
      fetching = false; toggleEditing();
      if (reloadRequested) { reloadRequested = false; refresh(true); }
    }
  }

  async function save() {
    if (!documentState || !dirty || busy || conflict || !healthy || !targetAvailable) return;
    const payload = Object.assign({ sessionId: selected, expectedRevision: documentState.revision }, draft());
    busy = true; toggleEditing(); message('대화 설정에 저장하고 있습니다.', 'loading');
    try {
      const response = await VASRuntime.request('/api/chat/session/design', { method: 'POST', body: payload });
      adopt(response);
      if (response.reviewFields && response.reviewFields.length) {
        message('저장했습니다. 민감한 값이나 적용할 수 없는 디자인 항목은 정리했습니다.', 'saved');
      } else message('저장했습니다. 다음 대화에서 이 디자인을 이어갑니다.', 'saved');
    } catch (error) {
      if (error.status === 409) {
        conflict = true;
        message('다른 곳에서 설정이 바뀌어 저장하지 않았습니다. 내 변경을 버리고 최신 설정을 불러오세요.', 'conflict');
      } else {
        healthy = false;
        message('저장하지 못했습니다. 화면의 변경은 유지됩니다. 연결을 다시 확인하세요.', 'error');
      }
    } finally { busy = false; toggleEditing(); }
  }

  async function choices() {
    try {
      const result = await VASRuntime.request('/api/chat/sessions');
      const select = el('chatDesignSession');
      select.replaceChildren(new Option('작업 선택', ''));
      result.sessions.forEach(item => select.add(new Option(item.name + ' · ' + (item.sourceType === 'new' ? '새 앱' : '기존 앱'), item.sessionId)));
      el('chatDesignPicker').hidden = !result.sessions.length;
      message(result.sessions.length ? '채팅에서 준비한 작업을 선택하면 디자인을 함께 사용할 수 있습니다.' : '채팅에서 작업 설정을 저장하면 여기서 연결할 수 있습니다.');
    } catch (error) { message('채팅 작업 목록을 읽지 못했습니다. 로컬 실행과 Python 연결을 확인하세요.', 'error'); }
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!connected) {
      if (global.VASRuntime && VASRuntime.isAvailable()) choices();
      else message('채팅 설정 연결은 로컬 VAS에서 사용할 수 있습니다. 스타일 비교는 그대로 이용하세요.');
      el('chatDesignConnect').addEventListener('click', function () {
        const id = el('chatDesignSession').value;
        if (!validId.test(id)) return;
        const url = new URL(global.location.href); url.searchParams.set('session', id);
        const fragments = new URLSearchParams(url.hash.slice(1)); fragments.delete('vas'); url.hash = fragments.toString();
        global.location.href = url.href;
      });
      return;
    }
    document.body.dataset.chatSession = 'true';
    el('applyProjectTheme').textContent = '대화 설정에 저장';
    el('applyProjectTheme').addEventListener('click', save);
    el('applyProjectStatus').hidden = true;
    toggleEditing();
    global.addEventListener('DOMContentLoaded', toggleEditing, { once: true });
    ['chatDesignScope', 'chatDesignScopeText', 'chatDesignDirection'].forEach(id => el(id).addEventListener('input', edited));
    global.addEventListener('vas-design-edit', () => {
      if (!documentState || suspended || busy) return;
      visualChanged = true; edited();
    });
    el('chatDesignReload').addEventListener('click', () => refresh(true));
    el('chatDesignRetry').addEventListener('click', () => refresh(false));
    if (!validId.test(selected || '')) { message('작업 연결 주소가 올바르지 않습니다. 채팅에서 다시 열어주세요.', 'error'); return; }
    if (!VASRuntime.isAvailable()) { message('로컬 연결이 필요합니다. 채팅에서 VAS 디자인 화면을 다시 열어주세요.', 'error'); return; }
    refresh(false);
    global.addEventListener('focus', () => refresh(false));
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(false); });
    global.setInterval(() => { if (!document.hidden) refresh(false); }, 4000);
    global.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  });
})(window);
