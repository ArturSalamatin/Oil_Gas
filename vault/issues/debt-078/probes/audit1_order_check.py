"""Аудит 1 DEBT-078: совместимость с DEBT-076 — якоря при любом порядке и слияние веток.

DEBT-076 (план «готов к реализации», 2026-10-17) вставляет блок плотностей в те же
файлы: io/config.py (после проверки c_r), test_config.py (класс после
TestValidationRock), P8 (строка _validate и абзац после «Порода»). Вставки DEBT-076
здесь — заглушки с его якорями «До» (из плана debt-076, шаги 1 и 3).

Проверки:
  A — сначала DEBT-078, затем якоря DEBT-076 находятся ровно один раз;
  B — сначала DEBT-076, затем якоря DEBT-078 находятся ровно один раз;
  M — git merge-file base/DEBT-078/DEBT-076 по каждому файлу: число конфликтов.

    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-078\\probes\\audit1_order_check.py
"""

import importlib.util
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

spec = importlib.util.spec_from_file_location("plan_apply", HERE / "plan_apply.py")
pa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pa)

D076 = [
    (pa.CONFIG,
     '            f"объём с ростом давления не уменьшается (вероятно, ошибка знака)")\n'
     '\n'
     '    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──\n',
     '            f"объём с ростом давления не уменьшается (вероятно, ошибка знака)")\n'
     '\n'
     '    # ── PVT: плотности при стандартных условиях (DEBT-076, P8 §5) ──\n'
     '    pc = cfg.pvt  # заглушка DEBT-076\n'
     '\n'
     '    # ── Скважина: скин-фактор (DEBT-056, P8 §5) ──\n'),
    (pa.T_CONFIG,
     '        assert cfg.rock.compressibility == c_r\n\n\nclass TestValidationInitial:\n',
     '        assert cfg.rock.compressibility == c_r\n\n\nclass TestValidationPVT:\n'
     '    pass  # заглушка DEBT-076\n\n\nclass TestValidationInitial:\n'),
    (pa.P8,
     'порода (`compressibility` ≥ 0 — DEBT-068), тепловые параметры',
     'порода (`compressibility` ≥ 0 — DEBT-068), PVT (`rho_o_std`, `rho_g_std` > 0 — '
     'DEBT-076), тепловые параметры'),
    (pa.P8,
     'при $c_r \\ge 0$ $\\varphi(p) \\le$ `porosity`.\n',
     'при $c_r \\ge 0$ $\\varphi(p) \\le$ `porosity`.\n\nPVT — наш config (заглушка DEBT-076).\n'),
]
FILES = sorted({p for p, _, _ in D076})


def base_text(path):
    """Файл на HEAD основного каталога, окончания строк — \\n."""
    out = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, check=True)
    return out.stdout.decode("utf-8").replace("\r\n", "\n")


def apply(texts, edits, label):
    ok = True
    for path, old, new in edits:
        if path not in texts:
            continue
        n = texts[path].count(old)
        ok &= n == 1
        print(f"  {label}: {'OK ' if n == 1 else f'НАЙДЕН {n} РАЗ'} {path}: {old.splitlines()[0][:60]!r}")
        if n == 1:
            texts[path] = texts[path].replace(old, new)
    return ok


head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                      capture_output=True, text=True).stdout.strip()
print(f"база: {head}; файлы, общие с DEBT-076: {', '.join(FILES)}")
mine = [e for e in pa.EDITS if e[0] in FILES]

print("\nA — сначала DEBT-078, затем DEBT-076:")
t = {p: base_text(p) for p in FILES}
a = apply(t, mine, "078") and apply(t, D076, "076")

print("\nB — сначала DEBT-076, затем DEBT-078:")
t = {p: base_text(p) for p in FILES}
b = apply(t, D076, "076") and apply(t, mine, "078")

print("\nM — трёхстороннее слияние (git merge-file):")
with tempfile.TemporaryDirectory(dir=HERE) as d:
    d = Path(d)
    for path in FILES:
        base = base_text(path)
        ours, theirs = {path: base}, {path: base}
        apply(ours, mine, "078 ")
        apply(theirs, D076, "076 ")
        for name, text in (("base", base), ("ours", ours[path]), ("theirs", theirs[path])):
            (d / name).write_bytes(text.encode("utf-8"))
        r = subprocess.run(["git", "merge-file", "-p", str(d / "ours"), str(d / "base"),
                            str(d / "theirs")], capture_output=True)
        print(f"  {path}: конфликтов {r.returncode}")

print(f"\nитог: A {'OK' if a else 'ОШИБКА'}, B {'OK' if b else 'ОШИБКА'}")
