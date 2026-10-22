"""BUG-025, аудит 2: тесты шага 2 плана — дословно из плана, для прогона до правки и с эмуляцией шага 3.

Пишет рядом test_prototype_residual_floor.py (GPN) и test_residual_floor.py (прототип) — блоки
```python после «Что сделать — 1.» и «Что сделать — 2.» шага 2. В начало каждого вставлена
одна строка `import emulate_step3`: при BUG025_EMULATE=1 она подставляет правку шага 3
(emulate_step3.py), иначе ничего не делает.

Запуск (PowerShell):
    python extract.py
    cd numerical_solver
    [$env:BUG025_EMULATE = "1";] .venv\\Scripts\\python -m pytest -c pyproject.toml --rootdir . -p no:cacheprovider -q ..\\vault\\issues\\bug-025\\probes\\audit2\\test_prototype_residual_floor.py
    cd HydroSolverPrototype\\Prototype_1.0.3
    ..\\..\\.venv\\Scripts\\python -m pytest -p no:cacheprovider -q ..\\..\\..\\vault\\issues\\bug-025\\probes\\audit2\\test_residual_floor.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[3] / "plans" / "bug-025 short-step-residual-floor.md"
text = PLAN.read_text(encoding="utf-8")
step2 = text[text.index("### Шаг 2:"):text.index("### Шаг 3:")]
for marker, name in (("Что сделать — 1.", "test_prototype_residual_floor.py"),
                     ("Что сделать — 2.", "test_residual_floor.py")):
    part = step2[step2.index(marker):]
    code = re.search(r"```python\n(.*?)\n```", part, re.S).group(1)
    # в плане тест лежит в numerical_solver/tests/, рядом с data/; копия — здесь
    tests_dir = HERE.parents[3].parent / "numerical_solver" / "tests"
    code = code.replace('Path(__file__).parent / "data"', f'Path(r"{tests_dir}") / "data"')
    (HERE / name).write_text("import emulate_step3  # noqa: F401 (аудит 2)\n" + code + "\n", encoding="utf-8")
    print(f"{name}: {len(code.splitlines())} строк")
