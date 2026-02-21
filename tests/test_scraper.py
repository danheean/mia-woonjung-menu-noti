"""Tests for src/scraper.py"""

from datetime import date
from textwrap import dedent
from unittest.mock import patch

import pytest

from src.scraper import parse_menu


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_weekly_table_html(target_day_idx: int, menu_rows: dict) -> str:
    """Build a minimal HTML page that mimics Sungshin's cafeteria table.

    *target_day_idx*: 0=월, 1=화, …
    *menu_rows*: { meal_type: menu_text }
    """
    days = ["월", "화", "수", "목", "금"]
    header_cells = "".join(f"<th>{d}</th>" for d in days)

    data_rows = ""
    for meal, text in menu_rows.items():
        cells = ""
        for i in range(len(days)):
            if i == target_day_idx:
                cells += f"<td>{text}</td>"
            else:
                cells += "<td>다른 날 메뉴</td>"
        data_rows += f"<tr><th>{meal}</th>{cells}</tr>"

    return dedent(
        f"""
        <html><body>
        <table>
          <tr><th>구분</th>{header_cells}</tr>
          {data_rows}
        </table>
        </body></html>
        """
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseMenu:
    def test_parse_wednesday_lunch(self):
        """parse_menu extracts 중식 for Wednesday (weekday index 2)."""
        target = date(2024, 3, 6)  # Wednesday
        html = _make_weekly_table_html(
            target_day_idx=2,
            menu_rows={"조식": "토스트\n우유", "중식": "비빔밥\n된장국", "석식": "볶음밥"},
        )
        result = parse_menu(html, target_date=target)

        assert result.get("중식") == "비빔밥\n된장국"

    def test_parse_all_meal_types(self):
        """All three meal types (조식, 중식, 석식) are parsed correctly."""
        target = date(2024, 3, 4)  # Monday
        html = _make_weekly_table_html(
            target_day_idx=0,
            menu_rows={"조식": "빵\n주스", "중식": "김치찌개\n공기밥", "석식": "불고기\n국"},
        )
        result = parse_menu(html, target_date=target)

        assert result.get("조식") == "빵\n주스"
        assert result.get("중식") == "김치찌개\n공기밥"
        assert result.get("석식") == "불고기\n국"

    def test_empty_html_returns_empty_dict(self):
        """parse_menu returns an empty dict when HTML has no menu table."""
        result = parse_menu("<html><body><p>내용 없음</p></body></html>")
        assert result == {}

    def test_returns_empty_on_weekend(self):
        """parse_menu returns empty dict when weekday header is not found."""
        target = date(2024, 3, 9)  # Saturday – table only has 월~금
        html = _make_weekly_table_html(
            target_day_idx=0,
            menu_rows={"중식": "비빔밥"},
        )
        result = parse_menu(html, target_date=target)
        # 토 column doesn't exist in our table, so menu should be empty
        assert result == {}

    def test_default_date_is_today(self):
        """parse_menu uses today's date when target_date is None."""
        today = date.today()
        html = _make_weekly_table_html(
            target_day_idx=today.weekday(),
            menu_rows={"중식": "오늘 메뉴"},
        )
        result = parse_menu(html)
        if today.weekday() < 5:  # weekday
            assert "중식" in result

    def test_default_date_mocked_monday(self):
        """parse_menu uses today's date (mocked to a Monday) when target_date is None."""
        monday = date(2024, 3, 4)  # Known Monday
        html = _make_weekly_table_html(
            target_day_idx=0,
            menu_rows={"중식": "월요일 점심"},
        )
        with patch("src.scraper.date") as mock_date:
            mock_date.today.return_value = monday
            result = parse_menu(html)

        assert result.get("중식") == "월요일 점심"
