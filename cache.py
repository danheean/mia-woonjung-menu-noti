import json
import logging
from pathlib import Path

MENU_CACHE_DIR = Path("cache/menu")
OG_CACHE_DIR = Path("cache/og")

logger = logging.getLogger(__name__)


def _ensure_dirs():
    MENU_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OG_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_menu_cache(date_str: str) -> list[str] | str | None:
    """캐시에서 메뉴 반환. 휴무이면 '휴무' 문자열, 없으면 None."""
    _ensure_dirs()
    path = MENU_CACHE_DIR / f"{date_str}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        logger.warning(f"메뉴 캐시 읽기 실패 ({date_str}): {e}")
        return None


def save_menu_cache(date_str: str, menu: list[str] | str) -> None:
    """메뉴 캐시 저장. 휴무이면 '휴무' 문자열 저장."""
    _ensure_dirs()
    path = MENU_CACHE_DIR / f"{date_str}.json"
    try:
        path.write_text(json.dumps(menu, ensure_ascii=False), encoding="utf-8")
        logger.info(f"메뉴 캐시 저장: {date_str}")
    except Exception as e:
        logger.warning(f"메뉴 캐시 저장 실패 ({date_str}): {e}")


def get_og_cache_path(date_str: str) -> Path | None:
    """OG 이미지 캐시 파일 경로 반환. 없으면 None."""
    _ensure_dirs()
    path = OG_CACHE_DIR / f"{date_str}.png"
    return path if path.exists() else None


def save_og_cache(date_str: str, image_bytes: bytes) -> None:
    """OG 이미지 캐시 저장."""
    _ensure_dirs()
    path = OG_CACHE_DIR / f"{date_str}.png"
    try:
        path.write_bytes(image_bytes)
        logger.info(f"OG 이미지 캐시 저장: {date_str}")
    except Exception as e:
        logger.warning(f"OG 이미지 캐시 저장 실패 ({date_str}): {e}")
