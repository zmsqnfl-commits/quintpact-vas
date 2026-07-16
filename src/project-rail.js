/** 현재 프로젝트와 RAG 상태를 모든 작업 화면에 같은 방식으로 표시합니다. */
(function (global) {
  'use strict';

  const stageLabels = { design: '디자인 정리', knowledge: 'RAG 연결', ready: '계속 작업' };
  let project = null;

  function insertRail() {
    let rail = document.querySelector('[data-vas-project-rail]');
    if (rail) return rail;
    rail = document.createElement('section');
    rail.className = 'vas-project-rail';
    rail.dataset.vasProjectRail = '';
    rail.setAttribute('aria-label', '현재 프로젝트 상태');
    rail.innerHTML = '<strong id="vasProjectName">현재 프로젝트</strong>' +
      '<span class="vas-project-meta" id="vasProjectStage"></span>' +
      '<span class="vas-rag-status"><span class="vas-rag-dot" aria-hidden="true"></span><button type="button" id="vasRagToggle">RAG 확인 중</button></span>';
    const header = document.querySelector('body > header, body > .topbar');
    if (header && header.parentNode) header.insertAdjacentElement('afterend', rail);
    else document.body.prepend(rail);
    return rail;
  }

  async function findProject(context) {
    if (!global.VASRuntime || !VASRuntime.isAvailable()) return context;
    try {
      const data = await VASRuntime.request('/api/projects');
      return (data.projects || []).find(function (item) { return item.projectId === context.projectId; }) || context;
    } catch (error) {
      return context;
    }
  }

  async function renderStatus(rail) {
    if (!global.VASPersonalization) {
      rail.dataset.rag = 'off';
      rail.querySelector('#vasRagToggle').textContent = 'RAG 사용 안 함';
      return;
    }
    await VASPersonalization.init();
    const status = await VASPersonalization.status();
    const mode = status.consent !== true ? 'off' : status.paused ? 'paused' : 'active';
    rail.dataset.rag = mode;
    rail.querySelector('#vasRagToggle').textContent = mode === 'active' ? 'RAG 활성' : mode === 'paused' ? 'RAG 일시정지' : 'RAG 사용 안 함';
    global.dispatchEvent(new CustomEvent('vas-rag-status', { detail: { mode: mode } }));
  }

  async function toggleRag(rail) {
    const status = await VASPersonalization.status();
    if (status.consent !== true) await VASPersonalization.consent(true);
    else await VASPersonalization.pause(!status.paused);
    await renderStatus(rail);
  }

  async function init() {
    if (!global.VASProjectContext) return null;
    const context = VASProjectContext.init();
    if (!context) return null;
    const rail = insertRail();
    project = await findProject(context);
    rail.querySelector('#vasProjectName').textContent = project.name || '현재 프로젝트';
    rail.querySelector('#vasProjectStage').textContent = (project.sourceType === 'imported' ? '가져온 프로젝트' : '새 프로젝트') + ' · ' + (stageLabels[project.stage] || '계속 작업');
    rail.querySelector('#vasRagToggle').addEventListener('click', function () {
      toggleRag(rail).catch(function () { rail.dataset.rag = 'off'; });
    });
    await renderStatus(rail);
    return project;
  }

  global.VASProjectRail = Object.freeze({ init, getProject: function () { return project; } });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init().catch(function () {}); }, { once: true });
  } else { init().catch(function () {}); }
})(window);
