"""Сравнение одноимённых скриптов примеров по AST — детектор дублирования.

ЗАЧЕМ. Вспомогательные проверки в examples/ имеют свойство расползаться
копиями по папкам примеров: скрипт пишется под один пример, потом
копируется в другой, дальше копии правятся независимо и расходятся. Так
возникла FEAT-016.

Хэш файла для отслеживания этого не годится: он меняется от любой правки
докстринга, и две копии с одинаковой логикой выглядят разными. Поэтому
сравниваем ast.dump тел функций с удалёнными докстрингами — видно, где
расходится собственно ЛОГИКА, а где только текст.

Вывод читается так:
  «ИДЕНТИЧНА во всех N» — функцию можно выносить в общий модуль механически;
  «K версий»            — сначала разобраться, содержательное различие или
                          разошедшаяся копия. Выносить, не разобравшись,
                          значит потерять одну из версий поведения.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\compare_script_copies.py
"""
import ast
import hashlib
from pathlib import Path
from collections import defaultdict

EXAMPLES = Path(__file__).resolve().parent

# Группы, за которыми следим. Пополнять при появлении новых копий.
GROUPS = [
    "energy_balance.py",
    "energy_balance_convergence.py",
    "temperature_ode.py",
    "ode_grid_convergence.py",
    "temperature_asymptotics.py",
    "two_phase_analytics.py",
]


def strip_docstrings(node):
    """Убрать докстринги из всех определений — они не логика."""
    for n in ast.walk(node):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            if (n.body and isinstance(n.body[0], ast.Expr)
                    and isinstance(n.body[0].value, ast.Constant)
                    and isinstance(n.body[0].value.value, str)):
                n.body = n.body[1:]
    return node


def func_hashes(path: Path) -> dict:
    """{имя функции: хэш AST тела} для всех функций верхнего уровня."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            clean = strip_docstrings(node)
            dumped = ast.dump(clean, annotate_fields=True,
                              include_attributes=False)
            out[node.name] = hashlib.md5(dumped.encode()).hexdigest()[:8]
    return out


for group in GROUPS:
    paths = sorted(EXAMPLES.glob(f"*/{group}"))
    if len(paths) < 2:
        continue
    print(f"\n=== {group} ({len(paths)} копий) ===")

    # собираем: функция -> {хэш: [примеры]}
    per_func = defaultdict(lambda: defaultdict(list))
    all_funcs = set()
    for p in paths:
        fh = func_hashes(p)
        all_funcs |= set(fh)
        for name, h in fh.items():
            per_func[name][h].append(p.parent.name)

    for name in sorted(all_funcs):
        variants = per_func[name]
        present = sum(len(v) for v in variants.values())
        if len(variants) == 1 and present == len(paths):
            print(f"  {name:28s} ИДЕНТИЧНА во всех {present}")
        else:
            print(f"  {name:28s} {len(variants)} версий "
                  f"(есть в {present}/{len(paths)}):")
            for h, examples in sorted(variants.items(),
                                      key=lambda kv: -len(kv[1])):
                print(f"      {h}  {', '.join(examples)}")
