import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup
import logging
from aiogram import Bot

from notify_users import notify_all_users


_old_data_path = None
old_data = []


async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


async def init_parser(old_data_path: str):
    global _old_data_path, old_data
    _old_data_path = old_data_path
    try:
        with open(old_data_path, "r+", encoding="utf-8") as f:
            old_data = json.load(f)["schedule"]
    except FileNotFoundError:
        old_data = await parse()
        save_old_data()


def save_old_data():
    with open(_old_data_path, "w", encoding="utf-8") as f:
        json.dump({"schedule": old_data}, f, indent=4, ensure_ascii=False)


async def parse() -> list:
    data = await fetch("https://ndtp.by/schedule/")
    soup = BeautifulSoup(data, "lxml")

    schedule = []
    
    for panel in soup.find_all("div", class_="fusion-panel"):
        panel_heading = panel.find("div", class_="panel-heading")
        columns = panel_heading.find_all("div", class_=["fusion-layout-column", "fusion_builder_column_inner"])
        
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
                feed = feed_tag.text.strip().replace("Прием заявок", "").strip().split("\n")[0]

            docs = {}
            for doc_link in panel_body.find_all("a"):
                doc_name = doc_link.text.strip()
                doc_href = doc_link["href"]
                if not doc_href.startswith("http"):
                    doc_href = "https://ndtp.by" + doc_href
                docs[doc_name] = doc_href
        
        if name:
            schedule.append({
                "name": name,
                "date": date,
                "feed": feed,
                "docs": docs
            })
    
    return schedule


def compare(new_data: list):
    global old_data

    if old_data == new_data:
        return None

    changes = {
        "new_shifts": [],
        "removed_shifts": [],
        "modified_shifts": []
    }

    old_shifts_dict = {shift['name']: shift for shift in old_data}
    new_shifts_dict = {shift['name']: shift for shift in new_data}

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
            modifications["added_docs"] = {doc: new_shift["docs"][doc] for doc in added_docs}

        if removed_docs:
            modifications["removed_docs"] = {doc: old_shift["docs"][doc] for doc in removed_docs}

        doc_url_changes = {}
        for doc_name in old_docs & new_docs:
            if old_shift["docs"][doc_name] != new_shift["docs"][doc_name]:
                doc_url_changes[doc_name] = {
                    "from": old_shift["docs"][doc_name],
                    "to": new_shift["docs"][doc_name]
                }
        if doc_url_changes:
            modifications["doc_url_changes"] = doc_url_changes

        if modifications:
            changes["modified_shifts"].append({
                "name": name,
                "changes": modifications
            })

    if any(changes.values()):
        old_data = new_data
        save_old_data()
        return changes

    return None

async def parse_and_compare(bot: Bot):
    new_data = await parse()
    changes = compare(new_data)
    logging.info(f"Changes: {changes}")
    if changes:
        await notify_all_users(bot, changes)


if __name__ == '__main__':
    async def main():
        result = await parse()
        print(json.dumps(result, indent=4, ensure_ascii=False))
    asyncio.run(main())
