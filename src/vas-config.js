/** VAS 런타임에서 공유하는 버전·스키마 상수입니다. */
(function (global) {
  'use strict';

  global.VASConfig = Object.freeze({
    version: '2.6.1',
    themeStateSchema: 1,
    personalizationSchema: 1,
    knowledgeSchema: 1,
    personalizationDbName: 'vas-personalization',
    memoryWarningEvents: 2000,
    maxRagContextChars: 4000
  });
})(typeof window !== 'undefined' ? window : globalThis);
