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
| `src/meta_ads/__init__.py` | 2 | fetch_first_page·fetch_more·get_meta_ads 배럴 export |
| `src/meta_ads/meta_ads_tool.py` | 403 | 첫 페이지 HTML 수집 + GraphQL 페이지네이션·챌린지 해결·doc_id config |
| `src/meta_ads/test_meta_ads_tool.py` | 344 | 파서·챌린지·페이지네이션·doc_id·캐시 계약 테스트 |

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

### 테스트 함수 지도

- `ParseTest`: parse_html(ads/count/cursor·dedupe·broken), parse_ad(image·carousel),
  aggregate_pages, parse_graphql(plain·for-loop·error)
- `BuildTest`: keyword_url·page_url·taiwan_country·variables(keyword·page/ALL)
- `FirstPageTest`: ok·challenge·timeout·curl_failure
- `FetchMoreTest`: ok(docid+cursor)·requires_cursor_lsd·docid_expired·http_error
- `GetMetaAdsTest`: negative_ttl·stores_context·has_more_false_no_lsd·
  pagination_uses_stored_lsd·serves_cache

## Dependencies

- `json`, `os`, `re`, `subprocess`, `threading`, `uuid`, `urllib.parse.urlencode`
- 시스템 `curl` 바이너리 (Windows 10+/macOS 기본 탑재)
- `settings.UA`, `settings.CONFIG_DIR`
- `shared.cache_tool`

## Dependents

- `src/main.py` `/api/meta_ads` 라우트 (`q`, `type`, `country`, `status`,
  `media`, `cursor`, `force` 파라미터 검증 후 `get_meta_ads` 호출)
- `src/frontend/index.html` 광고 탭: `loadMetaAds`/`loadMoreAds`, `adCard`,
  `renderAdPages`(페이지 칩 드릴다운), `appendAds`(누적·dedupe), 더 보기 버튼
  (`#adsMoreBtn`), 썸네일은 `/api/img` 프록시(.fbcdn.net 허용) 경유

## Sync Checklist

- [ ] `_BROWSER_HEADERS`/GraphQL 헤더 변경 시 실제 라이브 검색·더보기로 오류
      페이지가 돌아오지 않는지 확인한다.
- [ ] ad item 키 변경 시 프론트 `adCard`와 이 문서의 키 목록을 갱신한다.
- [ ] 챌린지/페이지네이션 로직 변경 시 해당 테스트를 갱신한다.
- [ ] Meta가 임베디드 JSON/GraphQL 구조를 바꾸면 `_walk_ads`의 조건
      (`ad_archive_id`+`snapshot`)과 `_parse_graphql`부터 의심한다.
- [ ] doc_id가 만료되면 브라우저 네트워크 탭에서 `AdLibrarySearchPaginationQuery`의
      새 doc_id를 찾아 `config/meta_ads_doc_ids.json`에 넣는다.

## 변경 기록

- 2026-07-22: 모듈 신설. curl+챌린지 우회, 키워드/페이지 검색, 페이지 집계,
  프론트 광고 탭 연동.
- 2026-07-22: GraphQL 페이지네이션("더 보기"), doc_id config 파일, 대만(TW) 국가,
  LSD 세션 컨텍스트 추가.

## 문서 연결

- 이전: [[tiktok.md]]
