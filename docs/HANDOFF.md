# VAS 2.6.2 인계

## 사용자용 AI 전달팩

기본 흐름은 `project-import.html → 폴더 선택/분석 → JSON 미리보기 → 전달팩 저장 및 프롬프트 복사`입니다.

- 공통 파일명: `VAS-AI-HANDOFF.json`
- 선택 파일: `VAS-AI-SOURCE.zip` (`START-HERE.md`, `PROMPT.md`, JSON, manifest, 검토 발췌, SHA-256)
- 사용 대상: Codex, Claude, Antigravity 및 JSON 첨부가 가능한 코딩 도구
- 실제 수정 기준: 사용자가 코딩 도구에서 연 원본 프로젝트 폴더
- 제외: 절대 경로, 비밀값, 개인화 메모리, 비승인 파일 내용

## 개발 인계 기준

- 단일 작업 원본: `src/`, `docs/`, `scripts/`, `tests/`
- 사용자 데이터: `workspace/`이며 Git·배포에서 제외
- 배포 생성: `python scripts/build_release.py`
- 기존 키 호환: `vasFavorites`, `vasThemeHistory`, `vasThemeTokens`, `vasCurrentPreset`
- 모든 화면: 외부 CDN 없이 시스템 sans/mono 사용

## 검증

```powershell
git status --short
npm.cmd run knowledge:check
npm.cmd run test:python
npm.cmd run test:browser
npm.cmd run test:package
```

10회 스트레스 테스트는 사용자가 명시한 경우에만 실행합니다. 릴리스 전 캐시·비밀·사용자 데이터가 스테이징되지 않았는지 확인합니다.
