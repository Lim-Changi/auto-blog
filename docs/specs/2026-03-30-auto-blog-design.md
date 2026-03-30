# Auto Blog Generator - Design Spec

## Overview

Blogger 플랫폼에 AI 일상 활용법 콘텐츠를 자동 생성/업로드하는 파이프라인.
Google AdSense 수익 창출을 목표로 한다.

## 핵심 결정사항

- **플랫폼:** Blogger (무료, AdSense 연동 용이)
- **언어:** 영어 (해외 트래픽, 높은 CPC)
- **니치:** AI를 일상생활에 쉽게 적용하는 방법 (비기술자 대상)
- **콘텐츠 유형:** How-to 가이드 + Best tools 리스트
- **톤:** 친근하고 실용적, 데이터/정보 기반
- **자동화:** 완전 무인 (크론잡)
- **업로드 주기:** 주 3~4편, 비정기적 (랜덤 타이밍)
- **실행 환경:** 로컬 Mac + 크론잡
- **LLM:** Claude Code CLI (Max 구독 활용, API 비용 0원)
- **업로드:** Blogger API v3 (무료)

## 아키텍처

### 디렉토리 구조

```
auto-blog/
├── config.yaml                 # 설정 (Blogger 계정, 스케줄, 프롬프트 등)
├── orchestrator.py             # 메인 실행기 - 파이프라인 조율
├── modules/
│   ├── trend_researcher.py     # Google Trends 기반 키워드 수집
│   ├── content_generator.py    # Claude Code CLI로 글 생성
│   └── blogger_uploader.py     # Blogger API v3로 업로드
├── prompts/
│   ├── howto_apply.md          # "How to Use AI for [일상 활동]" 템플릿
│   ├── best_tools.md           # "Best Free AI Tools for [일상 목적]" 템플릿
│   └── daily_ai_tips.md        # "X Ways AI Can Help You [일상 주제]" 템플릿
├── output/
│   ├── keywords/               # 키워드 리서치 결과 (JSON)
│   └── drafts/                 # 생성된 글 (Markdown)
├── logs/                       # 실행 로그
├── data/
│   └── posted_keywords.json    # 이미 포스팅한 키워드 추적 (중복 방지)
├── credentials/
│   └── google_oauth.json       # Blogger API 인증 정보 (gitignore)
├── setup.py                    # 최초 인증 셋업 스크립트
└── requirements.txt
```

### 실행 흐름

```
크론잡 (매일 실행)
  → orchestrator.py
    │
    ├── 오늘 포스팅 여부 결정 (확률 ~50%, 주 3~4편 목표)
    │   └── NO → 종료
    │   └── YES ↓
    │
    ├── 1단계: trend_researcher.py
    │   - pytrends로 최근 7일 "AI + {일상 카테고리}" 검색 트렌드 수집
    │   - 관련 검색어(related queries) 수집
    │   - 검색량 × 경쟁도 역수로 키워드 스코어링
    │   - 이미 포스팅한 키워드 중복 제거
    │   - 글 유형 자동 결정 (how-to / best tools / tips)
    │   → output/keywords/{date}.json 저장
    │
    ├── 2단계: content_generator.py
    │   - 키워드 + 템플릿 조합으로 프롬프트 조립
    │   - claude -p "프롬프트" 로 글 생성
    │   - 품질 검증 (800단어 이상, 제목/소제목 구조 확인)
    │   - 미통과 시 1회 재생성
    │   → output/drafts/{date}-{keyword}.md 저장
    │
    └── 3단계: blogger_uploader.py
        - Markdown → HTML 변환
        - Blogger API v3로 포스팅 (제목, 본문, 라벨)
        - posted_keywords.json에 기록
        - 결과 로깅
```

## 모듈 상세

### 1. Trend Researcher

**입력:** config.yaml의 카테고리 목록, 리서치 설정
**출력:** output/keywords/{date}.json

```json
{
  "keyword": "AI meal planning",
  "category": "cooking",
  "search_volume": 82,
  "competition_score": 0.3,
  "template": "howto_apply",
  "related_queries": ["ChatGPT meal prep", "AI diet planner"],
  "title_suggestion": "How to Use AI to Plan Your Weekly Meals in 5 Minutes"
}
```

**동작:**
1. 카테고리 풀에서 "AI + {카테고리}" 조합 생성
2. pytrends로 최근 7일 interest_over_time 조회 (지역: US/Global)
3. related_queries 수집 (글 본문 SEO 밀도 향상용)
4. 스코어링: 검색량(높을수록↑) × 경쟁도(낮을수록↑)
   - 경쟁도는 pytrends의 관련 주제 수 + Google 검색 결과 수(requests로 조회)로 추정
5. posted_keywords.json과 대조하여 중복 제거
6. pytrends 요청 간 2~5초 랜덤 딜레이 (rate limit 방지)
6. 검색 의도 분석으로 템플릿 자동 선택
   - "how to..." → howto_apply
   - "best..." / "top..." → best_tools
   - 그 외 → daily_ai_tips

**카테고리 풀:**
cooking, travel, health, finance, parenting, shopping, productivity, education, fitness, home, career, hobbies

### 2. Content Generator

**입력:** output/keywords/{date}.json
**출력:** output/drafts/{date}-{keyword}.md

**동작:**
1. 키워드 JSON에서 키워드, 관련 검색어, 카테고리, 템플릿 유형 로드
2. 해당 템플릿 파일 로드 + 키워드/카테고리 주입
3. SEO 지침 포함 (제목, H2 소제목, 메타 디스크립션)
4. Claude Code CLI 호출: `claude -p "$(cat assembled_prompt.md)" --output-format text --max-turns 1`
5. 품질 검증:
   - 최소 800단어
   - H1 제목 존재
   - H2 소제목 2개 이상
   - 미통과 시 1회 재생성

**프롬프트 핵심 지침:**
- 타겟: IT에 익숙하지 않은 일반 성인
- 톤: 친근하고 실용적
- 데이터/정보 기반 (구체적 수치, 도구명, 단계별 설명)
- AI가 썼다는 거부감 없도록 자연스러운 문체
- SEO: 키워드를 제목, 첫 문단, 소제목에 자연스럽게 배치

### 3. Blogger Uploader

**입력:** output/drafts/{date}-{keyword}.md
**출력:** Blogger 포스트 게시

**사전 준비 (1회):**
1. Google Cloud Console → 프로젝트 생성
2. Blogger API v3 활성화
3. OAuth 2.0 클라이언트 ID 발급 → credentials/google_oauth.json
4. `python setup.py` 실행 → 브라우저 Google 로그인 → 토큰 저장

**동작:**
1. draft.md 읽기
2. python-markdown으로 Markdown → HTML 변환
3. 메타데이터 추출 (제목, 라벨)
4. Blogger API 호출:
   ```
   POST https://www.googleapis.com/blogger/v3/blogs/{blogId}/posts
   {
     "kind": "blogger#post",
     "title": "How to Use AI to Plan Your Weekly Meals...",
     "content": "<p>변환된 HTML</p>",
     "labels": ["AI", "cooking", "meal planning"]
   }
   ```
5. 성공: 포스트 URL 로깅 + posted_keywords.json 업데이트
6. 실패: 에러 로깅, 다음 실행 시 재시도

**토큰 관리:**
- google-auth 라이브러리가 토큰 만료 시 자동 갱신
- refresh_token은 credentials/ 내에 저장

### 4. Orchestrator

**랜덤 스케줄링 로직:**
- 크론잡: 매일 고정 시간에 실행 (예: 매일 10:00)
- orchestrator 내부에서:
  1. 이번 주 이미 게시한 횟수 확인
  2. 남은 일수 대비 목표(3~4편) 달성을 위한 확률 계산
  3. 확률적으로 오늘 게시 여부 결정
  4. 게시 시, 실제 실행 전 0~2시간 랜덤 sleep (자연스러운 타이밍)

## Config

```yaml
# 블로그 설정
blogger:
  blog_id: "YOUR_BLOG_ID"
  credentials_path: "credentials/google_oauth.json"

# 스케줄 설정
schedule:
  posts_per_week: [3, 4]       # 주 3~4편
  time_range_hours: [6, 22]    # 이 범위 내 랜덤 시간
  random_delay_max_hours: 2    # 최대 랜덤 지연

# 콘텐츠 설정
content:
  language: "en"
  min_word_count: 800
  target_audience: "non-tech adults"
  tone: "friendly, practical, data-driven"
  categories:
    - cooking
    - travel
    - health
    - finance
    - parenting
    - shopping
    - productivity
    - education
    - fitness
    - home
    - career
    - hobbies

# 트렌드 리서치
trends:
  region: "US"
  lookback_days: 7
  max_keywords_per_run: 3

# Claude Code
claude:
  timeout_seconds: 120
  max_retries: 1
```

## 비용 구조

| 항목 | 비용 |
|------|------|
| Blogger 호스팅 | 무료 |
| Blogger API | 무료 |
| Google Trends (pytrends) | 무료 |
| Claude Code (Max 구독) | 기존 구독 활용 |
| **추가 비용 합계** | **0원** |

## 해외 타겟팅 전략 (한국 기반 → US 타겟)

한국 IP/계정에서 미국 대상 블로그를 운영할 때의 SEO 최적화:

### 계정 설정
- **새 Google 계정 생성** — 국가를 United States로 설정
- Google 계정 언어: English
- 이 계정으로 Blogger, Search Console, AdSense 모두 운영

### Blogger 설정
- 블로그 언어: English
- 타임존: America/New_York 또는 America/Los_Angeles
- 블로그 설명(description): 영어로 작성

### Google Search Console
- 블로그 등록 후 타겟 국가를 "United States"로 설정
- sitemap.xml 제출

### 콘텐츠 가이드라인
- USD 단위 사용 (가격 언급 시)
- 미국 기준 사례/서비스 우선 언급
- 날짜 형식: MM/DD/YYYY
- 미국식 영어 (color, not colour)

### IP 관련
- 콘텐츠 작성 IP는 SEO에 큰 영향 없음 (Google은 콘텐츠와 설정을 더 중시)
- Blogger API 호출은 IP 무관

## 셋업 절차 (사용자 1회 수행)

1. **새 Google 계정 생성** (국가: United States, 언어: English)
2. 해당 계정으로 Google Cloud Console에서 프로젝트 생성
3. Blogger API v3 활성화
4. OAuth 2.0 클라이언트 ID 발급 → `credentials/google_oauth.json`에 저장
5. Blogger에서 블로그 생성 (언어: English, 타임존: US)
6. Google Search Console에 블로그 등록, 타겟 국가: US
7. `config.yaml`에 `blog_id` 입력
8. `pip install -r requirements.txt`
9. `python setup_auth.py` → 브라우저에서 Google 로그인 → 토큰 자동 저장
10. 크론잡 등록: `crontab -e` → `0 10 * * * cd /path/to/auto-blog && python orchestrator.py`

## 추후 개선 가능 사항

- Mac 슬립/종료 시 대응 (GitHub Actions 이전)
- AdSense 승인 후 업로드 빈도 조절
- 글 성과 추적 (Google Analytics 연동)
- 이미지 자동 생성 (AI 이미지 도구 연동)
- 다중 블로그 지원
