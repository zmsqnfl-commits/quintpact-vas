/** Version-labelled source references are metadata, never automatically loaded assets. */
(function (global) {
  'use strict';
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
    if (!value) return '';
    return '디자인 시각 참조 (미확인):\n' + JSON.stringify(value, null, 2) + '\n' + instructions +
      (value.samplePreset ? '' : '\n이 스타일의 공개 샘플은 없습니다. 다른 스타일의 샘플로 대체하지 말고 확정 토큰을 기준으로 구현하세요.') + '\n\n';
  }

  global.VASDesignReference = Object.freeze({ reference: reference, attach: attach, prompt: prompt });
})(window);
