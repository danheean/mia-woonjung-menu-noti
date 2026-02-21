"""NanumGothic 폰트를 다운로드하여 static/fonts/ 에 저장합니다."""

import sys
from pathlib import Path

FONTS_DIR = Path(__file__).parent.parent / "static" / "fonts"

FONT_URLS = {
    "NanumGothic.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    ),
    "NanumGothicBold.ttf": (
        "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
    ),
}


def download_fonts():
    try:
        import requests
    except ImportError:
        print("requests 패키지가 필요합니다: uv add requests")
        sys.exit(1)

    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    for filename, url in FONT_URLS.items():
        dest = FONTS_DIR / filename
        if dest.exists():
            print(f"이미 존재: {dest}")
            continue

        print(f"다운로드 중: {filename} ...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            print(f"저장 완료: {dest} ({len(resp.content) // 1024}KB)")
        except Exception as e:
            print(f"실패: {filename}: {e}")
            sys.exit(1)

    print("\n폰트 다운로드 완료!")


if __name__ == "__main__":
    download_fonts()
