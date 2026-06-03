# NAS Client Form Package

이 폴더는 외부 공유용 Client Form만 담은 NAS 업로드 패키지입니다.

## 업로드 방법

1. `final/nas-client-form/` 폴더 전체를 NAS 웹 공유 위치에 업로드합니다.
2. 외부 공유 진입점은 `index.html`입니다.
3. 신청자는 브라우저에서 신청서를 작성한 뒤 `JSON 파일 저장` 버튼으로 결과 파일을 저장합니다.
4. 저장된 JSON 파일은 담당자에게 별도로 전달해야 합니다.
5. 참고 파일은 자동 업로드되지 않습니다. 화면에는 파일명만 기록되므로 실제 파일은 별도로 전달해야 합니다.

## 포함 범위

- Client Form HTML
- Client Form CSS
- Client Form JavaScript
- 이 README

## 제외 범위

- VAS 내부 허브
- 디자인 스튜디오
- 테스트 파일
- handoff 문서
- 운영 데이터
- 서버 저장/전송 기능
- 실제 파일 업로드 기능

## 주의

이 패키지는 정적 HTML 패키지입니다.
서버 저장, NAS 자동 업로드, 실제 제출 기능은 포함하지 않습니다.
