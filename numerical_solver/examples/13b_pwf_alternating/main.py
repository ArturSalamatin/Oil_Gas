"""Сценарий 13b: p_wf по суткам 6 <-> 10.75 МПа, 30 сут (R_ext = 200 м)."""

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
        title="13b: чередование забойного давления 6 ↔ 10.75 МПа",
        # 7 моментов равномерно по времени: 0, 5, 10, ..., 30 сут. Концы
        # 5, 15, 25 сут — состояние при 6 МПа, концы 10, 20, 30 сут — при
        # 10.75 МПа: на профилях видны оба режима (при 6 моментах все они
        # попадают на сутки при 10.75 МПа).
        n_profiles=7,
        # Без стационарной аналитики: замкнутое решение и асимптотика
        # температуры — пределы t -> inf при удержании одного режима, а
        # режим меняется каждые сутки. Проверка R_s остаётся: расхождение
        # на финале — недонасыщенная нефть после подъёма давления, см. README.
        steady_state=False,
    )
