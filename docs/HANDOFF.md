# VAS 2.6.1 인계

## 기준

- 단일 작업 원본: `src/`, `docs/`, `scripts/`, `tests/`
- 사용자 데이터: `workspace/`이며 Git·배포에서 제외
- 배포 생성: `python scripts/build_release.py`
- 시스템 지도: `docs/index.md`
- 운영: `docs/OPERATIONS.md`

## 시작 점검

```powershell
git status --short
npm.cmd ci
python -m pip install -r tests/requirements-dev.txt
npm.cmd run knowledge:check
npm.cmd run test:python
npm.cmd run test:browser
```

## 핵심 호환성

- 진입점: `Run-VAS-System.bat`, `src/vas-hub.html`, 독립 신청서 `index.html`
- 기존 테마 키: `vasFavorites`, `vasThemeHistory`, `vasThemeTokens`, `vasCurrentPreset`
- 기존 색상·간격은 보존하고 레거시 폰트만 시스템 폰트로 정규화
- 개인화는 명시적 동의 전 비활성

## 릴리즈 전

1. 단일 테스트와 브라우저 테스트를 통과시킵니다.
2. `npm.cmd run test:package`로 배포본을 생성·검증합니다.
3. 캐시·비밀·사용자 데이터가 스테이징되지 않았는지 확인합니다.
4. `docs/log.md`에 변경 이유와 검증 결과를 한 번만 기록합니다.

10회 스트레스 테스트는 사용자가 명시한 경우에만 실행합니다.
