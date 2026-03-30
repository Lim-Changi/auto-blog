# Auto Blog Generator

Blogger에 AI 일상 활용법 콘텐츠를 자동 생성/업로드하는 파이프라인.
Google AdSense 수익 창출을 목표로 합니다.

## Architecture

```
크론잡 (매일 1회 실행)
  → orchestrator.py (파이프라인 조율 + 랜덤 딜레이)
    │
    ├── Step 1: trend_researcher.py (키워드 리서치)
    │   Claude CLI + WebSearch로 Reddit, 뉴스, Google 등 종합 분석
    │   → output/keywords/{date}.json
    │
    ├── Step 2: content_generator.py (글 생성)
    │   프롬프트 템플릿 + Claude CLI로 800단어+ 블로그 글 생성
    │   → output/drafts/{date}-{slug}.md
    │
    └── Step 3: blogger_uploader.py (업로드)
        Markdown → HTML 변환 → Blogger API v3로 자동 게시
```

## Module Details

### Orchestrator (`orchestrator.py`)

파이프라인 전체를 조율하는 메인 실행기.

- **스케줄링:** 매일 1편 업로드. 이미 오늘 게시했으면 스킵
- **랜덤 딜레이:** 크론 실행 후 0~2시간 랜덤 대기 (자연스러운 포스팅 패턴)
- **`--now` 플래그:** 스케줄/딜레이 없이 즉시 실행 (테스트용)
- **에러 핸들링:** 파이프라인 실패 시 로깅 후 안전 종료

```bash
python orchestrator.py          # 크론잡용 (스케줄 + 딜레이 적용)
python orchestrator.py --now    # 즉시 실행 (테스트용)
```

### Trend Researcher (`modules/trend_researcher.py`)

Claude Code CLI의 웹 서치 기능을 활용한 키워드 리서치 에이전트.

**동작 방식:**
1. Claude CLI에 리서치 프롬프트 전달 (`--allowedTools WebSearch,WebFetch`)
2. Claude가 Reddit, 뉴스, Google, 포럼 등을 종합 분석
3. 각 키워드의 검색 수요(demand), 경쟁도(competition), 관심도(interest) 평가
4. 콘텐츠 앵글 자동 판단 (how-to / tools / tips)
5. 구조화된 JSON으로 출력

**스코어링:** `score = (interest / 100) × demand × competition`
- demand: high=3, medium=2, low=1
- competition: low=3, medium=2, high=1 (낮을수록 좋음)

**Fallback:** Claude CLI 실패 시 `output/keywords/`의 캐시된 키워드에서 미사용 키워드 선택

**출력 예시 (`output/keywords/2026-03-30.json`):**
```json
[
  {
    "keyword": "how to use AI for meal planning and grocery lists",
    "category": "cooking",
    "interest": 82,
    "search_demand": "high",
    "competition": "medium",
    "related_queries": ["AI meal planner app free", "ChatGPT meal planning prompts"],
    "template": "howto_apply",
    "reasoning": "AI meal planning is trending, few beginner-friendly guides exist",
    "score": 4.92,
    "title_suggestion": "How To Use AI For Meal Planning And Grocery Lists — A Simple Guide"
  }
]
```

### Content Generator (`modules/content_generator.py`)

Claude Code CLI로 블로그 글을 생성하는 에이전트.

**동작 방식:**
1. 키워드 데이터 + 프롬프트 템플릿 조합
2. `claude -p - --output-format text`로 stdin을 통해 프롬프트 전달
3. 생성된 글의 품질 검증 (최소 800단어, H2 2개 이상)
4. 검증 실패 시 자동 재시도 (`max_retries` 설정)
5. Claude 출력에서 비본문 노이즈 자동 제거 (`clean_draft`)

**프롬프트 템플릿 (3종):**

| 템플릿 | 용도 | 트리거 |
|--------|------|--------|
| `howto_apply.md` | "How to use AI for..." 가이드 | 키워드에 "how to" 포함 |
| `best_tools.md` | "Best AI tools for..." 리스트 | 키워드에 "best"/"top" 포함 |
| `daily_ai_tips.md` | "5 Easy Ways AI Can..." 팁 | 기본 |

**콘텐츠 톤:**
- 개인 블로그 스타일 ("나도 이런 어려움이 있었는데 해보니까 좋았다")
- 정형화된 오프닝 금지 ("In today's world..." 등)
- 매번 다른 서론 패턴 (실패담, 발견, before/after 등)
- American English, USD, 미국 기준 사례

### Blogger Uploader (`modules/blogger_uploader.py`)

Blogger API v3를 통한 자동 업로드 에이전트.

**동작 방식:**
1. Markdown 드래프트 읽기
2. `META:` 라인에서 메타 디스크립션 추출
3. `#` 헤딩에서 글 제목 추출
4. Markdown → HTML 변환 (문단 간격 스타일 자동 삽입)
5. Blogger API `posts.insert()` 호출
6. 성공 시 `posted_keywords.json`에 키워드 기록

**라벨 생성:** AI, 카테고리, 템플릿 유형, 관련 검색어 (40자 이하만, 최대 10개)

**인증:** OAuth 2.0 — 최초 `python setup_auth.py`로 토큰 발급, 이후 자동 갱신

## Cost

| 항목 | 비용 |
|------|------|
| Blogger 호스팅 | 무료 |
| Blogger API v3 | 무료 |
| Claude Code CLI (키워드 리서치 + 글 생성) | Max 구독 활용 |
| **추가 비용 합계** | **0원** |

## Prerequisites

- Python 3.11+
- Claude Code CLI (Max 구독)
- Google 계정 (US 설정 권장)
- macOS (크론잡 실행 환경)

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/{YOUR_USERNAME}/auto-blog.git
cd auto-blog
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Account (US 타겟용)

1. https://accounts.google.com/signup 에서 새 계정 생성
2. 국가: **United States**, 언어: **English**
3. 이 계정으로 Blogger, Cloud Console, Search Console, AdSense 모두 운영

### 3. Google Cloud Console

1. https://console.cloud.google.com 에서 프로젝트 생성
2. Blogger API v3 활성화 (APIs & Services → Library)
3. OAuth consent screen 설정 (External)
4. **Test users에 본인 Gmail 추가** (테스트 모드이므로 필수)
5. OAuth client ID 발급 (Desktop app)
6. JSON 다운로드 → `credentials/google_oauth.json`에 저장

### 4. Blogger

1. https://www.blogger.com 에서 블로그 생성
2. Settings → Language: English, Timezone: US Eastern/Pacific
3. 대시보드 URL에서 Blog ID 확인: `https://www.blogger.com/blog/posts/{BLOG_ID}`

### 5. Configuration

```bash
cp config.example.yaml config.yaml
# config.yaml의 blog_id를 본인 Blog ID로 변경
```

### 6. Authentication

```bash
python setup_auth.py
# 브라우저가 열리면 Google 계정으로 로그인 → Allow
# "Token saved to credentials/token.json" 확인
```

### 7. Test

```bash
# 유닛 테스트 (38개 전체 통과 확인)
python -m pytest tests/ -v

# 수동 실행 테스트 (실제로 글 1편 생성+업로드)
python orchestrator.py --now
```

### 8. Cron

```bash
crontab -e
# 매일 오전 10시 실행 (내부 랜덤 딜레이로 실제 포스팅은 10:00~12:00):
0 10 * * * cd /path/to/auto-blog && /path/to/venv/bin/python orchestrator.py >> logs/cron.log 2>&1
```

### 9. Google Search Console

1. https://search.google.com/search-console 에서 블로그 등록
2. International Targeting → Country: **United States**
3. Sitemaps → `sitemap.xml` 제출

## Project Structure

```
auto-blog/
├── config.example.yaml          # 설정 템플릿 (git 추적)
├── config.yaml                  # 실제 설정 (gitignore)
├── orchestrator.py              # 메인 파이프라인 실행기
├── setup_auth.py                # Blogger OAuth 최초 인증
├── modules/
│   ├── trend_researcher.py      # Claude CLI 기반 키워드 리서치
│   ├── content_generator.py     # Claude CLI 기반 글 생성
│   └── blogger_uploader.py      # Blogger API v3 업로드
├── prompts/
│   ├── howto_apply.md           # How-to 가이드 프롬프트 템플릿
│   ├── best_tools.md            # Best tools 리스트 프롬프트 템플릿
│   └── daily_ai_tips.md         # AI 팁 프롬프트 템플릿
├── output/
│   ├── keywords/                # 키워드 리서치 JSON (날짜별)
│   └── drafts/                  # 생성된 글 Markdown (날짜별)
├── data/
│   └── posted_keywords.json     # 게시 완료 키워드 추적 (중복 방지)
├── logs/                        # 실행 로그 (날짜별)
├── credentials/                 # OAuth 토큰 (gitignore)
├── docs/
│   ├── specs/                   # 설계 문서
│   └── plans/                   # 구현 계획
└── tests/                       # 38 tests
    ├── test_trend_researcher.py
    ├── test_content_generator.py
    ├── test_blogger_uploader.py
    ├── test_orchestrator.py
    └── test_integration.py
```

## Configuration

`config.yaml` 주요 설정:

```yaml
blogger:
  blog_id: "YOUR_BLOG_ID"            # Blogger 대시보드에서 확인

schedule:
  posts_per_day: 1                    # 하루 최대 포스팅 수
  random_delay_max_hours: 2           # 크론 실행 후 랜덤 대기 (시간)

content:
  min_word_count: 800                 # 최소 단어 수
  categories:                         # 키워드 리서치 대상 카테고리
    - cooking
    - travel
    - health
    - finance
    - productivity
    # ...

trends:
  max_keywords_per_run: 3             # 리서치당 키워드 수

claude:
  timeout_seconds: 300                # Claude CLI 타임아웃
  max_retries: 1                      # 글 생성 재시도 횟수
```

## Pipeline Flow

```
1. Orchestrator 시작
   ├── 오늘 이미 포스팅했는지 확인 (logs/{date}.log에서 "Published:" 검색)
   ├── NO → 0~2시간 랜덤 대기 후 파이프라인 실행
   └── YES → 종료

2. Trend Research (Claude CLI + WebSearch)
   ├── Claude가 웹 서치로 최근 트렌딩 AI 주제 리서치
   ├── 검색 수요 × 경쟁도 × 관심도로 스코어링
   ├── posted_keywords.json과 대조하여 중복 제거
   ├── 실패 시 → 캐시된 키워드에서 미사용 키워드 선택
   └── output/keywords/{date}.json 저장

3. Content Generation (Claude CLI)
   ├── 키워드 + 프롬프트 템플릿 조합
   ├── Claude CLI로 글 생성 (stdin 전달)
   ├── 비본문 노이즈 제거 (clean_draft)
   ├── 품질 검증 (800단어+, H2 2개+)
   ├── 실패 시 → 재시도 (max_retries)
   └── output/drafts/{date}-{slug}.md 저장

4. Blogger Upload (API v3)
   ├── Markdown → HTML 변환 (문단 간격 스타일 포함)
   ├── 제목, 메타 디스크립션, 라벨 추출
   ├── Blogger API posts.insert() 호출
   ├── posted_keywords.json에 키워드 기록
   └── 로그에 게시 URL 기록
```

## US Targeting

해외 트래픽 + 높은 AdSense CPC를 위한 설정:

- **Google 계정:** 국가 United States, 언어 English
- **Blogger:** 언어 English, 타임존 US Eastern/Pacific
- **콘텐츠:** American English, USD, 미국 기준 사례
- **Search Console:** 타겟 국가 United States
- **프롬프트:** US Targeting 지침이 모든 템플릿에 내장

## AdSense

1. 최소 20~30편의 양질의 글이 쌓인 후 신청
2. https://adsense.google.com 에서 블로그 URL 제출
3. 승인 후 Blogger Settings → Earnings에서 AdSense 연결
4. Google이 자동으로 광고 삽입 (코드 수정 불필요)

**승인률 높이는 팁:**
- 모든 글 800단어 이상 유지
- About, Contact, Privacy Policy 페이지 추가
- 카테고리 일관성 (AI 일상 활용법)
- 최소 1개월 이상 운영 이력
