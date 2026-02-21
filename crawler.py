import logging
import os
import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TARGET_URL = os.getenv("TARGET_URL", "https://www.sungshin.ac.kr/main_kor/11095/subview.do")
CAFETERIA_KEYWORD = os.getenv("CAFETERIA_KEYWORD", "운정교내식당")

WEEKDAY_MAP = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

BASE_DOMAIN = "https://www.sungshin.ac.kr"
MAX_RETRIES = 3


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _get(session: requests.Session, url: str) -> requests.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            return resp
        except Exception as e:
            logger.warning(f"요청 실패 ({attempt + 1}/{MAX_RETRIES}) {url}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
    return None


def get_weekly_post_url(session: requests.Session) -> str | None:
    """목록 페이지에서 운정교내식당 게시물 URL 추출."""
    resp = _get(session, TARGET_URL)
    if not resp:
        logger.error("목록 페이지 요청 실패")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # 게시물 링크 탐색: 제목에 키워드 포함된 <a> 태그
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        if CAFETERIA_KEYWORD in title:
            href = a["href"]
            if href.startswith("http"):
                return href
            return BASE_DOMAIN + href

    logger.warning(f"'{CAFETERIA_KEYWORD}' 게시물을 찾을 수 없습니다.")
    return None


_DATE_PATTERN = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")
_DAY_PATTERN = re.compile(r"[（(]([월화수목금])[）)]")
_ORIGIN_PATTERN = re.compile(r"(국내산|수입산|외국산|호주산|미국산|중국산|원산지|-)")


def _is_menu_item(text: str) -> bool:
    """메뉴 항목으로 유효한지 판단."""
    if not text or len(text) < 2:
        return False
    if text.startswith("*") or text.startswith("※"):
        return False
    if _ORIGIN_PATTERN.search(text):
        return False
    # 숫자만이거나 단위(원, 산, 지 등 1글자)
    if len(text) <= 2 and not any(c.isalpha() for c in text if "\uAC00" <= c <= "\uD7A3"):
        return False
    return True


def _parse_header_date(text: str, ref_year: int) -> date | None:
    """헤더 셀 텍스트에서 날짜 추출. 예: "2월 23일 (월)" → date(2026, 2, 23)"""
    m = _DATE_PATTERN.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    try:
        return date(ref_year, month, day)
    except ValueError:
        return None


def parse_weekly_table(post_url: str, session: requests.Session, ref_year: int) -> dict[date, list[str]]:
    """상세 페이지 HTML 테이블에서 날짜별 메뉴 파싱.

    헤더 셀 형식: "2월 23일 (월)", "2월 24일(화)" 등
    실제 날짜(date 객체)를 키로 반환하여 지난 주 게시물 오매칭 방지.

    Returns:
        {date(2026,2,23): [...], date(2026,2,24): [...], ...} 형태 dict. 실패 시 빈 dict.
    """
    resp = _get(session, post_url)
    if not resp:
        logger.error(f"상세 페이지 요청 실패: {post_url}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")

    container = soup.find(class_="artclView") or soup
    tables = container.find_all("table")

    if not tables:
        logger.warning("테이블을 찾을 수 없습니다.")
        return {}

    result: dict[date, list[str]] = {}

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # 헤더 행에서 날짜→컬럼 인덱스 매핑
        date_indices: dict[date, int] = {}
        header_row_idx = 0

        for r_idx, row in enumerate(rows[:3]):
            cells = row.find_all(["th", "td"])
            indices: dict[date, int] = {}
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                if _DAY_PATTERN.search(text):  # 요일 괄호 포함 셀만
                    d = _parse_header_date(text, ref_year)
                    if d:
                        indices[d] = i
            if len(indices) >= 3:
                date_indices = indices
                header_row_idx = r_idx
                break

        if not date_indices:
            continue

        for d in date_indices:
            result[d] = []

        for row in rows[header_row_idx + 1:]:
            cells = row.find_all(["td", "th"])
            for d, idx in date_indices.items():
                if idx < len(cells):
                    text = cells[idx].get_text(separator="\n", strip=True)
                    items = [line.strip() for line in text.splitlines() if _is_menu_item(line.strip())]
                    result[d].extend(items)

        if result:
            break

    if result:
        logger.info(f"메뉴 파싱 성공: {sorted(result.keys())}")
    else:
        logger.warning("날짜별 메뉴 파싱 실패")

    return result


def get_menu_for_date(target_date: date) -> list[str] | None:
    """주어진 날짜의 메뉴 반환. 날짜 불일치(지난 주 게시물 등)이면 None."""
    if target_date.weekday() >= 5:
        logger.info(f"{target_date}: 주말")
        return None

    session = _make_session()
    post_url = get_weekly_post_url(session)
    if not post_url:
        return None

    logger.info(f"게시물 URL: {post_url}")
    weekly = parse_weekly_table(post_url, session, ref_year=target_date.year)
    if not weekly:
        return None

    menu = weekly.get(target_date)
    if menu is None:
        logger.warning(
            f"{target_date} 날짜가 게시물에 없음 "
            f"(게시물 날짜: {sorted(weekly.keys())}). 이번 주 게시물 미게시 가능성."
        )
        return None

    return menu or None
