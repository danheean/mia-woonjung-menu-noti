"""
성신여자대학교 미아운정캠퍼스 학식 메뉴 스크래퍼
"""

import os
import logging
from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MENU_URL = os.environ.get(
    "MENU_URL",
    "https://www.sungshin.ac.kr/sungshin/3966/subview.do",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MEAL_TYPES = ["조식", "중식", "석식"]

DAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def fetch_html(url: str, timeout: int = 10) -> str:
    """Fetch raw HTML from *url*."""
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def parse_menu(html: str, target_date: Optional[date] = None) -> dict:
    """Parse the cafeteria menu page and return a dict keyed by meal type.

    Returns a mapping such as::

        {
            "조식": "메뉴 항목 ...",
            "중식": "메뉴 항목 ...",
            "석식": "메뉴 항목 ...",
        }

    When *target_date* is not given, today's date is used.
    """
    if target_date is None:
        target_date = date.today()

    soup = BeautifulSoup(html, "lxml")
    menu: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Strategy 1: look for a <table> that contains weekly menu data.
    # Sungshin Women's University uses a table whose first row contains
    # day-of-week headers (월, 화, 수, 목, 금) and subsequent rows
    # contain meal-type labels (조식/중식/석식) followed by menu text.
    # ------------------------------------------------------------------
    tables = soup.find_all("table")
    found_weekly_table = False
    day_abbr = DAY_KO[target_date.weekday()]

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        # Locate the header row that contains day names
        header_row_idx = None
        col_for_today: Optional[int] = None

        for idx, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            cell_texts = [c.get_text(strip=True) for c in cells]
            # If this row contains any Korean weekday abbreviation, treat it
            # as the weekly header row.
            if any(d in cell_texts for d in DAY_KO):
                found_weekly_table = True
                if day_abbr in cell_texts:
                    header_row_idx = idx
                    col_for_today = cell_texts.index(day_abbr)
                break

        if header_row_idx is None or col_for_today is None:
            continue

        # Walk the data rows below the header
        for row in rows[header_row_idx + 1 :]:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            first_cell = cells[0].get_text(strip=True)
            meal_label = next(
                (m for m in MEAL_TYPES if m in first_cell), None
            )
            if meal_label is None:
                continue

            if col_for_today < len(cells):
                content = cells[col_for_today].get_text(
                    separator="\n", strip=True
                )
                menu[meal_label] = content if content else "메뉴 정보 없음"

        if menu:
            return menu

    # ------------------------------------------------------------------
    # Strategy 2: look for definition lists or divs labelled by meal type.
    # Only used when no weekly-table structure was found in the page.
    # ------------------------------------------------------------------
    if not found_weekly_table:
        for meal in MEAL_TYPES:
            for tag in soup.find_all(string=lambda t: t and meal in t):
                parent = tag.find_parent()
                if parent is None:
                    continue
                sibling = parent.find_next_sibling()
                if sibling:
                    content = sibling.get_text(separator="\n", strip=True)
                    if content:
                        menu[meal] = content

    return menu


def get_today_menu() -> dict:
    """Convenience function: fetch and parse today's menu."""
    html = fetch_html(MENU_URL)
    return parse_menu(html)
