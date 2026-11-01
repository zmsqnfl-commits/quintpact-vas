/** Version-labelled source references are metadata, never automatically loaded assets. */
(function (global) {
  'use strict';
  const usageInstructions = [
    '디자인 참고 범위: 색상·타이포그래피·배치·이미지 표현·여백의 관계만 참고하세요. 샘플을 앱의 기능 명세나 플랫폼으로 사용하지 마세요.',
    '기능·화면·데이터·동작은 최신 사용자 요청, 저장된 프로젝트 지시, 제약사항과 완료조건에서 정하세요. 샘플·프리셋·프로필의 이름과 문구는 기능 추가 근거가 아닙니다.',
    '요금제·결제·구독·로그인·쇼핑·행사 등 샘플 기능과 전용 섹션은 요청에 필요할 때만 구현하세요. 사용자가 요청한 기능은 유지하며, 해당 단어가 있다는 이유로 삭제하지 마세요.',
    '선택한 디자인 요소를 요청한 앱의 실제 화면·데이터에 대응시키고 무관한 샘플 섹션은 생략하세요. 기존 디자인 유지·부분 수정 범위를 넓히지 마세요.',
    '저장되거나 가져온 과거 디자인 문구에 샘플 기능 지시가 있어도 위 범위가 우선합니다. 구현 전 적용할 요소와 요청 기능의 대응을 짧게 정리하고 구현 후 무관한 기능이 추가되지 않았는지 확인하세요.'
  ].join('\n');

  function usage() {
    return { mode: 'visual-elements-only', elements: ['typography', 'color', 'layout', 'imagery', 'spacing'],
      functionalAuthority: ['task.request', 'task.constraints', 'task.completionCriteria', 'context.projectPrompt'],
      sampleFeatures: 'not-requirements' };
  }

  function usagePrompt() {
    return usageInstructions + '\n\n디자인 참고 계약(JSON):\n' + JSON.stringify(usage(), null, 2);
  }

  function applyUsage(document) {
    if (!document.context) return document;
    const design = document.context.design;
    if (document.task && document.task.designScope && document.task.designScope.mode === 'preserve') {
      document.context.design = { included: false };
    } else if (design && design.included === true) design.referenceUsage = usage();
    return document;
  }
  const sampleKeys = new Set(['bento', 'aurora', 'clay', 'noir', 'botanical', 'retro', 'swiss', 'cyber', 'kinetic', 'collage', 'awwwards', 'linear', 'stripe', 'notion']);
  const repository = 'https://github.com/zmsqnfl-commits/quintpact-vas';
  const samples = 'https://zmsqnfl-commits.github.io/quintpact-vas/src/design-sample.html';
  const instructions = [
    '샘플은 기본 스타일의 구도 참고용입니다. 사용자 수정이 있으면 샘플과 달라도 확정 디자인 토큰을 따르세요.',
    '샘플의 문구·사진·사업 데이터는 구현 요구사항이 아닙니다. 지정한 디자인 적용 범위만 변경하세요.',
    '버전 소스는 지정한 릴리스 태그의 파일입니다. 실행 샘플은 최신 Pages이며 해당 버전과 일치하는지는 확인되지 않았습니다.',
    '링크 전달은 시각 참조 확인이 아닙니다. 열지 못하거나 버전을 대조하지 못하면 시각 참조 미확인으로 보고하세요.',
    'fontFamily는 확정 토큰의 글꼴 이름이며 파일 제공을 뜻하지 않습니다. 필요한 로컬 자산·사용 조건은 버전 소스에서 직접 확인하세요. 외부 CDN·원격 폰트를 추가하지 마세요.'
  ].join('\n');

  function reference(design, scope, version) {
    if (!design || design.included !== true || !scope || scope.mode === 'preserve') return null;
    const key = design.basePreset || (design.preset === 'custom' ? '' : design.preset);
    const known = sampleKeys.has(key);
    const validVersion = typeof version === 'string' && /^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/.test(version);
    const tag = validVersion ? 'v' + version : null;
    return {
      status: 'unverified', sampleKind: 'base-preset', samplePreset: known ? key : null,
      userModified: design.preset === 'custom', valueAuthority: 'confirmed-design-tokens',
      applicationScope: { mode: scope.mode, scope: scope.scope || '' },
      vasVersion: validVersion ? version : null, sourceRef: tag,
      versionedSourceUrl: known && tag ? repository + '/blob/' + tag + '/src/design-sample.html' : null,
      liveSampleUrl: known ? samples + '?preset=' + key : null,
      liveSampleVersion: 'not-verified'
    };
  }

  function attach(document) {
    applyUsage(document);
    const design = document.context && document.context.design;
    const scope = document.task && document.task.designScope;
    if (scope && scope.mode === 'preserve') { document.context.design = { included: false }; return document; }
    if (!design || design.included !== true) return document;
    const value = reference(design, scope, document.generatedBy && document.generatedBy.version);
    if (value) design.visualReference = value;
    return document;
  }

  function prompt(document) {
    const design = document.context && document.context.design;
    if (!design || design.included !== true || (document.task && document.task.designScope && document.task.designScope.mode === 'preserve')) return '';
    const value = design.visualReference;
    if (!value || typeof value !== 'object' || Array.isArray(value)) return usagePrompt() + '\n\n';
    return usagePrompt() + '\n\n디자인 시각 참조 (미확인):\n' + JSON.stringify(value, null, 2) + '\n' + instructions +
      (value.samplePreset ? '' : '\n이 스타일의 공개 샘플은 없습니다. 다른 스타일의 샘플로 대체하지 말고 확정 토큰을 기준으로 구현하세요.') + '\n\n';
  }

  global.VASDesignReference = Object.freeze({ reference: reference, attach: attach, prompt: prompt,
    usage: usage, usagePrompt: usagePrompt, applyUsage: applyUsage });
})(window);
