# 테스트

- `npm.cmd run test:python`: 단일 기능·무결성·런타임·마이그레이션 검사
- `npm.cmd run test:browser`: 실제 브라우저 사용자 흐름
- `npm.cmd run test:package`: 배포 ZIP·Pages·해시·재현성 검사
- `npm.cmd run test:release`: 위 검사와 10회 스트레스 검사

평소에는 앞의 세 명령까지만 사용합니다. 10회 검사는 사용자가 명시한 경우에만 실행합니다.
