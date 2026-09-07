# Designer 참고 자료

`profiles/*.md`는 VAS Taste Profile의 관리 원본입니다. 각 파일의 제목과 목록이 브라우저·Python 인계 지침으로 생성됩니다.

새 컬렉션 10종: Bento Studio, Aurora Glass, Clay Pop, Noir Luxe, Botanical Atelier, Retro Sunset, Swiss Poster, Cyber Deck, Kinetic Type, Paper Collage. 각각 독립된 화면 구성과 프로필을 제공합니다. 조사한 스킬과 이미지·글꼴 출처는 [design-sources.md](design-sources.md)에 기록합니다.

- premiumFrontend: 절제된 고급 제품 UI
- editorialMotion: 편집형 위계와 모션
- softPremium: 부드러운 고급 UI
- minimalistUtility: 간결한 작업 도구
- industrialBrutalist: 산업적 대비와 구조
- dataTool: 데이터 탐색과 조작
- redesignGuard: 기존 디자인을 보존하는 개선

추천 샘플 4종은 별도 프로필로 연결합니다: curatedEditorial(건축 스튜디오), curatedProduct(프로젝트 보드), curatedSaas(구독 서비스), curatedKnowledge(팀 위키). 선택 목록에는 새 컬렉션 10종과 이 4종만 표시하고, 나머지 이전 프리셋은 저장된 설정의 호환용으로 유지합니다. 샘플 사이트는 현재 토큰을 담아 새 탭에서 열며, 샘플 내부 조작으로 원래 설정을 변경하지 않습니다.

Designer 스킬 또는 프로필 수정 후 `npm run agents:build`를 실행합니다.
`npm run agents:check`는 원본과 생성 결과가 같은지 검사합니다.

추가 vendor 자료는 필요할 때만 참조합니다. 사용자 선택·토큰과 현재 실행 환경의 권한이 우선합니다.
Figma 등 외부 도구는 실제 연결과 호출 가능한 기능을 확인한 뒤 사용합니다.
문서에 도구 이름이 있다는 이유로 연결·양방향 동기화·자동 실행이 제공된다고 가정하지 않습니다.
