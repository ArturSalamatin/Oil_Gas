"""BUG-015: проверка плана на копии дерева — блоки «До/После» из файла плана как есть.

1. Находит в плане пары «**Правка X** `путь`» → блок «До» → блок «После».
2. Применяет их по порядку к копиям файлов в probes/tree/; каждое «До»
   должно встречаться ровно 1 раз.
3. .tex: собирает базу и копию тремя проходами pdflatex, сравнивает
   \\newlabel (метка → номер), страницы, Overfull, ошибки.
4. .py: py_compile каждой правленой копии.
5. Тесты кейса B VAL-002 из правленой копии test_val002.py — на коде как
   есть и на двух мутантах compute_jt («+ полуячейка», «JT выключен»).
6. Удаляет probes/tree/.

Запуск из numerical_solver/ (~2 мин, из них pdflatex — ~1.5 мин):
    .venv\\Scripts\\python ..\\vault\\issues\\bug-015\\probes\\plan_apply_check.py
"""

import importlib.util
import os
import py_compile
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

SOLVER = Path.cwd()
ROOT = SOLVER.parent
print(f"Код: {SOLVER}")
PROBES = Path(__file__).resolve().parent
TREE = PROBES / "tree"
PLAN = ROOT / "vault" / "plans" / "bug-015 well-face-jt-docs.md"

sys.path.insert(0, str(SOLVER))
sys.path.insert(0, str(SOLVER / "tests"))   # хелперы test_val002 импортирует сам

EDIT_RE = re.compile(
    r"\*\*Правка (\w+)\*\* `([^`]+)`.*?```\w*\n(.*?)\n```.*?```\w*\n(.*?)\n```",
    re.S)


def parse_plan():
    text = PLAN.read_text(encoding="utf-8")
    edits = EDIT_RE.findall(text)
    print(f"правок в плане: {len(edits)} ({', '.join(e[0] for e in edits)})")
    return edits


def apply_edits(edits):
    files = {}
    ok = True
    for eid, rel, before, after in edits:
        src = ROOT / rel
        txt = files.get(rel) or src.read_text(encoding="utf-8")
        n = txt.count(before)
        print(f"  {eid}: {rel} — «До» найдено {n} раз")
        if n != 1:
            ok = False
            continue
        files[rel] = txt.replace(before, after)
    for rel, txt in files.items():
        dst = TREE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(txt, encoding="utf-8")
    return ok, files


def build(tex_dir):
    for _ in range(3):
        subprocess.run(["pdflatex", "-interaction=nonstopmode",
                        "problem_statement.tex"], cwd=tex_dir,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = (tex_dir / "problem_statement.log").read_text(encoding="utf-8",
                                                        errors="replace")
    aux = (tex_dir / "problem_statement.aux").read_text(encoding="utf-8",
                                                        errors="replace")
    labels = dict(re.findall(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux))
    page = re.search(r"\\newlabel\{ssec:bc_disc\}\{\{[^}]*\}\{(\d+)\}", aux)
    print(f"  {tex_dir.name}: ssec:bc_disc на с. {page.group(1) if page else '?'}")
    pages = re.search(r"Output written on .*?\((\d+) pages", log)
    errors = [l for l in log.splitlines() if l.startswith("!")]
    undef = [l for l in log.splitlines() if "undefined" in l]
    return dict(labels=labels, pages=pages.group(1) if pages else None,
                overfull=log.count("Overfull"), errors=errors, undef=undef)


def check_tex(files):
    rel = "numerical_solver/doc/problem_statement.tex"
    if rel not in files:
        return
    base_dir = TREE / "base_doc"
    base_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / rel, base_dir / "problem_statement.tex")
    b = build(base_dir)
    n = build((TREE / rel).parent)
    print(f"\n.tex: страниц {b['pages']} → {n['pages']}, Overfull "
          f"{b['overfull']} → {n['overfull']}, ошибок {len(n['errors'])},"
          f" undefined {len(n['undef'])}")
    for e in n["errors"][:5]:
        print(f"  ! {e}")
    diff = {k: (b["labels"].get(k), v) for k, v in n["labels"].items()
            if b["labels"].get(k) != v}
    lost = set(b["labels"]) - set(n["labels"])
    print(f"  меток {len(b['labels'])} → {len(n['labels'])}; номера"
          f" изменились у {len(diff)}, пропало {len(lost)}")
    for k, (o, w) in list(diff.items())[:5]:
        print(f"    {k}: {o} → {w}")
    text = (TREE / rel).read_text(encoding="utf-8")
    bad = [w for w in ("основное охлаждение", "отличен от~нуля",
                       "не нулевой", "О~полушаге", "% BUG-015") if w in text]
    print(f"  запрещённые фразы в правленом .tex: {bad or 'нет'}")


def check_py(files):
    for rel in files:
        if rel.endswith(".py"):
            py_compile.compile(str(TREE / rel), doraise=True)
            print(f"py_compile: {rel} — ok")


def check_eq_references(files):
    """Правила tests/test_eq_references.py и шаблон DEBT-062 на правленых .py.

    Метки сверяются с правленым .tex (если он правится), иначе — с рабочим.
    """
    import test_eq_references as ter
    rx_label_number = re.compile(   # шаблон DEBT-062: «метка (N)»
        r"(?<![A-Za-z])(?:eq|sec|ssec|sssec|app):[A-Za-z0-9_]+[`)}]*\s*\(\d+\)")
    tex_rel = "numerical_solver/doc/problem_statement.tex"
    tex = (TREE / tex_rel) if tex_rel in files else (ROOT / tex_rel)
    labels = set(ter.LABEL_DEF.findall(tex.read_text(encoding="utf-8")))
    bad = []
    for rel in files:
        if not rel.endswith(".py"):
            continue
        for n, line in enumerate((TREE / rel).read_text(
                encoding="utf-8").splitlines(), 1):
            for what, rx in ter.FORBIDDEN.items():
                if rx.search(line):
                    bad.append(f"{rel}:{n}: {what}")
            if rx_label_number.search(line):
                bad.append(f"{rel}:{n}: метка (N), DEBT-062")
            for m in ter.LABEL_REF.finditer(line):
                if m.group() not in labels:
                    bad.append(f"{rel}:{n}: метка {m.group()} не объявлена")
    print(f"test_eq_references + DEBT-062 на правленых .py: "
          f"{'нарушений нет' if not bad else bad}")


def check_tests(files):
    rel = "numerical_solver/tests/test_val002.py"
    spec = importlib.util.spec_from_file_location("val002_tree", TREE / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
    orig = TridiagEnergySolver.compute_jt

    def plus_half(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf):
        J = orig(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext,
                 p_wf).copy()
        J[0] += (mu_o[0] * min(Phi_o[0], 0.0)
                 + mu_g[0] * min(Phi_g[0], 0.0)) * (p[0] - p_wf)
        return J

    def jt_off(self, Q_o, Q_g, Phi_o, Phi_g, mu_o, mu_g, p, N, ext, p_wf):
        return np.zeros(N)

    cls = mod.TestCaseB_PureJT
    names = ("test_T_profile_matches_analytical",
             "test_cell0_is_center_not_wellbore")
    print("\nТесты кейса B из правленой копии:")
    for label, fn in (("код как есть", orig), ("+ полуячейка", plus_half),
                      ("JT выключен", jt_off)):
        TridiagEnergySolver.compute_jt = fn
        try:
            inst = cls()
            res = cls.result.__wrapped__(inst)
            out = []
            for name in names:
                try:
                    getattr(inst, name)(res)
                    out.append(f"{name}: passed")
                except AssertionError as e:
                    msg = (str(e).splitlines() or ["без сообщения"])[0][:60]
                    out.append(f"{name}: FAILED ({msg})")
        finally:
            TridiagEnergySolver.compute_jt = orig
        print(f"  [{label}]")
        for o in out:
            print(f"    {o}")
    old = [n for n in dir(cls) if n == "test_wellbore_temperature"]
    print(f"  test_wellbore_temperature в копии: {'есть' if old else 'нет'}")


def main():
    if TREE.exists():
        shutil.rmtree(TREE)
    edits = parse_plan()
    ok, files = apply_edits(edits)
    print(f"все «До» единственны: {ok}")
    if ok:
        check_py(files)
        check_eq_references(files)
        check_tex(files)
        check_tests(files)
    # KEEP=1 — оставить копию (PDF для просмотра), иначе удалить
    if not os.environ.get("KEEP"):
        shutil.rmtree(TREE, ignore_errors=True)


if __name__ == "__main__":
    main()
