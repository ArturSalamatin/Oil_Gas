"""Перегенерация блока time.history в config.json примера 04a.

ЗАЧЕМ. ОДУ-аналитика температуры рекуррентна: T^n восстанавливается из
T^{n-1} по ЗАПИСЯМ истории, а коэффициенты замораживаются на интервале
между записями. Схема же внутри интервала делает dt/dt_integration подшагов
со своими коэффициентами на каждом.

При dt = 3600 с и dt_integration = 300 с в один интервал попадает 12
подшагов. Гидродинамика 04a за это время заметно дрейфует (характерное
время пьезопроводности ~210 ч против 72 ч расчёта — 21 % порового объёма
занимает сжимаемый газ), поэтому замороженные коэффициенты систематически
смещены, и пунктирные кривые ОДУ отходят от расчётных ПО ВСЕЙ ОБЛАСТИ,
включая однофазную зону, где нет ни газа, ни дегазации.

Замерено (BUG-006): ошибка в однофазной зоне 0.175 К при dt = 3600 с
против 0.005 К при dt = 300 с — в 35 раз. Полная ошибка 0.281 К -> 0.107 К.
Остаток 0.107 К у забоя — отдельный дефект на границе зоны полной
дегазации (Rs = 0), измельчением шага истории он не снимается.

ЦЕНА. 864 записи вместо 72: ОДУ делает 864 последовательных solve_ivp
вместо 72 (~10 мин против ~90 с), profiles.csv растёт примерно в 12 раз.

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

    # Управление берём из первого интервала: у 04a все 72 одинаковы
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
