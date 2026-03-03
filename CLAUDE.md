# CLAUDE.md

## 프로젝트 개요
성신여대 운정교내식당 메뉴 크롤링 → Flask 웹 제공 서비스.
포트: **5005** / 패키지 매니저: **uv** / Python 3.10+

## 실행
```bash
uv sync
cp .env.example .env   # GEMINI_API_KEY 설정 필요
uv run python scripts/download_fonts.py  # 최초 1회
uv run python app.py   # http://localhost:5005/
```

## 주요 파일
| 파일 | 역할 |
|------|------|
| `app.py` | Flask 라우트 (`/`, `/weekly`, `/og-image/<date>.png`) |
| `crawler.py` | 게시물 URL 탐색, `get_menu_for_date()` 진입점 |
| `crawler_graph.py` | LangGraph StateGraph — 테이블/이미지 분기 파싱 + 검증 |
| `cache.py` | 메뉴 JSON, OG PNG, post_url 파일 캐시 |
| `og_image.py` | Pillow OG 이미지 생성 (1200×630px) |
| `notifier.py` | 오류 알림 (현재 log only) |

## 크롤링 구조
- 목록 URL: `https://www.sungshin.ac.kr/main_kor/11095/subview.do`
- `get_weekly_post_url()` → 게시물 URL 탐색
- `run_crawl_graph()` (crawler_graph.py) → LangGraph로 파싱

### LangGraph 노드 흐름
```
fetch_post → detect_format → parse_table (HTML 테이블)
                           → parse_image (Gemini Vision OCR)
                                  ↓
                           validate_menu → END
```

- **detect_format**: `artclView` 내 `<table>` 유무로 분기 결정
- **parse_table**: 헤더 셀 `"2월 23일 (월)"` 형식 파싱
- **parse_image**: `gemini-2.5-flash` Vision으로 이미지 OCR → JSON 추출
- **validate_menu**: post_url HTTP 200 확인, 날짜·항목 수 검증

## LLM
- 모델: `gemini-2.5-flash` (`crawler_graph.py:17` `GEMINI_MODEL`)
- SDK: `google-genai` (구 `google-generativeai` deprecated)
- 용도: 이미지 형식 메뉴표 OCR 전용

## 캐시 구조
```
cache/
  menu/<date>.json     # 날짜별 메뉴 (list 또는 "휴무")
  og/<date>.png        # OG 이미지
  post_url.txt         # 마지막으로 조회한 게시물 URL
```

## 주의사항
- 성신여대 서버는 WAF 적용 — `Mozilla` UA 없으면 차단됨
  → `run_crawl_graph()`에서 자동 보완
- `artclView` 없는 응답 = WAF 차단 또는 페이지 구조 변경
- `GEMINI_API_KEY` 미설정 시 이미지 형식 게시물 파싱 불가
- Content-Type에 `; charset=UTF-8` 붙어 올 수 있음 → `.split(";")[0]` 처리

## 환경 변수 (.env)
```
FLASK_PORT=5005
GEMINI_API_KEY=          # Google AI Studio에서 발급
TARGET_URL=              # 기본값: 성신여대 공지 페이지
CAFETERIA_KEYWORD=운정교내식당
BASE_URL=                # 운영 서버 명시 필요 (OG 이미지용)
```
