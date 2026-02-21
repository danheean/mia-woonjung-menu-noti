"""Tests for src/notifier.py"""

from datetime import date

from src.notifier import format_menu_message


class TestFormatMenuMessage:
    def test_basic_format(self):
        menu = {"조식": "토스트\n우유", "중식": "비빔밥\n된장국", "석식": "볶음밥"}
        msg = format_menu_message(menu, target_date=date(2024, 3, 6))

        assert "성신여대 미아운정캠퍼스" in msg
        assert "2024년 03월 06일" in msg
        assert "수요일" in msg
        assert "비빔밥" in msg
        assert "🍱" in msg  # 중식 emoji

    def test_empty_menu_shows_warning(self):
        msg = format_menu_message({}, target_date=date(2024, 3, 6))
        assert "메뉴 정보를 가져올 수 없습니다" in msg

    def test_partial_menu(self):
        """Only 중식 available."""
        menu = {"중식": "국밥"}
        msg = format_menu_message(menu, target_date=date(2024, 3, 4))
        assert "국밥" in msg
        assert "조식" not in msg
        assert "석식" not in msg

    def test_default_date_is_today(self):
        """format_menu_message uses today when target_date is None."""
        msg = format_menu_message({"중식": "점심"})
        today = date.today()
        assert today.strftime("%Y년 %m월 %d일") in msg
