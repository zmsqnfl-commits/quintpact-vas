(function () {
  'use strict';

  const KEY = 'morrow.board.v1';
  const categories = { branding: '브랜딩', web: '웹', content: '콘텐츠' };
  const statuses = { todo: '할 일', doing: '진행 중', done: '완료' };
  let tasks = [];
  let warning = '';
  let writesBlocked = false;

  function validDate(value) {
    if (value === '') return true;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false;
    const date = new Date(value + 'T00:00:00Z');
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function normalizedTask(item) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Invalid task');
    const text = (name, limit) => {
      if (typeof item[name] !== 'string' || item[name].length > limit) throw new Error('Invalid text');
      return item[name];
    };
    const id = text('id', 128);
    const title = text('title', 160).trim();
    const note = text('note', 4000);
    if (!id || !title || !Object.hasOwn(categories, item.category) || !Object.hasOwn(statuses, item.status)) throw new Error('Invalid fields');
    if (typeof item.dueDate !== 'string' || !validDate(item.dueDate)) throw new Error('Invalid date');
    if (typeof item.archived !== 'boolean' || typeof item.sample !== 'boolean') throw new Error('Invalid flags');
    for (const name of ['createdAt', 'updatedAt']) {
      if (typeof item[name] !== 'string' || item[name].length > 32 || !Number.isFinite(Date.parse(item[name]))) throw new Error('Invalid timestamp');
    }
    return { id, title, note, category: item.category, status: item.status, dueDate: item.dueDate,
      archived: item.archived, sample: item.sample, createdAt: item.createdAt, updatedAt: item.updatedAt };
  }

  function snapshot() { return { version: 1, tasks: tasks.map(task => ({ ...task })) }; }

  function persist() {
    if (writesBlocked) return false;
    try {
      localStorage.setItem(KEY, JSON.stringify(snapshot()));
      warning = '';
      return true;
    } catch (_) {
      warning = '브라우저에 저장하지 못했어요. JSON으로 보관해 주세요.';
      return false;
    }
  }

  function samples() {
    const now = new Date().toISOString();
    return [
      ['Morrow 브랜드 방향 정리', '브랜드가 전할 세 가지 인상을 적어보세요.', 'branding', 'doing'],
      ['스튜디오 웹 첫 화면 만들기', '첫 화면의 제목과 작업 소개를 구성해 보세요.', 'web', 'todo'],
      ['첫 뉴스레터 원고 다듬기', '새롭게 시작한 작업과 배운 점을 짧게 전해보세요.', 'content', 'todo'],
      ['무드보드 모으기', '작업에 어울리는 색과 이미지 방향을 모아보세요.', 'branding', 'done']
    ].map(([title, note, category, status], index) => ({ id: 'sample-' + (index + 1), title, note, category,
      status, dueDate: '', archived: false, sample: true, createdAt: now, updatedAt: now }));
  }

  function load() {
    let raw;
    try { raw = localStorage.getItem(KEY); }
    catch (_) {
      writesBlocked = true;
      warning = '브라우저에 저장하지 못했어요. JSON으로 보관해 주세요. 저장된 작업도 읽지 못했으며 기존 저장 공간은 변경하지 않았어요.';
      return;
    }
    if (raw === null) {
      tasks = samples();
      persist();
      return;
    }
    try {
      const value = JSON.parse(raw);
      if (!value || value.version !== 1 || !Array.isArray(value.tasks)) throw new Error('Invalid board');
      const result = value.tasks.map(normalizedTask);
      if (new Set(result.map(task => task.id)).size !== result.length) throw new Error('Duplicate ids');
      tasks = result;
    } catch (_) {
      writesBlocked = true;
      warning = '저장된 작업 형식을 읽지 못했어요. 원본은 보존했으며, 새 작업은 JSON으로 보관해 주세요.';
    }
  }

  function upsert(values, id) {
    const existing = tasks.find(task => task.id === id);
    const now = new Date().toISOString();
    const task = normalizedTask({ ...values, id: existing ? existing.id : crypto.randomUUID(),
      archived: existing ? existing.archived : false, sample: existing ? existing.sample : false,
      createdAt: existing ? existing.createdAt : now, updatedAt: now });
    if (existing) tasks[tasks.indexOf(existing)] = task;
    else tasks.unshift(task);
    persist();
    return task;
  }

  function change(id, values) {
    const index = tasks.findIndex(task => task.id === id);
    if (index < 0) return;
    tasks[index] = normalizedTask({ ...tasks[index], ...values, updatedAt: new Date().toISOString() });
    persist();
  }

  function remove(id) {
    const index = tasks.findIndex(task => task.id === id);
    if (index < 0) return null;
    const [task] = tasks.splice(index, 1);
    persist();
    return { task, index };
  }

  function restore(record) {
    if (!record || tasks.some(task => task.id === record.task.id)) return;
    tasks.splice(Math.min(record.index, tasks.length), 0, { ...record.task });
    persist();
  }

  load();
  window.MorrowStore = { categories, statuses, validDate, snapshot, upsert, change, remove, restore,
    get tasks() { return tasks; }, get warning() { return warning; } };
})();
