import logging

logger = logging.getLogger(__name__)

_competition_cache: dict = {}


def _normalize(text: str) -> str:
    return text.lower().replace("\u0451", "\u0435")


def _match_direction(spiski_name: str, canonical_names: list[str]) -> str | None:
    n1 = _normalize(spiski_name).replace(" ", "")
    for c in canonical_names:
        n2 = _normalize(c).replace(" ", "")
        if n1 == n2 or n1.startswith(n2) or n2.startswith(n1):
            return c
    return None


_ALWAYS_10 = {
    _normalize("Машины и двигатели. Автомобилестроение"),
    _normalize("Архитектура и дизайн"),
}


def _get_places(direction: str, shift_name: str) -> int:
    if _normalize(direction) in _ALWAYS_10:
        return 10
    if "Октябрьская" in shift_name:
        return 8
    return 10


def _calculate_for_shift(shift_name: str, shifts: list, all_spiski: dict, all_dopusheni: dict, all_districts: dict) -> dict:
    if shift_name not in {s["name"] for s in shifts}:
        return {}

    dirs = all_districts.get(shift_name, {})
    num_dirs = len(dirs) if dirs else 15
    direction_names = sorted(dirs.keys())

    dop = all_dopusheni.get(shift_name, {})
    if not dop:
        return {}

    total = sum(len(p) for p in dop.values())
    other_shifts = [s["name"] for s in shifts if s["name"] != shift_name]

    known_counts = {d: 0 for d in direction_names}
    new_count = 0

    for region, persons in dop.items():
        for p in persons:
            p_surname = _normalize(p.get("surname", ""))
            p_name = _normalize(p.get("name", ""))
            if not p_surname or not p_name:
                new_count += 1
                continue

            found = False
            for other_shift in other_shifts:
                other_data = all_spiski.get(other_shift, {})
                if not other_data:
                    continue
                for dir_name, enrolled in other_data.items():
                    for ep in enrolled:
                        if (_normalize(ep.get("surname", "")) == p_surname
                                and _normalize(ep.get("name", "")) == p_name):
                            matched = _match_direction(dir_name, direction_names)
                            if matched:
                                known_counts[matched] += 1
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

            if not found:
                new_count += 1

    new_per_dir = new_count / num_dirs if num_dirs > 0 else 0

    total_places = sum(_get_places(d, shift_name) for d in direction_names)
    overall_comp = round(total / total_places, 1) if total_places > 0 else 0

    per_direction = {}
    for d in direction_names:
        estimated = known_counts[d] + new_per_dir
        places = _get_places(d, shift_name)
        comp = round(estimated / places, 1)
        per_direction[d] = comp

    return {
        "overall": overall_comp,
        "per_direction": per_direction,
        "new_count": new_count,
    }


def recalculate():
    global _competition_cache
    from parser import get_old_data, get_spiski, get_dopusheni, get_districts

    shifts = get_old_data()
    all_spiski = get_spiski(None) or {}
    all_dopusheni = get_dopusheni(None) or {}
    all_districts = get_districts(None) or {}

    _competition_cache = {}
    for s in shifts:
        name = s["name"]
        if name in all_dopusheni:
            result = _calculate_for_shift(name, shifts, all_spiski, all_dopusheni, all_districts)
            if result:
                _competition_cache[name] = result
                logger.info(
                    f"Competition for {name}: "
                    f"overall={result['overall']}, "
                    f"new={result['new_count']}"
                )

    logger.info(f"Competition cache recalculated for {len(_competition_cache)} shifts")


def get_competition(shift_name: str) -> dict | None:
    return _competition_cache.get(shift_name)


def get_competition_status(avg_competition: float, competition: float) -> str:
    if avg_competition * 0.83 >= competition:
        return "Очень низкий"
    if avg_competition * 0.97 >= competition:
        return "Низкий"
    if avg_competition * 1.03 >= competition:
        return "Средний"
    if avg_competition * 1.08 >= competition:
        return "Высокий"
    return "Очень высокий"
