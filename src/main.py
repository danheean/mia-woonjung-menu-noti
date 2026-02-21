"""
성신여자대학교 미아운정캠퍼스 학식 메뉴 알림 서비스 - 진입점
"""

import asyncio
import logging
import sys

from src.scraper import get_today_menu
from src.notifier import notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("메뉴 정보를 가져오는 중...")
    try:
        menu = get_today_menu()
    except Exception as exc:  # noqa: BLE001
        logger.error("메뉴 스크래핑 실패: %s", exc)
        menu = {}

    if not menu:
        logger.warning("메뉴 정보가 비어 있습니다. 알림을 보냅니다 (빈 메뉴).")

    asyncio.run(notify(menu))
    logger.info("완료.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        logger.error("오류 발생: %s", exc)
        sys.exit(1)
