---
name: security
description: VAS Git·배포 산출물에 비밀 파일과 사용자 데이터가 섞이지 않았는지 확인한다.
---
# security

`python scripts/agent_checks.py security`로 추적 경로와 실제 배포 ZIP manifest·해시·제외 규칙을 확인한다.
배포가 없거나 오래된 경우 `npm.cmd run test:package`로 재생성·검증한다. 검증 실패는 종료 코드와 항목으로 보고한다.
사용자 원본, .env, 키·토큰 파일 내용을 읽거나 보고서에 넣지 않는다.
이 검사는 배포 경계 검사다. 코드 전체 취약점이나 의존성 보안 감사를 완료했다고 보고하지 않는다.
