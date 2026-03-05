import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup


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
            old_data = json.loads(f)["schedule"]
    except FileNotFoundError:
        old_data = await parse()


def save_old_data():
    with open(_old_data_path, "w") as f:
        json.dump({"schedule": old_data}, f, indent=4)


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
                feed = feed_tag.text.strip().replace("Прием заявок", "").strip()

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


async def parse_and_compare():
    ...


if __name__ == '__main__':
    async def main():
        result = await parse()
        print(json.dumps(result, indent=4, ensure_ascii=False))
    asyncio.run(main())
