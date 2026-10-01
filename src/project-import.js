(function () {
  'use strict';

  let step = 1;
  let preview = null;
  let legacyScopeReview = false;

  function runtimeAvailable() {
    return Boolean(window.VASRuntime && VASRuntime.isAvailable());
  }

  VASThemeState.init();
  VASThemeState.decorateLinks(document);
  VASSetupDesign.mount('handoffDesignPreset', 'handoffDesignSummary');
  VASTaskInputs.mount('completionConditions');
  function designScope() { return { mode: document.getElementById('designScopeMode').value, scope: document.getElementById('designScopeDetails').value }; }
  function scopeVisibility() {
    const mode = designScope().mode;
    document.getElementById('activeDesignSettings').hidden = mode === 'preserve';
    document.getElementById('designScopeLabel').hidden = mode === 'preserve';
    document.getElementById('designScopeDetails').hidden = mode === 'preserve';
  }

  function focusStep(panel) {
    if (!panel) return;
    const target = panel.querySelector('input:not([type="hidden"]), textarea, select, button, a[href]');
    if (target) target.focus();
    else {
      const heading = panel.querySelector('h2');
      if (heading) { heading.tabIndex = -1; heading.focus(); }
    }
  }

  function go(next) {
    step = next;
    document.querySelectorAll('[data-step]').forEach(function (panel) { panel.classList.toggle('active', Number(panel.dataset.step) === step); });
    document.querySelectorAll('[data-nav-step]').forEach(function (item) {
      const number = Number(item.dataset.navStep);
      item.classList.toggle('active', number <= step);
      if (number === step) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
    });
    document.querySelector('.workspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
    saveDraft();
    window.setTimeout(function () { focusStep(document.querySelector('[data-step="' + step + '"]')); }, 0);
  }

  function showError(error) {
    const box = document.getElementById('errorBox');
    box.textContent = error && error.message ? error.message : String(error);
    box.hidden = false;
  }
  function clearError() {
    document.getElementById('errorBox').hidden = true;
    document.querySelectorAll('[aria-invalid="true"]').forEach(function (field) {
      field.removeAttribute('aria-invalid'); field.removeAttribute('aria-describedby');
    });
  }
  function invalid(field, message) {
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', 'errorBox');
    field.focus();
    showError(new Error(message));
    return false;
  }

  function taskContext() {
    const request = document.getElementById('taskRequest').value.trim();
    return {
      requirements: { included: Boolean(request), value: { request: request } },
      design: VASSetupDesign.context(designScope()),
      rag: { included: false, items: [] },
      continuation: { included: false }, preferences: { included: false, items: [] }
    };
  }

  function providerLabel() {
    const labels = { codex: 'Codex', claude: 'Claude', antigravity: 'Antigravity', universal: '코딩 AI' };
    return labels[document.getElementById('provider').value] || labels.universal;
  }

  function folderLocation() { return document.getElementById('folderPath').value.trim(); }

  function syncDesign() {
    if (!preview) return;
    const request = VASAgentContract.clean(document.getElementById('taskRequest').value, 4000);
    preview.document.project.name = VASAgentContract.clean(document.getElementById('projectName').value, 80);
    preview.document.project.summary = request;
    preview.document.task.request = request;
    preview.document.context.requirements = { included: Boolean(request), value: { request: request } };
    preview.document.context.design = VASAgentContract.sanitize(VASSetupDesign.context(designScope()));
    const changes = [];
    VASTaskPolicy.text(document.getElementById('projectName').value, 80, '프로젝트 이름', changes);
    VASTaskPolicy.text(document.getElementById('taskRequest').value, 4000, '요청', changes);
    const rawDesign = VASSetupDesign.context(designScope());
    if (VASAgentContract.stable(rawDesign) !== VASAgentContract.stable(VASAgentContract.sanitize(rawDesign))) changes.push('디자인');
    if (legacyScopeReview) changes.push('이전 초안의 디자인 범위');
    preview.document.task.constraints = [];
    VASTaskPolicy.apply(preview.document, { designScope: designScope(), completionCriteria: VASTaskInputs.read('completionConditions') }, changes);
    preview.document.context.rag = { included: false, items: [] };
    preview.document.context.continuation = { included: false };
    preview.document.context.preferences = { included: false, items: [] };
    preview.document.qualityGate.ragReviewed = false;
    preview.document.assistantGuide.target = document.getElementById('provider').value;
    preview.document.assistantGuide.pasteText = VASAgentHandoffWeb.prompt(preview.document, preview.document.assistantGuide.target);
  }

  function currentPrompt() {
    return VASAgentHandoffWeb.prompt(preview.document, preview.document.assistantGuide.target, folderLocation());
  }

  function renderPreview() {
    if (!preview) return;
    syncDesign();
    clearError();
    document.getElementById('previewContent').textContent = currentPrompt();
    VASTaskInputs.review(preview.document, 'handoffInputReview');
    document.getElementById('previewStatus').textContent = providerLabel() + ' 전달 준비됨';
    document.getElementById('copyPrompt').textContent = providerLabel() + '용 프롬프트 복사 →';
  }

  async function selectFolderLocation() {
    clearError();
    const input = document.getElementById('folderPath');
    const notice = document.getElementById('runtimeNotice');
    if (!runtimeAvailable()) {
      notice.textContent = 'Windows 폴더 선택창을 사용하려면 Run-VAS-System.bat로 실행해 주세요.';
      input.focus();
      return;
    }
    const result = await VASRuntime.request('/api/folder/select', { method: 'POST' });
    if (!result || result.cancelled || !result.selection) return;
    input.value = result.selection.path || '';
    const name = document.getElementById('projectName');
    if (!name.value.trim()) name.value = result.selection.name || '';
    notice.textContent = '위치만 선택했습니다. 폴더 내부는 분석하지 않습니다.';
    saveDraft();
    renderPreview();
  }

  async function prepare() {
    clearError();
    const folder = document.getElementById('folderPath');
    const name = document.getElementById('projectName');
    const task = document.getElementById('taskRequest');
    if (!folder.value.trim()) return invalid(folder, '작업할 폴더 위치를 선택하거나 붙여넣어 주세요.');
    if (!/^(?:[A-Za-z]:[\\/]|\\\\|\/)/.test(folder.value.trim())) return invalid(folder, '드라이브부터 시작하는 전체 폴더 위치를 적어주세요.');
    if (!name.value.trim()) return invalid(name, '프로젝트 이름을 적어주세요.');
    if (!task.value.trim()) return invalid(task, 'AI에게 맡길 일을 한 줄 이상 적어주세요.');
    preview = await VASAgentHandoffWeb.buildExisting(name.value, task.value, taskContext(), {
      designScope: designScope(), completionCriteria: VASTaskInputs.read('completionConditions'),
      rag: { included: false, items: [] }, ragReviewed: false,
      continuation: { included: false }
    });
    renderPreview();
    return true;
  }

  async function continueSettings() {
    try {
      if (await prepare()) {
        go(2);
      }
    } catch (error) { showError(error); }
  }

  async function saveJson() {
    clearError();
    try {
      if (!await prepare()) return;
      VASTaskInputs.confirm(preview.document, 'handoffInputReview');
      await VASAgentHandoffWeb.refreshIntegrity(preview.document, document.getElementById('provider').value);
      await VASAgentHandoffWeb.save(preview.document, 'VAS-AI-HANDOFF.json');
      document.getElementById('resultMessage').textContent = 'JSON을 저장했습니다. 폴더 위치가 포함된 프롬프트를 코딩 AI에 붙여넣으세요.';
      try { if (designScope().mode !== 'preserve') await VASSetupDesign.confirm(); } catch (error) { document.getElementById('resultMessage').textContent += ' 작업 기억은 저장하지 못했습니다.'; }
    } catch (error) { showError(error); }
  }

  async function copyPrompt(advance) {
    clearError();
    try {
      if (!await prepare()) return;
      VASTaskInputs.confirm(preview.document, 'handoffInputReview');
      await VASAgentHandoffWeb.refreshIntegrity(preview.document, document.getElementById('provider').value);
      VASAgentHandoffWeb.assertReviewed(preview.document);
      await VASAgentHandoffWeb.copy(currentPrompt());
      document.getElementById('resultMessage').textContent = providerLabel() + '용 프롬프트를 복사했습니다. 프롬프트에 적힌 폴더 위치를 코딩 AI가 확인합니다.';
      try { if (designScope().mode !== 'preserve') await VASSetupDesign.confirm(); } catch (error) { document.getElementById('resultMessage').textContent += ' 작업 기억은 저장하지 못했습니다.'; }
      if (advance !== false) go(3);
    } catch (error) { showError(error); }
  }

  document.getElementById('runtimeNotice').textContent = runtimeAvailable()
    ? '버튼을 누르면 Windows 폴더 선택창이 열립니다. 폴더 내부는 읽지 않습니다.'
    : 'Windows 폴더 선택창을 사용하려면 Run-VAS-System.bat로 실행해 주세요.';
  document.getElementById('selectFolder').addEventListener('click', function () { selectFolderLocation().catch(showError); });
  document.getElementById('continueSettings').addEventListener('click', continueSettings);
  document.getElementById('downloadJson').addEventListener('click', saveJson);
  document.getElementById('downloadAgain').addEventListener('click', saveJson);
  document.getElementById('copyPrompt').addEventListener('click', function () { copyPrompt(true); });
  document.getElementById('copyPromptAgain').addEventListener('click', function () { copyPrompt(false); });
  document.getElementById('editWork').addEventListener('click', function () { go(1); });
  document.getElementById('editSettings').addEventListener('click', function () { go(2); });
  document.getElementById('provider').addEventListener('change', renderPreview);
  function saveDraft() {
    if (!window.VASHandoffWorkflow) return;
    VASHandoffWorkflow.writeImportDraft({
      folderPath: folderLocation(), projectName: document.getElementById('projectName').value,
      taskRequest: document.getElementById('taskRequest').value, step: step, designScope: designScope(), completionCriteria: VASTaskInputs.read('completionConditions')
    });
  }
  ['folderPath', 'projectName', 'taskRequest'].forEach(function (id) {
    document.getElementById(id).addEventListener('input', function () {
      preview = null; saveDraft(); renderPreview();
      clearError();
    });
  });
  document.getElementById('handoffDesignPreset').addEventListener('change', function () {
    setTimeout(function () { try { renderPreview(); } catch (error) { showError(error); } }, 0);
  });
  ['designScopeMode', 'designScopeDetails'].forEach(function (id) {
    document.getElementById(id).addEventListener('change', function () { scopeVisibility(); saveDraft(); try { renderPreview(); } catch (error) { showError(error); } });
  });
  document.getElementById('completionConditions').addEventListener('input', function () { saveDraft(); });
  const draft = window.VASHandoffWorkflow && VASHandoffWorkflow.readImportDraft();
  if (draft) {
    document.getElementById('folderPath').value = draft.folderPath || '';
    document.getElementById('projectName').value = draft.projectName || '';
    document.getElementById('taskRequest').value = draft.taskRequest || '';
    if (draft.designScope) { document.getElementById('designScopeMode').value = draft.designScope.mode; document.getElementById('designScopeDetails').value = draft.designScope.scope || ''; }
    else { legacyScopeReview = true; document.getElementById('runtimeNotice').textContent += ' 이전 초안에는 디자인 변경 범위가 없습니다. 새 인계 기본값인 기존 디자인 유지로 전달할지 확인하세요.'; }
    document.querySelector('#completionConditions input[type=hidden]').value = JSON.stringify(draft.completionCriteria || []);
    VASTaskInputs.restore('completionConditions'); scopeVisibility();
    const restoredStep = Number(draft.step) === 1 ? 1 : 2;
    if (restoredStep === 2) prepare().then(function (ready) { if (ready) go(2); }).catch(showError);
  }
  window.addEventListener('focus', function () { try { renderPreview(); } catch (error) { showError(error); } });
})();
