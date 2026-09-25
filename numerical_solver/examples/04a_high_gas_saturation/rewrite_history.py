"""Перегенерация блока time.history в config.json примера 04a.

Выписывает расписание заново: 72 ч интервалами длиной dt_integration, то
есть по одному шагу решателя на запись. При dt_integration = 300 с это
864 интервала и 865 записей. Поля интервала (control, p_wf) копируются из
первого.

Нужен при смене dt_integration: 864 одинаковых интервала руками не
переписать. Длительность 72 ч держится намеренно — на ней стоит сравнение
с примером 04.

Запуск:
    cd numerical_solver
    .venv\\Scripts\\python examples\\04a_high_gas_saturation\\rewrite_history.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = HERE / "config.json"

# Суммарный срок сохраняем: 72 ч. Шаг записи = dt_integration,
# то есть история пишется на каждом подшаге схемы.
TOTAL_SECONDS = 72 * 3600.0


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    time_cfg = cfg["time"]
    old = time_cfg["history"]
    dt_int = float(time_cfg["dt_integration"])

    # Управление берём из первого интервала: у 04a все интервалы одинаковы
    # (постоянное p_wf = 4 МПа на всём сроке).
    template = dict(old[0])
    old_total = sum(float(h["dt"]) for h in old)
    n_new = int(round(TOTAL_SECONDS / dt_int))

    time_cfg["history"] = [
        {**template, "dt": dt_int} for _ in range(n_new)
    ]

    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")

    print(f"было:  {len(old)} интервалов по {old[0]['dt']:.0f} с "
          f"= {old_total / 3600:.0f} ч")
    print(f"стало: {n_new} интервалов по {dt_int:.0f} с "
          f"= {n_new * dt_int / 3600:.0f} ч")
    print(f"записей истории: {len(old) + 1} -> {n_new + 1}")


if __name__ == "__main__":
    main()
