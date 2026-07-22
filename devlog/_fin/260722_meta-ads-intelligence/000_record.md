---
created: 2026-07-22
tags: [trend-viewer, meta-ads, competitive-intelligence, longevity, watchlist]
aliases: [광고 인텔리전스 완료 기록, meta_ads intelligence]
---

# 260722 meta-ads-intelligence

## Summary

"검색해서 스크롤하는 것뿐이라 광고 라이브러리 웹사이트와 다를 게 없다"는 피드백을
받아, 광고 탭을 raw 검색에서 **경쟁 인텔리전스 도구**로 확장했다. 핵심 전제는
광고 라이브러리에서 무료로 얻는 가장 강한 신호가 **광고 수명**(오래 집행 = 검증된
승자)이라는 것. 이 위에 4개 실무 기능을 얹었다: 롱런 탐지, 크리에이티브 인사이트,
경쟁사 워치리스트, 스와이프 파일.

## Changes

- `src/meta_ads/meta_ads_tool.py`:
  - 워치리스트 — `load_watchlist`/`update_watchlist`(config/meta_ads_watchlist.json),
    `_summarize_page`(page 검색 1회로 요약 행), `get_watchlist_dashboard`(ThreadPoolExecutor
    병렬 조회·캐시), `_running_days`. `LONG_RUN_DAYS=30`.
  - 자산 다운로드 — `fetch_asset`(fbcdn 영상/이미지 curl 다운로드, Content-Disposition).
- `src/main.py`: `/api/meta_ads/dashboard`(GET), `/api/meta_ads/watchlist`(GET·POST),
  `/api/meta_ads/asset`(GET, attachment 스트리밍) 라우트.
- `src/frontend/index.html`:
  - 롱런 — `adRunningDays`, 카드 롱런 배지(30/90일+), 정렬 세그먼트(관련/롱런/신규),
    `30일+ 롱런만` 필터, `sortedFilteredAds`/`renderAdsGrid` 재렌더 리팩터.
  - 인사이트 — `renderAdsInsight`(포맷 믹스·집행 기간 분포·CTA 분포·훅 키워드),
    `extractHooks`(불용어 + `{{...}}` 템플릿 제거).
  - 워치리스트 — 대시보드 비교 테이블(`renderWatchTable`/`loadWatchlistDashboard`),
    페이지 칩 우클릭·"★ 워치리스트에 추가"로 등록, 국가 변경 시 갱신.
  - 스와이프 — 카드 다운로드 버튼(`/api/meta_ads/asset`), 북마크에 카피·CTA·집행
    일수를 note·tags로 저장(`createBookmarkButton` 확장), 저장됨 `savedCard`에 note 표시.
- `src/meta_ads/test_meta_ads_tool.py`: WatchlistTest·AssetTest 8건 추가.
- 문서: `devlog/str_func/meta_ads.md`, `README.md`, `.gitignore`(watchlist 제외).

## Verification

- `python -m unittest discover -s src -p 'test_*.py'` → 214 tests OK (206 + 8).
- 브라우저 라이브 "방치형 RPG"(KR):
  - 인사이트 4카드(영상 75%/이미지 25%, 롱런 10건 36%, 기간 분포, CTA 다운로드 82%/
    지금 설치 18%, 훅 키워드), 롱런 배지 10개, 다운로드 버튼 28개 확인.
  - `30일+ 롱런만` 필터 → 28건 중 10건(전부 롱런 배지), 롱런순 정렬 → 396·209·194·
    88·88일 내림차순 확인.
  - 자산 다운로드 프록시 → video/mp4, attachment, 1.9MB 확인.
  - 워치리스트 2개 등록 → 대시보드: 메이플 키우기 205건/4신규/11롱런/77% 영상/132일,
    픽셀 법사 39건/0신규/30롱런/23% 영상/508일. 삭제까지 확인.
- console error 0건. 검증용 워치리스트 항목은 정리했다.

## Risks

- 노출·지출은 비공개라 수명·소재량 신호에 집중한다. 성과의 직접 지표가 아니라 대리
  신호임을 UI 툴팁에 명시했다.
- 워치리스트 요약(신규/롱런/영상비중)은 각 페이지 첫 페이지 표본(≤30) 기준이고
  totalCount만 전체다. UI에 "표본 기준"임을 README·문서에 남겼다.
- 훅 키워드는 토큰 빈도 기반이라 동의어·표기 변형을 하나로 묶지 못한다.
  `{{product.name}}` 같은 다이내믹 카탈로그 템플릿 자리표시자는 제거했다.
- 대시보드는 경쟁사 수만큼 page 검색을 유발한다(동시성 4로 제한, 캐시). 워치리스트가
  커지면 첫 로드가 느려질 수 있다.

## 변경 기록

- 2026-07-22: 롱런 탐지·인사이트·워치리스트·스와이프 파일 구현과 라이브 검증을 기록했다.
