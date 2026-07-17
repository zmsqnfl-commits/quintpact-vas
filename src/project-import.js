(function () {
  'use strict';

  let step = 1;
  let selection = null;
  let preview = null;
  let webFiles = [];
  let previewKind = 'json';
  const localMode = VASRuntime.isAvailable();

  VASThemeState.init();
  VASThemeState.decorateLinks(document);
  VASSetupDesign.mount('handoffDesignPreset', 'handoffDesignSummary');
  document.getElementById('modeLabel').textContent = localMode ? 'WINDOWS / JSON' : 'WEB / JSON';

  function go(next) {
    step = next;
    document.querySelectorAll('[data-step]').forEach(function (panel) { panel.classList.toggle('active', Number(panel.dataset.step) === step); });
    document.querySelectorAll('[data-nav-step]').forEach(function (item) {
      const number = Number(item.dataset.navStep);
      item.classList.toggle('active', number <= step);
      if (number === step) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
    });
    document.querySelector('.workspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function showError(error) {
    const box = document.getElementById('errorBox');
    box.textContent = error && error.message ? error.message : String(error);
    box.hidden = false;
  }
  function clearError() { document.getElementById('errorBox').hidden = true; }

  function displaySelection(value) {
    selection = value;
    document.getElementById('selectedPath').textContent = value.path || value.name;
    document.getElementById('selection').hidden = false;
    document.getElementById('analyzeButton').disabled = false;
  }

  async function checkLocalCapabilities() {
    if (!localMode) return;
    const button = document.getElementById('selectFolder');
    const notice = document.getElementById('runtimeNotice');
    try {
      const status = await VASRuntime.request('/api/status');
      const capability = status && status.capabilities && status.capabilities.projectImport;
      if (capability && capability.available === false) {
        button.disabled = true;
        notice.textContent = '폴더 분석에는 Python 3.10 이상이 필요합니다. 설치 후 VAS를 다시 실행해 주세요.';
        notice.hidden = false;
      }
    } catch (error) {
      button.disabled = true;
      notice.textContent = '로컬 기능에 연결하지 못했습니다. VAS를 다시 실행해 주세요.';
      notice.hidden = false;
    }
  }

  async function selectLocalFolder() {
    const value = await VASRuntime.request('/api/folder/select', { method: 'POST' });
    if (value && !value.cancelled && value.selection) displaySelection(value.selection);
  }

  async function walkDirectory(handle, prefix, result) {
    const excluded = new Set(['.git', '.hg', '.svn', '.cache', '.venv', '__pycache__', 'build', 'coverage', 'dist', 'node_modules', 'target', 'test-results']);
    for await (const entry of handle.values()) {
      const relative = prefix ? prefix + '/' + entry.name : entry.name;
      if (entry.kind === 'directory') {
        if (!excluded.has(entry.name.toLowerCase())) await walkDirectory(entry, relative, result);
      } else {
        const file = await entry.getFile();
        result.push({ path: relative, size: file.size });
      }
      if (result.length > 20000) throw new Error('웹 분석 한도(20,000개 파일)를 초과했습니다. Windows 실행본을 이용해 주세요.');
    }
  }

  async function selectWebFolder() {
    if (window.showDirectoryPicker) {
      const handle = await window.showDirectoryPicker({ mode: 'read' });
      webFiles = [];
      await walkDirectory(handle, '', webFiles);
      displaySelection({ name: handle.name, path: handle.name });
      return;
    }
    document.getElementById('folderFallback').click();
  }

  function taskContext() {
    const request = document.getElementById('taskRequest').value.trim();
    return {
      requirements: { included: Boolean(request), value: { request: request } },
      design: VASSetupDesign.context(),
      rag: { included: false, items: [] },
      preferences: { included: false, items: [] }
    };
  }

  function requestBody(extra) {
    return Object.assign({
      selectionId: selection.selectionId,
      projectName: selection.name || 'existing-project',
      sourceType: 'existing',
      task: { request: document.getElementById('taskRequest').value.trim(), constraints: [], acceptanceCriteria: [] },
      context: taskContext()
    }, extra || {});
  }

  async function analyze() {
    clearError();
    const task = document.getElementById('taskRequest');
    if (!task.value.trim()) { task.focus(); showError(new Error('AI에게 맡길 일을 한 줄 이상 적어주세요.')); return; }
    const button = document.getElementById('analyzeButton');
    button.disabled = true; button.textContent = '분석 중…';
    try {
      preview = localMode
        ? await VASRuntime.request('/api/handoffs/preview', { method: 'POST', body: requestBody() })
        : await VASAgentHandoffWeb.build(selection.name, webFiles, task.value, taskContext());
      renderAnalysis(); renderPreview(); go(2);
      if (window.VASPersonalization) VASPersonalization.record({ type: 'navigation', source: 'project-import', payload: { action: 'handoff_analyzed', fileCount: preview.document.analysis.stats.fileCount } });
    } catch (error) { showError(error); }
    finally { button.disabled = false; button.textContent = '안전하게 분석하기 →'; }
  }

  function metric(label, value) {
    const item = document.createElement('div'); item.className = 'metric';
    const caption = document.createElement('span'); caption.textContent = label;
    const strong = document.createElement('strong'); strong.textContent = value;
    item.append(caption, strong); return item;
  }

  function renderAnalysis() {
    const data = preview.document; const stats = data.analysis.stats;
    const grid = document.getElementById('analysisGrid'); grid.innerHTML = '';
    grid.append(
      metric('기술 스택', data.analysis.stacks.join(', ') || '자동 감지 안 됨'),
      metric('파일', stats.fileCount.toLocaleString('ko-KR') + '개'),
      metric('전체 크기', (stats.totalBytes / 1048576).toFixed(1) + ' MB'),
      metric('Git', data.analysis.git.present ? '있음 / 내용 제외' : '없음'),
      metric('비밀값 후보', data.security.secretCandidates + '개 / 제외'),
      metric('최종 결과', 'VAS-AI-HANDOFF.json')
    );
    const risks = [];
    if (data.security.secretCandidates) risks.push('비밀값 후보 ' + data.security.secretCandidates + '개를 전달 목록에서 제외했습니다.');
    (data.inventory.excluded || []).forEach(function (item) { if (item.reason !== 'secret') risks.push(item.reason + ' 항목 ' + item.count + '개를 건너뛰었습니다.'); });
    (data.security.warnings || []).forEach(function (warning) { risks.push(warning); });
    if (!risks.length) risks.push('원본 파일은 실행하거나 변경하지 않았습니다.');
    const list = document.getElementById('riskList'); list.innerHTML = '';
    risks.forEach(function (risk) { const li = document.createElement('li'); li.textContent = risk; list.append(li); });
    document.getElementById('webNote').hidden = localMode;
  }

  function syncDesign() {
    if (!preview) return;
    preview.document.context = preview.document.context || {};
    preview.document.context.requirements = {
      included: Boolean(preview.document.task.request),
      value: { request: preview.document.task.request }
    };
    preview.document.context.design = VASSetupDesign.context();
    preview.document.context.rag = { included: false, items: [] };
    preview.document.context.preferences = { included: false, items: [] };
  }

  function currentPrompt() { syncDesign(); return VASAgentHandoffWeb.prompt(preview.document, document.getElementById('provider').value); }
  function renderPreview() {
    if (!preview) return;
    syncDesign();
    document.getElementById('previewContent').textContent = previewKind === 'prompt' ? currentPrompt() : JSON.stringify(preview.document, null, 2);
    document.getElementById('previewStatus').textContent = preview.document.analysis.stats.fileCount + '개 파일 분석됨';
    document.querySelectorAll('[data-preview]').forEach(function (button) { button.classList.toggle('active', button.dataset.preview === previewKind); });
  }

  function saveBlob(blob, name) { const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = name; link.click(); URL.revokeObjectURL(link.href); }

  async function downloadJson(advance) {
    clearError(); syncDesign();
    try {
      if (!localMode) {
        await VASAgentHandoffWeb.refreshIntegrity(preview.document);
        VASAgentHandoffWeb.save(preview.document, 'VAS-AI-HANDOFF.json');
      }
      else {
        const blob = await VASRuntime.download('/api/handoffs/export', { method: 'POST', body: requestBody({ mode: 'metadata', format: 'json', snapshotId: preview.snapshotId, approvedFiles: [] }) });
        saveBlob(blob, 'VAS-AI-HANDOFF.json');
      }
      let note = ' 프롬프트도 복사했습니다.';
      try { await copyPrompt(false); } catch (error) { note = ' PROMPT 탭에서 문장을 직접 복사해 주세요.'; }
      document.getElementById('resultMessage').textContent = 'VAS-AI-HANDOFF.json을 저장했습니다.' + note + ' 이제 VAS를 닫아도 됩니다.';
      if (advance !== false) go(4);
    } catch (error) { showError(error); }
  }

  async function copyPrompt(showFeedback) {
    await VASAgentHandoffWeb.copy(currentPrompt());
    if (showFeedback !== false) {
      const message = step === 4 ? document.getElementById('resultMessage') : document.getElementById('copyPrompt');
      const old = message.textContent; message.textContent = '프롬프트를 복사했습니다.';
      if (message.tagName === 'BUTTON') setTimeout(function () { message.textContent = old; }, 1400);
    }
  }

  document.getElementById('selectFolder').addEventListener('click', function () { (localMode ? selectLocalFolder() : selectWebFolder()).catch(showError); });
  document.getElementById('changeFolder').addEventListener('click', function () { (localMode ? selectLocalFolder() : selectWebFolder()).catch(showError); });
  document.getElementById('folderFallback').addEventListener('change', function (event) {
    const files = Array.from(event.target.files); if (!files.length) return;
    webFiles = files.map(function (file) { return { path: file.webkitRelativePath.replace(/^[^/]+\//, ''), size: file.size }; });
    const name = files[0].webkitRelativePath.split('/')[0]; displaySelection({ name: name, path: name });
  });
  document.getElementById('analyzeButton').addEventListener('click', analyze);
  document.getElementById('continueReview').addEventListener('click', function () { go(3); renderPreview(); });
  document.getElementById('downloadJson').addEventListener('click', function () { downloadJson(true); });
  document.getElementById('downloadAgain').addEventListener('click', function () { downloadJson(false); });
  document.getElementById('copyPrompt').addEventListener('click', function () { copyPrompt(true).catch(showError); });
  document.getElementById('copyPromptAgain').addEventListener('click', function () { copyPrompt(true).catch(showError); });
  document.getElementById('provider').addEventListener('change', renderPreview);
  document.getElementById('handoffDesignPreset').addEventListener('change', function () { setTimeout(renderPreview, 0); });
  document.querySelectorAll('[data-preview]').forEach(function (button) { button.addEventListener('click', function () { previewKind = button.dataset.preview; renderPreview(); }); });
  window.addEventListener('focus', renderPreview);
  checkLocalCapabilities();
})();
