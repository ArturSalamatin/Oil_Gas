"""DEBT-008: поправить README примеров, где упомянуты удалённые и мёртвые поля конфига.

Запуск из numerical_solver/ (основной каталог или worktree):
    .venv\\Scripts\\python ..\\vault\\issues\\debt-008\\probes\\fix_readmes.py          # проверка
    .venv\\Scripts\\python ..\\vault\\issues\\debt-008\\probes\\fix_readmes.py --write  # запись

Каждая замена ищется точно; в каждом файле группы — ровно одно вхождение, иначе
отказ без записи. После замен ни в одном README не должно остаться упоминаний
dt_min, dt_max, start_day, output.format, p_ref, «не читаются».
"""
import sys
from pathlib import Path

NEW_GRID = ("`grid.type` не трогать: решатель знает только `\"log_radial\"`, иное\n"
            "значение отвергается при загрузке конфига.")

REPLACEMENTS = [
    # 01
    (["01_single_phase_no_jt"],
     "`grid.type` и `output.format` не трогать: поля объявлены в `io/config.py`,\n"
     "но нигде не читаются.",
     NEW_GRID),
    # 02–04
    (["02_single_phase_jt", "03_standing_corey", "04_table_table"],
     "`grid.type` и `output.format` не трогать: объявлены в `io/config.py`,\n"
     "но не читаются.",
     NEW_GRID),
    # 05–10: раздел «Не трогать»
    (["05_standing_table_rp", "06_table_corey_rp", "07_degassing_adiabatic_only",
      "08_degassing_jt", "09_degassing_latent_heat", "10_deep_degassing"],
     "`grid.type` и `output.format` — объявлены в `io/config.py`, но не читаются.",
     "`grid.type` — только `\"log_radial\"`: иное значение отвергается при загрузке конфига."),
    # 13b
    (["13b_pwf_alternating"],
     "расчёта задаёт только `time.dt_integration`: поля `numerics.dt_min` и\n"
     "  `numerics.dt_max` решателем не читаются.",
     "расчёта задаёт только `time.dt_integration`."),
    # 14
    (["14_high_gor_cooling"],
     "задаёт только `time.dt_integration`; поля\n"
     "  `numerics.dt_min` и `dt_max` решателем не читаются.",
     "задаёт только `time.dt_integration`."),
    # 16, 17
    (["16_well_shut_in", "17_shut_in_strong_cooling"],
     " Поля\n"
     "  `numerics.dt_min`, `numerics.dt_max` и `time.start_day` решателем не\n"
     "  читаются.",
     ""),
    # 19–21
    (["19_rs150_cooling", "20_rs300_cooling", "21_rs100_cooling"],
     "Шаг интегрирования задаёт только `time.dt_integration`; поля\n"
     "`numerics.dt_min` и `dt_max` решателем не читаются. `grid.type` и\n"
     "`output.format` не трогать: объявлены, но не читаются.",
     "Шаг интегрирования задаёт только `time.dt_integration`. " + NEW_GRID),
]

LEFTOVERS = ("dt_min", "dt_max", "start_day", "output.format", "p_ref", "не читаются")


def main(write):
    texts = {}
    for names, old, new in REPLACEMENTS:
        for name in names:
            path = Path("examples") / name / "README.md"
            text = texts.get(path) or path.read_bytes().decode("utf-8")
            eol = "\r\n" if "\r\n" in text else "\n"
            o, n = old.replace("\n", eol), new.replace("\n", eol)
            count = text.count(o)
            if count != 1:
                raise SystemExit(f"{path}: вхождений {count}, нужно 1 — текст README изменился")
            texts[path] = text.replace(o, n)
    for path in sorted(Path("examples").glob("*/README.md")):
        text = texts.get(path) or path.read_bytes().decode("utf-8")
        left = [w for w in LEFTOVERS if w in text]
        if left:
            raise SystemExit(f"{path}: осталось {left}")
    for path, text in sorted(texts.items()):
        print(f"  {'записан' if write else 'изменится'}: {path}")
        if write:
            path.write_bytes(text.encode("utf-8"))
    print(f"README меняется: {len(texts)}")


if __name__ == "__main__":
    main("--write" in sys.argv[1:])
