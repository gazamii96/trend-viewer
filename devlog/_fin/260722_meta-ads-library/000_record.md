---
created: 2026-07-22
tags: [trend-viewer, meta-ads, ad-library, curl, frontend]
aliases: [Meta 광고 라이브러리 완료 기록, meta_ads record, 광고 탭]
---

# 260722 meta-ads-library

## Summary

Meta 광고 라이브러리(공개 투명성 페이지)를 로그인 없이 검색해 광고 레퍼런스를
모아보는 `meta_ads` 모듈과 광고 탭을 추가했다. 키워드 검색(`keyword_unordered`)이
광고 문구와 페이지 이름을 함께 매칭하므로 "키워드 또는 페이지 이름" 검색을 한
입력으로 처리하고, 결과에 등장한 광고주 페이지를 칩으로 집계해 클릭 시
`view_all_page_id` 페이지 검색으로 드릴다운한다.

## Changes

- `src/meta_ads/meta_ads_tool.py` (신규): curl subprocess 수집(urllib TLS 차단 우회),
  `__rd_verify` 챌린지 자동 해결과 쿠키 jar(`config/meta_ads_cookies.txt`) 유지,
  HTML 임베디드 JSON 파싱(walk 방식, doc_id 불필요), 미디어 폴백
  (videos→images→carousel cards), 페이지 집계, 120초 negative TTL 캐시.
- `src/meta_ads/test_meta_ads_tool.py` (신규): 파서·URL 빌더·챌린지 루프·오류
  계약·캐시 TTL을 mock 기반으로 검증하는 16개 테스트.
- `src/main.py`: `/api/meta_ads` 라우트 (`q` 필수, `type=keyword|page`,
  `country=KR|US|JP|ALL`, `status`, `media`, `force`; page 모드는 숫자 page_id만
  허용). 표준 status/errors 계약을 따른다.
- `src/frontend/index.html`: 광고 탭(메가폰 아이콘, `--c-meta` 색), 검색 폼과
  국가·게재 상태·미디어 필터, 페이지 칩 드릴다운/뒤로가기 칩, 광고 카드
  (크리에이티브 썸네일, 문구, CTA, 게재 상태·시작일·플랫폼·유사 소재 수,
  광고 라이브러리 영구 링크, 북마크), 빈 상태·오류 상태 처리.
- `devlog/str_func/meta_ads.md`: 모듈 문서.
- `README.md`: 광고 탭 상세, API 표, 프로젝트 구조, 테스트 수 갱신.

## Verification

- `python -m unittest discover -s src -p 'test_*.py'` → 195 tests OK (기존 179 + 16).
- 라이브 검색 "방치형 RPG" (KR, 게재 중) → 28건, 전체 약 976건, 페이지 칩
  7개(메이플 키우기 17건 등). 브라우저에서 카드·썸네일(30/30 로드)·순위·메타
  표시 확인.
- 페이지 칩 "메이플 키우기" 클릭 → page 모드 30건(전체 약 205건), 뒤로가기 칩
  동작 확인.
- `/api/img` 프록시로 서명된 fbcdn 썸네일 200 OK (기존 `.fbcdn.net` 허용 목록
  그대로 사용).
- 서버 캐시 확인: 같은 검색 재요청 시 재수집 없이 "1분 전 수집" 표시.

## Risks

- 비공식 경로다. Meta가 챌린지 방식·임베디드 JSON 구조·헤더 요구사항을 바꾸면
  깨질 수 있다. 실패 시 errors 계약으로 화면에 이유가 표시되고 120초 뒤
  재시도한다.
- 첫 페이지 30건 제한. 페이지네이션은 GraphQL doc_id가 필요해 v1에서 제외했다
  (Threads의 doc_id 로테이션 문제를 다시 들이지 않기 위한 의도적 선택).
- 페이지 이름 검색은 키워드 매칭에 의존하므로 광고를 집행하지 않는 페이지나
  이름이 광고 문구와 겹치지 않는 페이지는 칩에 나타나지 않을 수 있다.

## 후속 작업 — 페이지네이션 · doc_id config · 대만

사용자 요청으로 "더 보기" 페이지네이션, doc_id 교체 config, 대만 국가를 추가했다.

### 추가 구현

- `src/meta_ads/meta_ads_tool.py`: `fetch_first_page`(첫 페이지 + cursor/lsd 추출),
  `fetch_more`(AdLibrarySearchPaginationQuery GraphQL 재현), `_parse_graphql`
  (`for (;;);` 프리픽스 처리), `_build_variables`, doc_id config 로드
  (`config/meta_ads_doc_ids.json` 우선 + 내장 기본값 `24922295957467452` + 만료
  플래그), 검색별 lsd/sessionID `_context` 저장, `get_meta_ads(..., cursor)`로
  첫 페이지/페이지네이션 분기. COUNTRIES에 `TW` 추가.
- `src/main.py`: `/api/meta_ads`에 `cursor` 파라미터 추가.
- `src/frontend/index.html`: 국가 select에 대만, "더 보기" 버튼(`#adsMoreBtn`)과
  누적 렌더링(`appendAds` dedupe), `loadMoreAds`, 로딩 상태 표시.
- `src/meta_ads/test_meta_ads_tool.py`: 27개로 확장(페이지네이션·doc_id·parse_graphql·
  TW·context 저장·cursor 재사용).

### 리버스 엔지니어링 근거 (인앱 브라우저로 실제 요청 캡처)

- 페이지네이션은 `POST https://www.facebook.com/api/graphql/`,
  `fb_api_req_friendly_name=AdLibrarySearchPaginationQuery`, `doc_id=24922295957467452`.
- 최소 폼: lsd, fb_api_caller_class=RelayModern, friendly_name, variables(JSON),
  server_timestamps=true, doc_id, __a=1. fb_dtsg는 로그아웃이라 불필요.
- **커서는 세션(쿠키 자)에 묶임** — 새 자로는 error 1357054로 거부됨(검증). 그래서
  단일 영속 자 공유 + 첫 페이지 lsd 재사용 설계.
- GraphQL POST에 전체 헤더(X-FB-LSD, Origin, Referer, Sec-Fetch-* cors,
  X-FB-Friendly-Name) 필수 — 누락 시 error 페이지(검증).

### 검증

- `python -m unittest discover -s src -p 'test_*.py'` → 206 tests OK (195 + 11).
- 헤드리스 curl 재현: 첫 페이지 cursor → GraphQL 다음 페이지 10건 + 다음 커서,
  같은 자에서 연속 2회 체이닝 성공.
- 브라우저 라이브: "방치형 RPG"(KR) 28건 → 더 보기 38 → 48건 누적 확인. 대만(TW)
  "puzzle game" 30건(전체 약 3.7천건) 확인.

## 변경 기록

- 2026-07-22: meta_ads 모듈·API·광고 탭 구현과 라이브 검증을 완료 기록으로 정리했다.
- 2026-07-22: GraphQL 페이지네이션("더 보기"), doc_id config, 대만(TW) 국가 추가와
  라이브 검증을 기록에 덧붙였다.
