"""Поля секции output в 23 конфигах примеров: title, steady_state, n_profiles, closed_form_overlays (FEAT-030, шаг 4).

Значения — ровно то, что сейчас передают в run_example файлы main.py
(сняты при планировании 2026-10-13 на 3f3df63):
  title               — аргумент title / TITLE каждого main.py;
  steady_state        — false у 13b, 14, 16, 17, 18, 19, 20, 21 (флаг
                        steady_state=False), true у остальных 15: до FEAT-030
                        умолчание run_example было true, после — false
                        (решение пользователя 2026-10-13), поэтому true
                        пишется явно;
  n_profiles          — только где задан: 13a, 14, 15, 18 — 6; 13b, 16, 17 — 7;
  closed_form_overlays — только где main.py отключал наложения: 13a —
                        ["p"] (было overlays={"Sg": None}), 15 — [] (было
                        overlays={"p": None, "Sg": None}).

Правка текстовая: строка "log_level": "INFO" секции output дополняется
новыми полями, остальной файл (порядок ключей, числа, переводы строк CRLF)
не меняется. Проверка: json.loads нового текста = старый словарь + новые
ключи output, и ничего больше.

Запуск из numerical_solver:
    .venv\\Scripts\\python <путь>\\add_output_fields.py            # проверка без записи
    .venv\\Scripts\\python <путь>\\add_output_fields.py --write    # запись
"""

import argparse
import json
from pathlib import Path

EXAMPLES = Path.cwd() / "examples"

# (title, steady_state, n_profiles | None, closed_form_overlays | None)
VALUES = {
    "01_single_phase_no_jt": ("01: однофазная несжимаемая фильтрация без JT", True, None, None),
    "02_single_phase_jt": ("02: однофазная фильтрация с JT", True, None, None),
    "03_standing_corey": ("03: Standing + Corey", True, None, None),
    "04_table_table": ("04: Table PVT + Table ОФП", True, None, None),
    "04a_high_gas_saturation": ("04a: высокая газонасыщенность (Table PVT + Corey ОФП)", True, None, None),
    "05_standing_table_rp": ("05: Standing PVT + Table ОФП", True, None, None),
    "06_table_corey_rp": ("06: Table PVT + Corey ОФП", True, None, None),
    "07_degassing_adiabatic_only": ("07: только адиабатика", True, None, None),
    "08_degassing_jt": ("08: адиабатика + JT", True, None, None),
    "09_degassing_latent_heat": ("09: адиабатика + скрытая теплота", True, None, None),
    "10_deep_degassing": ("10: глубокое разгазирование", True, None, None),
    "11_degassing_at_boundary": ("11: разгазирование у контура", True, None, None),
    "12_large_drainage_radius": ("12: большая область дренирования", True, None, None),
    "13a_pwf_ramp_down": ("13a: ступенчатое снижение забойного давления", True, 6, ["p"]),
    "13b_pwf_alternating": ("13b: чередование забойного давления 6 ↔ 10.75 МПа", False, 7, None),
    "14_high_gor_cooling": ("14: высокий газовый фактор — охлаждение забоя", False, 6, None),
    "15_oil_rate_ramp_up": ("15: пуск скважины с линейно растущим дебитом нефти", True, 6, []),
    "16_well_shut_in": ("16: останов скважины после 15 сут добычи", False, 7, None),
    "17_shut_in_strong_cooling": ("17: останов после сильного охлаждения забоя", False, 7, None),
    "18_prototype_input": ("18: вход прототипа (INPUT_TEMPLATE.xlsx)", False, 6, None),
    "19_rs150_cooling": ("19: R_s0 = 150, горячий пласт — охлаждение забоя", False, None, None),
    "20_rs300_cooling": ("20: R_s0 = 300 — охлаждение забоя", False, None, None),
    "21_rs100_cooling": ("21: R_s0 = 100, горячий пласт — охлаждение забоя", False, None, None),
}

ANCHOR = '"log_level": "INFO"'


def new_fields(title, steady, n_profiles, overlays) -> dict:
    """Новые ключи output в порядке записи."""
    out = {"title": title, "steady_state": steady}
    if n_profiles is not None:
        out["n_profiles"] = n_profiles
    if overlays is not None:
        out["closed_form_overlays"] = overlays
    return out


def patched(text: str, fields: dict) -> str:
    """Текст конфига с новыми полями после log_level; перевод строки — как в файле."""
    nl = "\r\n" if "\r\n" in text else "\n"
    assert text.count(ANCHOR) == 1, "log_level не найден или не один"
    lines = [f'    "{k}": {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()]
    return text.replace(ANCHOR, ANCHOR + "," + nl + ("," + nl).join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    bad = 0
    on_disk = sorted(d.name for d in EXAMPLES.iterdir()
                     if d.is_dir() and (d / "config.json").is_file())
    if on_disk != sorted(VALUES):
        print(f"ОШИБКА: папки примеров {on_disk} != таблица {sorted(VALUES)}")
        return 1
    for name, vals in VALUES.items():
        path = EXAMPLES / name / "config.json"
        # newline="" — переводы строк CRLF читаются и пишутся как есть
        # (Path.read_text перевёл бы их в \n, и запись сменила бы окончания строк)
        with open(path, encoding="utf-8", newline="") as f:
            old = f.read()
        old_raw = json.loads(old)
        if set(new_fields(*vals)) & set(old_raw.get("output", {})):
            print(f"{name}: поля уже есть — пропуск")
            continue
        new = patched(old, new_fields(*vals))
        expect = json.loads(old)
        expect["output"].update(new_fields(*vals))
        ok = json.loads(new) == expect
        bad += not ok
        print(f"{name}: {'ОК' if ok else 'ОШИБКА'} {new_fields(*vals)}")
        if args.write and ok:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
    print(f"итог: {'ОК' if not bad else f'ошибок {bad}'}; "
          f"{'записано' if args.write else 'без записи'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
