# Auto Blog Generator

Blogger에 AI 일상 활용법 콘텐츠를 자동 생성/업로드하는 파이프라인.
Google AdSense 수익 창출을 목표로 합니다.

## Architecture

```
크론잡 (매일 실행)
  → orchestrator.py
    ├── trend_researcher.py   — Google Trends에서 AI+일상 키워드 수집
    ├── content_generator.py  — Claude Code CLI로 블로그 글 생성
    └── blogger_uploader.py   — Blogger API v3로 자동 업로드
```

- **플랫폼:** Blogger (무료)
- **언어:** English (US 타겟)
- **니치:** AI를 일상생활에 쉽게 적용하는 방법 (비기술자 대상)
- **콘텐츠 유형:** How-to 가이드 + Best tools 리스트 + AI 팁
- **업로드 주기:** 주 3~4편, 비정기적 랜덤 타이밍
- **LLM:** Claude Code CLI (Max 구독 활용, 추가 비용 0원)

## Cost

| 항목 | 비용 |
|------|------|
| Blogger 호스팅 | 무료 |
| Blogger API | 무료 |
| Google Trends (pytrends) | 무료 |
| Claude Code (Max 구독) | 기존 구독 활용 |
| **추가 비용 합계** | **0원** |

## Prerequisites

- Python 3.11+
- Claude Code CLI (Max 구독)
- Google 계정 (US 설정 권장)

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/{YOUR_USERNAME}/auto-blog.git
cd auto-blog
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Cloud Console

1. https://console.cloud.google.com 에서 프로젝트 생성
2. Blogger API v3 활성화 (APIs & Services → Library)
3. OAuth consent screen 설정 (External)
4. OAuth client ID 발급 (Desktop app)
5. JSON 다운로드 → `credentials/google_oauth.json`에 저장

### 3. Blogger

1. https://www.blogger.com 에서 블로그 생성
2. Settings에서 Language: English, Timezone: US
3. 대시보드 URL에서 Blog ID 확인: `https://www.blogger.com/blog/posts/{BLOG_ID}`

### 4. Configuration

```bash
cp config.example.yaml config.yaml
# config.yaml의 blog_id를 본인 Blog ID로 변경
```

### 5. Authentication

```bash
python setup_auth.py
# 브라우저가 열리면 Google 계정으로 로그인 → Allow
```

### 6. Test

```bash
# 유닛 테스트
python -m pytest tests/ -v

# 수동 실행 테스트 (실제로 글 1편 생성+업로드)
python orchestrator.py
```

### 7. Cron

```bash
crontab -e
# 아래 한 줄 추가 (매일 오전 10시):
0 10 * * * cd /path/to/auto-blog && /path/to/venv/bin/python orchestrator.py >> logs/cron.log 2>&1
```

## Project Structure

```
auto-blog/
├── config.example.yaml          # 설정 템플릿
├── config.yaml                  # 실제 설정 (gitignore)
├── orchestrator.py              # 메인 파이프라인 실행기
├── setup_auth.py                # OAuth 최초 인증
├── modules/
│   ├── trend_researcher.py      # Google Trends 키워드 수집
│   ├── content_generator.py     # Claude Code CLI 글 생성
│   └── blogger_uploader.py      # Blogger API 업로드
├── prompts/
│   ├── howto_apply.md           # How-to 가이드 템플릿
│   ├── best_tools.md            # Best tools 리스트 템플릿
│   └── daily_ai_tips.md         # AI 팁 템플릿
├── output/
│   ├── keywords/                # 키워드 리서치 결과
│   └── drafts/                  # 생성된 글
├── data/
│   └── posted_keywords.json     # 게시 완료 키워드 추적
├── logs/                        # 실행 로그
├── credentials/                 # OAuth 토큰 (gitignore)
└── tests/                       # 41 tests
```

## How It Works

1. **크론잡이 매일 `orchestrator.py` 실행**
2. **확률적 스케줄링:** 주 3~4편 목표로 오늘 포스팅 여부를 확률적으로 결정
3. **트렌드 리서치:** pytrends로 "AI + 일상 카테고리" 최근 7일 검색량 조회 → 키워드 스코어링
4. **글 생성:** 키워드에 맞는 프롬프트 템플릿 + Claude Code CLI로 800단어 이상 글 생성
5. **업로드:** Markdown → HTML 변환 후 Blogger API로 자동 게시
6. **중복 방지:** `posted_keywords.json`으로 이미 쓴 키워드 추적

## US Targeting

해외 트래픽 + 높은 CPC를 위한 설정:

- Google 계정 국가: United States
- Blogger 언어/타임존: English / US timezone
- 콘텐츠: American English, USD, 미국 기준 사례
- Google Search Console: 타겟 국가 United States

## AdSense

20~30편의 글이 쌓인 후 https://adsense.google.com 에서 신청.
Blogger Settings → Earnings에서 AdSense 연결.
