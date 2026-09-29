"""Сценарий 13a: ступенчатое снижение p_wf 14.4 -> 6 МПа за 15 сут (R_ext = 200 м)."""

import sys
from pathlib import Path

# examples/ в sys.path — для импорта example_runner.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from example_runner import run_example  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    run_example(
        config_path=here / "config.json",
        output_dir=here / "output",
        title="13a: ступенчатое снижение забойного давления",
        # 6 моментов равномерно по времени: 0, 3, 6, 9, 12, 15 сут — все
        # концы суток, то есть состояние перед следующей ступенью p_wf
        # (решение пользователя 2026-09-29; 31 кривая была нечитаема).
        n_profiles=6,
        # Без стационарного решения на профилях S_g (решение пользователя
        # 2026-09-29): замыкание GOR = Rs0 при GOR = 54.9 на 15 сут даёт S_g
        # почти вдвое ниже численной и выглядит как ошибка. Пунктир на
        # профилях давления остаётся — предел t -> inf при 6 МПа.
        overlays={"Sg": None},
    )
