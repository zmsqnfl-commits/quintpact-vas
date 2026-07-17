/** VAS AI 인계 v3·결과 v1 공용 계약과 안전 검증. */
(function (global) {
  'use strict';

  const SECRET = /(?:\b(?:password|passwd|secret|credential|api[_ -]?key|access[_ -]?token|authorization)\s*[:=]\s*[^\s,;]+|\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{12,}|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b(?:\+?82[- ]?0?1[016789]|01[016789])[- ]?\d{3,4}[- ]?\d{4})/gi;
  const ABSOLUTE_PATH = /(?:[A-Z]:[\\/][^\s'"`]+|\\\\[^\s]+|\/(?:Users|home|var|etc|mnt|volume\d*)\/[^\s'"`]+)/gi;
  const RESULT_STATUS = new Set(['complete', 'incomplete', 'blocked', 'failed']);
  const TEST_STATUS = new Set(['passed', 'failed', 'skipped']);
  const SOURCE_TYPES = new Set(['new', 'existing', 'registered']);
  const ACTIONS = new Set(['created', 'modified', 'deleted', 'renamed']);
  const SEVERITIES = new Set(['blocker', 'high', 'medium', 'low']);
  let fallbackSequence = 0;

  function cleanWithCount(value, limit) {
    const source = String(value == null ? '' : value).replace(/\r\n?/g, '\n');
    let redactions = 0;
    const replace = function () { redactions += 1; return '[redacted]'; };
    const text = source.replace(SECRET, replace).replace(ABSOLUTE_PATH, function () {
      redactions += 1; return '[absolute-path]';
    }).replace(/[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]/g, ' ').trim().slice(0, limit || 4000);
    return { text: text, redactions: redactions };
  }

  function clean(value, limit) { return cleanWithCount(value, limit).text; }

  function sanitize(value, depth) {
    const level = depth || 0;
    if (level > 8) return null;
    if (typeof value === 'string') return clean(value, 6000);
    if (Array.isArray(value)) return value.slice(0, 100).map(function (item) { return sanitize(item, level + 1); });
    if (value && Object.getPrototypeOf(value) === Object.prototype) {
      const result = {};
      Object.keys(value).sort().slice(0, 100).forEach(function (key) {
        if (['__proto__', 'prototype', 'constructor'].includes(key)) return;
        result[key] = sanitize(value[key], level + 1);
      });
      return result;
    }
    return typeof value === 'number' && !Number.isFinite(value) ? null : value;
  }

  function stable(value) {
    if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
    if (value && typeof value === 'object') {
      return '{' + Object.keys(value).sort().filter(function (key) { return value[key] !== undefined; })
        .map(function (key) { return JSON.stringify(key) + ':' + stable(value[key]); }).join(',') + '}';
    }
    return JSON.stringify(value);
  }

  async function digest(value) {
    if (!global.crypto || !global.crypto.subtle || !global.TextEncoder) return null;
    const buffer = await global.crypto.subtle.digest('SHA-256', new TextEncoder().encode(typeof value === 'string' ? value : stable(value)));
    return Array.from(new Uint8Array(buffer)).map(function (byte) { return byte.toString(16).padStart(2, '0'); }).join('');
  }

  function randomHex(length) {
    const bytes = new Uint8Array(Math.ceil(length / 2));
    if (global.crypto && global.crypto.getRandomValues) global.crypto.getRandomValues(bytes);
    else {
      fallbackSequence += 1;
      for (let index = 0; index < bytes.length; index += 1) bytes[index] = (Date.now() + fallbackSequence * 31 + index * 17) & 255;
    }
    return Array.from(bytes).map(function (byte) { return byte.toString(16).padStart(2, '0'); }).join('').slice(0, length);
  }

  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function semanticPayload(document) {
    const output = clone(document);
    delete output.integrity;
    if (output.assistantGuide) output.assistantGuide.pasteText = '';
    if (output.workflow) output.workflow.handoffId = '';
    return output;
  }

  function integrityPayload(document) {
    const output = clone(document);
    delete output.integrity;
    if (output.assistantGuide) output.assistantGuide.pasteText = '';
    return output;
  }

  async function finalize(document, promptBuilder, target) {
    document.schemaVersion = 3;
    document.workflow = Object.assign({ handoffId: '', iteration: 1, parentResultId: null, status: 'ready' }, document.workflow || {});
    document.workflow.status = 'ready';
    const semanticHash = await digest(semanticPayload(document));
    document.workflow.handoffId = semanticHash ? 'h_' + semanticHash.slice(0, 32) : 'h_' + randomHex(32);
    const payloadHash = await digest(integrityPayload(document));
    document.integrity = Object.assign({ algorithm: 'SHA-256', payloadSha256: null, sourcePackSha256: null }, document.integrity || {});
    document.integrity.payloadSha256 = payloadHash;
    document.assistantGuide = document.assistantGuide || {};
    document.assistantGuide.target = target || document.assistantGuide.target || 'universal';
    document.assistantGuide.pasteText = promptBuilder(document, document.assistantGuide.target);
    return document;
  }

  function safeIdentifier(value, prefix) {
    const pattern = prefix === 'h' ? /^h_[a-f0-9]{32}$/i : /^r_[a-z0-9_-]{16,64}$/i;
    return pattern.test(String(value || '')) ? String(value) : '';
  }

  function safeRelative(value) {
    const source = String(value || '').trim();
    if (/^(?:[A-Za-z]:[\\/]|[\\/])/.test(source)) return '';
    const normalized = source.replace(/\\/g, '/').replace(/\/+$/g, '');
    if (!normalized || normalized.length > 300 || /[\x00-\x1f\x7f]/.test(normalized)) return '';
    const parts = normalized.split('/');
    if (parts.some(function (part) { return !part || part === '.' || part === '..' || part.includes(':'); })) return '';
    return normalized;
  }

  function approvedRag(rag) {
    const items = rag && Array.isArray(rag.items) ? rag.items : [];
    const approved = items.filter(function (item) { return item && item.userApproved === true; }).slice(0, 3).map(function (item, index) {
      return {
        sourceId: clean(item.sourceId, 64) || 'context-' + (index + 1),
        sourceKind: ['memory', 'knowledge'].includes(item.sourceKind) ? item.sourceKind : 'memory',
        title: clean(item.title, 120), summary: clean(item.summary, 400),
        reason: clean(item.reason, 200), userApproved: true
      };
    }).filter(function (item) { return item.title || item.summary; });
    return { included: approved.length > 0, items: approved };
  }

  async function normalizeHandoff(raw) {
    if (!raw || raw.format !== 'vas-ai-handoff' || ![2, 3].includes(Number(raw.schemaVersion))) throw new Error('지원하지 않는 VAS 인계 JSON입니다.');
    const document = sanitize(raw, 0);
    if (Number(raw.schemaVersion) === 2) {
      document.schemaVersion = 3;
      document.workflow = { handoffId: '', iteration: 1, parentResultId: null, status: 'ready', legacySourceSchema: 2 };
      document.context = document.context || {};
      document.context.rag = { included: false, items: [] };
      document.context.continuation = { included: false };
      document.qualityGate = { requirementsConfirmed: false, designConfirmed: false, sourceHandlingConfirmed: false, privacyChecked: false, ragReviewed: false, continuationReviewed: true };
    }
    return finalize(document, function () { return document.assistantGuide && document.assistantGuide.pasteText || ''; }, document.assistantGuide && document.assistantGuide.target);
  }

  function safeStringArray(value, limit, redactionState) {
    if (!Array.isArray(value)) return [];
    return value.slice(0, limit).map(function (item) {
      const result = cleanWithCount(item, 4000); redactionState.count += result.redactions; return result.text;
    }).filter(Boolean);
  }

  function validateResult(raw, expectedSourceType) {
    const errors = [];
    const warnings = [];
    const redactionState = { count: 0 };
    if (!raw || raw.format !== 'vas-ai-result' || Number(raw.schemaVersion) !== 1) errors.push('VAS-AI-RESULT.json 형식이 아닙니다.');
    const resultId = safeIdentifier(raw && raw.resultId, 'r');
    const handoffId = safeIdentifier(raw && raw.handoffId, 'h');
    if (!resultId) errors.push('resultId 형식이 올바르지 않습니다.');
    if (!handoffId) errors.push('handoffId 형식이 올바르지 않습니다.');
    const iteration = Number(raw && raw.iteration);
    if (!Number.isInteger(iteration) || iteration < 1 || iteration > 9999) errors.push('iteration 값이 올바르지 않습니다.');
    const sourceType = SOURCE_TYPES.has(raw && raw.sourceType) ? raw.sourceType : '';
    if (!sourceType) errors.push('sourceType이 필요합니다.');
    if (expectedSourceType && sourceType && sourceType !== expectedSourceType && !(expectedSourceType === 'existing' && sourceType === 'registered')) errors.push('현재 선택한 작업 종류와 결과의 sourceType이 다릅니다.');
    let status = RESULT_STATUS.has(raw && raw.status) ? raw.status : '';
    if (!status) errors.push('결과 상태가 올바르지 않습니다.');
    const hash = raw && raw.handoffPayloadSha256;
    if (hash != null && hash !== '' && !/^[a-f0-9]{64}$/i.test(String(hash))) errors.push('handoffPayloadSha256 형식이 올바르지 않습니다.');

    const readback = raw && raw.readback || {};
    const checkedFiles = [];
    (Array.isArray(readback.checkedFiles) ? readback.checkedFiles : []).slice(0, 100).forEach(function (path) {
      const safe = safeRelative(path); if (!safe) errors.push('읽은 파일에 안전하지 않은 경로가 있습니다.'); else checkedFiles.push(safe);
    });
    const confirmedEntrypoints = [];
    (Array.isArray(readback.confirmedEntrypoints) ? readback.confirmedEntrypoints : []).slice(0, 50).forEach(function (path) {
      const safe = safeRelative(path); if (!safe) errors.push('진입점에 안전하지 않은 경로가 있습니다.'); else confirmedEntrypoints.push(safe);
    });
    const commands = (Array.isArray(readback.commands) ? readback.commands : []).slice(0, 50).map(function (item) {
      const command = cleanWithCount(item && item.command, 500); redactionState.count += command.redactions;
      const source = item && item.source ? safeRelative(item.source) : null;
      if (item && item.source && !source) errors.push('명령 출처에 안전하지 않은 경로가 있습니다.');
      return { kind: clean(item && item.kind, 20), command: command.text, source: source };
    });
    const changes = raw && raw.changes || {};
    const relativeFiles = [];
    (Array.isArray(changes.relativeFiles) ? changes.relativeFiles : []).slice(0, 100).forEach(function (item) {
      const path = safeRelative(item && item.path);
      const action = ACTIONS.has(item && item.action) ? item.action : '';
      const fromPath = item && item.fromPath ? safeRelative(item.fromPath) : null;
      if (!path || !action || (item && item.fromPath && !fromPath)) errors.push('변경 파일 경로 또는 작업 형식이 올바르지 않습니다.');
      else relativeFiles.push({ path: path, action: action, fromPath: fromPath });
    });
    const tests = (Array.isArray(raw && raw.tests) ? raw.tests : []).slice(0, 50).map(function (item) {
      const state = TEST_STATUS.has(item && item.status) ? item.status : 'skipped';
      const name = cleanWithCount(item && item.name, 200); const command = cleanWithCount(item && item.command, 500); const summary = cleanWithCount(item && item.summary, 1000);
      redactionState.count += name.redactions + command.redactions + summary.redactions;
      return { name: name.text || '검증', command: command.text, status: state, summary: summary.text };
    });
    if (status === 'complete' && tests.some(function (item) { return item.status === 'failed'; })) {
      status = 'incomplete'; warnings.push('실패한 테스트가 있어 상태를 incomplete로 바꿨습니다.');
    }
    const remaining = (Array.isArray(raw && raw.remaining) ? raw.remaining : []).slice(0, 50).map(function (item) {
      const summary = cleanWithCount(item && item.summary, 1000); const action = cleanWithCount(item && item.nextAction, 1000);
      redactionState.count += summary.redactions + action.redactions;
      return { severity: SEVERITIES.has(item && item.severity) ? item.severity : 'medium', summary: summary.text, nextAction: action.text };
    }).filter(function (item) { return item.summary || item.nextAction; });
    const changeSummary = cleanWithCount(changes.summary, 8000); const nextTask = cleanWithCount(raw && raw.nextRecommendedTask, 4000);
    redactionState.count += changeSummary.redactions + nextTask.redactions;
    const normalizedResult = {
        format: 'vas-ai-result', schemaVersion: 1, resultId: resultId, handoffId: handoffId,
        handoffPayloadSha256: /^[a-f0-9]{64}$/i.test(String(hash || '')) ? String(hash) : null,
        iteration: iteration, sourceType: sourceType, status: status,
        generatedBy: { tool: clean(raw && raw.generatedBy && raw.generatedBy.tool, 80) || 'other' },
        readback: {
          checkedFiles: checkedFiles,
          confirmedRules: safeStringArray(readback.confirmedRules, 50, redactionState),
          confirmedEntrypoints: confirmedEntrypoints, commands: commands,
          facts: safeStringArray(readback.facts, 50, redactionState), assumptions: safeStringArray(readback.assumptions, 50, redactionState)
        },
        changes: { summary: changeSummary.text, relativeFiles: relativeFiles }, tests: tests, remaining: remaining,
        nextRecommendedTask: nextTask.text,
        safety: { absolutePathsExcluded: true, secretsExcluded: true, rawCommandOutputExcluded: true }
      };
    if (redactionState.count) warnings.push('민감 정보 또는 절대 경로 ' + redactionState.count + '건을 제거했습니다.');
    return {
      ok: errors.length === 0, errors: Array.from(new Set(errors)), warnings: warnings,
      redactions: redactionState.count, result: normalizedResult
    };
  }

  function continuation(result, verdict, note) {
    return {
      included: true, resultId: result.resultId, sourceHandoffId: result.handoffId,
      previousStatus: result.status, userVerdict: verdict === 'needs-revision' ? 'needs-revision' : 'accepted',
      changeSummary: clean(result.changes && result.changes.summary, 2000),
      relativeFiles: (result.changes && result.changes.relativeFiles || []).map(function (item) { return item.path; }).slice(0, 100),
      tests: (result.tests || []).map(function (item) { return { name: item.name, status: item.status, summary: item.summary }; }).slice(0, 50),
      remaining: (result.remaining || []).slice(0, 50), correction: clean(note, 2000)
    };
  }

  global.VASAgentContract = Object.freeze({
    clean: clean, sanitize: sanitize, stable: stable, digest: digest, finalize: finalize,
    approvedRag: approvedRag, normalizeHandoff: normalizeHandoff, validateResult: validateResult,
    continuation: continuation, safeRelative: safeRelative
  });
})(window);
