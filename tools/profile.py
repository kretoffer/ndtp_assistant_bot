import html

from database import get_user_by_name
from parser import get_dopusheni, get_spiski
from parser.distance_parser import get_distance_students


def format_person_name(
    surname: str,
    name: str,
    patronymic: str = "",
    *,
    bold: bool = True,
    icon: str | None = "👤",
    user: dict | None = None,
) -> str:
    full_name = " ".join(filter(None, (surname, name, patronymic)))
    if user is None:
        user = get_user_by_name(name, surname)
    if user and user["username"]:
        if user["username"]:
            url = f'https://t.me/{html.escape(user["username"])}'
        else:
            url = f'tg://user?id={html.escape(str(user["id"]))}'
        name_part = f'<a href="{url}">{html.escape(full_name)}</a>'
    else:
        name_part = html.escape(full_name)
    if bold:
        name_part = f"<b>{name_part}</b>"
    if icon:
        name_part = f"{icon} {name_part}"
    return name_part


def format_distance_block(entries: list[dict]) -> str:
    lines = ["📡 <b>Дистанционная форма обучения</b>"]
    for i, e in enumerate(entries):
        if i > 0:
            lines.append("")
        lines.append(f"  📌 Направление: {html.escape(e['direction'])}")
        if e.get("project"):
            lines.append(f"  🔬 Проект: {html.escape(e['project'])}")
        if e.get("study_period"):
            lines.append(f"  📅 {html.escape(e['study_period'])}")
    return "\n".join(lines)


def _key(s: str) -> str:
    return s.lower().replace("ё", "е").strip()


def build_profile_text(surname: str, name: str, *, distance_entries: list[dict] | None = None) -> str:
    user = get_user_by_name(name, surname)
    lines = [format_person_name(surname, name, user=user)]

    sn_key = _key(surname)
    n_key = _key(name)

    education = None
    shifts = {}
    for list_type, source in (("dopusheni", get_dopusheni(None)), ("spiski", get_spiski(None))):
        if not source:
            continue
        for shift_name, regions in source.items():
            for region, persons in regions.items():
                for person in persons:
                    if _key(person.get("surname", "")) == sn_key and _key(person.get("name", "")) == n_key:
                        entry = shifts.setdefault(shift_name, {})
                        entry.setdefault(list_type, []).append(region)
                        if person.get("education"):
                            education = person["education"]

    if education:
        lines.append(f"🏫 {html.escape(education)}\n")

    for shift_name in shifts:
        shift_data = shifts[shift_name]
        dop = shift_data.get("dopusheni", [])
        spis = shift_data.get("spiski", [])
        lines.append(f"📌 <b>{html.escape(shift_name)}</b>")
        if dop:
            lines.append(f"  📋 Допущен: {', '.join(html.escape(r) for r in dop)}")
        if spis:
            lines.append(f"  👀 Прошёл: {', '.join(html.escape(r) for r in spis)}")

    dists = distance_entries
    if dists is None:
        dists = [s for s in get_distance_students() if _key(s.get("surname", "")) == sn_key and _key(s.get("name", "")) == n_key]
    if dists:
        if shifts:
            lines.append("")
        lines.append(format_distance_block(dists))

    return "\n".join(lines)
