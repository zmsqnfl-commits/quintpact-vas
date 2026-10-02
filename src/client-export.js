/** 새 프로젝트 입력을 공통 VAS-AI-HANDOFF.json으로 내보냅니다. */
(function (global) {
  'use strict';

  let prepared = null;
  let inputRevision = 0;
  let preparation = 0;
  let preparedSignature = '';
  VASTaskInputs.mount('completionConditions');

  function collectApplicationData(form, files) {
    const data = {};
    form.querySelectorAll('input, textarea, select').forEach(function (element) {
      if (!element.name || element.disabled || ['file', 'button', 'submit', 'reset'].includes(element.type) || element.name === 'attached_files') return;
      if (element.type === 'checkbox' || element.type === 'radio') {
        if (element.checked) data[element.name] = (data[element.name] || []).concat(element.value);
      } else if (typeof element.value === 'string' && element.value.trim()) {
        data[element.name] = element.value.trim();
      }
    });
    data.attachment_count = Array.isArray(files) ? files.length : 0;
    return data;
  }

  async function prepare() {
    const form = document.getElementById('projectForm');
    const criteria = VASTaskInputs.validate('completionConditions');
    const values = collectApplicationData(form, typeof uploadedFiles === 'undefined' ? [] : uploadedFiles);
    const design = VASSetupDesign.context();
    const revision = inputRevision;
    const request = ++preparation;
    const signature = JSON.stringify([values, design]);
    prepared = null;
    const result = await VASAgentHandoffWeb.buildNew(values, design, {
      completionCriteria: criteria,
      rag: { included: false, items: [] }, ragReviewed: false,
      continuation: { included: false }
    });
    if (revision !== inputRevision || request !== preparation || signature !== currentSignature()) {
      throw new Error('준비 중 내용이 변경되었습니다. 최신 입력으로 다시 준비해 주세요.');
    }
    prepared = result;
    preparedSignature = signature;
    const preview = document.getElementById('handoffReview');
    if (preview) preview.textContent = prepared.pasteText;
    VASTaskInputs.review(prepared.document, 'handoffInputReview');
    const heading = document.querySelector('#doneScreen h2');
    if (heading) heading.textContent = 'READY.';
    return prepared;
  }

  function currentSignature() {
    return JSON.stringify([collectApplicationData(document.getElementById('projectForm'), typeof uploadedFiles === 'undefined' ? [] : uploadedFiles), VASSetupDesign.context()]);
  }
  function invalidate() {
    inputRevision += 1; prepared = null; preparedSignature = '';
    document.getElementById('handoffReview').textContent = '내용 변경됨 · 다시 준비 필요';
    const status = document.getElementById('handoffStatus');
    status.textContent = '내용 변경됨 · 다시 준비 필요'; status.hidden = false;
    const heading = document.querySelector('#doneScreen.active h2');
    if (heading) heading.textContent = 'REVIEW.';
  }
  function ensureCurrent(result) {
    if (prepared !== result || preparedSignature !== currentSignature()) throw new Error('내용이 변경되었습니다. 최신 입력으로 다시 준비해 주세요.');
  }

  function showStatus(message) {
    const status = document.getElementById('handoffStatus');
    status.hidden = false;
    status.textContent = message;
  }

  async function exportJson() {
    try {
      const result = await prepare();
      VASTaskInputs.confirm(result.document, 'handoffInputReview');
      ensureCurrent(result);
      await VASAgentHandoffWeb.save(result.document, 'VAS-AI-HANDOFF.json');
      const draftFailed = global.VASClientDraft && VASClientDraft.clear() === false;
      let message = 'JSON을 저장했습니다. 필요하면 프롬프트와 함께 코딩 도구에 전달하세요.';
      if (draftFailed) message += ' 브라우저 초안은 삭제하지 못했습니다.';
      showStatus(message);
      try { await VASSetupDesign.confirm(); } catch (error) { showStatus(message + ' 작업 기억은 저장하지 못했습니다.'); }
    } catch (error) {
      showStatus(error && error.message ? error.message : 'JSON을 만들지 못했습니다.');
    }
  }

  async function copyNewProjectPrompt() {
    try {
      const result = await prepare();
      VASTaskInputs.confirm(result.document, 'handoffInputReview');
      await VASAgentHandoffWeb.refreshIntegrity(result.document);
      ensureCurrent(result);
      VASAgentHandoffWeb.assertReviewed(result.document);
      await VASAgentHandoffWeb.copy(VASAgentHandoffWeb.prompt(result.document, 'universal'));
      showStatus('프롬프트를 복사했습니다. 코딩 도구에 붙여넣은 뒤 VAS는 닫아도 됩니다.');
      try { await VASSetupDesign.confirm(); } catch (error) { showStatus('프롬프트를 복사했습니다. 작업 기억은 저장하지 못했습니다.'); }
    } catch (error) {
      showStatus(error && error.message ? error.message : '자동 복사를 사용할 수 없습니다.');
    }
  }

  VASSetupDesign.mount('projectDesignPreset', 'projectDesignSummary');
  function changedInput(event) {
    if (event.target.closest('#handoffInputReview')) return;
    invalidate();
  }
  document.getElementById('projectForm').addEventListener('input', changedInput);
  document.getElementById('projectForm').addEventListener('change', changedInput);
  let designSignature = JSON.stringify(VASSetupDesign.context());
  global.addEventListener('vas-theme-state', function () {
    const next = JSON.stringify(VASSetupDesign.context());
    if (next !== designSignature) { designSignature = next; invalidate(); }
  });
  global.collectApplicationData = collectApplicationData;
  global.exportJson = exportJson;
  global.copyNewProjectPrompt = copyNewProjectPrompt;
  global.VASNewHandoff = Object.freeze({ prepare: prepare, get: function () { return prepared; } });
})(window);
