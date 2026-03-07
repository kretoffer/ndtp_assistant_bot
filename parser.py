import aiohttp
import json
from bs4 import BeautifulSoup
import io
import re
import pdfplumber
import logging
from aiogram import Bot
from typing import List

from notify_users import notify_all_users


_old_data_path = None
_districts_data_path = None
_dopusheni_data_path = None
_spiski_data_path = None
old_data = []
districts = {}
dopusheni = {}
spiski = {}

DOC_NAME = "Положение об образовательной смене"
SPISKI_DOPUSCHENNYH_START_WITH = "Списочный состав участников, допущенных ко второму этапу"
SPISKI_START_WITH = "Списочный состав групп учащихся, зачисленных"
FIRST_DISTRICT = "Авиакосмические технологии"


async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


async def init_parser(old_data_path: str, districts_data_path: str, dopusheni_data_path: str, spiski_data_path: str):
    global _old_data_path, _districts_data_path, _dopusheni_data_path, _spiski_data_path,\
            old_data, districts, dopusheni, spiski
    _old_data_path = old_data_path
    _districts_data_path = districts_data_path
    _dopusheni_data_path = dopusheni_data_path
    _spiski_data_path = spiski_data_path
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
        return changes

    return None


async def parse_and_compare(bot: Bot):
    global districts
    new_data = await parse()
    changes = compare(new_data)
    logging.info(f"Changes: {changes}")
    if changes:
        await notify_all_users(bot, changes)
        districts = await parse_all_districts()
        save_districts_data()


def get_old_data() -> list:
    return old_data


async def parse_district(url: str) -> dict:
    logging.info(f"Found URL: {url}")
    if not url:
        return {}

    async with aiohttp.ClientSession() as session:
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
                logging.error(f"Failed to parse PDF with pdfplumber: {e}")
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

            return districts


async def parse_all_districts() -> dict:
    _districts = {}
    for shift in old_data:
        if DOC_NAME in shift["docs"]:
            _districts[shift["name"]] = await parse_district(shift["docs"][DOC_NAME])
    return _districts


def get_districts(name: str | None = None):
    if name:
        return districts.get(name)
    return districts
