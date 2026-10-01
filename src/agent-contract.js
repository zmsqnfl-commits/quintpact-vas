/** VAS AI 인계 v3·결과 v1 공용 계약과 안전 검증. */
(function (global) {
  'use strict';

  // Match credential field names, never the plural design.tokens container.
  const CREDENTIAL_NAMES = '(?:[a-z0-9]+[_-])*(?:password|pgpassword|passwd|pwd|passphrase|secret|secrets|credential|credentials|api[_ -]?key|(?:access|refresh|auth|session)[_ -]?token|token|client[_ -]?secret|authorization|private[_ -]?key|database[_ -]?url|db[_ -]?(?:url|password|pass)|(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|aws[_ -]?(?:secret[_ -]?)?access[_ -]?key(?:[_ -]?id)?|connection[_ -]?string|github[_ -]?pat)';
  const CREDENTIAL_KEY = new RegExp('^' + CREDENTIAL_NAMES + '$', 'i');
  const GAP = String.raw`\s*(?:(?:/\*[\s\S]*?\*/|//[^\r\n]*)\s*)*`;
  const ASSIGNMENT = new RegExp(String.raw`\b` + CREDENTIAL_NAMES + String.raw`\b["']?` + GAP + String.raw`(?:\]` + GAP + ')?[:=]' + GAP + '("(?:\\\\.|[^"\\\\])*(?:"|$)|\'(?:\\\\.|[^\'\\\\])*(?:\'|$)|`(?:\\\\.|[^`\\\\])*(?:`|$)|(?:Bearer|Basic)\\s+[^\\s,;]+|[^\\s,;]+)', 'gi');
  const TRIPLE_ASSIGNMENT = new RegExp(String.raw`\b` + CREDENTIAL_NAMES + String.raw`\b["']?` + GAP + String.raw`(?:\]` + GAP + ")?[:=]" + GAP + "(?:[rbuf]{0,2})(\"{3}|'{3})(?:\\\\[\\s\\S]|(?!\\1)[^\\\\])*(?:\\1|\\\\?$)", 'gi');
  const XML_CREDENTIAL = new RegExp('<(?:[^\\s<>/=:]+:)?' + CREDENTIAL_NAMES + '(?=[\\s/>])', 'i');
  const INDEXED_CREDENTIAL = new RegExp(String.raw`\[` + GAP + "[\"'`]" + CREDENTIAL_NAMES + "[\"'`]" + GAP + String.raw`\]`, 'i');
  const SECRET = /(?:\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{12,}|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b(?:\+?82[- ]?0?1[016789]|01[016789])[- ]?\d{3,4}[- ]?\d{4})/gi;

  function sensitiveKey(key) { return CREDENTIAL_KEY.test(String(key)); }

  const ADJACENT_LITERAL = /^\s*(?:(?:\+|\\)\s*)?(?:[rbuf]{0,2})?["'`]/i;
  function redactTriples(source) {
    let ambiguous = false;
    const safe = source.replace(TRIPLE_ASSIGNMENT, function (match, quote, offset) {
      if (ADJACENT_LITERAL.test(source.slice(offset + match.length))) ambiguous = true;
      return '[redacted]';
    });
    return ambiguous ? '[redacted]' : safe;
  }

  function redactYamlBlocks(source) {
    const lines = source.split(/\r?\n/), output = [];
    const header = new RegExp('^([ \\t]*)(?:-[ \\t]+)?["\']?' + CREDENTIAL_NAMES + '["\']?[ \\t]*:[ \\t]*[|>][1-9+-]{0,2}[ \\t]*(?:#.*)?$', 'i');
    for (let i = 0; i < lines.length; i += 1) {
      const match = header.exec(lines[i]);
      if (!match) { output.push(lines[i]); continue; }
      output.push(match[1] + '[redacted]');
      while (i + 1 < lines.length) {
        const next = lines[i + 1];
        if (next.trim() && /^[ \t]*/.exec(next)[0].length <= match[1].length) break;
        i += 1;
      }
    }
    return output.join('\n');
  }

  const CREDENTIAL_VALUE = /-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z]+ )*PRIVATE KEY-----|$)|\b(?:Bearer|Basic)\s+[a-z0-9._~+\/=-]{10,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}|\b(?:postgres(?:ql)?|mysql|mariadb|mongodb|rediss?|mssql)(?:\+[a-z0-9_.-]+)?:\/\/[^\s"'<>`]+/gi;

  // An authorization value owns its full line and any folded continuation.
  const AUTHORIZATION_FIELD = new RegExp(String.raw`\b(?:[a-z0-9]+[_-])*authorization\b["']?` + GAP + String.raw`[:=][ \t]*(?![ \t]*["'\x60])[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*`, 'gi');
  const URI_USERINFO = /\b([a-z][a-z0-9+.-]*:\/\/)[^\s/\\"<>`?#]+@/gi;

  function redactCredentials(value, depth) {
    const raw = String(value == null ? '' : value);
    const labels = raw.replace(/\\(?:u([a-f0-9]{4})|x([a-f0-9]{2}))/gi, (_, unicode, hex) => String.fromCharCode(parseInt(unicode || hex, 16)));
    if (INDEXED_CREDENTIAL.test(labels)) return '[redacted]';
    // Credential XML may contain nested markup, CDATA or an unclosed element.
    if (XML_CREDENTIAL.test(raw)) return '[redacted]';
    const source = redactYamlBlocks(redactTriples(raw));
    const level = depth || 0;
    if (level > 24) return '[redacted]';
    function scrub(item, nested) {
      if (nested > 24) return '[redacted]';
      if (typeof item === 'string') return redactCredentials(item, nested + 1);
      if (Array.isArray(item)) return item.map(function (child) { return scrub(child, nested + 1); });
      if (item && typeof item === 'object') {
        const out = Object.create(null);
        Object.keys(item).forEach(function (key) {
          out[redactCredentials(key, nested + 1)] = sensitiveKey(key) ? '[redacted]' : scrub(item[key], nested + 1);
        });
        return out;
      }
      return item;
    }
    // Keep valid JSON byte-for-byte unless a credential is actually removed.
    try {
      const parsed = JSON.parse(source);
      const safe = scrub(parsed, level);
      if (JSON.stringify(parsed) !== JSON.stringify(safe)) return JSON.stringify(safe);
    } catch (error) { /* Free text and embedded JSON use the same field policy below. */ }
    let text = source.replace(/"(?:\\.|[^"\\])*"/g, function (token, offset) {
      try {
        const decoded = JSON.parse(token);
        if (/^\s*(?::|\]\s*=)/.test(source.slice(offset + token.length))) {
          return sensitiveKey(decoded) ? JSON.stringify(decoded) : token;
        }
        const safe = redactCredentials(decoded, level + 1);
        return safe === decoded ? token : JSON.stringify(safe);
      } catch (error) { return token; }
    });
    text = text.replace(AUTHORIZATION_FIELD, '[redacted]').replace(URI_USERINFO, '$1[redacted]@');
    let complex = false;
    text = text.replace(ASSIGNMENT, function (match, value, offset) {
      // In non-JSON text, an object-valued credential has no safe scalar boundary.
      if (/^[{\[(]/.test(value) || ADJACENT_LITERAL.test(text.slice(offset + match.length))) complex = true;
      return /^(?:"\[redacted\]"|'\[redacted\]'|\[redacted\])$/.test(value) ? match : '[redacted]';
    });
    return complex ? '[redacted]' : text.replace(CREDENTIAL_VALUE, '[redacted]').replace(SECRET, '[redacted]').replace(ABSOLUTE_PATH, '[absolute-path]');
  }
  const ABSOLUTE_PATH = /file:\/\/[^\s'"`]+|(?<![A-Za-z0-9_])[A-Z]:[\\/][^\s'"`]+|\\\\[^\s]+|(?<![A-Za-z0-9_:\/])\/(?:Users|home|var|etc|mnt|volume\d*)\/[^\s'"`]+/gi;
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
    const credentials = redactCredentials(source);
    if (credentials !== source) redactions += 1;
    const text = credentials.replace(SECRET, replace).replace(ABSOLUTE_PATH, function () {
      redactions += 1; return '[absolute-path]';
    }).replace(/[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]/g, ' ').trim().slice(0, limit || 4000);
    return { text: text, redactions: redactions };
  }

  function clean(value, limit) { return cleanWithCount(value, limit).text; }

  function sanitize(value, depth, field) {
    const level = depth || 0;
    if (level > 8) return null;
    if (typeof value === 'string') return clean(value, field === 'pasteText' ? 32000 : 12000);
    if (Array.isArray(value)) return value.slice(0, 500).map(function (item) { return sanitize(item, level + 1, field); });
    if (value && typeof value === 'object') {
      const result = {};
      Object.keys(value).sort().slice(0, 500).forEach(function (key) {
        if (['__proto__', 'prototype', 'constructor'].includes(key) || sensitiveKey(key)) return;
        result[clean(key, 500)] = sanitize(value[key], level + 1, key);
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
    const safe = sanitize(document, 0);
    const changed = stable(safe) !== stable(document);
    Object.keys(document).forEach(function (key) { delete document[key]; });
    Object.assign(document, safe);
    if (document.security && changed) document.security.redactionCount = (Number(document.security.redactionCount) || 0) + 1;
    document.assistantGuide = document.assistantGuide || {};
    document.assistantGuide.target = target || document.assistantGuide.target || 'universal';
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
    if (!isObject(raw) || raw.format !== 'vas-ai-handoff' || !jsonInteger(raw.schemaVersion, 2, 3)) throw new Error('unsupported_handoff');
    ['workflow', 'context', 'task', 'project', 'assistantGuide', 'integrity', 'qualityGate', 'security'].forEach(function (key) {
      if (key in raw && !isObject(raw[key])) throw new Error('invalid_handoff_object');
    });
    if (raw.schemaVersion === 3 && raw.workflow && 'iteration' in raw.workflow && !jsonInteger(raw.workflow.iteration, 1, 9999)) throw new Error('invalid_iteration');
    const document = sanitize(raw, 0);
    if (raw.schemaVersion === 2) {
      document.schemaVersion = 3;
      document.workflow = { handoffId: '', iteration: 1, parentResultId: null, status: 'ready', legacySourceSchema: 2 };
      document.context = document.context || {};
      document.context.rag = { included: false, items: [] };
      document.context.continuation = { included: false };
      document.qualityGate = { requirementsConfirmed: false, designConfirmed: false, sourceHandlingConfirmed: false, privacyChecked: false, ragReviewed: false, continuationReviewed: true };
    }
    return finalize(document, function () { return document.assistantGuide && document.assistantGuide.pasteText || ''; }, document.assistantGuide && document.assistantGuide.target);
  }

  function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function jsonInteger(value, minimum, maximum) {
    return typeof value === 'number' && Number.isInteger(value) && value >= minimum && value <= maximum;
  }

  // Explicit recovery proposal only. Normal validation never invokes this helper.
  function repairLegacyNumbers(raw) {
    const document = clone(raw), conversions = [];
    if (!isObject(document)) return { document: document, conversions: conversions, requiresConfirmation: false };
    const slots = [[document, 'schemaVersion', 'schemaVersion', 1, 3]];
    if (document.format === 'vas-ai-result') slots.push([document, 'iteration', 'iteration', 1, 9999]);
    if (document.format === 'vas-ai-handoff' && isObject(document.workflow)) slots.push([document.workflow, 'iteration', 'workflow.iteration', 1, 9999]);
    slots.forEach(function (slot) {
      const value = slot[0][slot[1]];
      if (typeof value !== 'boolean' && !(typeof value === 'string' && /^\d+(?:\.0+)?$/.test(value.trim()))) return;
      const number = Number(value);
      if (!jsonInteger(number, slot[3], slot[4])) return;
      slot[0][slot[1]] = number;
      conversions.push({ field: slot[2], from: value, to: number });
    });
    return { document: document, conversions: conversions, requiresConfirmation: conversions.length > 0 };
  }

  function validateResult(raw, expectedSourceType) {
    const warnings = [], redactionState = { count: 0 };
    function fail(code) { throw new Error(code); }
    function object(value, code) { if (!isObject(value)) fail(code); return value; }
    function array(owner, key, maximum, itemType) {
      if (!(key in owner)) return [];
      const value = owner[key];
      if (!Array.isArray(value)) fail('invalid_' + key + '_list');
      if (value.length > maximum) fail('too_many_' + key);
      if (value.some(function (item) { return itemType === 'object' ? !isObject(item) : typeof item !== 'string'; })) fail('invalid_' + key + '_item');
      return value;
    }
    function text(owner, key, maximum, required) {
      const value = owner[key];
      if (value === undefined) { if (required) fail('invalid_' + key); return ''; }
      if (typeof value !== 'string') fail('invalid_' + key);
      if (value.length > maximum) fail('too_long_' + key);
      const safe = cleanWithCount(value, maximum); redactionState.count += safe.redactions;
      if (required && !safe.text) fail('invalid_' + key);
      return safe.text;
    }
    function relative(value, code) { const safe = typeof value === 'string' && safeRelative(value); if (!safe) fail(code); return safe; }
    function strings(owner, key, maximum) { return array(owner, key, maximum, 'string').map(function (value) { return text({ value: value }, 'value', 4000); }).filter(Boolean); }
    try {
      if (!isObject(raw) || raw.format !== 'vas-ai-result' || !jsonInteger(raw.schemaVersion, 1, 1)) fail('invalid_result_format');
      const resultId = typeof raw.resultId === 'string' && safeIdentifier(raw.resultId, 'r');
      const handoffId = typeof raw.handoffId === 'string' && safeIdentifier(raw.handoffId, 'h');
      if (!resultId) fail('invalid_result_id');
      if (!handoffId) fail('invalid_handoff_id');
      if (typeof raw.handoffPayloadSha256 !== 'string' || !/^[a-f0-9]{64}$/i.test(raw.handoffPayloadSha256)) fail('invalid_handoff_hash');
      if (!jsonInteger(raw.iteration, 1, 9999)) fail('invalid_iteration');
      if (!SOURCE_TYPES.has(raw.sourceType)) fail('invalid_source_type');
      if (expectedSourceType && raw.sourceType !== expectedSourceType && !(expectedSourceType === 'existing' && raw.sourceType === 'registered')) fail('source_type_mismatch');
      if (!RESULT_STATUS.has(raw.status)) fail('invalid_result_status');
      const readback = object('readback' in raw ? raw.readback : {}, 'invalid_readback');
      const changes = object('changes' in raw ? raw.changes : {}, 'invalid_changes');
      const generatedBy = object('generatedBy' in raw ? raw.generatedBy : {}, 'invalid_generatedBy');
      const safety = object('safety' in raw ? raw.safety : {}, 'invalid_safety_confirmation');
      const checkedFiles = array(readback, 'checkedFiles', 100, 'string').map(function (path) { return relative(path, 'unsafe_readback_path'); });
      const confirmedRules = strings(readback, 'confirmedRules', 50);
      const confirmedEntrypoints = array(readback, 'confirmedEntrypoints', 50, 'string').map(function (path) { return relative(path, 'unsafe_entrypoint_path'); });
      const commands = array(readback, 'commands', 50, 'object').map(function (item) {
        return { kind: text(item, 'kind', 20), command: text(item, 'command', 500), source: item.source == null || item.source === '' ? null : relative(item.source, 'unsafe_command_source') };
      });
      const facts = strings(readback, 'facts', 50), assumptions = strings(readback, 'assumptions', 50);
      const relativeFiles = array(changes, 'relativeFiles', 100, 'object').map(function (item) {
        const path = relative(item.path, 'unsafe_result_path');
        if (!ACTIONS.has(item.action)) fail('unsafe_result_path');
        return { path: path, action: item.action, fromPath: item.fromPath == null || item.fromPath === '' ? null : relative(item.fromPath, 'unsafe_result_path') };
      });
      const tests = array(raw, 'tests', 50, 'object').map(function (item) {
        if (!TEST_STATUS.has(item.status)) fail('invalid_test_status');
        return { name: text(item, 'name', 200) || '검증', command: text(item, 'command', 500), status: item.status, summary: text(item, 'summary', 1000) };
      });
      let status = raw.status;
      if (status === 'complete' && tests.some(function (item) { return item.status === 'failed'; })) {
        status = 'incomplete'; warnings.push('실패한 테스트가 있어 상태를 incomplete로 바꿨습니다.');
      }
      const remaining = array(raw, 'remaining', 50, 'object').map(function (item) {
        if ('severity' in item && !SEVERITIES.has(item.severity)) fail('invalid_remaining_severity');
        const entry = { severity: item.severity || 'medium', summary: text(item, 'summary', 1000), nextAction: text(item, 'nextAction', 1000) };
        if (!entry.summary && !entry.nextAction) fail('invalid_remaining_item');
        return entry;
      });
      const artifactVersion = text(raw, 'artifactVersion', 160);
      const evidence = array(raw, 'evidence', 50, 'object').map(function (item) {
        if (!['automatic', 'manual', 'static'].includes(item.method)) fail('invalid_evidence_method');
        if (!['passed', 'failed', 'skipped', 'not-applicable'].includes(item.outcome)) fail('invalid_evidence_outcome');
        return { criterionId: text(item, 'criterionId', 80, true), artifactVersion: text(item, 'artifactVersion', 160, true), method: item.method,
          outcome: item.outcome, summary: text(item, 'summary', 1000), source: 'agent-submitted' };
      });
      if ('scopeViolation' in raw && typeof raw.scopeViolation !== 'boolean') fail('invalid_scopeViolation');
      if (safety.absolutePathsExcluded !== true || safety.secretsExcluded !== true || safety.rawCommandOutputExcluded !== true) fail('invalid_safety_confirmation');
      const result = {
        format: 'vas-ai-result', schemaVersion: 1, resultId: resultId, handoffId: handoffId, handoffPayloadSha256: raw.handoffPayloadSha256,
        iteration: raw.iteration, sourceType: raw.sourceType, status: status, reportedStatus: raw.status,
        generatedBy: { tool: text(generatedBy, 'tool', 80) || 'other' },
        readback: { checkedFiles: checkedFiles, confirmedRules: confirmedRules, confirmedEntrypoints: confirmedEntrypoints, commands: commands, facts: facts, assumptions: assumptions },
        changes: { summary: text(changes, 'summary', 8000), relativeFiles: relativeFiles }, tests: tests, remaining: remaining,
        artifactVersion: artifactVersion, evidence: evidence, scopeViolation: raw.scopeViolation === true, nextRecommendedTask: text(raw, 'nextRecommendedTask', 4000),
        safety: { absolutePathsExcluded: true, secretsExcluded: true, rawCommandOutputExcluded: true }
      };
      if (redactionState.count) warnings.push('민감 정보 또는 절대 경로 ' + redactionState.count + '건을 제거했습니다.');
      return { ok: true, errors: [], errorCodes: [], warnings: warnings, redactions: redactionState.count, result: result };
    } catch (error) {
      return { ok: false, errors: ['결과 JSON을 확인하세요: ' + error.message], errorCodes: [error.message], warnings: warnings, redactions: redactionState.count, result: null };
    }
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
    clean: clean, sanitize: sanitize, sensitiveKey: sensitiveKey, redactCredentials: redactCredentials, stable: stable, digest: digest, finalize: finalize,
    approvedRag: approvedRag, normalizeHandoff: normalizeHandoff, validateResult: validateResult,
    continuation: continuation, safeRelative: safeRelative, repairLegacyNumbers: repairLegacyNumbers
  });
})(window);
