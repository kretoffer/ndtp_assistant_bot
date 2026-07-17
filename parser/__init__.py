import aiohttp
import json
from bs4 import BeautifulSoup
import io
import re
import pdfplumber
import logging
from aiogram import Bot
from typing import List
import ssl
import certifi

from notify_users import notify_all_users
from parser.districts_info_parser import parse_educational_directions

logger = logging.getLogger(__name__)


_old_data_path = None
_districts_data_path = None
_dopusheni_data_path = None
_spiski_data_path = None
_districts_info_path = None
old_data = []
districts = {}
dopusheni = {}
spiski = {}
districts_info = {}

DOC_NAME = "Положение об образовательной смене"
SPISKI_DOPUSCHENNYH_START_WITH = "Списочный состав участников, допущенных ко второму этапу"
SPISKI_START_WITH = "Списочный состав групп учащихся, зачисленных"
FIRST_DISTRICT = "Авиакосмические технологии"


async def fetch(url):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))) as session:
        async with session.get(url) as response:
            return await response.text()


async def init_parser(old_data_path: str, districts_data_path: str, dopusheni_data_path: str, spiski_data_path: str,\
                      districts_info_path):
    global _old_data_path, _districts_data_path, _dopusheni_data_path, _spiski_data_path, _districts_info_path,\
            old_data, districts, dopusheni, spiski, districts_info
    _old_data_path = old_data_path
    _districts_data_path = districts_data_path
    _dopusheni_data_path = dopusheni_data_path
    _spiski_data_path = spiski_data_path
    _districts_info_path = districts_info_path
    try:
        with open(old_data_path, "r+", encoding="utf-8") as f:
            old_data = json.load(f)["schedule"]
    except FileNotFoundError:
        old_data = await parse()
        save_old_data()
    try:
        with open(districts_data_path, "r+", encoding="utf-8") as f:
            districts = json.load(f)
    except FileNotFoundError:
        districts = await parse_all_districts()
        save_districts_data()
    try:
        with open(dopusheni_data_path, "r+", encoding="utf-8") as f:
            dopusheni = json.load(f)
    except FileNotFoundError:
        dopusheni = await parse_all_spiski(SPISKI_DOPUSCHENNYH_START_WITH, False)
        save_dopusheni_data()
    try:
        with open(spiski_data_path, "r+", encoding="utf-8") as f:
            spiski = json.load(f)
    except FileNotFoundError:
        spiski = await parse_all_spiski(SPISKI_START_WITH, True)
        save_spiski_data()
    try:
        with open(_districts_info_path, "r+", encoding="utf-8") as f:
            districts_info = json.load(f)
    except FileNotFoundError:
        districts_info = await parse_educational_directions()
        save_districts_info()


def save_old_data():
    if not _old_data_path:
        raise FileExistsError("No old data path")
    with open(_old_data_path, "w", encoding="utf-8") as f:
        json.dump({"schedule": old_data}, f, indent=4, ensure_ascii=False)


def save_dopusheni_data():
    if not _dopusheni_data_path:
        raise FileExistsError("No data path")
    with open(_dopusheni_data_path, "w", encoding="utf-8") as f:
        json.dump(dopusheni, f, indent=4, ensure_ascii=False)


def save_spiski_data():
    if not _spiski_data_path:
        raise FileExistsError("No data path")
    with open(_spiski_data_path, "w", encoding="utf-8") as f:
        json.dump(spiski, f, indent=4, ensure_ascii=False)


def save_districts_data():
    if not _districts_data_path:
        raise FileExistsError("No data path")
    with open(_districts_data_path, "w", encoding="utf-8") as f:
        json.dump(districts, f, indent=4, ensure_ascii=False)


def save_districts_info(info: dict | None = None):
    global districts_info
    info = info if info else districts_info
    districts_info = info
    if not _districts_info_path:
        raise FileExistsError("No data path")
    with open(_districts_info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=4, ensure_ascii=False)


async def parse() -> list:
    data = await fetch("https://ndtp.by/schedule/")
    soup = BeautifulSoup(data, "lxml")

    schedule = []

    for panel in soup.find_all("div", class_="fusion-panel"):
        docs = {}
        panel_heading = panel.find("div", class_="panel-heading")
        if not panel_heading:
            continue
        columns = panel_heading.find_all(
            "div", class_=["fusion-layout-column", "fusion_builder_column_inner"]
        )

        name = ""
        date = ""

        if len(columns) > 0:
            name_tag = columns[0].find("h1")
            if name_tag:
                name = name_tag.text.strip()

        if len(columns) > 1:
            date_tag = columns[1].find("h1")
            if date_tag:
                date = date_tag.text.strip()
                year_match = re.search(r'\b(20\d{2})\b', date)
                if year_match:
                    year = year_match.group(1)
                    name = f"{year} {name}"

        feed = ""
        panel_body = panel.find("div", class_="panel-body")
        if panel_body:
            feed_tag = panel_body.find("p")
            if feed_tag and "Прием заявок" in feed_tag.text:
                feed = (
                    feed_tag.text.strip()
                    .replace("Прием заявок", "")
                    .strip()
                    .split("\n")[0]
                )

            for doc_link in panel_body.find_all("a"):
                doc_name = doc_link.text.strip()
                doc_href_raw = doc_link.get("href")
                if isinstance(doc_href_raw, list):
                    doc_href = doc_href_raw[0]
                else:
                    doc_href = doc_href_raw

                if doc_href and not doc_href.startswith("http"):
                    doc_href = "https://ndtp.by" + doc_href
                if doc_href:
                    docs[doc_name] = doc_href

        if name:
            schedule.append({"name": name, "date": date, "feed": feed, "docs": docs})

    return schedule


def compare(new_data: list):
    global old_data

    if old_data == new_data:
        return None

    changes = {"new_shifts": [], "removed_shifts": [], "modified_shifts": []}

    old_shifts_dict = {shift["name"]: shift for shift in old_data}
    new_shifts_dict = {shift["name"]: shift for shift in new_data}

    old_shift_names = set(old_shifts_dict.keys())
    new_shift_names = set(new_shifts_dict.keys())

    for name in new_shift_names - old_shift_names:
        changes["new_shifts"].append(new_shifts_dict[name])

    for name in old_shift_names - new_shift_names:
        changes["removed_shifts"].append(old_shifts_dict[name])

    new_spiski = []

    for name in old_shift_names & new_shift_names:
        old_shift = old_shifts_dict[name]
        new_shift = new_shifts_dict[name]
        modifications = {}

        if old_shift["date"] != new_shift["date"]:
            modifications["date"] = {"from": old_shift["date"], "to": new_shift["date"]}

        if old_shift["feed"] != new_shift["feed"]:
            modifications["feed"] = {"from": old_shift["feed"], "to": new_shift["feed"]}

        old_docs = set(old_shift["docs"].keys())
        new_docs = set(new_shift["docs"].keys())

        added_docs = new_docs - old_docs
        removed_docs = old_docs - new_docs

        for doc in added_docs:
            if doc.startswith(SPISKI_DOPUSCHENNYH_START_WITH) or doc.startswith(SPISKI_START_WITH):
                new_spiski.append({
                    "shift": name,
                    "doc": doc,
                    "link": new_shift["docs"][doc],
                    "is_spiski": doc.startswith(SPISKI_START_WITH)
                })

        if added_docs:
            modifications["added_docs"] = {
                doc: new_shift["docs"][doc] for doc in added_docs
            }

        if removed_docs:
            modifications["removed_docs"] = {
                doc: old_shift["docs"][doc] for doc in removed_docs
            }

        doc_url_changes = {}
        for doc_name in old_docs & new_docs:
            if old_shift["docs"][doc_name] != new_shift["docs"][doc_name]:
                doc_url_changes[doc_name] = {
                    "from": old_shift["docs"][doc_name],
                    "to": new_shift["docs"][doc_name],
                }
        if doc_url_changes:
            modifications["doc_url_changes"] = doc_url_changes

        if modifications:
            changes["modified_shifts"].append({"name": name, "changes": modifications})

    if any(changes.values()):
        old_data = new_data
        save_old_data()
        return changes, new_spiski

    return None


async def parse_and_compare(bot: Bot):
    global districts
    new_data = await parse()
    changes = compare(new_data)
    logger.info(f"Changes: {changes}")
    if changes:
        await notify_all_users(bot, *changes)
        districts = await parse_all_districts()
        save_districts_data()


async def parse_district(url: str) -> dict:
    logger.info(f"Found URL: {url}")
    if not url:
        return {}

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))) as session:
        async with session.get(url) as response:
            if response.status != 200:
                return {}
            pdf_raw = await response.read()
            pdf_file = io.BytesIO(pdf_raw)
            text = ""
            try:
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text(x_tolerance=2)
                        if page_text:
                            text += page_text + "\n"
            except Exception as e:
                logger.error(f"Failed to parse PDF with pdfplumber: {e}")
                return {}

            # Clean up text by splitting on any whitespace and rejoining with single spaces.
            text = " ".join(text.split())

            # Insert space between a closing parenthesis and a capital letter,
            # to separate concatenated items.
            text = re.sub(r"\)(?=[А-Я])", ") ", text)

            regex = r"([0-9\.]*\s*[А-Яа-я][^()]*?)\s*\((направление\s*–\s*[^)]+)\)"

            matches = re.findall(regex, text)

            districts_str: List[str] = []
            for match in matches:
                name = match[0].strip()
                name = re.sub(r"^[0-9\.\s]+", "", name)
                direction = match[1].strip()
                districts_str.append(f"{name} ({direction})")

            districts = {}
            for el in districts_str:
                dist = re.split(r"\s*\(\s*направление\s*–\s*", el.replace(")", ""))
                if len(dist) > 1:
                    districts[dist[1].strip()] = dist[0].strip()

            if FIRST_DISTRICT in districts and districts[FIRST_DISTRICT].count(": ") >= 2:
                districts[FIRST_DISTRICT] = districts[FIRST_DISTRICT].split(": ")[2]
            if FIRST_DISTRICT in districts and districts[FIRST_DISTRICT].startswith("1 "):
                districts[FIRST_DISTRICT] = districts[FIRST_DISTRICT][2:]

            return districts


async def parse_all_districts() -> dict:
    _districts = {}
    for shift in old_data:
        if DOC_NAME in shift["docs"]:
            _districts[shift["name"]] = await parse_district(shift["docs"][DOC_NAME])
    return _districts


def get_user(fio, school_and_class, is_spiski = False):
    try:
        fio_parts = fio.split()

        school_parts = school_and_class.split(',\n')

        education = None
        grade = None
        district = None
        if not is_spiski:
            education = school_parts[0].strip().replace("\n", " ")
            grade = school_parts[1].strip() if len(school_parts) > 1 else None
        else:
            district = school_parts[0].strip().replace("\n", " ")
            education = school_parts[1].strip().replace("\n", " ") if len(school_parts) > 1 else None
            grade = school_parts[2].strip() if len(school_parts) > 2 else None

        surname = fio_parts[0] if len(fio_parts) > 0 else ''
        name = fio_parts[1] if len(fio_parts) > 1 else ''
        patronymic = ' '.join(fio_parts[2:]) if len(fio_parts) > 2 else ''

        user = {
            "surname": surname,
            "name": name,
            "patronymic": patronymic,
            "education": education,
            "class": grade
        }
        if district:
            user["district"] = district
        return user
    except Exception as e:
        logger.error(f"Could not parse row: {fio} {school_and_class}, error: {e}")


async def parse_spisok(url: str, is_spisok = False) -> dict:
    dopusheni_data = {}

    logger.info(f"Parsing dopusheni from {url}")
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(
                        f"Failed to fetch {url}, status: {response.status}"
                    )
                    return {}
                pdf_raw = await response.read()

        pdf_file = io.BytesIO(pdf_raw)
        with pdfplumber.open(pdf_file) as pdf:
            data = []
            for page in pdf.pages:
                tables = page.find_tables()
                for table in tables:
                    _data = table.extract()
                    if _data:
                        data.extend(_data)
            region = None
            peoples = []
            for row in data:
                if len(row) >= 3 and row[0] and not re.match(r'^\d+\.\s*$', str(row[0])) and all([not bool(row[i]) for i in range(1, len(row))]):
                    if region:
                        dopusheni_data[region] = peoples
                    peoples = []
                    region = row[0]
                    if region.startswith("Образовательное направление"):
                        region = region .split("«")[1].rsplit("»")[0].replace("\n", " ")
                elif len(row) == 3 and (row[0].startswith("№") or row[1] == "ФИО" or row[2] == "Учреждение образования, класс"): # pyright: ignore[reportOptionalMemberAccess]
                    continue
                elif len(row) >= 3 and not row[0] and not row[1] and peoples:
                    valid_row = [el for el in row if el]
                    if len(valid_row) == 2:
                        people = peoples[-1]
                        fio = " ".join((people["surname"], people["name"], people["patronymic"], valid_row[0])) # pyright: ignore[reportOptionalSubscript]
                        school = people["education"] # pyright: ignore[reportOptionalSubscript]
                        school = school if school else ""
                        if people["class"]: # pyright: ignore[reportOptionalSubscript]
                            school += f",\n{people['class']}" # pyright: ignore[reportOptionalSubscript]
                        for number in range(9, 12):
                            if valid_row[1].startswith(str(number)) and valid_row[1].endswith("класс"):
                                school+=",\n"
                        school+=valid_row[1]
                        peoples[-1] = get_user(fio, school, is_spisok)
                elif len(row) >= 3:
                    new_row = [el for el in row if el]
                    valid_row = []
                    if len(new_row) > 3:
                        for el in new_row:
                            valid = True
                            for elem in valid_row:
                                if elem.startswith(el):
                                    valid = False
                            if valid:
                                valid_row.append(el)
                    else:
                        valid_row = new_row
                    if new_row and new_row[0].startswith("Образовательное направление"):
                        if region:
                            dopusheni_data[region] = peoples
                        peoples = []
                        region = new_row[1]
                        continue
                    if len(valid_row) >= 2 and valid_row[1] == "ФИО":
                        continue
                    if len(valid_row) == 3:
                        peoples.append(get_user(valid_row[1], valid_row[2], is_spisok))
                    elif len(valid_row) == 2:
                        peoples.append(get_user(valid_row[0], valid_row[1], is_spisok))
                    elif len(valid_row) == 1 and not row[0] and peoples:
                        people = peoples[-1]
                        fio = " ".join((people["surname"], people["name"], people["patronymic"])) # pyright: ignore[reportOptionalSubscript]
                        school = people["education"] # pyright: ignore[reportOptionalSubscript]
                        if people["class"]: # pyright: ignore[reportOptionalSubscript]
                            school += f",\n{people['class']}" # pyright: ignore[reportOptionalSubscript]
                        for number in range(9, 12):
                            if valid_row[0].startswith(str(number)) and valid_row[0].endswith("класс"):
                                school+=",\n"
                        school+=valid_row[0]
                        peoples[-1] = get_user(fio, school, is_spisok)
                    else:
                        logger.warning(f"Unprocessed row: {row}")
                else:
                    logger.warning(f"Unprocessed row: {row}")
            if region and peoples:
                dopusheni_data[region] = peoples

    except Exception as e:
        logger.error(f"Error processing {url}: {e}", exc_info=True)

    return dopusheni_data


async def parse_all_spiski(start_with: str, is_spiski = False):
    new_dopusheni = {}
    for shift in old_data:
        for doc_name, url in shift["docs"].items():
            if doc_name.startswith(start_with):
                new_dopusheni[shift["name"]] = await parse_spisok(url, is_spiski)
    return new_dopusheni


async def parse_new_spisok(url: str, shift_name: str, is_spiski = False):
    spisok = spiski if is_spiski else dopusheni
    spisok[shift_name] = await parse_spisok(url, is_spiski)
    save_dopusheni_data()
    save_spiski_data()
    return spisok[shift_name]


def get_old_data() -> list:
    return old_data


def get_districts(name: str | None = None):
    if name:
        return districts.get(name)
    return districts


def get_dopusheni(name: str | None = None):
    if name:
        return dopusheni.get(name)
    return dopusheni


def get_spiski(name: str | None = None):
    if name:
        return spiski.get(name)
    return spiski


def get_districts_info(name: str | None = None):
    if name:
        return districts_info.get(name) # pyright: ignore[reportOptionalMemberAccess]
    return districts_info
