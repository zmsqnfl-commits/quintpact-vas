/* =========================================
   client-export.js
   내보내기 로직: JSON 저장
   폼에서 직접 수집하며 초안은 유지합니다.
   ========================================= */

function collectApplicationData(form, files) {
    const data = {};
    form.querySelectorAll('input, textarea, select').forEach(el => {
        if (!el.name || el.disabled || ['file', 'button', 'submit', 'reset'].includes(el.type) || el.name === 'attached_files') return;
        if (el.type === 'checkbox' || el.type === 'radio') {
            if (el.checked) data[el.name] = (data[el.name] || []).concat(el.value);
        } else if (typeof el.value === 'string' && el.value.trim()) {
            data[el.name] = el.value.trim();
        }
    });

    data.attached_files = Array.isArray(files) ? files.slice() : [];
    const themeState = window.VASThemeState ? window.VASThemeState.get() : null;
    data._meta = {
        schemaVersion: 1,
        appVersion: window.VASConfig ? window.VASConfig.version : '2.6.1',
        exportedAt: new Date().toISOString(),
        preset: themeState ? themeState.preset : VASStorage.readText('vasCurrentPreset', 'awwwards'),
        themeTokens: themeState ? themeState.tokens : VASStorage.getDefaultTheme(),
        language: window.currentLang || 'ko'
    };
    return data;
}

function exportJson() {
    const form = document.getElementById('projectForm');
    const data = collectApplicationData(form, typeof uploadedFiles === 'undefined' ? [] : uploadedFiles);

    const now = new Date();
    const stamp = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}-${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`;
    const filename = `vas-client-${stamp}.json`;

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    if (window.VASClientDraft) window.VASClientDraft.clear();
    if (window.VASPersonalization) {
        window.VASPersonalization.record({ type: 'export', source: 'client-application', payload: { fields: Object.keys(data).filter(key => key !== '_meta') } });
    }
}

async function createWorkspaceProject() {
    const button = document.getElementById('createProjectButton');
    const status = document.getElementById('projectCreateStatus');
    if (!window.VASRuntime || !VASRuntime.isAvailable()) return;
    const form = document.getElementById('projectForm');
    const data = collectApplicationData(form, typeof uploadedFiles === 'undefined' ? [] : uploadedFiles);
    button.disabled = true;
    status.hidden = false;
    status.textContent = currentLang === 'ko' ? '작업공간을 준비하고 있습니다.' : 'Creating the workspace.';
    try {
        const result = await VASRuntime.request('/api/projects/create', {
            method: 'POST', body: { name: data.project_name || '', brief: data }
        });
        const project = result && result.project;
        if (!project || !project.projectId) throw new Error('생성된 프로젝트 연결 정보를 받지 못했습니다.');
        VASProjectContext.set(project);
        status.textContent = currentLang === 'ko'
            ? '작업공간을 만들었습니다. 이제 디자인을 정하면 RAG가 이 프로젝트에 연결됩니다.'
            : 'Workspace created. Open it from My Projects in the hub.';
        button.hidden = true;
        document.getElementById('createdProjectNext').hidden = false;
        VASProjectContext.decorateLinks(document.getElementById('createdProjectNext').parentNode);
        if (window.VASRuntime && VASRuntime.preserveTokenInLinks) VASRuntime.preserveTokenInLinks();
        if (window.VASProjectRail) VASProjectRail.init().catch(function () {});
        if (window.VASClientDraft) window.VASClientDraft.clear();
        if (window.VASPersonalization) {
            window.VASPersonalization.record({
                type: 'project_created', source: 'client-application',
                payload: { environment: data.env_web || data.env_mobile || data.env_windows || data.env_edge || [] }
            });
        }
    } catch (error) {
        status.textContent = error && error.message ? error.message : String(error);
        button.disabled = false;
    }
}

if (window.VASRuntime && VASRuntime.isAvailable()) {
    document.getElementById('createProjectButton').hidden = false;
}

window.collectApplicationData = collectApplicationData;
window.createWorkspaceProject = createWorkspaceProject;
