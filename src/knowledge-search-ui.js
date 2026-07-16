(function () {
  'use strict';
  const state = VASThemeState.init();
  const root = document.documentElement;
  root.style.setProperty('--bg', state.tokens.colors.background);
  root.style.setProperty('--surface', state.tokens.colors.surface);
  root.style.setProperty('--text', state.tokens.colors.text);
  root.style.setProperty('--border', state.tokens.colors.border);
  root.style.setProperty('--font', state.tokens.fontFamily);
  VASThemeState.decorateLinks(document);

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
      const meta = document.createElement('div'); meta.className = 'result-meta'; meta.textContent = result.kind.toUpperCase() + '\n' + result.source;
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

  const initialQuery = new URLSearchParams(window.location.search).get('q');
  if (initialQuery && initialQuery.trim().length >= 2) {
    input.value = initialQuery.trim().slice(0, 200);
    form.requestSubmit();
  }
})();
