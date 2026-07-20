import html

from database import get_user_by_name


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
