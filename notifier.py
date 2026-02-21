import logging
import os

logger = logging.getLogger(__name__)


def notify_error(error: Exception, context: str) -> None:
    """오류 발생 시 개발자에게 알림. 현재는 로그만 기록."""
    method = os.getenv("NOTIFY_METHOD", "log")

    message = f"[오류] {context}: {type(error).__name__}: {error}"

    if method == "log":
        logger.error(message)
    else:
        # 추후 email/slack 확장
        logger.error(message)
