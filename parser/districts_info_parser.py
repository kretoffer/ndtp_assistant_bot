import aiohttp
from bs4 import BeautifulSoup
import logging
import ssl
import certifi
import re

from aiogram import Bot
import parser

from notify_users import notify_about_directions
from tools.retry import retry as _retry

logger = logging.getLogger(__name__)

MAIN_PAGE_URL = "https://ndtp.by/educational_directions/"

async def fetch_page(url):
    """Fetches the HTML content of a given URL asynchronously."""
    try:
        async def _do():
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    logger.info(f"Successfully fetched: {url}")
                    return await response.text()
        return await _retry(_do, name=url)
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

async def parse_main_page(html_content):
    """Parses the main page to find links to educational direction sub-pages."""
    soup = BeautifulSoup(html_content, 'html.parser')
    sub_page_links = []

    educational_blocks = soup.find_all('div', class_=lambda c: isinstance(c, str) and 'educational' in c.split())

    for block in educational_blocks:
        link = block.find('a', class_='fusion-column-anchor')
        title_h1 = block.find('h1', class_='title-heading-left')

        if link and 'href' in link.attrs and title_h1:
            href = str(link['href'])
            if href.startswith(MAIN_PAGE_URL) and href != MAIN_PAGE_URL:
                sub_page_links.append({
                    "url": href,
                    "title": title_h1.get_text(strip=True)
                })
    return sub_page_links

async def parse_sub_page(html_content):
    """Parses an educational direction sub-page to extract details."""
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {"info": "", "programs": {}}

    containers = soup.find_all("div", class_=['fusion-text', 'fusion-text-no-margin'])
    texts = [el.get_text(strip=True, separator='\n') for el in containers]
    del texts[-9:]
    texts = [el.replace("\xa0", " ") for el in texts]
    filter_list = ("Авиационная и космическая отрасль",
                   "Архитектура и дизайн",
                   "Биотехнологии",
                   "Виртуальная и дополненная реальности",
                   "Зеленая химия",
                   "Инженерная экология",
                   "Информационная безопасность",
                   "Лазерные технологии",
                   "Машиностроение",
                   "Наноиндустрия",
                   "Природные ресурсы",
                   "Робототехника",
                   "Электроника",
                   "Энергетика будущего")
    if texts[0].startswith(filter_list):
        data["info"] = texts[0].replace("\n", " ")
        del texts[0]
    for title, text in enumerate(texts):
        if text.startswith(("Программы реализуются при содействии", "Кураторы программ")):
            continue
        t = re.findall(r'[«"“](.*?)[»"”]', text, re.DOTALL)
        if t:
            title = " ".join(str(t[0]).split())
        data["programs"][str(title)] = text

    return data

async def parse_educational_directions():
    """Orchestrates the parsing of all educational directions asynchronously."""
    all_directions_data = {}
    main_page_html = await fetch_page(MAIN_PAGE_URL)
    if not main_page_html:
        logger.error("Failed to fetch main page HTML.")
        return all_directions_data

    sub_page_infos = await parse_main_page(main_page_html)

    for info in sub_page_infos:
        direction_title, direction_data = await process_sub_page(info['url'], info['title'])
        if direction_title and direction_data:
            all_directions_data[direction_title] = direction_data
        else:
            logger.error("Failed to fetch sub-page: %s, aborting districts cycle", info['title'])
            return {}

    return all_directions_data


async def process_sub_page(url, title):
    """Fetches and parses a single sub-page."""
    logger.info(f"Processing sub-page: {url} (Title: {title})")
    sub_page_html = await fetch_page(url)
    if sub_page_html:
        direction_data = await parse_sub_page(sub_page_html)
        return title, direction_data
    return None, None


async def parse_and_compare_districts(bot: Bot):
    new_data = await parse_educational_directions()
    if not new_data:
        logger.warning("Districts parse returned empty, skipping comparison")
        return

    old_data = parser.get_districts_info()

    changes = compare(old_data, new_data)

    logger.info(f"Districts changes: {changes}")

    if changes:
        await notify_about_directions(bot, changes)
        parser.save_districts_info(new_data)


def compare(old_data: dict, new_data: dict):
    """
    Compares old and new educational directions data and identifies changes.
    It tracks new/removed directions and new/removed programs within directions.
    """
    if old_data == new_data:
        return None

    changes = {
        "added_directions": [],
        "removed_directions": [],
        "modified_directions": []
    }

    old_directions_keys = set(old_data.keys())
    new_directions_keys = set(new_data.keys())

    # Find added directions
    for direction_name in new_directions_keys - old_directions_keys:
        changes["added_directions"].append({
            "name": direction_name,
            "data": new_data[direction_name]
        })

    # Find removed directions
    for direction_name in old_directions_keys - new_directions_keys:
        changes["removed_directions"].append({
            "name": direction_name,
            "data": old_data[direction_name]
        })

    # Check for modified directions (changes in programs)
    for direction_name in old_directions_keys & new_directions_keys:
        old_direction = old_data.get(direction_name, {})
        new_direction = new_data.get(direction_name, {})
        modifications = {}

        old_programs = old_direction.get("programs", {})
        new_programs = new_direction.get("programs", {})

        old_program_keys = set(old_programs.keys())
        new_program_keys = set(new_programs.keys())

        added_programs = new_program_keys - old_program_keys
        removed_programs = old_program_keys - new_program_keys

        if added_programs:
            modifications["added_programs"] = {
                prog: new_programs[prog] for prog in added_programs
            }
        if removed_programs:
            modifications["removed_programs"] = {
                prog: old_programs[prog] for prog in removed_programs
            }

        if modifications:
            changes["modified_directions"].append({
                "name": direction_name,
                "changes": modifications
            })

    # Return None if no changes were found, filtering out empty lists
    final_changes = {k: v for k, v in changes.items() if v}
    if not final_changes:
        return None

    return final_changes
