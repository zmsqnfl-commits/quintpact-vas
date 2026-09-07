(function () {
  'use strict';
  const store = window.MorrowStore;
  const $ = id => document.getElementById(id);
  const dialog = $('task-dialog');
  const form = $('task-form');
  const list = $('task-list');
  let view = 'board';
  let status = 'all';
  let editingId = null;
  let focusId = null;
  let returnFocus = null;
  let returnRow = null;
  let deleted = null;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function openIcon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M14 4h6v6M20 4l-9 9M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5');
    svg.append(path);
    return svg;
  }

  function announce(message) { $('live-message').textContent = message; }

  function renderRow(task) {
    const row = element('li', 'task-row');
    row.dataset.taskId = task.id;
    row.dataset.status = task.status;
    const checkLabel = element('label', 'check-control');
    const check = element('input');
    check.type = 'checkbox';
    check.checked = task.status === 'done';
    check.setAttribute('aria-label', task.title + ' 완료');
    check.addEventListener('change', () => {
      store.change(task.id, { status: check.checked ? 'done' : 'todo' });
      render();
      const updatedRow = [...list.children].find(node => node.dataset.taskId === task.id);
      (updatedRow ? updatedRow.querySelector('input') : $('board-heading')).focus();
      announce(check.checked ? '작업을 완료했어요.' : '작업을 할 일로 변경했어요.');
    });
    checkLabel.append(check);
    const title = element('button', 'task-title-button', task.title);
    title.type = 'button';
    title.addEventListener('click', () => openEditor(task.id, title));
    const category = element('span', 'task-category', store.categories[task.category]);
    const state = element('span', 'task-status', store.statuses[task.status]);
    state.dataset.status = task.status;
    const sample = element('span', 'task-example', task.sample ? '예시' : '');
    const due = element(task.dueDate ? 'time' : 'span', 'task-date', task.dueDate || '기한 없음');
    if (task.dueDate) due.dateTime = task.dueDate;
    const open = element('button', 'icon-button');
    open.type = 'button';
    open.setAttribute('aria-label', task.title + ' 열기');
    open.append(openIcon());
    open.addEventListener('click', () => openEditor(task.id, open));
    row.append(checkLabel, title, category, state, sample, due, open);
    return row;
  }

  function filteredTasks() {
    const query = $('search').value.trim().toLocaleLowerCase();
    const category = $('category-filter').value;
    return store.tasks.filter(task => task.archived === (view === 'archive') &&
      (status === 'all' || task.status === status) &&
      (category === 'all' || task.category === category) &&
      (!query || (task.title + '\n' + task.note).toLocaleLowerCase().includes(query)));
  }

  function hasFilters() {
    return $('search').value.trim() !== '' || status !== 'all' || $('category-filter').value !== 'all';
  }

  function render() {
    const tasks = filteredTasks();
    list.replaceChildren(...tasks.map(renderRow));
    $('board-heading').textContent = view === 'archive' ? '보관함' : '모든 작업';
    $('result-count').textContent = '작업 ' + tasks.length + '개';
    $('empty-state').hidden = tasks.length > 0;
    $('empty-message').textContent = hasFilters() ? '조건에 맞는 작업이 없어요.' :
      view === 'archive' ? '보관한 작업이 없어요.' : '첫 작업을 적어보세요.';
    $('empty-action').textContent = hasFilters() ? '필터 초기화' : view === 'archive' ? '작업 보드로 이동' : '새 작업';
    $('example-note').hidden = !tasks.some(task => task.sample);
    const active = store.tasks.filter(task => !task.archived && task.status !== 'done');
    const focus = active.find(task => task.status === 'doing') || active[0];
    focusId = focus ? focus.id : null;
    $('focus-title').textContent = focus ? focus.title : '집중할 작업이 없어요.';
    $('focus-meta').textContent = focus ? store.categories[focus.category] + (focus.sample ? ' · 예시' : '') : '';
    $('focus-status').textContent = focus ? store.statuses[focus.status] : '';
    $('focus-open').textContent = focus ? '작업 열기' : '새 작업';
    $('storage-status').textContent = store.warning || '변경 사항은 자동으로 저장돼요.';
    document.querySelector('.storage-tile').dataset.state = store.warning ? 'error' : 'saved';
  }

  function resetFilters() {
    status = 'all';
    $('search').value = '';
    $('category-filter').value = 'all';
    document.querySelectorAll('[data-status-filter]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.statusFilter === status));
    });
  }

  function changeView(nextView) {
    view = nextView;
    resetFilters();
    document.querySelectorAll('[data-view]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.view === view));
    });
    render();
  }

  function resetErrors() {
    $('title-error').hidden = true;
    $('date-error').hidden = true;
    $('task-title').removeAttribute('aria-invalid');
    $('task-due').removeAttribute('aria-invalid');
  }

  function openEditor(id, trigger) {
    const task = store.tasks.find(item => item.id === id);
    editingId = task ? task.id : null;
    returnFocus = trigger || document.activeElement;
    const parentRow = returnFocus.closest('[data-task-id]');
    returnRow = parentRow ? { id: parentRow.dataset.taskId,
      selector: returnFocus.classList.contains('icon-button') ? '.icon-button' : '.task-title-button' } : null;
    form.reset();
    resetErrors();
    $('dialog-heading').textContent = task ? '작업 수정' : '새 작업';
    $('task-title').value = task ? task.title : '';
    $('task-note').value = task ? task.note : '';
    $('task-category').value = task ? task.category : 'branding';
    $('task-status').value = task ? task.status : 'todo';
    $('task-due').value = task ? task.dueDate : '';
    $('save-task').textContent = task ? '변경 저장' : '작업 추가';
    $('edit-actions').hidden = !task;
    $('archive-task').textContent = task && task.archived ? '복원' : '보관';
    dialog.showModal();
    $('task-title').focus();
  }

  dialog.addEventListener('close', () => {
    const row = returnRow && [...list.children].find(node => node.dataset.taskId === returnRow.id);
    const target = returnFocus && returnFocus.isConnected ? returnFocus : row ? row.querySelector(returnRow.selector) : $('board-heading');
    target.focus();
    editingId = null;
  });

  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button, input, select, textarea')]
      .filter(control => !control.disabled && control.getClientRects().length);
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  form.addEventListener('submit', event => {
    event.preventDefault();
    resetErrors();
    const title = $('task-title').value.trim();
    if (!title) {
      $('title-error').hidden = false;
      $('task-title').setAttribute('aria-invalid', 'true');
      $('task-title').focus();
      return;
    }
    const due = $('task-due');
    if (!due.validity.valid || !store.validDate(due.value)) {
      $('date-error').hidden = false;
      due.setAttribute('aria-invalid', 'true');
      due.focus();
      return;
    }
    const isNew = !editingId;
    store.upsert({ title, note: $('task-note').value, category: $('task-category').value,
      status: $('task-status').value, dueDate: due.value }, editingId);
    if (isNew) changeView('board');
    else render();
    dialog.close();
    announce(store.warning ? '작업을 이 화면에 반영했어요. 저장 안내를 확인해 주세요.' :
      isNew ? '작업을 추가했어요.' : '작업을 수정했어요.');
  });

  $('archive-task').addEventListener('click', () => {
    const task = store.tasks.find(item => item.id === editingId);
    if (!task) return;
    const archived = !task.archived;
    store.change(task.id, { archived });
    render();
    dialog.close();
    announce(archived ? '작업을 보관했어요.' : '작업 보드로 복원했어요.');
  });

  $('delete-task').addEventListener('click', () => {
    deleted = store.remove(editingId);
    if (!deleted) return;
    $('notice-message').textContent = '“' + deleted.task.title + '” 작업을 삭제했어요.';
    $('notice').hidden = false;
    render();
    dialog.close();
  });

  $('undo-button').addEventListener('click', () => {
    if (!deleted) return;
    const restored = deleted.task;
    store.restore(deleted);
    deleted = null;
    $('notice').hidden = true;
    changeView(restored.archived ? 'archive' : 'board');
    const row = [...list.children].find(node => node.dataset.taskId === restored.id);
    (row ? row.querySelector('.task-title-button') : $('board-heading')).focus();
    announce('삭제한 작업을 되돌렸어요.');
  });

  $('export-json').addEventListener('click', () => {
    const data = { ...store.snapshot(), exportedAt: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = element('a');
    link.href = url;
    link.download = 'morrow-board-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    announce('현재 작업의 JSON 파일을 내보냈어요.');
  });

  $('new-task').addEventListener('click', event => openEditor(null, event.currentTarget));
  $('focus-open').addEventListener('click', event => openEditor(focusId, event.currentTarget));
  $('close-dialog').addEventListener('click', () => dialog.close());
  $('cancel-dialog').addEventListener('click', () => dialog.close());
  $('task-title').addEventListener('input', resetErrors);
  $('search').addEventListener('input', render);
  $('category-filter').addEventListener('change', render);
  $('empty-action').addEventListener('click', event => {
    if (hasFilters()) { resetFilters(); render(); $('search').focus(); }
    else if (view === 'archive') { changeView('board'); $('board-heading').focus(); }
    else openEditor(null, event.currentTarget);
  });
  document.querySelectorAll('[data-status-filter]').forEach(button => {
    button.addEventListener('click', () => {
      status = button.dataset.statusFilter;
      document.querySelectorAll('[data-status-filter]').forEach(item => {
        item.setAttribute('aria-pressed', String(item === button));
      });
      render();
    });
  });
  document.querySelectorAll('[data-view]').forEach(button => {
    button.addEventListener('click', () => changeView(button.dataset.view));
  });
  render();
})();
