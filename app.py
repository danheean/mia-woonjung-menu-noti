import logging
import os
from datetime import datetime, date, timedelta, timezone

KST = timezone(timedelta(hours=9))


def today_kst() -> date:
    """KST 기준 오늘 날짜 반환."""
    return datetime.now(KST).date()

import holidays
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, Response, render_template, send_file, request
from werkzeug.middleware.proxy_fix import ProxyFix

import cache
import crawler
import notifier
import og_image

load_dotenv()

# 로깅 설정
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

KR_HOLIDAYS = holidays.KR()


def _is_holiday(d: date) -> bool:
    return d.weekday() >= 5 or d in KR_HOLIDAYS


def _get_menu(target_date: date) -> list[str] | str | None:
    """메뉴 반환. '휴무' 문자열이면 휴무, None이면 오류/미게시."""
    date_str = target_date.isoformat()
    cached = cache.get_menu_cache(date_str)
    if cached is not None:
        return cached

    if _is_holiday(target_date):
        cache.save_menu_cache(date_str, "휴무")
        return "휴무"

    try:
        menu = crawler.get_menu_for_date(target_date)
    except Exception as e:
        notifier.notify_error(e, f"크롤링 오류 ({date_str})")
        return None

    if menu is None:
        return None

    cache.save_menu_cache(date_str, menu)
    return menu


def _get_base_url() -> str:
    base = os.getenv("BASE_URL", "")
    if not base:
        base = request.host_url.rstrip("/")
    return base


@app.route("/")
def index():
    d_param = request.args.get("d")
    if d_param:
        try:
            today = date.fromisoformat(d_param)
        except ValueError:
            today = today_kst()
    else:
        today = today_kst()
    date_str = today.isoformat()
    date_display = _format_date_ko(today)

    if _is_holiday(today):
        cache.save_menu_cache(date_str, "휴무")
        return render_template(
            "index.html",
            is_holiday=True,
            date_str=date_str,
            date_display=date_display,
            menu_items=[],
            base_url=_get_base_url(),
        )

    menu = _get_menu(today)

    if menu is None:
        return render_template(
            "index.html",
            is_holiday=False,
            is_not_available=True,
            date_str=date_str,
            date_display=date_display,
            menu_items=[],
            base_url=_get_base_url(),
        )

    if menu == "휴무":
        return render_template(
            "index.html",
            is_holiday=True,
            date_str=date_str,
            date_display=date_display,
            menu_items=[],
            base_url=_get_base_url(),
        )

    menu_preview = ", ".join(menu[:3]) + (f" 외 {len(menu) - 3}가지" if len(menu) > 3 else "")
    return render_template(
        "index.html",
        is_holiday=False,
        date_str=date_str,
        date_display=date_display,
        menu_items=menu,
        menu_preview=menu_preview,
        base_url=_get_base_url(),
    )


@app.route("/weekly")
def weekly():
    today = today_kst()
    # 이번 주 월요일 기준
    monday = today - timedelta(days=today.weekday())

    week_data = {}
    for i in range(5):
        d = monday + timedelta(days=i)
        date_str = d.isoformat()
        day_name = ["월", "화", "수", "목", "금"][i]

        if _is_holiday(d):
            week_data[day_name] = {"date": date_str, "menu": None, "is_holiday": True}
            continue

        menu = _get_menu(d)
        week_data[day_name] = {
            "date": date_str,
            "menu": menu if isinstance(menu, list) else None,
            "is_holiday": menu == "휴무",
        }

    return render_template(
        "weekly.html",
        week_data=week_data,
        today=today.isoformat(),
        base_url=_get_base_url(),
    )


@app.route("/og-image/<date_str>.png")
def og_image_endpoint(date_str: str):
    cached_path = cache.get_og_cache_path(date_str)
    if cached_path:
        return send_file(str(cached_path), mimetype="image/png")

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return Response("Invalid date", status=400)

    menu = _get_menu(target_date)

    if menu is None or menu == "휴무" or _is_holiday(target_date):
        png_bytes = og_image.generate_rest_image(target_date)
    else:
        png_bytes = og_image.generate_menu_image(target_date, menu)

    cache.save_og_cache(date_str, png_bytes)
    return Response(png_bytes, mimetype="image/png")


def _format_date_ko(d: date) -> str:
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return f"{d.year}년 {d.month}월 {d.day}일 ({weekdays[d.weekday()]})"


def _scheduled_cache_refresh():
    """매일 오전 10:50 오늘의 메뉴를 미리 크롤링해서 캐시에 저장."""
    today = today_kst()
    date_str = today.isoformat()

    if _is_holiday(today):
        logger.info(f"[스케줄러] {date_str} 휴무 — 크롤링 스킵")
        return

    # 이미 캐시 있으면 스킵
    if cache.get_menu_cache(date_str) is not None:
        logger.info(f"[스케줄러] {date_str} 캐시 이미 존재 — 스킵")
        return

    logger.info(f"[스케줄러] {date_str} 메뉴 크롤링 시작")
    try:
        menu = crawler.get_menu_for_date(today)
        if menu:
            cache.save_menu_cache(date_str, menu)
            # OG 이미지도 미리 생성
            png_bytes = og_image.generate_menu_image(today, menu)
            cache.save_og_cache(date_str, png_bytes)
            logger.info(f"[스케줄러] {date_str} 캐시 완료 ({len(menu)}개 메뉴)")
        else:
            logger.warning(f"[스케줄러] {date_str} 메뉴 없음 (미게시 또는 오류)")
    except Exception as e:
        notifier.notify_error(e, f"스케줄러 크롤링 오류 ({date_str})")


def _start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        _scheduled_cache_refresh,
        trigger="cron",
        hour=10,
        minute=50,
        id="daily_menu_refresh",
    )
    scheduler.start()
    logger.info("[스케줄러] 시작 — 매일 오전 10:50 자동 갱신")
    return scheduler


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5005"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    scheduler = _start_scheduler()
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        scheduler.shutdown()
