/** Completion assessment. Submitted reports never become locally observed evidence. */
(function (global) {
  'use strict';
  const METHODS = ['automatic', 'manual', 'static'];
  const OUTCOMES = ['passed', 'failed', 'skipped', 'not-applicable'];
  function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function text(value) { return typeof value === 'string' && value.trim().length > 0; }
  function criteriaValid(criteria) {
    return Array.isArray(criteria) && criteria.length <= 20 && criteria.every(function (item) {
      return object(item) && /^C[1-9][0-9]*$/.test(item.id || '') && text(item.description) &&
        METHODS.includes(item.method) && typeof item.required === 'boolean';
    }) && new Set(criteria.map(function (item) { return item.id; })).size === criteria.length;
  }
  function validResult(result) {
    return object(result) && result.format === 'vas-ai-result' && result.schemaVersion === 1 &&
      Number.isInteger(result.iteration) && result.iteration >= 1 && result.iteration <= 9999 &&
      ['complete', 'incomplete', 'blocked', 'failed'].includes(result.status) &&
      Array.isArray(result.tests) && result.tests.length <= 50 && result.tests.every(function (item) {
        return object(item) && ['passed', 'failed', 'skipped'].includes(item.status);
      }) && Array.isArray(result.remaining) && result.remaining.length <= 50 && result.remaining.every(function (item) {
        return object(item) && ['low', 'medium', 'high', 'blocker'].includes(item.severity);
      }) && (result.evidence === undefined || (Array.isArray(result.evidence) && result.evidence.length <= 50 && result.evidence.every(function (item) {
        return object(item) && text(item.criterionId) && text(item.artifactVersion) && METHODS.includes(item.method) && OUTCOMES.includes(item.outcome);
      }))) && (result.scopeViolation === undefined || typeof result.scopeViolation === 'boolean');
  }
  function observationValid(item, result, criterion) {
    return object(item) && item.criterionId === criterion.id && item.source === 'user-direct' &&
      item.artifactVersion === result.artifactVersion && ['manual', 'static'].includes(item.method) &&
      (item.method === criterion.method || item.alternativeApproved === true) &&
      OUTCOMES.includes(item.outcome) && text(item.summary) && text(item.observedAt) &&
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(item.observedAt) &&
      Number.isFinite(Date.parse(item.observedAt)) && new Date(item.observedAt).toISOString() === item.observedAt;
  }
  function evaluate(result, context) {
    context = object(context) ? context : {};
    const answer = { status: 'needs-verification', reasons: [], conditions: [], evidenceSource: 'local-user-review' };
    function finish(status, reason) { answer.status = status; if (reason) answer.reasons.push(reason); return answer; }
    if (!validResult(result)) return finish('invalid', 'invalid-result');
    if (['mismatch', 'invalid', 'unsupported'].includes(context.linkStatus)) return finish('invalid', 'handoff-mismatch');
    const criteria = context.criteria === undefined ? [] : context.criteria;
    if (!criteriaValid(criteria)) return finish('invalid', 'invalid-criteria');
    const observations = Array.isArray(context.observations) ? context.observations : [];
    const failures = [];
    if (result.status === 'failed') failures.push('reported-failure');
    if (result.status === 'blocked' || result.remaining.some(function (item) { return item.severity === 'blocker'; })) failures.push('unresolved-blocker');
    if (result.tests.some(function (item) { return item.status === 'failed'; })) failures.push('failed-test');
    if (result.scopeViolation === true) failures.push('scope-violation');
    const evidence = result.evidence || [];
    criteria.forEach(function (criterion) {
      const own = observations.filter(function (item) { return observationValid(item, result, criterion); }).pop();
      const allSubmitted = evidence.filter(function (item) { return item.criterionId === criterion.id; });
      const submitted = allSubmitted.filter(function (item) { return item.artifactVersion === result.artifactVersion; });
      if (allSubmitted.length !== submitted.length) answer.reasons.push('artifact-evidence-mismatch:' + criterion.id);
      const failed = (own && own.outcome === 'failed') || submitted.some(function (item) { return item.outcome === 'failed'; });
      if (failed) failures.push('failed-criterion:' + criterion.id);
      answer.conditions.push({ id: criterion.id, required: criterion.required,
        status: failed ? 'failed' : own && own.outcome === 'passed' ? 'confirmed' : 'unconfirmed',
        source: failed ? own && own.outcome === 'failed' ? 'user-direct' : 'agent-submitted' : own ? 'user-direct' : submitted.length ? 'agent-submitted' : 'missing' });
    });
    if (failures.length) { answer.reasons = failures; return finish('incomplete'); }
    if (context.linkStatus !== 'verified') answer.reasons.push('handoff-unverified');
    if (!criteria.length || !criteria.some(function (item) { return item.required; })) answer.reasons.push('missing-required-criteria');
    if (!text(result.artifactVersion)) answer.reasons.push('missing-artifact-version');
    answer.conditions.filter(function (item) { return item.required && item.status !== 'confirmed'; }).forEach(function (item) {
      answer.reasons.push('unconfirmed-criterion:' + item.id);
    });
    if (answer.reasons.length) return answer;
    return finish('complete');
  }
  global.VASResultAssessment = Object.freeze({ evaluate: evaluate, criteriaValid: criteriaValid });
})(typeof window === 'undefined' ? globalThis : window);
