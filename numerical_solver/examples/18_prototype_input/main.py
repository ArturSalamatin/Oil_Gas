"""Сценарий 18: вход прототипа (INPUT_TEMPLATE.xlsx) — расчёт с температурой, сверка с прототипом и CMG IMEX."""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner и figure_io. Папка
# скрипта уже в sys.path (её кладёт Python) — оттуда prototype_input.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from example_runner import run_example  # noqa: E402
from figure_io import export_emf  # noqa: E402
import prototype_input  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    output = here / "output"
    title = "18: вход прототипа (INPUT_TEMPLATE.xlsx)"
    _, history, grid, _ = run_example(
        config_path=here / "config.json",
        output_dir=output,
        title=title,
        # Профили на 0, 6, 14, 16, 30 сут — ближайшие записи к 0, 6, …, 30 сут:
        # по моменту на каждый режим p_wf (150 / 120 / 100 бар) и конец.
        n_profiles=6,
        # Без стационарной аналитики: режим скважины меняется на 5 и 15 сут,
        # двухфазная зона к 30 сут ещё растёт (до 15 м, GOR 45.4 < R_s0 = 50);
        # замкнутое решение дало бы фронт 19.5 м и q_o на 6.7 % ниже.
        # Проверка R_s остаётся.
        steady_state=False,
    )
    # Прототип на той же книге и эталон CMG IMEX T07: сводка и два рисунка.
    prototype_input.report_and_plot(history, grid, output, title)
    # Рисунки сравнения созданы после export_emf внутри run_example —
    # второй вызов переводит в EMF только их.
    export_emf(output)
