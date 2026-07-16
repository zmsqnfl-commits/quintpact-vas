# 접근 제어

## 역할

| 역할 | 주 쓰기 영역 | 제한 |
|---|---|---|
| Architect | 설계 문서 | 운영 코드 직접 변경 금지 |
| Designer | `src/assets/`, UI 명세 | 사용자 데이터 접근 금지 |
| Implementer | `src/`, `scripts/` | 테스트 결과 조작 금지 |
| Reviewer | 리뷰 결과 | 기능 파일 직접 변경 금지 |
| Tester | `tests/` | 사용자 원본 변경 금지 |
| Security | 릴리즈 검증·로그 | 검증 전 배포 금지 |

## 동적 정책

- `review_before_release`: 리뷰와 단일 테스트 전 배포 금지
- `source_read_only`: 기존 프로젝트는 승인 전 읽기만 허용
- `staging_only`: 가져오기는 staging 검증 후에만 대상 승격
- `sensitive_data_guard`: `.env`, 키, 토큰, 개인화 원문은 Git·배포 금지
- `consent_required`: 동의 전 사용 이벤트 저장 금지
- `workspace_isolation`: 사용자 산출물은 `workspace/projects/` 밖에 쓰지 않음
- `stress_test_opt_in`: 10회 검사는 명시적 요청 때만 허용

GitHub Pages와 릴리즈에는 `workspace/`, 백업, 캐시, 테스트 결과, 환경 변수 파일이 포함되지 않습니다.
