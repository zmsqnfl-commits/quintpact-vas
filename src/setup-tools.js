/** 모든 설정 단계에서 다시 열 수 있는 사용 방법과 작업 기억 제어입니다. */
(function (global) {
  'use strict';

  let helpDialog;
  let settingsDialog;
  let initialized = false;

  function close(dialog) {
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
  }

  function open(dialog) {
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }

  function dialogs() {
    const holder = document.createElement('div');
    holder.innerHTML = [
      '<dialog class="setup-dialog" id="vasSetupHelp" aria-labelledby="vasSetupHelpTitle">',
      '<div class="setup-dialog-shell"><div class="setup-dialog-head"><h2 id="vasSetupHelpTitle">이 순서대로 하면 됩니다.</h2><button type="button" class="setup-dialog-close" data-setup-close aria-label="닫기">닫기</button></div>',
      '<ol class="setup-help-list"><li><b>01</b><div><strong>시작 방식을 고릅니다.</strong><p>새 프로그램을 만들거나 기존 프로그램 폴더를 선택합니다.</p></div></li>',
      '<li><b>02</b><div><strong>필요한 내용과 디자인을 정합니다.</strong><p>화면에 나오는 질문만 차례대로 확인하면 됩니다.</p></div></li>',
      '<li><b>03</b><div><strong>JSON을 코딩 도구에 줍니다.</strong><p>Codex·Claude·Antigravity에서 작업 폴더를 열고 VAS-AI-HANDOFF.json을 첨부한 뒤 복사한 문장을 붙여넣습니다.</p></div></li></ol></div></dialog>',
      '<dialog class="setup-dialog" id="vasSetupSettings" aria-labelledby="vasSetupSettingsTitle">',
      '<div class="setup-dialog-shell"><div class="setup-dialog-head"><h2 id="vasSetupSettingsTitle">설정을 다시 바꿀 수 있습니다.</h2><button type="button" class="setup-dialog-close" data-setup-close aria-label="닫기">닫기</button></div>',
      '<div class="setup-memory-state"><span>작업 기억</span><strong id="vasSetupMemoryState">확인 중</strong></div>',
      '<p class="setup-dialog-copy setup-setting-note">작업 기억은 다음 설정을 조금 더 편하게 만들기 위한 선택 기능입니다. 파일 내용·비밀값·절대 경로는 저장하지 않으며 최종 JSON에도 원본 기록을 넣지 않습니다.</p>',
      '<div class="setup-setting-actions"><button type="button" id="vasSetupToggleMemory">기억 사용</button><button type="button" id="vasSetupTogglePause">잠시 중지</button><button type="button" id="vasSetupDeleteMemory">기억 내용 삭제</button><button type="button" id="vasSetupReset">설정 전체 초기화</button></div>',
      '<p class="setup-setting-feedback" id="vasSetupFeedback" role="status"></p></div></dialog>'
    ].join('');
    document.body.append.apply(document.body, Array.from(holder.children));
    helpDialog = document.getElementById('vasSetupHelp');
    settingsDialog = document.getElementById('vasSetupSettings');
  }

  async function memoryStatus() {
    if (!global.VASPersonalization) return { available: false, consent: false, paused: false, count: 0 };
    await global.VASPersonalization.init();
    const status = await global.VASPersonalization.status();
    return Object.assign({ available: true }, status);
  }

  function feedback(message) {
    const node = document.getElementById('vasSetupFeedback');
    if (node) node.textContent = message || '';
  }

  async function refresh() {
    const status = await memoryStatus();
    const state = document.getElementById('vasSetupMemoryState');
    const toggle = document.getElementById('vasSetupToggleMemory');
    const pause = document.getElementById('vasSetupTogglePause');
    if (!status.available) {
      state.textContent = '이 실행본에서는 사용하지 않음';
      toggle.disabled = true;
      pause.disabled = true;
      return;
    }
    state.textContent = status.consent !== true ? '사용 안 함' : status.paused ? '잠시 중지됨' : '사용 중 · ' + status.count + '건';
    toggle.textContent = status.consent === true ? '기억 사용 끄기' : '기억 사용 켜기';
    pause.textContent = status.paused ? '기억 다시 시작' : '기억 잠시 중지';
    pause.disabled = status.consent !== true;
  }

  async function toggleMemory() {
    const status = await memoryStatus();
    if (!status.available) return;
    const enabled = status.consent !== true;
    await global.VASPersonalization.consent(enabled);
    if (enabled) await global.VASPersonalization.pause(false);
    if (global.VASStorage) VASStorage.writeText('vasPersonalizationConsent', enabled ? 'accepted' : 'declined');
    feedback(enabled ? '작업 기억을 켰습니다.' : '새 기록을 중지했습니다. 기존 기억은 삭제 버튼을 누르기 전까지 남습니다.');
    await refresh();
  }

  async function togglePause() {
    const status = await memoryStatus();
    if (!status.available || status.consent !== true) return;
    await global.VASPersonalization.pause(!status.paused);
    feedback(status.paused ? '작업 기억을 다시 시작했습니다.' : '작업 기억을 잠시 중지했습니다.');
    await refresh();
  }

  async function deleteMemory() {
    if (!global.VASPersonalization || !global.confirm('저장된 작업 기억을 모두 지울까요?')) return;
    await global.VASPersonalization.clear();
    feedback('저장된 작업 기억을 삭제했습니다.');
    await refresh();
  }

  async function resetSettings() {
    if (!global.confirm('작업 기억과 디자인 설정을 기본값으로 되돌릴까요? 프로젝트 폴더와 작성 중인 내용은 지우지 않습니다.')) return;
    if (global.VASPersonalization) {
      await global.VASPersonalization.clear();
      await global.VASPersonalization.consent(false);
      await global.VASPersonalization.pause(false);
    }
    if (global.VASStorage) {
      ['vasPersonalizationConsent', 'vasFavorites', 'vasThemeHistory', 'vasThemeTokens', 'vasCurrentPreset', 'vasTasteProfileMode', 'vasThemeTokensVersion', 'vasThemeStateMeta'].forEach(function (key) { VASStorage.remove(key); });
    }
    feedback('설정을 초기화했습니다. 다음 화면부터 기본 디자인을 사용합니다.');
    await refresh();
  }

  async function openSettings() {
    feedback('');
    await refresh();
    open(settingsDialog);
  }

  function init() {
    if (initialized) return;
    initialized = true;
    dialogs();
    document.querySelectorAll('[data-setup-help]').forEach(function (button) { button.addEventListener('click', function () { open(helpDialog); }); });
    document.querySelectorAll('[data-setup-settings]').forEach(function (button) { button.addEventListener('click', function () { openSettings().catch(function () {}); }); });
    document.querySelectorAll('[data-setup-close]').forEach(function (button) { button.addEventListener('click', function () { close(button.closest('dialog')); }); });
    document.getElementById('vasSetupToggleMemory').addEventListener('click', function () { toggleMemory().catch(function () { feedback('설정을 바꾸지 못했습니다. 다시 시도해 주세요.'); }); });
    document.getElementById('vasSetupTogglePause').addEventListener('click', function () { togglePause().catch(function () { feedback('설정을 바꾸지 못했습니다. 다시 시도해 주세요.'); }); });
    document.getElementById('vasSetupDeleteMemory').addEventListener('click', function () { deleteMemory().catch(function () { feedback('기억을 삭제하지 못했습니다.'); }); });
    document.getElementById('vasSetupReset').addEventListener('click', function () { resetSettings().catch(function () { feedback('설정을 초기화하지 못했습니다.'); }); });
  }

  global.VASSetupTools = Object.freeze({ init: init, openHelp: function () { open(helpDialog); }, openSettings: openSettings, refresh: refresh });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})(window);
