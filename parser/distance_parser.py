import aiohttp
import json
import logging
import re
import ssl
import certifi

from typing import Any
from docx import Document
import io

from tools.retry import retry as _retry

logger = logging.getLogger(__name__)

DISTANCE_PAGE_URL = "https://ndtp.by/distance-learning/"

_dists_data: list[dict[str, Any]] = []
_dists_data_path: str | None = None


def _split_full_name(full_name: str) -> tuple[str, str, str]:
    parts = full_name.split()
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], ""
    if len(parts) == 1:
        parts = re.findall(r"[А-ЯЁ][а-яё]+", parts[0])
        if len(parts) >= 3:
            return parts[0], parts[1], " ".join(parts[2:])
        if len(parts) == 2:
            return parts[0], parts[1], ""
        return parts[0] if parts else full_name, "", ""
    return "", "", ""


def _normalize_name(name: str) -> str:
    name = name.strip().lstrip("«").rstrip("»").strip()
    if name.endswith(")"):
        name = name.rstrip(")")
    name = name.replace("ё", "е").replace("Ё", "Е")
    name = re.sub(r"(?<=[а-я])-(?=[а-я])", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name[0].upper() + name[1:] if name else name
    name = name.replace(". автомобилестроение", ". Автомобилестроение")
    return name


def _extract_project(rest: str) -> str:
    rest = rest.strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1]
    return rest


def _parse_direction_field(raw: str) -> tuple[str, str]:
    raw = raw.strip().replace("\n", " ")
    raw = re.sub(r"\s+", " ", raw)
    if not raw.startswith("«"):
        raw = "«" + raw
    first_close = raw.find("»")
    if first_close != -1:
        candidate = raw[1:first_close]
        idx = candidate.find("(«")
        if idx != -1:
            direction = _normalize_name(candidate[:idx])
            rest = candidate[idx:]
            project_match = re.search(r"«([^»]*)»?\)?", rest)
            project = _normalize_name(project_match.group(1)) if project_match else ""
        else:
            direction = _normalize_name(candidate)
            rest = raw[first_close + 1:].strip()
            project = _normalize_name(_extract_project(rest)) if rest else ""
        if project == direction:
            project = ""
        return direction, project
    return _normalize_name(raw.lstrip("«")), ""


async def fetch_page(url: str) -> str | None:
    async def _do():
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.text()
    try:
        return await _retry(_do, name=url)
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


async def fetch_docx_url() -> str | None:
    html = await fetch_page(DISTANCE_PAGE_URL)
    if not html:
        return None
    m = re.search(r'href="([^"]+\.docx)"', html)
    if not m:
        logger.error("No .docx link found on distance-learning page")
        return None
    url = m.group(1)
    if not url.startswith("http"):
        url = "https://ndtp.by" + url
    return url


async def parse_distance_docx(url: str) -> list[dict[str, Any]]:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"Failed to download docx: {response.status}")
                return []
            content = await response.read()

    doc = Document(io.BytesIO(content))
    result = []
    for table in doc.tables:
        for ri, row in enumerate(table.rows):
            if ri == 0:
                continue
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) < 6:
                continue
            full_name = cells[2].replace("\n", " ").replace("\xa0", " ").strip()
            full_name = re.sub(r"\s+", " ", full_name)
            surname, name, patronymic = _split_full_name(full_name)
            direction, project = _parse_direction_field(cells[1])
            try:
                number = int(cells[0].replace("\xa0", ""))
            except (ValueError, TypeError):
                number = ri
            region_raw = cells[3].replace("\xa0", " ").replace("\n", " ").strip()
            school_raw = cells[4].replace("\xa0", " ").replace("\n", " ").strip()
            if re.match(r"^(ГУО|УО|ГУ)\s*[«\"'(]", region_raw) and not re.match(r"^(ГУО|УО|ГУ)\s*[«\"'(]", school_raw):
                region_raw, school_raw = school_raw, region_raw
            result.append({
                "number": number,
                "direction": direction,
                "project": project,
                "full_name": full_name,
                "surname": surname,
                "name": name,
                "patronymic": patronymic,
                "region": region_raw,
                "school": school_raw,
                "study_period": cells[5].replace("\xa0", " ").replace("\n", " ").strip(),
            })
    return result


def save_dists_data(data: list[dict[str, Any]]):
    global _dists_data
    _dists_data = data
    if not _dists_data_path:
        return
    with open(_dists_data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Saved {len(data)} distance students to {_dists_data_path}")


def load_dists_data() -> list[dict[str, Any]]:
    global _dists_data
    if _dists_data_path:
        try:
            with open(_dists_data_path, "r", encoding="utf-8") as f:
                _dists_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _dists_data = []
    return _dists_data


def get_distance_students() -> list[dict[str, Any]]:
    return _dists_data


async def parse_and_save_distance():
    url = await fetch_docx_url()
    if not url:
        logger.warning("Could not fetch docx URL, skipping distance parse")
        return
    data = await parse_distance_docx(url)
    if data:
        save_dists_data(data)
        logger.info(f"Parsed {len(data)} distance students")
    else:
        logger.warning("Parsed 0 distance students")


def init_distance_parser(data_path: str):
    global _dists_data_path
    _dists_data_path = data_path
    load_dists_data()
