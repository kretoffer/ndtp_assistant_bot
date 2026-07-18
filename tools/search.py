from typing import Literal

from database import get_user_by_name
from parser import get_dopusheni, get_spiski


ListType = Literal["all", "dopusheni", "spiski"]


def search_persons(
    query: str,
    shift_name: str | None = None,
    lists: ListType = "all",
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[dict], int]:
    query = query.lower().strip()
    if not query:
        return [], 0

    results = []

    def _search_in(data, list_type, sname):
        if not data:
            return
        for region, persons in data.items():
            for person in persons:
                if (
                    query in (person.get("surname") or "").lower()
                    or query in (person.get("name") or "").lower()
                    or query in (person.get("patronymic") or "").lower()
                    or query in (person.get("education") or "").lower()
                ):
                    results.append({
                        "shift_name": sname,
                        "region": region,
                        "list_type": list_type,
                        "person": person,
                    })

    if lists in ("all", "dopusheni"):
        data = get_dopusheni(shift_name)
        if data:
            if shift_name is None:
                for sname, sdata in data.items():
                    _search_in(sdata, "dopusheni", sname)
            else:
                _search_in(data, "dopusheni", shift_name)

    if lists in ("all", "spiski"):
        data = get_spiski(shift_name)
        if data:
            if shift_name is None:
                for sname, sdata in data.items():
                    _search_in(sdata, "spiski", sname)
            else:
                _search_in(data, "spiski", shift_name)

    total = len(results)
    if limit is not None:
        results = results[offset:offset + limit]

    return results, total


def get_person_profile(surname: str, name: str) -> dict | None:
    profile: dict = {
        "surname": surname,
        "name": name,
        "shifts": {},
    }

    user = get_user_by_name(name, surname)
    if user:
        profile["user"] = dict(user)

    for list_type, source in (("dopusheni", get_dopusheni(None)), ("spiski", get_spiski(None))):
        if not source:
            continue
        for shift_name, regions in source.items():
            for region, persons in regions.items():
                for person in persons:
                    if person.get("surname") == surname and person.get("name") == name:
                        entry = profile["shifts"].setdefault(shift_name, {})
                        entry.setdefault(list_type, []).append(region)
                        profile["patronymic"] = person.get("patronymic") or ""
                        if person.get("education"):
                            profile["education"] = person["education"]

    return profile if profile["shifts"] else None
