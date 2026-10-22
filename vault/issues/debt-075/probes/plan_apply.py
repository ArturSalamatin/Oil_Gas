"""DEBT-075, аудит плана: правки шага 1 — из текста плана, в память; рабочие файлы не меняются.

Блоки «До/После» и код тестов раздела J берутся из vault/plans/debt-075 saturation-bounds-check.md
(отступ пункта списка — 3 пробела — снимается). Скрипт проверяет, что каждый блок «До» найден
в файле ровно один раз, пишет исправленные копии в probes/patched/ (для просмотра diff) и
файл тестов probes/test_plan_j.py.

Подстановка в память — patch_in_memory(): методы Simulator._advance и _check_hydro_state из
исправленного исходника ставятся в существующий класс (тождество класса сохраняется: фабрика
и тесты держат ссылку на него). Подключение к pytest — plan_patch_plugin.py (-p).

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-075\\probes\\plan_apply.py
"""
import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]     # probes → debt-075 → issues → vault → корень проекта
PLAN = ROOT / "vault" / "plans" / "debt-075 saturation-bounds-check.md"
SOLVER = ROOT / "numerical_solver"
PKG = SOLVER / "gpn_multiphase_solver"


def _blocks(text: str, lang: str) -> list[str]:
    """Блоки ```lang шага 1 по порядку; отступ пункта списка (3 пробела) снят."""
    step1 = text.split("### Шаг 1", 1)[1].split("### Шаг 2", 1)[0]
    out, cur, cur_lang = [], None, None
    # Ограждения разбираются построчно: открывающее «   ```<язык>», закрывающее «   ```»
    for ln in step1.split("\n"):
        m = re.fullmatch(r"   ```(\w*)", ln)
        if m and cur is None:
            cur, cur_lang = [], m.group(1)
        elif m and cur is not None and m.group(1) == "":
            if cur_lang == lang:
                out.append("\n".join(x[3:] if x.startswith("   ") else x for x in cur) + "\n")
            cur = None
        elif cur is not None:
            cur.append(ln)
    return out


def _replace_once(src: str, old: str, new: str, what: str) -> str:
    n = src.count(old)
    assert n == 1, f"{what}: блок «До» найден {n} раз"
    return src.replace(old, new)


def build() -> dict:
    text = PLAN.read_text(encoding="utf-8")
    py = _blocks(text, "python")
    plain = _blocks(text, "")
    assert len(py) == 6, f"python-блоков в шаге 1: {len(py)}"
    tests_j, adv_old, adv_new, method, pipe_old, pipe_new = py
    assert len(plain) == 4, f"простых блоков в шаге 1: {len(plain)}"
    _header, doc_old, doc_new, base_par = plain

    # ── simulator.py ──
    sim = (PKG / "simulator.py").read_text(encoding="utf-8")
    sim = _replace_once(sim, adv_old, adv_new, "п. 4 _advance")
    anchor = "\n    def _mass_snapshot("
    assert sim.count(anchor) == 1
    sim = sim.replace(anchor, "\n" + method.rstrip("\n") + "\n" + anchor)
    sim = _replace_once(sim, doc_old, doc_new, "п. 6 докстринг модуля")
    ast.parse(sim)

    # ── hydro/base.py: абзац после «Один шаг без дробления …» ──
    base = (PKG / "hydro" / "base.py").read_text(encoding="utf-8")
    anchor_b = "        шли ровно по принятым подшагам (BUG-010).\n"
    assert base.count(anchor_b) == 1
    base = base.replace(anchor_b, anchor_b + base_par.rstrip("\n") + "\n")
    ast.parse(base)

    # ── report/pipeline.py: только комментарий (п. 8, аудит 2) ──
    pipe = (PKG / "report" / "pipeline.py").read_text(encoding="utf-8")
    pipe = _replace_once(pipe, pipe_old, pipe_new, "п. 8 комментарий run_case")
    ast.parse(pipe)

    # ── тесты раздела J: тот же код, импорты — как в test_simulator.py после п. 2 ──
    header = (
        "# Сгенерировано plan_apply.py из плана DEBT-075 (раздел J). Не править вручную.\n"
        "from dataclasses import replace\n\n"
        "import numpy as np\n"
        "import pytest\n\n"
        "from gpn_multiphase_solver.simulator import Simulator\n"
        "from tests._doubles import FailingHydroStub\n"
        "from tests.test_simulator import (\n"
        "    _make_simulator, _initial_state, _single_interval_schedule,\n"
        "    _CorruptingEnergySolver)\n")
    test_src = header + tests_j
    ast.parse(test_src)
    return {"simulator.py": sim, "base.py": base, "pipeline.py": pipe,
            "test_plan_j.py": test_src}


def write(files: dict) -> None:
    (HERE / "patched").mkdir(exist_ok=True)
    (HERE / "patched" / "simulator.py").write_text(files["simulator.py"], encoding="utf-8")
    (HERE / "patched" / "base.py").write_text(files["base.py"], encoding="utf-8")
    (HERE / "patched" / "pipeline.py").write_text(files["pipeline.py"], encoding="utf-8")
    (HERE / "test_plan_j.py").write_text(files["test_plan_j.py"], encoding="utf-8")


def patch_in_memory() -> None:
    """Simulator._advance и _check_hydro_state — из исправленного исходника плана."""
    import gpn_multiphase_solver.simulator as mod
    files = build()
    ns = dict(mod.__dict__)
    exec(compile(files["simulator.py"], mod.__file__ + " [план DEBT-075]", "exec"), ns)
    new = ns["Simulator"]
    mod.Simulator._advance = new.__dict__["_advance"]
    mod.Simulator._check_hydro_state = new.__dict__["_check_hydro_state"]


def check_eq_refs(files: dict) -> list[str]:
    """Сторож DEBT-010/062 (tests/test_eq_references.py) по новым текстам плана — файлы с диска он не видит."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "eq_refs", SOLVER / "tests" / "test_eq_references.py")
    eq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eq)
    tex = (SOLVER / "doc" / "problem_statement.tex").read_text(encoding="utf-8")
    labels = set(eq.LABEL_DEF.findall(tex))
    # шаг 2 — тексты для заметок vault (DEBT-074 проверяет заметки теми же шаблонами)
    step2 = PLAN.read_text(encoding="utf-8").split("### Шаг 2", 1)[1].split("### Шаг 3", 1)[0]
    texts = dict(files, **{"шаг 2 (заметки vault)": step2})
    bad = []
    for name, text in texts.items():
        for i, line in enumerate(text.split("\n"), 1):
            bad += [f"{name}:{i}: {what}: {line.strip()}"
                    for what, rx in eq.FORBIDDEN.items() if rx.search(line)]
            bad += [f"{name}:{i}: метки {m} нет в problem_statement.tex"
                    for m in eq.LABEL_REF.findall(line) if m not in labels]
    return bad


if __name__ == "__main__":
    files = build()
    write(files)
    print("блоки плана найдены, «До» совпали; копии — probes/patched/, тесты — probes/test_plan_j.py")
    bad = check_eq_refs(files)
    print(f"сторож ссылок (FORBIDDEN, LABEL_REF) по новым текстам: нарушений {len(bad)}")
    for b in bad:
        print("  " + b)
