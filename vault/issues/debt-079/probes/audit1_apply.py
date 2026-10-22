"""DEBT-079, аудит 1: шаг 1 плана — из ТЕКСТА плана, в память и в копии; рабочие файлы не меняются.

Блоки ```…``` шага 1 берутся из vault/plans/debt-079 relperm-immobile-gas-first-row.md по порядку
(отступ пункта списка — 3 пробела — снимается); каждый «До» обязан найтись ровно один раз.
Пишет: probes/patched/factory.py (для просмотра diff) и probes/patched/tests/ — переделанные
test_factory_prototype.py и test_table_range_warnings.py; в копиях Path(__file__).parent.parent
заменён абсолютным путём numerical_solver/ (копии лежат вне tests/).
patch_in_memory() — _check_relperm_table и create_relperm из исправленного исходника (плагин
audit1_plugin.py). check_eq_refs() — сторож tests/test_eq_references.py по новым текстам шагов 1–2.

Запуск из numerical_solver/:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-079\\probes\\audit1_apply.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = ROOT / "vault" / "plans" / "debt-079 relperm-immobile-gas-first-row.md"
SOLVER = ROOT / "numerical_solver"
PKG = SOLVER / "gpn_multiphase_solver"


def _blocks(text):
    """[(язык, текст)] блоков шага 1 по порядку; отступ 3 пробела снят."""
    step1 = text.split("### Шаг 1", 1)[1].split("### Шаг 2", 1)[0]
    out, cur, lang = [], None, None
    for ln in step1.split("\n"):
        m = re.fullmatch(r"   ```(\w*)", ln)
        if m and cur is None:
            cur, lang = [], m.group(1)
        elif m and cur is not None and m.group(1) == "":
            out.append((lang, "\n".join(x[3:] if x.startswith("   ") else x for x in cur) + "\n"))
            cur = None
        elif cur is not None:
            cur.append(ln)
    return out


def _once(src, old, new, what):
    n = src.count(old)
    assert n == 1, f"{what}: «До» найден {n} раз"
    return src.replace(old, new)


def build():
    b = [t for _, t in _blocks(PLAN.read_text(encoding="utf-8"))]
    assert len(b) == 16, f"блоков в шаге 1: {len(b)}"
    (sig_old, sig_new, check, call_old, call_new, list_old, list_new, doc_old, doc_new,
     tests_new, acc_doc_old, acc_doc_new, acc_body_old, acc_body_new, w_old, w_new) = b

    fac = (PKG / "factory.py").read_text(encoding="utf-8")
    fac = _once(fac, sig_old, sig_new, "п. 1")
    anchor = "    # DEBT-073: выше последней строки TabulatedRelPerm берёт k_ro, k_rg из неё\n"
    fac = _once(fac, anchor, check + anchor, "п. 2 (якорь)")
    fac = _once(fac, call_old, call_new, "п. 3")
    fac = _once(fac, list_old, list_new, "п. 4")
    compile(fac, "factory.py", "exec")

    tf = (SOLVER / "tests" / "test_factory_prototype.py").read_text(encoding="utf-8")
    tf = _once(tf, doc_old, doc_new, "п. 5")
    anchor6 = "    # ── Последняя строка ОФП: k_ro = 0 (DEBT-073) ──\n"
    tf = _once(tf, anchor6, tests_new + "\n" + anchor6, "п. 6 (якорь)")
    tf = _once(tf, acc_doc_old, acc_doc_new, "п. 7 докстринг")
    tf = _once(tf, acc_body_old, acc_body_new, "п. 7 тело")
    compile(tf, "test_factory_prototype.py", "exec")

    tw = (SOLVER / "tests" / "test_table_range_warnings.py").read_text(encoding="utf-8")
    tw = _once(tw, w_old, w_new, "п. 8")
    compile(tw, "test_table_range_warnings.py", "exec")
    return {"factory.py": fac, "test_factory_prototype.py": tf,
            "test_table_range_warnings.py": tw, "_new_texts": [sig_new, check, call_new, list_new,
                                                              doc_new, tests_new, acc_doc_new,
                                                              acc_body_new, w_new]}


def write(files):
    (HERE / "patched" / "tests").mkdir(parents=True, exist_ok=True)
    (HERE / "patched" / "factory.py").write_text(files["factory.py"], encoding="utf-8")
    here_root = f'Path(r"{SOLVER}")'
    for name in ("test_factory_prototype.py", "test_table_range_warnings.py"):
        src = files[name]
        assert src.count("Path(__file__).parent.parent") == 1
        src = src.replace("Path(__file__).parent.parent", here_root)
        (HERE / "patched" / "tests" / name).write_text(src, encoding="utf-8")


def patch_in_memory():
    import gpn_multiphase_solver.factory as mod
    ns = dict(mod.__dict__)
    exec(compile(build()["factory.py"], mod.__file__ + " [план DEBT-079]", "exec"), ns)
    mod._check_relperm_table = ns["_check_relperm_table"]
    mod.create_relperm = ns["create_relperm"]


def check_eq_refs(files):
    """Шаблоны FORBIDDEN сторожа по новым текстам шага 1 и всему тексту шага 2 (README, P8)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("eq_refs", SOLVER / "tests" / "test_eq_references.py")
    eq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eq)
    step2 = PLAN.read_text(encoding="utf-8").split("### Шаг 2", 1)[1].split("### Шаг 3", 1)[0]
    bad = []
    for k, text in enumerate(files["_new_texts"] + [step2]):
        for i, line in enumerate(text.split("\n"), 1):
            bad += [f"текст {k}:{i}: {what}: {line.strip()}"
                    for what, rx in eq.FORBIDDEN.items() if rx.search(line)]
    return bad


def long_lines(files):
    """Строки > 100 символов, которых не было в исходнике (стиль: длина строки)."""
    out = []
    for name, path in (("factory.py", PKG / "factory.py"),
                       ("test_factory_prototype.py", SOLVER / "tests" / "test_factory_prototype.py"),
                       ("test_table_range_warnings.py",
                        SOLVER / "tests" / "test_table_range_warnings.py")):
        old = set(path.read_text(encoding="utf-8").split("\n"))
        out += [f"{name}: {len(ln)}: {ln.strip()[:90]}" for ln in files[name].split("\n")
                if len(ln) > 100 and ln not in old]
    return out


if __name__ == "__main__":
    files = build()
    write(files)
    print("блоки шага 1 из текста плана: 16, каждый «До» найден один раз; копии — probes/patched/")
    bad = check_eq_refs(files)
    print(f"сторож ссылок (FORBIDDEN) по новым текстам шагов 1–2: нарушений {len(bad)}")
    for x in bad:
        print("  " + x)
    ll = long_lines(files)
    print(f"новых строк длиннее 100 символов: {len(ll)}")
    for x in ll:
        print("  " + x)
