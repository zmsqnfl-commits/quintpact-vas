(function () {
  'use strict';
  const state = VASThemeState.init();
  const projectContext = VASProjectContext.init();
  const root = document.documentElement;
  root.style.setProperty('--bg', state.tokens.colors.background);
  root.style.setProperty('--surface', state.tokens.colors.surface);
  root.style.setProperty('--text', state.tokens.colors.text);
  root.style.setProperty('--border', state.tokens.colors.border);
  root.style.setProperty('--font', state.tokens.fontFamily);
  VASThemeState.decorateLinks(document);
  VASProjectContext.decorateLinks(document);

  const form = document.getElementById('searchForm');
  const input = document.getElementById('searchInput');
  const resultsRoot = document.getElementById('results');
  const count = document.getElementById('resultCount');

  function sourceLink(result) {
    if (result.kind !== 'knowledge' || !result.source) return null;
    if (!/^docs\//.test(result.source.replace(/\\/g, '/'))) return null;
    const link = document.createElement('a');
    link.href = '../' + result.source.replace(/\\/g, '/');
    link.textContent = '원문 열기' + (result.line ? ' · ' + result.line + '줄' : '');
    return link;
  }

  function render(results) {
    resultsRoot.innerHTML = '';
    count.textContent = results.length + '건';
    if (!results.length) {
      const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '관련 결과를 찾지 못했습니다.'; resultsRoot.append(empty); return;
    }
    results.forEach(function (result) {
      const article = document.createElement('article'); article.className = 'result-item';
      const meta = document.createElement('div'); meta.className = 'result-meta'; meta.textContent = (result.kind === 'memory' ? '사용 기록' : '지식 문서') + '\n' + result.source;
      const content = document.createElement('div');
      const title = document.createElement('h3'); title.textContent = result.title;
      const excerpt = document.createElement('p'); excerpt.textContent = result.text.slice(0, 360);
      content.append(title, excerpt);
      const link = sourceLink(result); if (link) content.append(link);
      article.append(meta, content); resultsRoot.append(article);
    });
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const query = input.value.trim();
    if (query.length < 2) return;
    await VASPersonalization.init();
    const results = await VASPersonalization.retrieve(query, { limit: 12 });
    render(results);
    VASPersonalization.record({ type: 'search', source: 'knowledge', payload: { query: query, resultCount: results.length } });
  });

  document.querySelectorAll('[data-query]').forEach(function (button) {
    button.addEventListener('click', function () {
      input.value = button.dataset.query;
      form.requestSubmit();
    });
  });

  async function loadProjectRecommendation() {
    await VASPersonalization.init();
    const status = await VASPersonalization.status();
    const scope = document.getElementById('ragScope');
    if (!projectContext) {
      scope.textContent = 'VAS 문서에서 검색합니다. 허브에서 프로젝트의 계속 작업을 누르면 해당 프로젝트 RAG도 연결됩니다.';
      count.textContent = '검색어를 입력해 주세요.';
      return;
    }
    if (status.consent !== true || status.paused) {
      scope.textContent = '현재 프로젝트가 연결되어 있습니다. 위 RAG 상태에서 활성화하면 이 프로젝트 자료와 사용 흐름을 자동으로 함께 찾습니다.';
      count.textContent = 'RAG를 활성화하거나 검색어를 입력해 주세요.';
      return;
    }
    scope.textContent = '현재 프로젝트의 허용된 자료와 이 프로젝트에서 남긴 사용 흐름만 자동으로 함께 찾고 있습니다.';
    const goalQueries = {
      redesign: '디자인 구현 계획', improve: '기능 개선 우선순위',
      upgrade: '업그레이드 배포 계획', manage: '다음 작업 우선순위'
    };
    const query = goalQueries[projectContext.goal] || goalQueries.manage;
    const recommendations = await VASPersonalization.retrieve(query, { limit: 6 });
    if (recommendations.length) {
      render(recommendations);
      count.textContent = '현재 프로젝트 RAG 추천 ' + recommendations.length + '건';
    } else { count.textContent = '검색어를 입력해 주세요.'; }
  }

  window.addEventListener('vas-rag-status', function (event) {
    if (event.detail && event.detail.mode === 'active') loadProjectRecommendation().catch(function () {});
  });

  const initialQuery = new URLSearchParams(window.location.search).get('q');
  if (initialQuery && initialQuery.trim().length >= 2) {
    input.value = initialQuery.trim().slice(0, 200);
    form.requestSubmit();
  } else { loadProjectRecommendation().catch(function () { count.textContent = '검색어를 입력해 주세요.'; }); }
})();
