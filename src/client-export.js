/** 새 프로젝트 입력을 공통 VAS-AI-HANDOFF.json으로 내보냅니다. */
(function (global) {
  'use strict';

  let prepared = null;

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
    data.attached_files = Array.isArray(files) ? files.slice() : [];
    return data;
  }

  function review(document) {
    return {
      project: document.project,
      task: document.task,
      requirements: document.context.requirements.value,
      design: {
        preset: document.context.design.preset,
        tasteProfileMode: document.context.design.tasteProfileMode,
        tokens: document.context.design.tokens
      },
      safety: document.security.warnings
    };
  }

  async function prepare() {
    const form = document.getElementById('projectForm');
    const values = collectApplicationData(form, typeof uploadedFiles === 'undefined' ? [] : uploadedFiles);
    prepared = await VASAgentHandoffWeb.buildNew(values, VASSetupDesign.context());
    const preview = document.getElementById('handoffReview');
    if (preview) preview.textContent = JSON.stringify(review(prepared.document), null, 2);
    return prepared;
  }

  function showStatus(message) {
    const status = document.getElementById('handoffStatus');
    status.hidden = false;
    status.textContent = message;
  }

  async function exportJson() {
    try {
      const result = await prepare();
      VASAgentHandoffWeb.save(result.document, 'VAS-AI-HANDOFF.json');
      if (global.VASClientDraft) VASClientDraft.clear();
      if (global.VASPersonalization) VASPersonalization.record({ type: 'export', source: 'new-project', payload: { format: 'vas-ai-handoff', design: result.document.context.design.preset } });
      showStatus('VAS-AI-HANDOFF.json을 저장했습니다. 이제 코딩 도구에 첨부하세요.');
    } catch (error) {
      showStatus(error && error.message ? error.message : 'JSON을 만들지 못했습니다.');
    }
  }

  async function copyNewProjectPrompt() {
    try {
      const result = prepared || await prepare();
      await VASAgentHandoffWeb.copy(VASAgentHandoffWeb.prompt(result.document, 'universal'));
      showStatus('프롬프트를 복사했습니다. 코딩 도구에 붙여넣으세요.');
    } catch (error) {
      showStatus('자동 복사를 사용할 수 없습니다. JSON의 assistantGuide.pasteText를 복사해 주세요.');
    }
  }

  VASSetupDesign.mount('projectDesignPreset', 'projectDesignSummary');
  global.collectApplicationData = collectApplicationData;
  global.exportJson = exportJson;
  global.copyNewProjectPrompt = copyNewProjectPrompt;
  global.VASNewHandoff = Object.freeze({ prepare: prepare, get: function () { return prepared; } });
})(window);
