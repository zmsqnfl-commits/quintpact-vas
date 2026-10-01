/** Shared accessible completion-condition editor and sanitized-content review. */
(function (global) {
  'use strict';
  const editors = new Map();
  const reviews = new Map();
  function mount(id) {
    const host = document.getElementById(id);
    if (!host) return;
    const input = host.querySelector('input[type=hidden]');
    const rows = host.querySelector('[data-criteria-rows]');
    const button = host.querySelector('[data-add-criterion]');
    const state = { host: host, input: input, rows: rows, value: input.value, button: button };
    editors.set(id, state);
    function serialize() {
      input.value = JSON.stringify(Array.from(rows.children).map(function (row) {
        return { description: row.querySelector('textarea').value, method: row.querySelector('select').value, required: row.querySelector('input').checked };
      }));
      state.value = input.value;
      button.disabled = rows.children.length >= 20;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    state.add = function (value) {
      if (rows.children.length >= 20) return;
      const row = document.createElement('div'); row.className = 'criterion-row';
      row.innerHTML = '<label>완료조건<textarea placeholder="예: CSV를 열면 한글이 깨지지 않고 합계가 일치한다"></textarea></label><div class="criterion-controls"><label>확인 방법 <select><option value="automatic">자동 검사</option><option value="manual">수동 확인</option><option value="static">정적 검토</option></select></label><label><input type="checkbox" checked> 필수조건</label><button type="button">조건 삭제</button></div>';
      if (value) { row.querySelector('textarea').value = value.description || ''; row.querySelector('select').value = value.method || 'manual'; row.querySelector('input').checked = value.required !== false; }
      else row.querySelector('select').value = 'manual';
      row.addEventListener('input', serialize); row.addEventListener('change', serialize);
      row.querySelector('button').addEventListener('click', function () { row.remove(); serialize(); button.focus(); });
      rows.append(row);
      button.disabled = rows.children.length >= 20;
      return row;
    };
    button.addEventListener('click', function () { const row = state.add(); serialize(); if (row) row.querySelector('textarea').focus(); });
    restore(id);
  }
  function restore(id) {
    const state = editors.get(id); if (!state) return;
    let values;
    try { values = JSON.parse(state.input.value || '[]'); } catch (error) { return; }
    if (!Array.isArray(values) || values.length > 20) return;
    state.rows.replaceChildren(); values.forEach(state.add); state.value = state.input.value;
  }
  function read(id) {
    const state = editors.get(id); if (!state) return [];
    if (state.input.value !== state.value) restore(id);
    try { return JSON.parse(state.input.value || '[]'); } catch (error) { throw new Error('완료조건을 읽지 못했습니다. 내용을 다시 입력하세요.'); }
  }
  function review(doc, id) {
    const host = document.getElementById(id); if (!host) return;
    const check = host.querySelector('input');
    const signature = JSON.stringify([doc.project, doc.task, doc.context, doc.inputReview]);
    if (reviews.get(id) !== signature) { check.checked = false; reviews.set(id, signature); }
    const needed = doc.inputReview && doc.inputReview.required;
    host.querySelector('[data-review-change]').textContent = needed
      ? '입력 중 ' + doc.inputReview.fields.join(', ') + ' 내용이 정제 또는 이전 초안 변환으로 변경되었습니다. 최종 내용을 확인한 뒤 복사·저장하세요.'
      : '알려진 패턴의 자동 정제를 적용했습니다. 사용자 확인과 독립 보안 검증은 별도이며 자동 정제는 안전 보증이 아닙니다.';
    host.querySelector('[data-review-label]').textContent = needed ? '변경된 최종 요청·완료조건·디자인 범위를 확인했습니다. (필수)' : '최종 요청·완료조건·디자인 범위를 확인했습니다. (선택)';
  }
  function confirm(doc, id) {
    const host = document.getElementById(id);
    const checked = Boolean(host && host.querySelector('input').checked);
    if (doc.inputReview && doc.inputReview.required && !checked) {
      if (host) host.querySelector('input').focus();
      throw new Error('정제로 변경된 최종 내용을 확인하고 확인란을 선택해 주세요.');
    }
    if (doc.inputReview) doc.inputReview.acknowledged = checked;
    doc.qualityGate.requirementsConfirmed = checked;
    doc.qualityGate.designConfirmed = checked;
    doc.qualityGate.userConfirmation = checked ? { status: 'confirmed', scope: ['requirements', 'completion-criteria', 'design-scope'], confirmedAt: new Date().toISOString() } : { status: 'not-performed', scope: [] };
  }
  global.VASTaskInputs = Object.freeze({ mount: mount, read: read, restore: restore, review: review, confirm: confirm });
})(window);
