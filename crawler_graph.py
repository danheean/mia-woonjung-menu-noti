"""LangGraph 기반 크롤러: 테이블 vs 이미지 형식 자동 분기 처리."""
import json
import logging
import os
import re
from datetime import date, timedelta
from typing import TypedDict

import requests
from bs4 import BeautifulSoup
from langgraph.graph import END, StateGraph

from crawler import _get, _is_menu_item, _parse_header_date, _DAY_PATTERN

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
_DATE_STR_PATTERN = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")


class CrawlState(TypedDict):
    post_url: str
    ref_year: int
    session: object  # requests.Session (not serializable, kept in-process only)
    html: str | None
    has_table: bool
    image_urls: list[str]
    menu_dict: dict  # {date: [items]}
    is_valid: bool
    validation_errors: list[str]


# ---------------------------------------------------------------------------
# 노드 1: HTTP GET
# ---------------------------------------------------------------------------

def fetch_post(state: CrawlState) -> CrawlState:
    resp = _get(state["session"], state["post_url"])
    if resp:
        return {**state, "html": resp.text}
    logger.error(f"상세 페이지 요청 실패: {state['post_url']}")
    return {**state, "html": None}


# ---------------------------------------------------------------------------
# 노드 2: 포맷 감지 (테이블 or 이미지)
# ---------------------------------------------------------------------------

def detect_format(state: CrawlState) -> CrawlState:
    if not state["html"]:
        return {**state, "has_table": False, "image_urls": []}

    soup = BeautifulSoup(state["html"], "html.parser")
    container = soup.find(class_="artclView")
    if not container:
        logger.warning("artclView를 찾을 수 없습니다 (WAF 차단 또는 페이지 구조 변경 가능성).")
        return {**state, "has_table": False, "image_urls": []}

    tables = container.find_all("table")
    has_table = len(tables) > 0

    image_urls: list[str] = []
    if not has_table:
        for img in container.find_all("img", src=True):
            src = img["src"]
            # 메뉴 이미지로 추정: editorUpload 경로 포함 또는 일반 업로드 이미지
            if src.startswith("http"):
                image_urls.append(src)
            elif src.startswith("/"):
                image_urls.append("https://www.sungshin.ac.kr" + src)

    logger.info(f"포맷 감지: has_table={has_table}, images={len(image_urls)}")
    return {**state, "has_table": has_table, "image_urls": image_urls}


# ---------------------------------------------------------------------------
# 노드 3: 테이블 파싱 (기존 crawler.py 로직 재사용)
# ---------------------------------------------------------------------------

def parse_table(state: CrawlState) -> CrawlState:
    soup = BeautifulSoup(state["html"], "html.parser")
    container = soup.find(class_="artclView") or soup
    tables = container.find_all("table")
    ref_year = state["ref_year"]
    result: dict[date, list[str]] = {}

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        date_indices: dict[date, int] = {}
        header_row_idx = 0

        for r_idx, row in enumerate(rows[:3]):
            cells = row.find_all(["th", "td"])
            indices: dict[date, int] = {}
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                if _DAY_PATTERN.search(text):
                    d = _parse_header_date(text, ref_year)
                    if d:
                        indices[d] = i
            if len(indices) >= 3:
                date_indices = indices
                header_row_idx = r_idx
                break

        if not date_indices:
            continue

        for d in date_indices:
            result[d] = []

        for row in rows[header_row_idx + 1:]:
            cells = row.find_all(["td", "th"])
            for d, idx in date_indices.items():
                if idx < len(cells):
                    text = cells[idx].get_text(separator="\n", strip=True)
                    items = [line.strip() for line in text.splitlines() if _is_menu_item(line.strip())]
                    result[d].extend(items)

        if result:
            break

    if result:
        logger.info(f"테이블 파싱 성공: {sorted(result.keys())}")
    else:
        logger.warning("테이블 파싱 실패")

    return {**state, "menu_dict": result}


# ---------------------------------------------------------------------------
# 노드 4: 이미지 OCR (Gemini Vision)
# ---------------------------------------------------------------------------

def parse_image(state: CrawlState) -> CrawlState:
    from google import genai
    from google.genai import types as genai_types

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return {**state, "menu_dict": {}}

    client = genai.Client(api_key=api_key)

    ref_year = state["ref_year"]
    result: dict[date, list[str]] = {}

    prompt = (
        "이 이미지는 구내식당 주간 메뉴표입니다.\n"
        "날짜별(월~금) 메뉴를 JSON으로 추출해주세요.\n"
        '형식: {"3월 3일": ["메뉴1", "메뉴2"], ...}\n'
        "원산지(국내산, 수입산 등)와 가격은 제외, 음식명만 포함.\n"
        "JSON 외 다른 텍스트 없이 JSON만 반환해주세요."
    )

    for img_url in state["image_urls"]:
        logger.info(f"Gemini Vision 처리: {img_url}")
        try:
            img_resp = _get(state["session"], img_url)
            if not img_resp:
                continue

            content_type = img_resp.headers.get("Content-Type", "image/png").split(";")[0].strip()
            image_part = genai_types.Part.from_bytes(
                data=img_resp.content, mime_type=content_type
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, image_part],
            )
            raw = response.text.strip()

            # JSON 블록 추출
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            json_str = json_match.group(1) if json_match else raw
            # 중괄호로 감싸진 첫 번째 JSON 객체 추출 (fallback)
            if not json_match:
                brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group()

            parsed: dict = json.loads(json_str)

            for date_str, items in parsed.items():
                m = _DATE_STR_PATTERN.search(date_str)
                if not m:
                    continue
                month, day = int(m.group(1)), int(m.group(2))
                try:
                    d = date(ref_year, month, day)
                except ValueError:
                    continue
                clean_items = [str(item).strip() for item in items if _is_menu_item(str(item).strip())]
                if clean_items:
                    result[d] = clean_items

            if result:
                logger.info(f"이미지 OCR 성공: {sorted(result.keys())}")
                break

        except Exception as e:
            logger.error(f"Gemini Vision 처리 실패 ({img_url}): {e}")

    if not result:
        logger.warning("이미지 OCR 파싱 결과 없음")

    return {**state, "menu_dict": result}


# ---------------------------------------------------------------------------
# 노드 5: Validation
# ---------------------------------------------------------------------------

MIN_ITEMS_PER_DAY = 3
MAX_DATE_DELTA_DAYS = 14


def validate_menu(state: CrawlState) -> CrawlState:
    """파싱 결과와 post_url 접근 가능 여부를 검증."""
    errors: list[str] = []
    menu_dict: dict = state.get("menu_dict", {})
    today = date.today()

    # 1. post_url 접근 가능 여부 (HTTP 200)
    try:
        resp = _get(state["session"], state["post_url"])
        if not resp:
            errors.append(f"post_url 접근 실패: {state['post_url']}")
        else:
            logger.info(f"post_url 접근 확인: HTTP {resp.status_code} — {state['post_url']}")
    except Exception as e:
        errors.append(f"post_url 요청 오류: {e}")

    # 2. menu_dict 비어있지 않은지
    if not menu_dict:
        errors.append("menu_dict가 비어 있습니다 (파싱 실패)")
    else:
        for d, items in menu_dict.items():
            # 3. 날짜가 평일인지
            if d.weekday() >= 5:
                errors.append(f"{d}: 주말 날짜가 포함됨 (weekday={d.weekday()})")

            # 4. 오늘 기준 ±14일 이내인지
            if abs((d - today).days) > MAX_DATE_DELTA_DAYS:
                errors.append(f"{d}: 오늘({today})과 {MAX_DATE_DELTA_DAYS}일 이상 차이남")

            # 5. 메뉴 항목 수가 최소 기준 이상인지
            if len(items) < MIN_ITEMS_PER_DAY:
                errors.append(f"{d}: 메뉴 항목이 {len(items)}개로 너무 적음 (최소 {MIN_ITEMS_PER_DAY}개)")

    is_valid = len(errors) == 0
    if is_valid:
        logger.info(f"검증 통과: {len(menu_dict)}일치 메뉴, {sum(len(v) for v in menu_dict.values())}개 항목")
    else:
        for err in errors:
            logger.warning(f"검증 실패: {err}")

    return {**state, "is_valid": is_valid, "validation_errors": errors}


# ---------------------------------------------------------------------------
# 조건 엣지
# ---------------------------------------------------------------------------

def route_format(state: CrawlState) -> str:
    if not state.get("html"):
        return END
    if state["has_table"]:
        return "parse_table"
    if state["image_urls"]:
        return "parse_image"
    return END


# ---------------------------------------------------------------------------
# 그래프 빌드
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    g = StateGraph(CrawlState)
    g.add_node("fetch_post", fetch_post)
    g.add_node("detect_format", detect_format)
    g.add_node("parse_table", parse_table)
    g.add_node("parse_image", parse_image)
    g.add_node("validate_menu", validate_menu)

    g.set_entry_point("fetch_post")
    g.add_edge("fetch_post", "detect_format")
    g.add_conditional_edges("detect_format", route_format, {
        "parse_table": "parse_table",
        "parse_image": "parse_image",
        END: END,
    })
    g.add_edge("parse_table", "validate_menu")
    g.add_edge("parse_image", "validate_menu")
    g.add_edge("validate_menu", END)

    return g.compile()


_graph = _build_graph()


def run_crawl_graph(post_url: str, session: requests.Session, ref_year: int) -> dict[date, list[str]]:
    """LangGraph를 통해 게시물을 크롤링하고 날짜별 메뉴를 반환."""
    from crawler import HEADERS
    # WAF 차단 방지: 브라우저 UA가 아니면 강제 보완
    ua = session.headers.get("User-Agent", "")
    if not ua.startswith("Mozilla"):
        session.headers.update(HEADERS)

    initial_state: CrawlState = {
        "post_url": post_url,
        "ref_year": ref_year,
        "session": session,
        "html": None,
        "has_table": False,
        "image_urls": [],
        "menu_dict": {},
        "is_valid": False,
        "validation_errors": [],
    }
    final_state = _graph.invoke(initial_state)
    return final_state.get("menu_dict", {})
