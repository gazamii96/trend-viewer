---
created: 2026-07-22
tags: [trend-viewer, Meta, AdLibrary, curl]
aliases: [meta_ads 모듈, 광고 라이브러리 수집, Meta Ad Library]
---

# meta_ads 모듈 문서

이 문서는 `src/meta_ads/` 모듈을 다음 작업자가 바로 이어받을 수 있게 설명한다.
소스 코드를 먼저 읽고, 파일 경계와 함수 경계를 기준으로 책임을 적는다.
여기서 말하는 동기화는 코드 변경 뒤 이 문서와 테스트 관점도 함께 맞추는 일을 뜻한다.

---

## File Tree

| 파일 | 라인 수 | 역할 |
|---|---:|---|
| `src/meta_ads/__init__.py` | 18 | 배럴 export (검색·페이지네이션·워치리스트·자산) |
| `src/meta_ads/meta_ads_tool.py` | 521 | 검색·페이지네이션·워치리스트 대시보드·자산 다운로드·doc_id config |
| `src/meta_ads/test_meta_ads_tool.py` | 440 | 파서·챌린지·페이지네이션·워치리스트·자산·캐시 계약 테스트 |

## Module Responsibility

`src/meta_ads/`는 Meta 광고 라이브러리(공개 투명성 페이지)를 로그인 없이 검색해
광고 레퍼런스(문구·CTA·크리에이티브 URL·게재 기간)를 가져오는 모듈이다.

- Facebook은 Python urllib의 TLS 핑거프린트를 403 "Client challenge"로 차단하므로
  x_twitter_tool과 같은 **시스템 curl subprocess** 우회를 쓴다.
- 브라우저형 헤더(sec-ch-ua, Sec-Fetch-*)가 없으면 챌린지 통과 후에도 일반 400
  오류 페이지가 오므로 `_BROWSER_HEADERS`를 반드시 유지한다.
- 403 응답 본문의 `__rd_verify_*` 챌린지 URL에 POST 후 재요청하면 통과한다.
  발급된 쿠키는 `config/meta_ads_cookies.txt`(gitignore 대상)에 보관해 이후
  요청은 챌린지 왕복을 건너뛴다.
- 검색 결과 첫 페이지(최대 30건)는 HTML의
  `<script type="application/json">` 블록에 서버렌더링으로 임베드되어 있어
  doc_id 없이 파싱한다. 첫 페이지의 `end_cursor`/`has_next_page`도 여기서 읽는다.
- **"더 보기"(페이지네이션)**는 브라우저가 스크롤 시 쏘는
  `AdLibrarySearchPaginationQuery` GraphQL(`/api/graphql/`)을 재현한다.
  - doc_id는 Threads처럼 로테이션되므로 `config/meta_ads_doc_ids.json`이 있으면
    우선하고, 없으면 내장 기본값(`_DEFAULT_DOC_IDS`)을 쓴다. 모든 doc_id가 실패하면
    `config/.meta_ads_docid_expired` 플래그를 남긴다.
  - 커서는 그 커서를 만든 **쿠키 자(세션)에 묶여** 있다. 새 쿠키 자로는 거부되므로
    (검증됨), 모듈이 유지하는 단일 영속 자(`config/meta_ads_cookies.txt`)를
    공유하고 첫 페이지에서 뽑은 **LSD 토큰을 검색별로 메모리(`_context`)에 저장**해
    페이지네이션 POST에서 재사용한다.
  - GraphQL POST는 전체 헤더(X-FB-LSD, Origin, Referer, Sec-Fetch-* cors,
    X-FB-Friendly-Name)가 없으면 에러 페이지가 온다. 헤더 세트를 반드시 유지한다.
  - 응답은 `for (;;);` 프리픽스가 붙을 수 있어 `_parse_graphql`이 벗겨낸 뒤 파싱한다.
    파싱 결과는 첫 페이지와 동일 구조(`collated_results` → `ad_archive_id`+`snapshot`)라
    `_walk_ads`/`_parse_ad`를 그대로 공유한다.

### 검색 모드

- `keyword`: `q=<검색어>&search_type=keyword_unordered`. 광고 문구와 페이지
  이름을 함께 매칭하므로 "페이지 이름 검색"도 이 모드로 흡수된다.
- `page`: `view_all_page_id=<숫자 page_id>&search_type=page`. 특정 광고주
  페이지의 광고 전체를 모아본다. 프론트는 키워드 결과의 페이지 칩 클릭으로만
  진입하므로 page_id는 항상 숫자다 (main.py에서 숫자 검증).

### 국가

`COUNTRIES = ("KR", "US", "JP", "TW", "ALL")`. 프론트 select도 같은 순서다.
`ALL`은 페이지네이션 변수에서 `countries: []`로 변환한다.

### 실무 기능 (검색을 인텔리전스로)

raw 검색을 넘어 판단을 돕는 4개 기능. 광고 라이브러리에서 무료로 얻는 가장 강한
신호는 **광고 수명**(오래 집행 = 검증된 승자)이라는 전제 위에 설계했다.

1. **롱런 탐지**: 집행 일수 = `now - startDate`. 프론트에서 계산해 배지(30일+ 롱런,
   90일+ 🔥)와 정렬(관련순/롱런순/신규순), `30일+ 롱런만` 필터를 제공한다.
   `LONG_RUN_DAYS = 30`.
2. **크리에이티브 인사이트**: 로드된 광고를 프론트에서 집계 — 포맷 믹스(영상/이미지),
   집행 기간 분포, CTA 분포, 카피 훅/키워드(불용어 제거, `{{product.name}}` 등
   다이내믹 카탈로그 템플릿 자리표시자 제거). 3건 이상일 때만 표시.
3. **경쟁사 워치리스트**: `config/meta_ads_watchlist.json`에 `[{pageId, pageName}]`
   저장. `get_watchlist_dashboard`가 각 페이지를 page 검색으로 병렬 조회(`ThreadPoolExecutor`,
   max 4)해 요약 행(집행 소재 수 totalCount, 이번 주 신규, 롱런 수, 최장 집행일,
   영상 비중, 최장수 광고)을 만든다. 신규/롱런/영상비중은 첫 페이지 표본(≤30) 기준,
   totalCount는 전체.
4. **스와이프 파일**: `fetch_asset`이 fbcdn 호스트의 영상/이미지를 curl로 받아
   Content-Disposition attachment로 반환(다운로드). 북마크 저장 시 카피·CTA·집행
   일수를 note로, 페이지명·포맷·롱런 여부를 tags로 함께 저장한다(저장됨 탭에 note 표시).

### 운영 관점

- Ad item 키: `id`, `pageId`, `pageName`, `pagePic`, `isActive`, `startDate`,
  `endDate`, `platforms`, `title`, `body`, `ctaText`, `ctaType`, `linkUrl`,
  `caption`, `displayFormat`, `thumbnail`, `videoUrl`, `collationCount`, `url`.
- `url`은 광고 라이브러리 영구 링크(`/ads/library/?id=<ad_archive_id>`)다.
- 다이내믹 카탈로그 광고는 `{{product.name}}` 같은 템플릿 문자열이 원본
  데이터에 그대로 들어있다. 버그가 아니다.
- 응답의 `pages`는 결과에 등장한 광고주 페이지 집계(광고 수 내림차순, 첫 페이지 기준),
  `totalCount`는 `search_results_connection.count`(전체 결과 수 추정)다.
- 응답의 `cursor`(다음 커서)와 `hasMore`로 프론트 "더 보기" 버튼을 제어한다.
  첫 페이지는 lsd가 있어야 `hasMore`가 참이 된다.
- 실패 시 errors 계약은 다른 피드와 같다: `{"account": query, "kind":
  http|timeout|parse|doc_id_expired, "code": ...}`. 빈 결과+오류는 120초 네거티브 캐시.

## Key Function Signatures

### `_curl(url, method="GET", data=None, extra_headers=None)`

- 시스템 curl을 쿠키 jar와 브라우저형 헤더로 실행한다. POST 본문·추가 헤더 지원.
- `-w`로 붙인 `__HTTP_STATUS__:` 마커를 잘라 `(status, body)`를 반환한다.

### `_fetch_html(url)`

- GET 후 403+`__rd_verify`면 챌린지 POST → 재GET을 최대 3회 반복한다.

### `_build_url(...)` / `_build_variables(..., cursor)`

- `_build_url`: keyword/page 모드 검색 URL. `_build_variables`: GraphQL
  페이지네이션 변수(cursor, countries, queryString, searchType, viewAllPageID 등).
  `sessionID`는 호출자가 채운다. `country=="ALL"`이면 `countries: []`.

### `_walk_ads(...)` / `_parse_ad(raw)` / `_first_media(snapshot)`

- `_walk_ads`는 JSON 트리를 재귀 순회해 `ad_archive_id`+`snapshot` dict를 광고로
  변환하고 `search_results_connection.count`/`page_info`도 수집한다. 첫 페이지와
  GraphQL 응답이 공유한다. 미디어 우선순위: videos → images → carousel cards.

### `_parse_html(html)` / `_parse_graphql(body)`

- `_parse_html`: 임베디드 JSON 블록 → `(ads, total, cursor, has_next)`.
- `_parse_graphql`: `for (;;);` 프리픽스 제거 후 파싱 → `(ads, cursor, has_next)`.
  `errors`/`error` 키가 있으면 `ValueError`.

### `_load_doc_ids()` / `_flag_doc_id_expired()` / `_clear_doc_id_expired()`

- config/meta_ads_doc_ids.json 우선, 없으면 내장 기본값. 전 doc_id 실패 시 플래그.

### `fetch_first_page(...)`

- 첫 페이지 HTML 스크레이프. `(ads, pages, total, cursor, has_more, lsd, error)`.

### `fetch_more(..., cursor, lsd, session_id)`

- doc_id들을 순회하며 GraphQL POST. `(ads, next_cursor, has_more, error)`.

### `get_meta_ads(..., force, cursor=None)`

- cursor 없으면 첫 페이지(캐시 key `("meta_ads", search_type, query, country,
  active_status, media_type)`, `_context`에 lsd/sessionID 저장). cursor 있으면
  페이지네이션(캐시 key에 `("page", cursor)` 추가, 저장된 lsd 재사용).
  `(data, fetched_at, errors, cache_ttl)` 반환. data에 `cursor`/`hasMore` 포함.

### `load_watchlist()` / `update_watchlist(action, page_id, page_name)`

- `config/meta_ads_watchlist.json` 로드/추가/삭제. 숫자 page_id만 허용, 중복 무시.

### `_summarize_page(entry, country, now)` / `get_watchlist_dashboard(country, force)`

- page 검색 한 번으로 경쟁사 요약 행 생성. 대시보드는 워치리스트 전체를 병렬 조회해
  `{rows, watchlist}` 반환(캐시 key에 정렬된 pageId 튜플 포함).

### `fetch_asset(url)`

- fbcdn 호스트의 영상/이미지를 curl로 받아 `(status, content_type, body, filename)`
  반환. 비-fbcdn·비-https는 400, 실패는 502.

### 테스트 함수 지도

- `ParseTest`: parse_html(ads/count/cursor·dedupe·broken), parse_ad(image·carousel),
  aggregate_pages, parse_graphql(plain·for-loop·error)
- `BuildTest`: keyword_url·page_url·taiwan_country·variables(keyword·page/ALL)
- `FirstPageTest`: ok·challenge·timeout·curl_failure
- `FetchMoreTest`: ok(docid+cursor)·requires_cursor_lsd·docid_expired·http_error
- `GetMetaAdsTest`: negative_ttl·stores_context·has_more_false_no_lsd·
  pagination_uses_stored_lsd·serves_cache
- `WatchlistTest`: add_and_remove·rejects_non_numeric·dashboard_summarizes_pages
- `AssetTest`: rejects_non_fbcdn·rejects_non_https·downloads_video·downloads_image·
  fetch_failure_502

## Dependencies

- `json`, `os`, `re`, `subprocess`, `threading`, `time`, `uuid`,
  `concurrent.futures.ThreadPoolExecutor`, `urllib.parse`
- 시스템 `curl` 바이너리 (Windows 10+/macOS 기본 탑재)
- `settings.UA`, `settings.CONFIG_DIR`
- `shared.cache_tool`

## Dependents

- `src/main.py` 라우트: `/api/meta_ads`(검색·페이지네이션), `/api/meta_ads/dashboard`
  (워치리스트 요약), `/api/meta_ads/watchlist`(GET·POST), `/api/meta_ads/asset`(다운로드)
- `src/frontend/index.html` 광고 탭: `loadMetaAdsTab`(진입 시 워치리스트+검색),
  `loadMetaAds`/`loadMoreAds`, `adCard`(롱런 배지·다운로드 버튼·풍부한 북마크),
  `renderAdsGrid`(정렬·필터 재렌더), `renderAdsInsight`(집계 패널), `sortedFilteredAds`,
  `renderWatchTable`/`loadWatchlistDashboard`/`addToWatchlist`, `initAdsControls`.
  썸네일·자산은 `/api/img`·`/api/meta_ads/asset` 경유. 저장됨 탭 `savedCard`는
  meta_ads 북마크의 note를 표시(`createBookmarkButton`이 note·tags 전달)

## Sync Checklist

- [ ] `_BROWSER_HEADERS`/GraphQL 헤더 변경 시 실제 라이브 검색·더보기로 오류
      페이지가 돌아오지 않는지 확인한다.
- [ ] ad item 키 변경 시 프론트 `adCard`와 이 문서의 키 목록을 갱신한다.
- [ ] 챌린지/페이지네이션 로직 변경 시 해당 테스트를 갱신한다.
- [ ] Meta가 임베디드 JSON/GraphQL 구조를 바꾸면 `_walk_ads`의 조건
      (`ad_archive_id`+`snapshot`)과 `_parse_graphql`부터 의심한다.
- [ ] doc_id가 만료되면 브라우저 네트워크 탭에서 `AdLibrarySearchPaginationQuery`의
      새 doc_id를 찾아 `config/meta_ads_doc_ids.json`에 넣는다.
- [ ] ad item에 새 필드가 생기면 인사이트 집계(`renderAdsInsight`)·훅 추출·워치리스트
      요약(`_summarize_page`)이 활용하는지 검토한다.
- [ ] 워치리스트 요약 통계가 첫 페이지 표본 기준임을 UI가 오해시키지 않는지 확인한다.

## 변경 기록

- 2026-07-22: 모듈 신설. curl+챌린지 우회, 키워드/페이지 검색, 페이지 집계,
  프론트 광고 탭 연동.
- 2026-07-22: GraphQL 페이지네이션("더 보기"), doc_id config 파일, 대만(TW) 국가,
  LSD 세션 컨텍스트 추가.
- 2026-07-22: 실무 기능 추가 — 롱런 탐지(배지·정렬·필터), 크리에이티브 인사이트 집계,
  경쟁사 워치리스트 대시보드, 스와이프 파일(자산 다운로드·컨텍스트 저장).

## 문서 연결

- 이전: [[tiktok.md]]
