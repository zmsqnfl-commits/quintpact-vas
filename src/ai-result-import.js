/** VAS-AI-RESULT.json 파일·붙여넣기 검토와 다음 반복 연결 UI. */
(function (global) {
  'use strict';

  const MAX_BYTES = 256 * 1024;
  const moduleSource = document.currentScript && document.currentScript.src;
  const contractScript = document.querySelector('script[src$="agent-contract.js"]');
  const styleUrl = new URL('handoff-loop.css', moduleSource || contractScript && contractScript.src || document.baseURI);
  let dialog;
  let options = {};
  let current = null;
  let verification = null;
  let inputRevision = 0;
  let closeTimer = null;
  let legacyCandidate = null;

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
    global.clearTimeout(closeTimer);
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
      '<section id="vasResultLegacy" class="result-legacy" hidden><h3>이전 숫자 형식 복구 제안</h3><p>원본은 변경하지 않습니다. 아래 변환을 승인하면 일반 검증을 다시 실행합니다.</p><ul id="vasResultLegacyChanges"></ul><button type="button" id="vasResultLegacyApprove">표시된 변환 승인 후 다시 검증</button></section>',
      '<section class="result-review" id="vasResultReview" hidden><div class="result-review-grid"><div><span>AI 보고</span><strong id="vasResultState"></strong></div><div><span>반복</span><strong id="vasResultIteration"></strong></div><div><span>변경 파일</span><strong id="vasResultFiles"></strong></div><div><span>AI 제출 테스트</span><strong id="vasResultTests"></strong></div></div>',
      '<div class="result-assessment"><span>VAS 평가</span><strong id="vasResultAssessment"></strong><p id="vasResultAssessmentReason"></p><p>사용자 수용: <b id="vasResultUserAcceptance">미확인</b>. 다음 작업 연결과 완료 판정은 별개입니다.</p></div>',
      '<h3>작업 요약</h3><p id="vasResultSummary"></p><h3>남은 작업</h3><ul id="vasResultRemaining"></ul>',
      '<details class="result-evidence"><summary>완료조건별 직접 확인</summary><p>AI가 제출한 통과 표시·로그·해시는 직접 확인 기록이 아닙니다. 실제 산출물을 확인한 내용만 적으세요. 이 기록도 독립 보안 감사나 실행 보증은 아닙니다.</p><p id="vasResultArtifact"></p><div id="vasResultCriteria"></div></details>',
      '<div class="result-confirmations"><label id="vasResultManualRow" hidden><input type="checkbox" id="vasResultManual"> 원본 인계와 연결된 결과임을 직접 확인했습니다. 완료 확인은 아닙니다.</label><label id="vasResultRedactionRow" hidden><input type="checkbox" id="vasResultRedaction"> 민감 정보가 제거된 결과로 계속합니다.</label><label><input type="checkbox" id="vasResultUserAccepted"> VAS 평가와 별개로, 확인된 한계를 포함해 이 결과를 수용합니다. <small>선택 사항 · 완료 판정을 변경하지 않습니다.</small></label><label id="vasResultRememberRow" hidden><input type="checkbox" id="vasResultRemember"> 경로를 제외한 안전한 결과 요약을 작업 기억에 저장합니다.</label></div>',
      '<label class="result-correction" for="vasResultCorrection">추가로 고칠 내용 <small>수정 요청으로 반영할 때 필수</small><textarea id="vasResultCorrection" maxlength="2000"></textarea></label><div class="result-accept-actions"><button type="button" id="vasResultAccept">다음 작업에 반영</button><button type="button" id="vasResultRevise">수정 요청으로 반영</button></div></section>',
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
    node('vasResultUserAccepted').addEventListener('change', function () { node('vasResultUserAcceptance').textContent = this.checked ? '수용 선택 (아직 저장 전)' : '미확인'; });
    node('vasResultLegacyApprove').addEventListener('click', function () {
      if (legacyCandidate) readText(JSON.stringify(legacyCandidate.document));
    });
  }

  function sourceType() { return typeof options.sourceType === 'function' ? options.sourceType() : options.sourceType; }
  function validationMessages(checked) {
    if (!checked.errorCodes || !checked.errorCodes.length) return checked.errors.join(' ');
    const labels = { invalid_result_format: '지원하는 결과 JSON 형식과 버전을 확인해 주세요.',
      invalid_iteration: '반복 번호는 1~9999 사이의 정수 숫자여야 합니다.', invalid_handoff_hash: '원본 인계 JSON 해시 형식이 올바르지 않습니다.',
      invalid_handoff_id: '원본 인계 식별자 형식이 올바르지 않습니다.', invalid_result_id: '결과 식별자 형식이 올바르지 않습니다.',
      source_type_mismatch: '현재 작업 종류와 결과의 작업 종류가 다릅니다.', invalid_source_type: '작업 종류를 확인해 주세요.',
      invalid_safety_confirmation: '비밀값·절대 경로·원본 명령 출력을 제외했는지 확인해 주세요.',
      invalid_test_status: '테스트 결과 상태 형식을 확인해 주세요.', invalid_result_status: 'AI가 보고한 작업 상태 형식을 확인해 주세요.' };
    return checked.errorCodes.map(function (code) {
      if (labels[code]) return labels[code];
      if (/path|entrypoint/.test(code)) return '결과에 허용되지 않은 경로 형식이 있습니다.';
      if (code.indexOf('too_many_') === 0) return '결과 항목 수가 허용 범위를 넘었습니다. 생략하거나 자르지 않은 유효한 결과를 다시 받아 주세요.';
      if (code.indexOf('too_long_') === 0) return '결과 내용이 허용 길이를 넘었습니다. 요약한 결과를 다시 받아 주세요.';
      return '결과 JSON의 항목 형식이 올바르지 않습니다. 작성한 AI에게 다시 확인해 주세요.';
    }).join(' ');
  }

  const assessmentLabels = { complete: '완료 · 합의된 범위의 직접 확인 기록 있음', incomplete: '미완료', 'needs-verification': '확인 필요', invalid: '평가 불가' };
  function assessmentReason(code) {
    const labels = { 'missing-required-criteria': '원본 인계에 필수 완료조건이 없습니다.', 'missing-artifact-version': '확인할 산출물 버전이 없습니다.',
      'handoff-unverified': '원본 인계 연결을 확인할 수 없습니다.', 'handoff-mismatch': '원본 인계와 일치하지 않습니다.',
      'failed-test': '실패한 테스트가 남아 있습니다.', 'unresolved-blocker': '차단 문제가 남아 있습니다.',
      'scope-violation': '허용된 작업 범위를 벗어났다고 보고되었습니다.', 'reported-failure': '작업 실패가 보고되었습니다.',
      'invalid-result': '결과 형식이 올바르지 않습니다.', 'invalid-criteria': '원본 완료조건 형식을 확인해야 합니다.',
      'assessment-unavailable': '평가 모듈을 불러오지 못했습니다.' };
    if (code.indexOf('unconfirmed-criterion:') === 0) return code.split(':')[1] + ' 직접 확인 근거가 없습니다.';
    if (code.indexOf('failed-criterion:') === 0) return code.split(':')[1] + ' 실패가 기록되어 있습니다.';
    if (code.indexOf('artifact-evidence-mismatch:') === 0) return code.split(':')[1] + ' 제출 근거가 다른 산출물 버전을 가리킵니다. 같은 버전의 결과를 다시 받아 주세요.';
    return labels[code] || code;
  }
  function element(tag, text, attributes) {
    const value = document.createElement(tag);
    if (text) value.textContent = text;
    Object.keys(attributes || {}).forEach(function (name) { value.setAttribute(name, attributes[name]); });
    return value;
  }
  function field(parent, label, control) {
    const row = element('label', label); row.append(control); parent.append(row); return control;
  }
  function selectOptions(values, selected) {
    const control = element('select');
    values.forEach(function (item) { const option = element('option', item[1], { value: item[0] }); option.selected = item[0] === selected; control.append(option); });
    return control;
  }
  function renderAssessment() {
    const state = global.VASHandoffWorkflow && VASHandoffWorkflow.review
      ? VASHandoffWorkflow.review(current)
      : { assessment: { status: 'needs-verification', reasons: ['assessment-unavailable'] }, criteria: [], observations: [] };
    node('vasResultAssessment').textContent = assessmentLabels[state.assessment.status] || '확인 필요';
    node('vasResultAssessment').dataset.state = state.assessment.status;
    node('vasResultAssessmentReason').textContent = state.assessment.reasons.map(assessmentReason).join(' ') || '필수 조건을 현재 산출물 버전에서 직접 확인했습니다. 확인 방법과 범위 안에서의 판정입니다.';
    node('vasResultArtifact').textContent = 'AI가 제출한 산출물 버전: ' + (current.artifactVersion || '없음') + ' · 제출 근거 ' + (current.evidence || []).length + '건 (직접 검증 전)';
    const host = node('vasResultCriteria'); host.replaceChildren();
    if (!global.VASResultAssessment || !VASResultAssessment.criteriaValid(state.criteria) || !state.criteria.length) {
      host.append(element('p', '원본 인계의 완료조건이 없어 완료를 판정할 수 없습니다. 조건을 정한 새 작업으로 이어갈 수 있습니다.')); return;
    }
    state.criteria.forEach(function (criterion) {
      const own = state.observations.find(function (item) { return item.criterionId === criterion.id; });
      const box = element('fieldset', '', { 'data-criterion-id': criterion.id });
      box.append(element('legend', criterion.id + ' · ' + (criterion.required ? '필수' : '선택') + ' · ' + criterion.description));
      box.append(element('p', '합의된 확인 방법: ' + criterion.method));
      const version = field(box, '직접 확인한 산출물 버전', element('input', '', { type: 'text', maxlength: '200', 'data-review-version': '' }));
      version.value = own ? own.artifactVersion : '';
      const method = field(box, '직접 수행한 확인 방법', selectOptions([['manual', '실제 사용·실행 확인'], ['static', '문서·코드·화면 비교 확인']], own ? own.method : criterion.method === 'static' ? 'static' : 'manual'));
      method.setAttribute('data-review-method', '');
      const alternative = element('input', '', { type: 'checkbox', 'data-review-alternative': '' });
      alternative.checked = !!(own && own.alternativeApproved);
      field(box, '원래 방법을 대신해 이 방법으로 조건을 확인하는 것을 승인합니다. 방법이 다르면 필수입니다.', alternative);
      const outcome = field(box, '확인 결과', selectOptions([['', '선택'], ['passed', '통과'], ['failed', '실패'], ['skipped', '확인하지 못함'], ['not-applicable', '이 방법으로 확인할 수 없음']], own ? own.outcome : ''));
      outcome.setAttribute('data-review-outcome', '');
      const summary = field(box, '직접 관찰한 내용 · 비밀값·원본 로그·절대 경로 제외', element('textarea', '', { maxlength: '1000', 'data-review-summary': '' }));
      summary.value = own ? own.summary : '';
      if (own) box.append(element('p', '사용자가 직접 기록한 확인: ' + own.observedAt));
      const button = element('button', '이 조건의 직접 확인 기록 저장', { type: 'button', 'data-review-save': '' });
      button.disabled = !current.artifactVersion || verification.status !== 'verified';
      button.addEventListener('click', function () {
        const recorded = VASHandoffWorkflow.recordObservation(current, { criterionId: criterion.id,
          artifactVersion: version.value.trim(), method: method.value, outcome: outcome.value,
          summary: summary.value, alternativeApproved: alternative.checked });
        if (!recorded.ok) { setStatus(recorded.message, true); return; }
        renderAssessment(); setStatus(criterion.id + ' 직접 확인 기록을 저장했습니다. 사용자 수용과 완료 평가는 별개입니다.');
      });
      box.append(button); host.append(box);
    });
  }

  function render(result, checked) {
    current = result;
    verification = checked;
    node('vasResultReview').hidden = false;
    node('vasResultState').textContent = result.reportedStatus || result.status;
    node('vasResultUserAccepted').checked = false;
    node('vasResultUserAcceptance').textContent = '미확인';
    node('vasResultIteration').textContent = String(result.iteration) + (result.iteration >= 9999 ? ' · 새 인계 필요' : ' → ' + String(result.iteration + 1));
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
    const locked = ['mismatch', 'duplicate'].includes(checked.status) || result.iteration >= 9999;
    node('vasResultAccept').disabled = locked;
    node('vasResultRevise').disabled = locked;
    renderAssessment();
  }

  function readText(text) {
    inputRevision += 1;
    global.clearTimeout(closeTimer);
    current = null;
    verification = null;
    legacyCandidate = null;
    node('vasResultLegacy').hidden = true;
    node('vasResultReview').hidden = true;
    const source = String(text || '').replace(/^\uFEFF/, '');
    if (new Blob([source]).size > MAX_BYTES) { setStatus('결과 JSON은 256KiB보다 작아야 합니다.', true); return; }
    let raw;
    try { raw = JSON.parse(source); } catch (error) { setStatus('JSON 문법이 올바르지 않습니다.', true); return; }
    const checked = VASAgentContract.validateResult(raw, sourceType());
    if (!checked.ok) {
      node('vasResultReview').hidden = true; setStatus(validationMessages(checked), true);
      const repaired = VASAgentContract.repairLegacyNumbers && VASAgentContract.repairLegacyNumbers(raw);
      if (repaired && repaired.requiresConfirmation) {
        legacyCandidate = repaired; node('vasResultLegacy').hidden = false;
        const changes = node('vasResultLegacyChanges'); changes.replaceChildren();
        repaired.conversions.forEach(function (change) { changes.append(element('li', change.field + ': ' + JSON.stringify(change.from) + ' → ' + change.to)); });
      }
      return;
    }
    checked.result.__redactions = checked.redactions;
    const linked = global.VASHandoffWorkflow ? VASHandoffWorkflow.verifyResult(checked.result) : { status: 'unverified', message: '연결 기록을 확인할 수 없습니다.' };
    render(checked.result, linked);
    const messages = checked.warnings.concat(linked.message || '').filter(Boolean);
    if (checked.result.iteration >= 9999) messages.push('최대 반복 번호입니다. 새 인계를 만들어 다음 작업을 시작해 주세요.');
    setStatus(messages.join(' '), linked.status === 'mismatch' || linked.status === 'duplicate');
  }

  function readFile(file) {
    const revision = ++inputRevision;
    global.clearTimeout(closeTimer);
    current = null;
    verification = null;
    legacyCandidate = null;
    node('vasResultLegacy').hidden = true;
    node('vasResultReview').hidden = true;
    if (file.size > MAX_BYTES) { setStatus('결과 JSON은 256KiB보다 작아야 합니다.', true); return; }
    const reader = new FileReader();
    reader.onload = function () { if (revision === inputRevision) readText(reader.result); };
    reader.onerror = function () { if (revision === inputRevision) setStatus('결과 파일을 읽지 못했습니다.', true); };
    reader.readAsText(file, 'utf-8');
  }

  function accept(verdict) {
    if (current && global.VASHandoffWorkflow) {
      const previousStatus = verification && verification.status;
      verification = VASHandoffWorkflow.verifyResult(current);
      if (verification.status !== previousStatus) { render(current, verification); setStatus(verification.message, verification.status !== 'verified'); return; }
      if (['mismatch', 'duplicate'].includes(verification.status)) { setStatus(verification.message, true); render(current, verification); return; }
    }
    if (!current || !verification || ['mismatch', 'duplicate'].includes(verification.status)) return;
    if (current.iteration >= 9999) { setStatus('최대 반복 번호입니다. 새 인계를 만들어 다음 작업을 시작해 주세요.', true); return; }
    if (verification.status === 'unverified' && !node('vasResultManual').checked) { setStatus('원본 인계와 연결된 결과인지 확인해 주세요.', true); node('vasResultManual').focus(); return; }
    if (current.__redactions && !node('vasResultRedaction').checked) { setStatus('민감 정보 제거 후 계속하는 것에 확인해 주세요.', true); node('vasResultRedaction').focus(); return; }
    const correction = node('vasResultCorrection').value.trim();
    if (verdict === 'needs-revision' && !correction) { setStatus('수정이 필요한 내용을 적어주세요.', true); node('vasResultCorrection').focus(); return; }
    delete current.__redactions;
    const state = VASHandoffWorkflow.acceptResult(current, verdict, correction, node('vasResultUserAccepted').checked);
    if (!state) { setStatus('이미 반영했거나 연결할 수 없는 결과입니다.', true); return; }
    if (node('vasResultRemember').checked && global.VASPersonalization) {
      VASPersonalization.record({
        type: 'workflow_completed', source: 'ai-result',
        payload: { status: state.context.assessment.status, reportedStatus: current.reportedStatus || current.status,
          summary: current.changes.summary, nextTask: current.nextRecommendedTask, verdict: verdict }
      }).catch(function () { setStatus('결과는 연결했지만 작업 기억을 저장하지 못했습니다.', true); });
    }
    if (typeof options.onAccepted === 'function') options.onAccepted(state, current);
    setStatus('이 결과를 다음 작업에 연결했습니다. 반복 번호는 ' + state.workflow.iteration + '입니다.');
    closeTimer = global.setTimeout(close, 500);
  }

  function init(settings) {
    options = settings || {};
    const styled = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).some(function (link) {
      const url = new URL(link.href, document.baseURI);
      return url.origin === styleUrl.origin && url.pathname === styleUrl.pathname;
    });
    if (!styled) {
      const link = document.createElement('link');
      link.rel = 'stylesheet'; link.href = styleUrl.href;
      document.head.append(link);
    }
    if (!dialog) createDialog();
    document.querySelectorAll('[data-result-import]').forEach(function (button) { button.addEventListener('click', open); });
  }

  global.VASAIResultImport = Object.freeze({ init: init, open: open, readText: readText, current: function () { return current; } });
})(window);
