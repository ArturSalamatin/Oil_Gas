"""FEAT-023: полный конвейер run_example на конфиге 13b до реализации.

Конфиг и CSV пишутся в cfg_13b/ рядом с пробой (не в examples/: папка
примера там сломала бы test_no_extra_example_folders до шага 6 плана).
Параметры рисования — как решено для 13b: n_profiles=7, без стационарных
наложений на профилях p и S_g (флага steady_state ещё нет, поэтому
report_closed и report_asymptotics пока печатаются — видно, что именно
флаг снимет). Цель — посмотреть графики и снять время и консоль для README.

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-023\\probes\\run_example_13b.py
"""

import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE.parents[3] / "numerical_solver" / "examples"
sys.path.insert(0, str(EX))

from example_runner import run_example  # noqa: E402

SRC = EX / "12_large_drainage_radius"
DST = HERE / "cfg_13b"
DST.mkdir(exist_ok=True)
for f in ("oil_pvt.csv", "gas_pvt.csv", "relperm.csv"):
    shutil.copyfile(SRC / f, DST / f)

cfg = json.loads((SRC / "config.json").read_text(encoding="utf-8"))
# Сутки d = 1..30: нечётные 6 МПа, чётные 10.75 МПа; по два интервала 0.5 сут
cfg["time"]["history"] = [
    {"dt": 43200.0, "control": "pressure",
     "p_wf": 6_000_000.0 if d % 2 == 1 else 10_750_000.0}
    for d in range(1, 31) for _ in range(2)
]
(DST / "config.json").write_text(
    json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

t0 = time.perf_counter()
run_example(
    config_path=DST / "config.json",
    output_dir=DST / "output",
    title="13b: чередование забойного давления 6 ↔ 10.75 МПа",
    n_profiles=7,
    overlays={"p": None, "Sg": None},
)
print(f"\nrun_example целиком: {time.perf_counter() - t0:.1f} с")
