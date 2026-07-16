# VAS 2.6.0 시스템 지도

## 사용자 흐름

```text
Run-VAS-System.bat
  -> 로컬 서버 + 허브
     -> 새 프로젝트 -> 의뢰서/디자인 -> workspace/projects
     -> 기존 프로젝트 -> 분석/승인/복제 -> workspace/projects
     -> 지식 검색/RAG -> 관련 문서와 이전 작업 추천
     -> 내 메모리 -> 동의/일시정지/삭제/내보내기
```

## 구성

| 영역 | 역할 | 기준 파일 |
|---|---|---|
| 허브 | 첫 실행, 프로젝트 목록, 기능 연결 | `src/vas-hub.html` |
| 신청서 | 요구사항 입력, 초안 복원, JSON 저장 | `src/client-application.html` |
| 디자인 | 테마 편집과 상태 전달 | `src/design-controller.html` |
| 가져오기 | 폴더 분석·승인·진행·되돌리기 | `src/project-import.html` |
| 개인화 | 동의 기반 이벤트와 추천 | `src/personalization-store.js` |
| RAG | 로컬 지식 색인·검색·프롬프트 보강 | `src/rag-lite.js` |
| 런타임 | 토큰·동일 출처 보호 로컬 HTTP API | `scripts/Start-VAS.ps1` |
| 마이그레이션 | 아카이브·해시·원자적 배치·롤백 | `scripts/vas_project_import.py` |
| 배포 | 재현 가능한 ZIP/Pages 생성 | `scripts/build_release.py` |

## 저장 위치

- 작업 원본: `src/`, `docs/`, `scripts/`, `tests/`
- 사용자 프로젝트·가져오기 상태: `workspace/` (Git 제외)
- Windows 개인화 메모리: `%LOCALAPPDATA%\QUINTPACT\VAS\` (Git·배포 제외)
- 로컬 체크포인트: `.vas_backups/` (Git 제외)
- 생성 배포물: `dist/` (Git 제외)
- 공개 배포에는 사용자 데이터와 메모리를 포함하지 않습니다.

## 운영 원칙

- 모든 기능은 외부 CDN 없이 동작합니다.
- 저장소가 차단되거나 손상돼도 기본값으로 실행합니다.
- 폴더 가져오기는 분석 전 실행 금지, 승인 전 쓰기 금지입니다.
- 저장소 내부 배포 미러는 사용하지 않습니다. 배포본은 매번 원본에서 생성합니다.
- 파일은 500줄 이하로 유지합니다.
- 고정 커밋 번호나 고정 테스트 개수를 문서에 기록하지 않습니다.

관련 문서: `docs/OPERATIONS.md`, `docs/MIGRATION.md`, `docs/import-existing-project.md`, `docs/HANDOFF.md`.
