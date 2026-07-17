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
      workflow: document.workflow,
      project: document.project,
      task: document.task,
      requirements: document.context.requirements.value,
      design: {
        preset: document.context.design.preset,
        tasteProfileMode: document.context.design.tasteProfileMode,
        tokens: document.context.design.tokens
      },
      approvedRag: document.context.rag,
      continuation: document.context.continuation,
      qualityGate: document.qualityGate,
      safety: document.security.warnings
    };
  }

  async function prepare() {
    const form = document.getElementById('projectForm');
    const values = collectApplicationData(form, typeof uploadedFiles === 'undefined' ? [] : uploadedFiles);
    const linked = global.VASHandoffWorkflow && VASHandoffWorkflow.current();
    prepared = await VASAgentHandoffWeb.buildNew(values, VASSetupDesign.context(), {
      rag: global.VASHandoffContextReview ? VASHandoffContextReview.context() : { included: false, items: [] },
      ragReviewed: global.VASHandoffContextReview ? VASHandoffContextReview.isReviewed() : true,
      continuation: linked ? linked.context : { included: false }, workflow: linked ? linked.workflow : null
    });
    const preview = document.getElementById('handoffReview');
    if (preview) preview.textContent = JSON.stringify(review(prepared.document), null, 2);
    return prepared;
  }

  function showStatus(message) {
    const status = document.getElementById('handoffStatus');
    status.hidden = false;
    status.textContent = message;
  }

  function showLoopStatus(message) {
    const status = document.getElementById('newLoopStatus');
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
  }

  async function exportJson() {
    try {
      const result = await prepare();
      VASAgentHandoffWeb.save(result.document, 'VAS-AI-HANDOFF.json');
      if (global.VASHandoffWorkflow) VASHandoffWorkflow.remember(result.document);
      if (global.VASClientDraft) VASClientDraft.clear();
      if (global.VASPersonalization) VASPersonalization.record({ type: 'export', source: 'new-project', payload: { format: 'vas-ai-handoff', design: result.document.context.design.preset } });
      showStatus('VAS-AI-HANDOFF.json을 저장했습니다. 이제 코딩 도구에 첨부하세요.');
    } catch (error) {
      showStatus(error && error.message ? error.message : 'JSON을 만들지 못했습니다.');
    }
  }

  async function copyNewProjectPrompt() {
    try {
      const result = await prepare();
      if (global.VASHandoffWorkflow) VASHandoffWorkflow.remember(result.document);
      await VASAgentHandoffWeb.copy(VASAgentHandoffWeb.prompt(result.document, 'universal'));
      showStatus('프롬프트를 복사했습니다. 코딩 도구에 붙여넣으세요.');
    } catch (error) {
      showStatus('자동 복사를 사용할 수 없습니다. JSON의 assistantGuide.pasteText를 복사해 주세요.');
    }
  }

  VASSetupDesign.mount('projectDesignPreset', 'projectDesignSummary');
  if (global.VASHandoffContextReview) VASHandoffContextReview.mount('newProjectContextReview', {
    query: function () {
      return [document.getElementById('problemDescription').value, document.getElementById('projectExtra').value, VASSetupDesign.context().preset].join(' ');
    },
    onChange: function () { prepared = null; }
  });
  if (global.VASAIResultImport) VASAIResultImport.init({
    sourceType: 'new',
    onAccepted: function (state) {
      prepared = null;
      const message = 'AI 결과를 연결했습니다. 다음 인계는 ' + state.workflow.iteration + '번째 작업입니다.';
      showLoopStatus(message + ' 요구사항을 확인한 뒤 계속하세요.');
      showStatus(message);
    }
  });
  document.getElementById('projectDesignPreset').addEventListener('change', function () {
    prepared = null;
    if (global.VASHandoffContextReview) VASHandoffContextReview.invalidate();
  });
  global.collectApplicationData = collectApplicationData;
  global.exportJson = exportJson;
  global.copyNewProjectPrompt = copyNewProjectPrompt;
  global.VASNewHandoff = Object.freeze({ prepare: prepare, get: function () { return prepared; } });
})(window);
