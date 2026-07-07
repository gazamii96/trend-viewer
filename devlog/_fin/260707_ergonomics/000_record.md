# WP4 반복 사용성 개선 기록

이번 작업은 트렌드 뷰어를 매일 반복해서 볼 때 같은 항목을 다시 훑는 부담을 줄이고, 필터 상태를 URL로 공유하거나 복원할 수 있게 만드는 데 초점을 맞췄다. 변경 범위는 단일 프론트엔드 파일 `src/frontend/index.html`에 한정했고, 서버와 데이터 수집 계층은 건드리지 않았다.

---

### src/frontend/index.html — 본 항목 표시와 초기화 버튼
- **Changes**: `trend-viewer:seen:v1` localStorage 키를 추가해 카드 활성화 시 stable id를 FIFO 800개까지 저장한다. 저장 파싱 실패는 빈 목록으로 복구하며, `wireCardAction()`이 click/Enter/Space 활성화 경로를 공통 처리한다. 북마크와 삭제 버튼은 기존처럼 이벤트 전파를 막으므로 seen 처리에서 제외된다. 본 항목은 `.seen` 클래스로 썸네일과 제목 계층만 흐리게 표시하고, hover/focus-visible에서는 원래 선명도로 돌아온다. 헤더의 `#clearSeenBtn`은 저장소를 비우고 현재 렌더된 `.seen` 클래스를 즉시 제거한다.
- **Impact**: 공통 카드 생성기 `createTrendCard()`와 홈 row `createHomeRow()`, 저장 카드 `savedCard()`가 같은 seen 저장 규칙을 공유한다. 관련 위치: `src/frontend/index.html:59`, `src/frontend/index.html:64`, `src/frontend/index.html:306`, `src/frontend/index.html:437`, `src/frontend/index.html:720`, `src/frontend/index.html:829`, `src/frontend/index.html:1476`, `src/frontend/index.html:1624`, `src/frontend/index.html:1934`.
- **Verification**: `python3 -m unittest discover -s src -p 'test_*.py'` 실행 결과 60개 테스트 통과. `TREND_VIEWER_PORT=8795 python3 src/main.py` 후 `curl -s http://localhost:8795/ | grep -c 'trend-viewer:seen'` 결과 `1`.

### src/frontend/index.html — URL hash 상태와 키보드 이동
- **Changes**: `#tab`, `#cat`, `#period`, `#q`를 `URLSearchParams`로 인코딩하고 기본값은 생략한다. 부팅 시 hash를 먼저 읽어 `state.category`, `state.period`, `state.search`와 입력/기간 UI를 복원한 뒤 `switchTab(restoredTab)`을 한 번만 호출한다. 알 수 없는 tab은 `home`, 알 수 없는 period는 `week`로 되돌린다. 전역 keydown 핸들러는 Escape 처리와 함께 1-9 탭 전환, `/` 검색 포커스를 담당하며 입력/textarea/select/contenteditable 또는 meta/ctrl/alt 조합에서는 단축키를 실행하지 않는다.
- **Impact**: 탭 클릭, 홈 점프, 숫자 단축키, 검색 제출, 카테고리/기간 변경이 모두 같은 hash 갱신 경로를 지난다. 관련 위치: `src/frontend/index.html:547`, `src/frontend/index.html:602`, `src/frontend/index.html:655`, `src/frontend/index.html:666`, `src/frontend/index.html:1050`, `src/frontend/index.html:1907`, `src/frontend/index.html:1923`, `src/frontend/index.html:1940`.
- **Verification**: `rg -n "then\\(\\(\\) => switchTab|switchTab\\('home'\\)" src/frontend/index.html`로 시작부 `switchTab` 호출이 복원 탭을 쓰는 한 곳만 남은 것을 확인했다. `python3 -m unittest discover -s src -p 'test_*.py'` 통과.

### src/frontend/index.html — 모바일 탭 한 줄 유지
- **Changes**: `.tabs`를 `nowrap` + 가로 스크롤로 바꾸고 스크롤바는 숨겼다. roving arrow-key 탭 이동 후에는 포커스된 탭을 `scrollIntoView({ inline: 'nearest', block: 'nearest' })`로 보이게 했고, 선택 탭도 렌더 후 같은 방식으로 가시 영역에 들어오게 했다.
- **Impact**: 데스크톱에서는 기존처럼 한 줄로 보이고, 모바일에서는 탭이 줄바꿈으로 헤더 아래를 밀지 않는다. 관련 위치: `src/frontend/index.html:64`, `src/frontend/index.html:547`, `src/frontend/index.html:586`.
- **Verification**: 서버 smoke에서 HTML 응답을 확인했고, 단일 HTML/CSS 변경이라 stdlib 서버 동작에는 영향이 없음을 유닛 테스트로 확인했다.
