/** 작업 기억 RAG 후보를 보여주고 사용자가 승인한 요약만 인계에 포함합니다. */
(function (global) {
  'use strict';

  let root = null;
  let queryProvider = function () { return ''; };
  let changeHandler = function () {};
  let candidates = [];
  let reviewed = false;

  function element(name, className, text) {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function statusText(message) {
    const node = root && root.querySelector('[data-context-status]');
    if (node) node.textContent = message;
  }

  function approvedItems() {
    if (!root) return [];
    return Array.from(root.querySelectorAll('input[data-context-item]:checked')).map(function (input) {
      return candidates[Number(input.value)];
    }).filter(Boolean);
  }

  function context() {
    return VASAgentContract.approvedRag({ included: true, items: approvedItems() });
  }

  function renderCandidates() {
    const list = root.querySelector('[data-context-list]');
    list.replaceChildren();
    if (!candidates.length) {
      const empty = element('p', 'context-empty', '관련 작업 기억 추천이 없습니다. 추천 없이 계속할 수 있습니다.');
      list.append(empty);
      return;
    }
    candidates.forEach(function (item, index) {
      const label = element('label', 'context-item');
      const input = element('input'); input.type = 'checkbox'; input.value = String(index); input.setAttribute('data-context-item', '');
      const copy = element('span', 'context-item-copy');
      copy.append(element('strong', '', item.title || '이전 작업 참고'));
      copy.append(element('span', '', item.summary));
      copy.append(element('small', '', item.reason));
      label.append(input, copy);
      list.append(label);
    });
  }

  async function refresh() {
    if (!root) return;
    reviewed = false;
    candidates = [];
    root.dataset.reviewed = 'false';
    const button = root.querySelector('[data-context-confirm]');
    button.textContent = '추천 확인 완료';
    statusText('작업 기억 상태를 확인하고 있습니다.');
    if (!global.VASPersonalization || !global.VASRagLite) {
      renderCandidates(); statusText('이 실행본은 작업 기억을 사용하지 않습니다.'); return;
    }
    try {
      await VASPersonalization.init();
      const state = await VASPersonalization.status();
      if (state.consent !== true || state.paused) {
        renderCandidates(); statusText(state.paused ? '작업 기억이 잠시 중지되어 추천 없이 진행합니다.' : '작업 기억을 사용하지 않아 추천 없이 진행합니다.'); return;
      }
      const query = String(queryProvider() || '').trim().slice(0, 1000);
      if (!query) { renderCandidates(); statusText('작업 내용을 입력하면 관련 기억을 찾습니다.'); return; }
      const result = await VASPersonalization.recommend(query, { limit: 6 });
      candidates = (result && Array.isArray(result.results) ? result.results : []).slice(0, 3).map(function (item, index) {
        return {
          sourceId: String(item.id || 'memory-' + (index + 1)).replace(/[^a-z0-9_-]/gi, '').slice(0, 64) || 'memory-' + (index + 1),
          sourceKind: item.kind === 'knowledge' ? 'knowledge' : 'memory',
          title: VASAgentContract.clean(item.title, 120) || '이전 작업 참고',
          summary: VASAgentContract.clean(item.text, 400),
          reason: '현재 작업 내용과 관련도가 높은 안전 요약입니다.', userApproved: true
        };
      }).filter(function (item) { return item.summary; });
      renderCandidates();
      statusText(candidates.length ? '선택한 항목만 JSON과 프롬프트에 포함됩니다.' : '관련 추천을 찾지 못했습니다. 추천 없이 계속하세요.');
    } catch (error) {
      candidates = []; renderCandidates(); statusText('저장소를 사용할 수 없어 추천 없이 계속합니다.');
    }
  }

  function confirmReview() {
    reviewed = true;
    root.dataset.reviewed = 'true';
    root.querySelector('[data-context-confirm]').textContent = approvedItems().length ? '선택한 추천 검토 완료' : '추천 없이 계속 확인됨';
    statusText(approvedItems().length + '개 안전 요약을 전달하도록 확인했습니다.');
    changeHandler(context());
  }

  function ensureReviewed() {
    if (reviewed) return true;
    statusText('추천 내용을 확인한 뒤 아래 버튼을 눌러주세요.');
    root.scrollIntoView({ behavior: 'smooth', block: 'center' });
    root.querySelector('[data-context-confirm]').focus();
    return false;
  }

  function invalidate() {
    if (!root) return;
    reviewed = false; root.dataset.reviewed = 'false';
    statusText('작업 내용이 바뀌었습니다. 추천을 다시 확인해 주세요.');
  }

  function mount(containerId, options) {
    root = document.getElementById(containerId);
    if (!root) return;
    queryProvider = options && options.query || queryProvider;
    changeHandler = options && options.onChange || changeHandler;
    root.classList.add('context-review');
    root.innerHTML = '<div class="context-review-head"><div><span>RAG · 작업 기억</span><h3>관련 작업 기억을 확인하세요.</h3></div><button type="button" data-context-refresh>다시 찾기</button></div><p class="context-review-copy">추천은 자동 적용되지 않습니다. 직접 선택한 안전 요약만 코딩 AI에 전달됩니다.</p><div data-context-list></div><div class="context-review-foot"><p data-context-status role="status"></p><button type="button" data-context-confirm>추천 확인 완료</button></div>';
    root.querySelector('[data-context-refresh]').addEventListener('click', function () { refresh(); });
    root.querySelector('[data-context-confirm]').addEventListener('click', confirmReview);
    root.addEventListener('change', function () { reviewed = false; root.dataset.reviewed = 'false'; statusText('선택이 바뀌었습니다. 다시 확인해 주세요.'); });
    refresh();
  }

  global.VASHandoffContextReview = Object.freeze({ mount: mount, refresh: refresh, invalidate: invalidate, ensureReviewed: ensureReviewed, context: context, isReviewed: function () { return reviewed; } });
})(window);
