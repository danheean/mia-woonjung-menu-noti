"""
Telegram 알림 전송 모듈
"""

import logging
import os
from datetime import date

import telegram

logger = logging.getLogger(__name__)

MEAL_EMOJI = {
    "조식": "🌅",
    "중식": "🍱",
    "석식": "🌙",
}

DAY_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def format_menu_message(menu: dict, target_date: date | None = None) -> str:
    """Format the *menu* dict into a human-readable Telegram message."""
    if target_date is None:
        target_date = date.today()

    day_name = DAY_KO[target_date.weekday()]
    date_str = target_date.strftime("%Y년 %m월 %d일")
    lines = [
        f"🏫 성신여대 미아운정캠퍼스 학식 메뉴",
        f"📅 {date_str} ({day_name})",
        "",
    ]

    if not menu:
        lines.append("⚠️ 오늘의 메뉴 정보를 가져올 수 없습니다.")
        return "\n".join(lines)

    for meal_type in ["조식", "중식", "석식"]:
        if meal_type in menu:
            emoji = MEAL_EMOJI.get(meal_type, "🍽️")
            lines.append(f"{emoji} [{meal_type}]")
            lines.append(menu[meal_type])
            lines.append("")

    return "\n".join(lines).rstrip()


async def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
) -> None:
    """Send *text* to Telegram *chat_id* using bot *token*."""
    bot = telegram.Bot(token=token)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=None,
    )
    logger.info("Telegram 메시지 전송 완료 (chat_id=%s)", chat_id)


async def notify(menu: dict) -> None:
    """Read credentials from environment variables and send the menu message."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 환경 변수가 설정되지 않았습니다."
        )
        raise EnvironmentError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set."
        )

    message = format_menu_message(menu)
    await send_telegram_message(token, chat_id, message)
