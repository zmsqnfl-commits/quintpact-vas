/** VAS-AI-RESULT.json 파일·붙여넣기 검토와 다음 반복 연결 UI. */
(function (global) {
  'use strict';

  const MAX_BYTES = 256 * 1024;
  let dialog;
  let options = {};
  let current = null;
  let verification = null;

  function node(id) { return dialog.querySelector('#' + id); }
  function setStatus(message, error) {
    const target = node('vasResultStatus');
    target.textContent = message || '';
    target.dataset.error = error ? 'true' : 'false';
  }

  function close() {
    if (dialog && typeof dialog.close === 'function') dialog.close();
    else if (dialog) dialog.removeAttribute('open');
  }

  function open() {
    if (!dialog) return;
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    updateMemoryOption();
    node('vasResultFileButton').focus();
  }

  async function updateMemoryOption() {
    const row = node('vasResultRememberRow');
    row.hidden = true;
    node('vasResultRemember').checked = false;
    if (!global.VASPersonalization) return;
    try {
      const state = await VASPersonalization.status();
      row.hidden = state.consent !== true || state.paused;
    } catch (error) { row.hidden = true; }
  }

  function createDialog() {
    dialog = document.createElement('dialog');
    dialog.className = 'result-dialog';
    dialog.setAttribute('aria-labelledby', 'vasResultTitle');
    dialog.innerHTML = [
      '<div class="result-dialog-shell">',
      '<div class="result-dialog-head"><div><span>AI RESULT</span><h2 id="vasResultTitle">AI 작업 결과를 이어서 사용합니다.</h2></div><button type="button" data-result-close>닫기</button></div>',
      '<p class="result-dialog-copy">코딩 AI가 만든 <b>VAS-AI-RESULT.json</b>을 선택하거나 JSON 내용을 붙여넣으세요. 파일은 외부로 전송되지 않습니다.</p>',
      '<div class="result-source-actions"><button type="button" id="vasResultFileButton">결과 JSON 선택</button><button type="button" id="vasResultPasteButton">JSON 붙여넣기</button></div>',
      '<input type="file" id="vasResultFile" accept="application/json,.json" hidden>',
      '<div class="result-paste" id="vasResultPasteBox" hidden><label for="vasResultPaste">결과 JSON 내용</label><textarea id="vasResultPaste" spellcheck="false" placeholder="{ &quot;format&quot;: &quot;vas-ai-result&quot;, ... }"></textarea><button type="button" id="vasResultReadPaste">붙여넣은 내용 확인</button></div>',
      '<p class="result-status" id="vasResultStatus" role="status">결과 파일을 선택해 주세요.</p>',
      '<section class="result-review" id="vasResultReview" hidden><div class="result-review-grid"><div><span>상태</span><strong id="vasResultState"></strong></div><div><span>반복</span><strong id="vasResultIteration"></strong></div><div><span>변경 파일</span><strong id="vasResultFiles"></strong></div><div><span>테스트</span><strong id="vasResultTests"></strong></div></div><h3>작업 요약</h3><p id="vasResultSummary"></p><h3>남은 작업</h3><ul id="vasResultRemaining"></ul><div class="result-confirmations"><label id="vasResultManualRow" hidden><input type="checkbox" id="vasResultManual"> 원본 인계와 연결된 결과임을 직접 확인했습니다.</label><label id="vasResultRedactionRow" hidden><input type="checkbox" id="vasResultRedaction"> 민감 정보가 제거된 결과로 계속합니다.</label><label id="vasResultRememberRow" hidden><input type="checkbox" id="vasResultRemember"> 경로를 제외한 안전한 결과 요약을 작업 기억에 저장합니다.</label></div><label class="result-correction" for="vasResultCorrection">추가로 고칠 내용 <small>수정 요청으로 반영할 때 필수</small><textarea id="vasResultCorrection" maxlength="2000"></textarea></label><div class="result-accept-actions"><button type="button" id="vasResultAccept">다음 작업에 반영</button><button type="button" id="vasResultRevise">수정 요청으로 반영</button></div></section>',
      '</div>'
    ].join('');
    document.body.append(dialog);
    dialog.querySelector('[data-result-close]').addEventListener('click', close);
    node('vasResultFileButton').addEventListener('click', function () { node('vasResultFile').click(); });
    node('vasResultPasteButton').addEventListener('click', function () { node('vasResultPasteBox').hidden = false; node('vasResultPaste').focus(); });
    node('vasResultReadPaste').addEventListener('click', function () { readText(node('vasResultPaste').value); });
    node('vasResultFile').addEventListener('change', function () { if (node('vasResultFile').files[0]) readFile(node('vasResultFile').files[0]); });
    node('vasResultAccept').addEventListener('click', function () { accept('accepted'); });
    node('vasResultRevise').addEventListener('click', function () { accept('needs-revision'); });
  }

  function sourceType() { return typeof options.sourceType === 'function' ? options.sourceType() : options.sourceType; }

  function render(result, checked) {
    current = result;
    verification = checked;
    node('vasResultReview').hidden = false;
    node('vasResultState').textContent = result.status;
    node('vasResultIteration').textContent = String(result.iteration) + ' → ' + String(result.iteration + 1);
    node('vasResultFiles').textContent = String(result.changes.relativeFiles.length) + '개';
    const passed = result.tests.filter(function (item) { return item.status === 'passed'; }).length;
    const failed = result.tests.filter(function (item) { return item.status === 'failed'; }).length;
    node('vasResultTests').textContent = '통과 ' + passed + ' · 실패 ' + failed;
    node('vasResultSummary').textContent = result.changes.summary || result.nextRecommendedTask || '요약이 없습니다.';
    const remaining = node('vasResultRemaining'); remaining.replaceChildren();
    const entries = result.remaining.length ? result.remaining : [{ severity: 'low', summary: '남은 작업 없음', nextAction: result.nextRecommendedTask || '' }];
    entries.forEach(function (item) {
      const li = document.createElement('li');
      const title = document.createElement('strong'); title.textContent = item.severity;
      li.append(title, document.createTextNode(' · ' + (item.summary || item.nextAction || '확인 필요'))); remaining.append(li);
    });
    node('vasResultManualRow').hidden = checked.status !== 'unverified';
    node('vasResultManual').checked = checked.status === 'verified';
    node('vasResultRedactionRow').hidden = !current.__redactions;
    node('vasResultRedaction').checked = !current.__redactions;
    const locked = ['mismatch', 'duplicate'].includes(checked.status);
    node('vasResultAccept').disabled = locked;
    node('vasResultRevise').disabled = locked;
  }

  function readText(text) {
    const source = String(text || '').replace(/^\uFEFF/, '');
    if (new Blob([source]).size > MAX_BYTES) { setStatus('결과 JSON은 256KiB보다 작아야 합니다.', true); return; }
    let raw;
    try { raw = JSON.parse(source); } catch (error) { setStatus('JSON 문법이 올바르지 않습니다.', true); return; }
    const checked = VASAgentContract.validateResult(raw, sourceType());
    if (!checked.ok) { node('vasResultReview').hidden = true; setStatus(checked.errors.join(' '), true); return; }
    checked.result.__redactions = checked.redactions;
    const linked = global.VASHandoffWorkflow ? VASHandoffWorkflow.verifyResult(checked.result) : { status: 'unverified', message: '연결 기록을 확인할 수 없습니다.' };
    render(checked.result, linked);
    const messages = checked.warnings.concat(linked.message || '').filter(Boolean);
    setStatus(messages.join(' '), linked.status === 'mismatch' || linked.status === 'duplicate');
  }

  function readFile(file) {
    if (file.size > MAX_BYTES) { setStatus('결과 JSON은 256KiB보다 작아야 합니다.', true); return; }
    const reader = new FileReader();
    reader.onload = function () { readText(reader.result); };
    reader.onerror = function () { setStatus('결과 파일을 읽지 못했습니다.', true); };
    reader.readAsText(file, 'utf-8');
  }

  function accept(verdict) {
    if (!current || !verification || ['mismatch', 'duplicate'].includes(verification.status)) return;
    if (verification.status === 'unverified' && !node('vasResultManual').checked) { setStatus('원본 인계와 연결된 결과인지 확인해 주세요.', true); node('vasResultManual').focus(); return; }
    if (current.__redactions && !node('vasResultRedaction').checked) { setStatus('민감 정보 제거 후 계속하는 것에 확인해 주세요.', true); node('vasResultRedaction').focus(); return; }
    const correction = node('vasResultCorrection').value.trim();
    if (verdict === 'needs-revision' && !correction) { setStatus('수정이 필요한 내용을 적어주세요.', true); node('vasResultCorrection').focus(); return; }
    delete current.__redactions;
    const state = VASHandoffWorkflow.acceptResult(current, verdict, correction);
    if (node('vasResultRemember').checked && global.VASPersonalization) {
      VASPersonalization.record({
        type: 'workflow_completed', source: 'ai-result',
        payload: { status: current.status, summary: current.changes.summary, nextTask: current.nextRecommendedTask, verdict: verdict }
      });
    }
    if (typeof options.onAccepted === 'function') options.onAccepted(state, current);
    setStatus('이 결과를 다음 작업에 연결했습니다. 반복 번호는 ' + state.workflow.iteration + '입니다.');
    global.setTimeout(close, 500);
  }

  function init(settings) {
    options = settings || {};
    if (!dialog) createDialog();
    document.querySelectorAll('[data-result-import]').forEach(function (button) { button.addEventListener('click', open); });
  }

  global.VASAIResultImport = Object.freeze({ init: init, open: open, readText: readText, current: function () { return current; } });
})(window);
