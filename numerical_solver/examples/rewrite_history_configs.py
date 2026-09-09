"""Одноразовый генератор: перевести конфиги на частую запись истории (DEBT-013).

Раньше частоту вывода задавали ДВА механизма: структура time.history и
параметр output.save_every. Второй перебивал первый — при одном интервале
на весь расчёт запись всё равно шла на каждом подшаге, потому что
save_every = 1. После удаления параметра тот же конфиг дал бы всего две
записи (начало и конец), поэтому расписание надо выписать явно.

Что делает: каждый интервал history дробится на части длиной STEP секунд
(остальные поля интервала сохраняются как есть), и удаляется поле
output.save_every. Число записей и моменты вывода остаются прежними.

Запуск (из numerical_solver):
    .venv\\Scripts\\python examples\\rewrite_history_configs.py
"""

import json
from pathlib import Path

# Шаг записи результатов, с. Совпадает с dt_integration у десяти примеров
# из одиннадцати, поэтому у них на запись приходится ровно один подшаг —
# как было при save_every = 1. У 04a шаг интегрирования мельче (300 с
# из-за высокой газонасыщенности), там в интервал попадает 12 подшагов.
STEP = 3600.0

_ROOT = Path(__file__).resolve().parent.parent


def _split(interval: dict, step: float) -> list[dict]:
    """Разбить интервал на части длиной step (последняя добирает остаток)."""
    total = float(interval["dt"])
    n = max(int(round(total / step)), 1)
    out = []
    for _ in range(n):
        part = dict(interval)          # копия: control, p_wf и прочее без изменений
        part["dt"] = total / n
        out.append(part)
    return out


def rewrite(path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))

    history = raw["time"]["history"]
    new_history = []
    for iv in history:
        new_history.extend(_split(iv, STEP))
    raw["time"]["history"] = new_history

    removed = raw.get("output", {}).pop("save_every", None)

    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return (f"{len(history)} -> {len(new_history)} интервалов"
            + (f", удалён save_every = {removed}" if removed is not None else ""))


if __name__ == "__main__":
    targets = sorted((_ROOT / "examples").glob("*/config.json"))
    targets += [_ROOT / "configs" / "baseline.json",
                _ROOT / "configs" / "val001.json",
                _ROOT / "configs" / "table_pvt" / "config.json"]

    for p in targets:
        print(f"{p.relative_to(_ROOT)}: {rewrite(p)}")
