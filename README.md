<div align="center">

# trend-viewer

### 급상승 검색어, AI 트렌드 분석, 유튜브, 릴스, X, 스레드, 틱톡, AI 뉴스, 데이트 레이더를 한 화면에서 보는 로컬 트렌드 관제판

[![Python](https://img.shields.io/badge/Python_3-stdlib_only-3776AB?logo=python&logoColor=white)](#실행)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-214_passing-brightgreen)](#테스트)

</div>

---

플랫폼마다 브라우저 탭을 따로 열지 않아도 됩니다. `python3 src/main.py` 한 줄이면
`http://localhost:8779`에서 오늘 볼 만한 흐름을 바로 훑을 수 있습니다.

추가 패키지 설치는 필요 없습니다. **Python 표준 라이브러리만 사용합니다.**

<div align="center">

| 홈 브리핑 (데스크톱) | 급상승 탭 |
|:---:|:---:|
| ![홈 데스크톱](docs/screenshot-home-desktop.png) | ![급상승 데스크톱](docs/screenshot-trends-desktop.png) |

| 분석 탭 |
|:---:|
| ![분석 데스크톱](docs/screenshot-analysis-desktop.png) |

| 영상 탭 | AI 탭 |
|:---:|:---:|
| ![영상 데스크톱](docs/screenshot-videos-desktop.png) | ![AI 데스크톱](docs/screenshot-ai-desktop.png) |

| X 탭 | 급상승 (모바일) |
|:---:|:---:|
| ![X 데스크톱](docs/screenshot-x-desktop.png) | ![급상승 모바일](docs/screenshot-trends-mobile.png) |

</div>

---

## 왜 만들었나요

트렌드는 플랫폼마다 다르게 보입니다. 유튜브는 조회수와 카테고리가 중요하고,
릴스와 틱톡은 계정 흐름을 같이 봐야 합니다. X와 스레드는 텍스트 맥락과
참여 지표가 핵심입니다. 이걸 매일 플랫폼별로 확인하는 건 비효율입니다.

`trend-viewer`는 이 흐름을 로컬 브라우저 한 장에 모읍니다. 로그인 정보는
서버로 보내지 않습니다. 계정 목록과 캐시는 이 기기 안의 파일로 관리합니다.

---

## 실행

```bash
python3 src/main.py
# 브라우저에서 http://localhost:8779
```

포트를 바꾸려면 환경변수를 넣으세요.

```bash
TREND_VIEWER_PORT=8780 python3 src/main.py
```

---

## 탭별 상세

### 홈 (데일리 브리핑)

첫 화면입니다. 아래 모든 플랫폼의 상위 5개 항목을 한 페이지에 모아 보여줍니다.
각 섹션 헤더의 화살표를 누르면 해당 탭 전체 보기로 이동합니다.

### 급상승

Google Trends 실시간 급상승 검색어를 국가별(한국, 미국, 일본)로 보여줍니다.
검색어마다 근사 검색량, 대표 이미지, 관련 뉴스 기사 최대 3건이 함께 옵니다.
"지금 무엇이 뜨는가"를 다른 탭보다 먼저 확인하는 자리라서 홈 브리핑 맨 위에도
같은 데이터가 올라갑니다.

- 데이터 소스: Google Trends Trending Now RSS (무인증, geo별)
- 실패 시 2분 네거티브 캐시 후 자동 재시도

### 분석

Google Trends, YouTube, 릴스, X, 스레드, 틱톡, AI 뉴스의 7개 채널을 함께 읽어
같은 주제가 여러 플랫폼에서 겹치는지 찾고, 이전 분석 기록과 비교해 상승·유지·하락
속도를 계산합니다. 교차 플랫폼 상관관계와 속도 판정은 휴리스틱이라 오프라인에서도
동작하며, 선택적으로 로컬 LLM이 근거 링크를 묶은 클러스터와 한국어 브리핑을 만듭니다.

trend-viewer 자체는 Python 표준 라이브러리만 사용하며 API 키 없이 휴리스틱 분석까지 동작한다. 로컬 ocx 프록시(gpt-5.6-luna)가 떠 있으면 자동으로 LLM 클러스터링·브리핑으로 강화되고, 없으면 조용히 휴리스틱으로 폴백한다.

- 데이터 소스: Google Trends + YouTube + Instagram Reels + X + Threads + TikTok + AI 뉴스
- 제한: 플랫폼 응답 지연·차단 시 해당 채널을 제외한 부분 결과로 분석하며, 휴리스틱 연결은 제목 토큰 일치에 기반

### 영상

유튜브 인기 영상을 카테고리(전체, AI, 먹방, 뷰티/패션, 브이로그, 예능/코미디,
영화/드라마, 테크/IT, 지식/교육, 여행, 동물)별로, 기간(오늘, 이번 주, 이번 달)별로
필터링합니다. 국가 선택(한국, 미국, 일본)을 바꾸면 해당 국가 언어의 검색어 세트로
다시 수집합니다. 검색어 입력도 가능합니다. 카드 클릭 시 팝업으로 바로 재생합니다.

- 데이터 소스: YouTube InnerTube 검색 API (무인증, 조회수순)
- 제한: 공식 API가 아니므로 YouTube 정책 변경 시 영향 가능

### 쇼츠

유튜브 쇼츠만 따로 봅니다. 카테고리와 기간 필터를 영상 탭과 공유합니다.

- 데이터 소스: InnerTube `shorts=1` 파라미터

### AI

AI 영상 모델(Hugging Face 트렌딩/최신)과 국내외 AI 뉴스를 한 탭에 모읍니다.
뉴스는 TechCrunch, The Verge, MIT Tech Review, arXiv, Hacker News, AI타임스,
전자신문, ZDNet Korea 등 17개 피드에서 수집하고, 헤드라인 키워드 분류기가
모델·제품 / 연구 / 산업·투자 / 정책·규제 카테고리를 붙입니다. 칩으로 필터링하세요.

- 데이터 소스: Hugging Face API + 국내외 RSS 17종 + HN Algolia
- 제한: RSS 피드 지연 있음

### 데이트

이번 주 데이트 코스 후보를 자동으로 추립니다. 별도 API 키 없이 YouTube 무인증
검색과 Google Trends RSS를 기존 캐시 레이어에 붙여 `서울 데이트 코스`, `주말 데이트`,
`실내 데이트`, `전시 데이트`, `맛집 데이트` 흐름을 조회수·급상승 신호로 정렬합니다.
국가 선택을 바꾸면 해당 locale의 YouTube 검색 결과로 다시 수집합니다.

- 데이터 소스: YouTube InnerTube 검색 API + Google Trends Trending Now RSS
- 제한: Google Trends 데이트 키워드 보강은 한국(KR) 급상승 RSS 기준

### 릴스

인스타그램 공개 프로필의 릴스를 수집합니다. 계정을 화면에서 추가/삭제할 수 있습니다.
접이식 정렬 메뉴로 조회수순/좋아요순/댓글순을 전환합니다.

- 데이터 소스: Instagram `web_profile_info` API (공개 앱 ID 헤더, 무인증)
- 제한: **메타가 비로그인 접근을 차단할 경우 계정 바로가기로 자동 폴백합니다.**
  차단 여부는 시간대에 따라 달라집니다. 캐시(1시간)로 요청 빈도를 줄입니다.

### X (트위터)

구독 계정들의 최신 트윗을 참여 지표(좋아요, 댓글, 리트윗, 조회수)와 함께 봅니다.

- 데이터 소스: `syndication.twitter.com` 임베드 위젯 API (무인증)
- 구현: Python urllib의 TLS 핑거프린트가 Cloudflare에 차단되므로
  `subprocess`로 시스템 `curl`을 호출합니다 (`x_twitter_tool.py`).
- 제한: 조회수(impressions)는 이 API에 항상 포함되지 않습니다.
  계정별로 rate limit(429)이 걸릴 수 있으며, 실패한 계정 수를 화면에 표시합니다.

### 스레드

Threads GraphQL 엔드포인트로 로그인 없이 실시간 조회를 시도합니다.

- 데이터 소스: `threads.com/api/graphql` (LSD 토큰 + doc_id)
- 제한: **현재 메타가 비로그인 조회를 거의 차단하는 상태입니다.**
  `doc_id`가 수시로 바뀌어 안정 조회가 어렵습니다. 조회 실패 시
  각 계정 바로가기 링크로 자동 폴백합니다.

### 틱톡

실시간 인기 피드(한국)와 구독 계정 최신 영상을 함께 봅니다.

- 데이터 소스: tikwm 공개 API (`www.tikwm.com/api`)
- 제한: 무료 티어라 동시성이 높으면 일시 제한됩니다. 동시성 3으로 호출하고
  1시간 캐시합니다.

### 광고

Meta 광고 라이브러리(공개 투명성 페이지)를 검색하는 데서 그치지 않고, 결과를
**경쟁 인텔리전스**로 바꿉니다. 광고 라이브러리에서 무료로 얻는 가장 강한 신호는
**광고 수명**입니다 — 광고주가 몇 달째 같은 소재에 계속 돈을 쓴다면 그건 성과가
검증된 승자 소재입니다. 이 관점을 중심으로 다음을 제공합니다.

- **롱런 탐지**: 각 광고의 집행 일수를 계산해 `롱런 N일`(30일+)·`🔥 N일 롱런`(90일+)
  배지를 붙이고, 롱런순·신규순 정렬과 `30일+ 롱런만` 필터를 지원합니다. 오래 살아남은
  소재부터 보면 검증된 승자를 먼저 훑을 수 있습니다.
- **크리에이티브 인사이트**: 수집한 광고를 집계해 영상/이미지 비중, 집행 기간 분포,
  CTA 분포, 카피에서 자주 쓰는 훅·키워드를 한 패널에 요약합니다.
- **경쟁사 워치리스트**: 우리 게임·경쟁사 페이지를 등록하면(검색 결과 칩 우클릭 또는
  "★ 워치리스트에 추가"), 광고주별 집행 소재 수·이번 주 신규·롱런 수·영상 비중·최장
  집행일을 한 표로 비교합니다.
- **스와이프 파일**: 카드의 다운로드 버튼으로 광고 영상·이미지를 로컬에 저장하고,
  북마크하면 카피·CTA·집행 일수가 저장됨 탭에 함께 기록됩니다.

기본 검색은 키워드나 페이지 이름으로 하고, **더 보기** 버튼으로 다음 페이지를 이어
받아 수십~수백 건까지 누적합니다. 국가(한국, 미국, 일본, 대만, 전체), 게재 상태,
미디어 형식 필터를 지원합니다.

- 데이터 소스: Meta Ad Library 공개 검색 페이지(첫 페이지, 임베디드 JSON) +
  `AdLibrarySearchPaginationQuery` GraphQL(더 보기·워치리스트), 무인증
- 구현: Facebook이 Python urllib을 차단해 시스템 `curl`을 호출하고, 봇 확인
  챌린지를 자동으로 통과합니다 (`meta_ads_tool.py`)
- 페이지네이션 doc_id는 수시로 바뀌므로 `config/meta_ads_doc_ids.json`으로
  교체할 수 있습니다(없으면 내장 기본값 사용). 스레드 탭과 같은 방식입니다.
- 제한: 노출·지출은 (정치 광고가 아닌 한) 비공개라 수명·소재량 신호에 집중합니다.
  워치리스트 통계는 각 페이지 첫 페이지 표본(≤30건) 기준입니다. 비공식 경로라 메타
  정책·doc_id 변경 시 영향 가능

### 저장됨

카드 위에 보이는 북마크 아이콘을 누르면 이 탭에 모입니다. 저장 항목은
`config/saved_items.json`에 기록되고, 삭제도 화면에서 할 수 있습니다.

---

## 편의 기능

| 기능 | 설명 |
| --- | --- |
| 북마크 | 카드 우상단 아이콘 클릭으로 저장/해제, 저장됨 탭에서 모아보기 |
| 캐시 나이 | 각 응답의 동적 TTL을 "N분 전 수집 · N분 캐시"로 표시 (분석은 LLM 성공 1800초, 휴리스틱 폴백 300초) |
| 오류 표시 | 수집 실패 시 이유(429 등)와 실패 계정 수를 화면에 표시 |
| 본 항목 흐리기 | 클릭한 카드는 다음 방문 시 살짝 어두워짐 (헤더 버튼으로 초기화) |
| 키보드 단축키 | `1`~`9` 탭 전환, `/` 검색 포커스, `Esc` 모달 닫기 |
| URL 해시 복원 | 탭/카테고리/기간/검색이 `#hash`에 남아 새로고침 시 복원 |
| 반응형 레이아웃 | 모바일 폭에서 탭이 한 줄 가로 스크롤로 전환 |

---

## 계정 설정

계정 기반 피드를 보려면 `config/` 안에 JSON 파일을 만듭니다.
이 파일들은 `.gitignore`에 등록되어 있어 개인 설정이 공유되지 않습니다.

```json
["xazinga", "openai"]
```

| 플랫폼 | 파일 | 기본 계정 수 |
| --- | --- | --- |
| 릴스 | `config/reels_accounts.json` | 9 |
| X | `config/x_accounts.json` | 10 |
| 스레드 | `config/threads_accounts.json` | 5 |
| 틱톡 | `config/tiktok_accounts.json` | 8 |

파일이 없으면 코드에 내장된 기본 계정 목록으로 동작합니다.

---

## API 엔드포인트

조회 엔드포인트는 `GET`으로 JSON을 반환합니다. 저장 항목과 계정 목록 변경은 `POST`를 사용합니다.

| 경로 | 설명 | 주요 파라미터 |
| --- | --- | --- |
| `/api/videos` | 유튜브 영상/쇼츠 | `category`, `period`, `shorts`, `q`, `country`(KR/US/JP), `force` |
| `/api/trends` | 급상승 검색어 | `country`(KR/US/JP), `force` |
| `/api/reels` | 릴스 | `force` |
| `/api/x` | X 타임라인 | `force` |
| `/api/threads` | 스레드 | `force` |
| `/api/tiktok` | 틱톡 | `force` |
| `/api/ai` | AI 모델/뉴스 | `force` |
| `/api/meta_ads` | Meta 광고 라이브러리 검색 | `q`(필수), `type`(keyword/page), `country`(KR/US/JP/TW/ALL), `status`(active/inactive/all), `media`(all/video/image), `cursor`(더 보기), `force` |
| `/api/meta_ads/dashboard` | 경쟁사 워치리스트 요약 | `country`, `force` |
| `/api/meta_ads/watchlist` | 워치리스트 조회(GET)/수정(POST) | POST: `{action(add/remove), pageId, pageName}` |
| `/api/meta_ads/asset` | 광고 소재 다운로드 프록시 | `u`(fbcdn 영상/이미지 URL) |
| `/api/date` | 데이트 레이더 | `country`(KR/US/JP), `force` |
| `/api/analysis` | 교차 플랫폼 트렌드 분석 | `country`(KR/US/JP), `force` |
| `/api/categories` | 유튜브 카테고리 목록 | |
| `/api/saved` | 저장된 항목 (GET/POST) | POST: `{action, source, title, url, ...}` |
| `/api/img` | 이미지 프록시 | `u` (원본 URL) |
| `/api/oembed` | oEmbed 정보 | `url` |
| `/api/{source}/accounts` | 계정 추가/삭제 (POST) | `{action, username}` |

소셜/트렌드 엔드포인트(`/api/x`, `/api/reels`, `/api/threads`, `/api/trends`)의 응답에는 수집 상태가 포함됩니다.

```json
{
  "posts": [...],
  "accounts": ["OpenAI", ...],
  "fetchedAt": 1783421000,
  "cacheTtl": 3600,
  "status": "ok | empty | error | partial",
  "errors": [{"account": "...", "kind": "http", "code": 429}]
}
```

`force=1`을 붙이면 캐시를 무시하고 새로 수집합니다. 분석은 같은 국가의 중복 LLM
호출을 막기 위해 30초 안에 만든 결과라면 강제 요청에서도 재사용합니다.

---

## 환경변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `TREND_VIEWER_PORT` | `8779` | HTTP 서버 포트 |
| `TREND_VIEWER_CACHE_TTL` | `3600` | 정상 결과 캐시 TTL (초) |
| `TREND_ANALYSIS_ENABLED` | `1` | 로컬 LLM 분석 사용 여부 (`0`이면 휴리스틱만 사용) |
| `TREND_ANALYSIS_BASE_URL` | `http://127.0.0.1:10100/v1` | 로컬 Responses 호환 프록시 주소 |
| `TREND_ANALYSIS_MODEL` | `gpt-5.6-luna` | 분석 클러스터링·브리핑 모델 |

---

## 프로젝트 구조

원본은 `_upstream/`의 단일 파일 프로토타입입니다. 현재 버전은 같은 기능을
기능별 모듈로 나눠 포팅한 구조입니다.

```text
trend-viewer/
├── src/
│   ├── main.py              # HTTP 서버, 라우팅, 정적 HTML 제공
│   ├── settings.py           # 포트, 경로, 캐시, 이미지 프록시 허용 도메인
│   ├── frontend/
│   │   └── index.html        # 단일 파일 프론트엔드 (HTML + CSS + JS)
│   ├── shared/
│   │   ├── cache_tool.py     # TTL 기반 인메모리 캐시
│   │   ├── http_tool.py      # HTTP GET/JSON 래퍼
│   │   ├── accounts_tool.py  # 계정 목록 로드/저장
│   │   ├── img_proxy_tool.py # CDN 이미지 프록시
│   │   ├── saved_items_tool.py # 북마크 영속화
│   │   └── test_*.py         # 공유 모듈 테스트
│   ├── youtube/              # InnerTube API 수집
│   ├── trends/               # Google Trends RSS 수집 (급상승)
│   ├── reels/                # Instagram web_profile_info 수집
│   ├── x_twitter/            # syndication API + curl subprocess 수집
│   ├── threads/              # GraphQL + LSD 토큰 수집
│   ├── tiktok/               # tikwm API 수집
│   ├── meta_ads/             # Meta 광고 라이브러리 검색 (curl + 임베디드 JSON)
│   ├── ai_news/              # Hugging Face + 국내외 RSS 17종 (카테고리 분류)
│   ├── date/                 # 국가별 데이트 후보 수집·교차 배치
│   └── analysis/             # 7채널 상관·속도 분석 + 선택적 로컬 LLM 합성
├── config/                   # 사용자 계정/저장 파일 (.gitignore)
│   └── analysis_history.json # 속도 기준 이력 (자동 생성, .gitignore)
├── _upstream/                # 원본 단일 파일 서버 (읽기 전용 참조)
├── docs/                     # 스크린샷
└── devlog/                   # 개발 로그와 계획 문서
```

Python import 규칙 때문에 폴더명은 `snake_case`를 씁니다. 각 기능 폴더에
`*_tool.py`(로직)와 `test_*.py`(테스트)를 같이 둡니다.

---

## 테스트

```bash
python3 -m unittest discover -s src -p 'test_*.py'
```

현재 214개 테스트가 등록되어 있습니다. 외부 API 호출은 전부 mock 처리되어
오프라인에서도 실행됩니다.

---

## 업데이트

```bash
git pull
```

`config/` 안의 계정 목록과 저장 항목은 `.gitignore`에 등록된 개인 파일이라
업데이트해도 그대로 유지됩니다. 받은 뒤에는 서버를 껐다가 다시 켜 주세요.

---

## 트러블슈팅

| 증상 | 원인과 해결 |
| --- | --- |
| X 탭이 "일시적으로 가져오지 못했습니다" | X syndication API의 rate limit(429)입니다. 2분 후 새로고침하면 재시도됩니다. |
| 릴스/스레드가 바로가기만 보입니다 | 메타가 비로그인 API 접근을 차단한 상태입니다. 시간이 지나면 풀리기도 합니다. |
| 틱톡 데이터가 비어 있습니다 | tikwm 무료 API 일시 제한입니다. 잠시 후 다시 시도하세요. |
| 포트가 이미 사용 중입니다 | `TREND_VIEWER_PORT=8780 python3 src/main.py`로 다른 포트를 쓰세요. |
| 썸네일이 안 보입니다 | 이미지 프록시(`/api/img`)가 허용 도메인만 통과합니다. `settings.py`의 `IMG_PROXY_ALLOW` 확인. |

---

## 기여

1. 이 저장소를 fork 합니다.
2. 기능 브랜치를 만듭니다: `git checkout -b feat/my-feature`
3. 변경 후 테스트를 돌립니다: `python3 -m unittest discover -s src -p 'test_*.py'`
4. 커밋합니다: `git commit -m "feat: describe your change"`
5. PR을 올립니다.

커밋 메시지는 `feat|fix|refactor|docs|test|chore: 설명` 형식을 따릅니다.
외부 패키지를 추가하지 마세요 (stdlib only 원칙).

---

## 함께 만든 사람

이 저장소는 [`xazingatrend`](https://github.com/xazingatrend) 조직에서
공개 관리합니다.

| 역할 | 이름 |
| --- | --- |
| 원본 아이디어/운영 맥락 | `xazinga` |
| 운영 연락 | `geonu0812@gmail.com` |
| GitHub 조직 | [`xazingatrend`](https://github.com/xazingatrend) |
| GitHub contributor | [`lidge-jun`](https://github.com/lidge-jun) |
| Git 커밋 작성자 | `bitkyc08-arch <bitkyc08@gmail.com>` |

---

## 더 읽을 문서

- 포팅 계획: [`devlog/_plan/010_porting-plan.md`](devlog/_plan/010_porting-plan.md)
- 프론트엔드 정책: [`devlog/_plan/020_frontend-policy.md`](devlog/_plan/020_frontend-policy.md)
- CI 파이프라인 계획: [`devlog/_plan/100_ci-pipeline.md`](devlog/_plan/100_ci-pipeline.md)
- 기능별 구조 문서: [`devlog/str_func/`](devlog/str_func/)
- 완료된 작업 로그: [`devlog/_fin/`](devlog/_fin/)

---

## 라이선스

MIT

---

## 변경 기록

- 2026-07-22: 광고 탭 실무 기능 — 롱런 탐지, 크리에이티브 인사이트, 경쟁사 워치리스트, 스와이프 파일(소재 다운로드)
- 2026-07-22: 광고 탭 "더 보기"(GraphQL 페이지네이션), doc_id 교체 config, 대만(TW) 국가 추가
- 2026-07-22: Meta 광고 라이브러리 검색(`/api/meta_ads`)과 광고 탭 추가
- 2026-07-10: 7채널 교차 플랫폼 분석 엔진, 선택적 로컬 LLM 합성, `/api/analysis`, 분석 탭 추가
- 2026-07-07: README 확장 (배지, 스크린샷 갤러리, API 레퍼런스,
  트러블슈팅, 기여 가이드)
- 2026-07-07: X syndication을 curl subprocess로 전환해 TLS 차단 해결
- 2026-07-07: 피드 오류 계약(status/errors) 추가, 실패 결과 120초 단기 캐시
- 2026-07-07: 반복 사용 인체공학 (dimming, hash 복원, 단축키, 모바일 탭)
- 2026-07-07: 저장 루프 완성 (북마크 토글, 저장됨 탭, 캐시 나이, 폴백 배너)
- 2026-07-07: 홈 브리핑 탭과 캐시 메타데이터 API 추가
- 2026-07-07: 단일 파일 프로토타입을 stdlib 기반 feature 구조로 포팅
