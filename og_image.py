import logging
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

IMG_WIDTH = 1200
IMG_HEIGHT = 630

FONT_PATH = Path("static/fonts/NanumGothic.ttf")
FONT_PATH_BOLD = Path("static/fonts/NanumGothicBold.ttf")

FALLBACK_FONT_DIRS = [
    Path("/usr/share/fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path("/usr/local/share/fonts"),
]

# 색상 팔레트
BG_COLOR_TOP = (255, 243, 224)     # 연한 주황
BG_COLOR_BOTTOM = (255, 224, 178)  # 베이지
ACCENT_COLOR = (230, 100, 30)      # 진한 주황
TEXT_DARK = (50, 30, 10)           # 진한 갈색
TEXT_LIGHT = (120, 80, 40)         # 연한 갈색
WHITE = (255, 255, 255)

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """폰트 로드 (fallback 포함)."""
    paths_to_try = []

    if bold and FONT_PATH_BOLD.exists():
        paths_to_try.append(FONT_PATH_BOLD)
    if FONT_PATH.exists():
        paths_to_try.append(FONT_PATH)

    # 시스템 폰트 fallback
    for font_dir in FALLBACK_FONT_DIRS:
        if font_dir.exists():
            for suffix in ["*.ttf", "**/*.ttf", "*.otf", "**/*.otf"]:
                for p in font_dir.glob(suffix):
                    name = p.name.lower()
                    if "nanum" in name or "gothic" in name or "malgun" in name:
                        paths_to_try.append(p)

    for path in paths_to_try:
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            continue

    logger.warning("한글 폰트를 찾을 수 없습니다. 기본 폰트 사용.")
    return ImageFont.load_default()


def _draw_gradient_background(draw: ImageDraw.Draw, width: int, height: int):
    """세로 그라데이션 배경 그리기."""
    for y in range(height):
        t = y / height
        r = int(BG_COLOR_TOP[0] * (1 - t) + BG_COLOR_BOTTOM[0] * t)
        g = int(BG_COLOR_TOP[1] * (1 - t) + BG_COLOR_BOTTOM[1] * t)
        b = int(BG_COLOR_TOP[2] * (1 - t) + BG_COLOR_BOTTOM[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _format_date(d: date) -> str:
    weekday = WEEKDAY_KO[d.weekday()]
    return f"{d.year}년 {d.month}월 {d.day}일 {weekday}요일"


def _image_to_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_menu_image(target_date: date, menu_items: list[str]) -> bytes:
    """날짜와 메뉴 목록을 담은 OG 이미지 생성."""
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT))
    draw = ImageDraw.Draw(img)

    _draw_gradient_background(draw, IMG_WIDTH, IMG_HEIGHT)

    # 상단 헤더 바
    draw.rectangle([(0, 0), (IMG_WIDTH, 80)], fill=ACCENT_COLOR)

    font_header = _load_font(32)
    font_date = _load_font(52, bold=True)
    font_menu = _load_font(40)
    font_item = _load_font(36)

    # 헤더 텍스트
    header_text = "🍱 운정교내식당"
    draw.text((50, 22), header_text, font=font_header, fill=WHITE)

    # 날짜
    date_text = _format_date(target_date)
    draw.text((50, 110), date_text, font=font_date, fill=TEXT_DARK)

    # 구분선
    draw.rectangle([(50, 185), (IMG_WIDTH - 50, 188)], fill=ACCENT_COLOR)

    # 메뉴 목록
    y = 210
    max_items = 8
    line_height = 50

    for item in menu_items[:max_items]:
        if y + line_height > IMG_HEIGHT - 40:
            break
        draw.text((70, y), f"• {item}", font=font_item, fill=TEXT_DARK)
        y += line_height

    if len(menu_items) > max_items:
        draw.text((70, y), f"  외 {len(menu_items) - max_items}가지", font=font_item, fill=TEXT_LIGHT)

    return _image_to_bytes(img)


def generate_rest_image(target_date: date) -> bytes:
    """휴무일 OG 이미지 생성."""
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT))
    draw = ImageDraw.Draw(img)

    _draw_gradient_background(draw, IMG_WIDTH, IMG_HEIGHT)

    # 상단 헤더 바
    draw.rectangle([(0, 0), (IMG_WIDTH, 80)], fill=ACCENT_COLOR)

    font_header = _load_font(32)
    font_date = _load_font(48, bold=True)
    font_msg = _load_font(64, bold=True)
    font_sub = _load_font(36)

    # 헤더
    draw.text((50, 22), "🍱 운정교내식당", font=font_header, fill=WHITE)

    # 날짜
    date_text = _format_date(target_date)
    draw.text((50, 110), date_text, font=font_date, fill=TEXT_DARK)

    # 구분선
    draw.rectangle([(50, 185), (IMG_WIDTH - 50, 188)], fill=ACCENT_COLOR)

    # 중앙 메시지
    msg = "오늘은 쉽니다 🍽️"
    bbox = draw.textbbox((0, 0), msg, font=font_msg)
    msg_w = bbox[2] - bbox[0]
    draw.text(((IMG_WIDTH - msg_w) // 2, 300), msg, font=font_msg, fill=TEXT_DARK)

    sub = "주말 또는 공휴일입니다"
    bbox2 = draw.textbbox((0, 0), sub, font=font_sub)
    sub_w = bbox2[2] - bbox2[0]
    draw.text(((IMG_WIDTH - sub_w) // 2, 400), sub, font=font_sub, fill=TEXT_LIGHT)

    return _image_to_bytes(img)
