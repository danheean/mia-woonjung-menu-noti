# mia-woonjung-menu-noti

성신여자대학교 미아운정캠퍼스 학식 메뉴 알림 서비스

매일 오전 8시(KST) 평일에 당일 학식 메뉴를 Telegram으로 자동 전송합니다.

---

## 기능

- 성신여대 미아운정캠퍼스 학식 페이지에서 조식/중식/석식 메뉴를 스크래핑
- Telegram 봇을 통해 채널/그룹/개인에게 메뉴 알림 전송
- GitHub Actions 스케줄러로 평일 매일 자동 실행

---

## 설정

### 1. Telegram 봇 생성

1. Telegram에서 [@BotFather](https://t.me/BotFather)에게 `/newbot` 명령어로 봇을 만드세요.
2. 발급받은 **Bot Token**을 메모해 두세요.
3. 알림을 받을 채팅방(채널, 그룹 등)의 **Chat ID**를 확인하세요.

### 2. GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions 에서 다음 값을 등록합니다:

| 이름 | 설명 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급받은 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 알림을 받을 채팅방 ID |

### 3. 메뉴 URL 설정 (선택)

기본 URL이 학교 서버 변경으로 달라진 경우, Actions 변수에 `MENU_URL`을 추가하세요:

Repository → Settings → Secrets and variables → Actions → Variables

| 이름 | 설명 |
|------|------|
| `MENU_URL` | 학식 메뉴 페이지 URL (기본값: `https://www.sungshin.ac.kr/sungshin/3966/subview.do`) |

---

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# 실행
python -m src.main
```

---

## 테스트

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## 프로젝트 구조

```
├── .github/
│   └── workflows/
│       └── menu_notify.yml   # 스케줄 워크플로 (평일 오전 8시 KST)
├── src/
│   ├── __init__.py
│   ├── main.py               # 진입점
│   ├── scraper.py            # 학식 메뉴 스크래퍼
│   └── notifier.py           # Telegram 알림 전송
├── tests/
│   ├── test_scraper.py
│   └── test_notifier.py
├── requirements.txt
└── README.md
```
