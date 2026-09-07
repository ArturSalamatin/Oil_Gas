# Запуск решателя

Пользователь указал конфиг или параметры: `$ARGUMENTS`

## 0. Определи направление

| Признак в `$ARGUMENTS` | Направление | Каталог |
|---|---|---|
| путь внутри `numerical_solver/`, пусто, «солвер», «PDE» | **PDE-солвер** | `numerical_solver/` |
| путь внутри `method_of_moments/`, «метод моментов», `rb`, `Sgw` | Метод моментов (завершён) | `method_of_moments/` |

По умолчанию — **PDE-солвер**. Если `$ARGUMENTS` пуст, взять `configs/baseline.json` из соответствующего каталога.

---

## A. PDE-солвер (`numerical_solver/`)

Отдельного CLI нет — запуск через API библиотеки.

```powershell
cd d:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver
$env:PYTHONPATH = "$PWD\HydroSolverPrototype\Prototype_1.0.3"
.venv\Scripts\python -c @'
from gpn_multiphase_solver.io.config import load_config
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.output import save_csv, save_npz
cfg = load_config(r"<путь к конфигу>")
sim, st0 = SimulatorFactory.from_config(cfg)
hist = sim.run(st0)
print("шагов:", hist.n_saved)
'@
```

⚠️ `radial_blackoil` не установлен в venv — нужен `PYTHONPATH` (или `sys.path`, как в `tests/conftest.py`). Без него — `ModuleNotFoundError`.

Если в `examples/` есть готовый сценарий — предпочесть его:
```powershell
.venv\Scripts\python examples\<сценарий>\main.py
```

### Проверка результата

- Расчёт завершился без исключений, `history.n_saved > 0`?
- Нет NaN / Inf в `p`, `T`, `Sg`, `Rs`?
- `p > 0`, `T > 0`, `Sg ∈ [0, 1]` всюду?
- Ньютон не расходился? (`RuntimeError: HydroSolver не сошёлся` → уменьшить `dt_integration`, см. DEBT-007)

### Физическая проверка

- $p(r_w) \to p_{wf}$, $p(R_{ext}) \to p_0$?
- Профиль $p(r)$ монотонно растёт от забоя к контуру?
- Однофазный режим ($R_{s,0} = 0$ или $p_{wf} > p_b$): $S_g \equiv 0$, $q_g \equiv 0$?
- Двухфазный: $S_g > 0$ у забоя, $S_g = 0$ за фронтом $r_b$, $R_s$ убывает к скважине?
- $T(r_w) < T_0$ при включённых $\mu_{JT} > 0$ или $L > 0$?
- GOR $= q_g / q_o$ — в стационаре равен $R_{s,0}$ (весь газ с контура выносится)?

Если $S_g \equiv 0$ там, где ожидалось разгазирование, — первым делом сверить $p_{wf}$ с $p_b$ выбранной PVT-модели: разгазирования не будет при $p_{wf} \geq p_b$.

### Визуализация

```python
import matplotlib; matplotlib.use("Agg")
from gpn_multiphase_solver.io.output import (
    plot_profiles, plot_wellbore_dynamics, plot_well_rate)
grid = sim._grid
```

1. **p(r)** на нескольких моментах (`plot_profiles(..., field='p')`, semilogx)
2. **T(r)** — `field='T'`
3. **Sg(r)** — `field='Sg'` (для двухфазных режимов)
4. **q_o(t), q_g(t)** — `plot_well_rate`
5. **Динамика на забое** — `plot_wellbore_dynamics`

Сохранить в `numerical_solver/results/` (в `.gitignore`).

---

## B. Метод моментов (`method_of_moments/`) — завершённое направление

```powershell
cd d:\Lessons\Grants\2026\GPN\Oil_Gas\method_of_moments
.venv\Scripts\python src/main.py $ARGUMENTS
```

Если `src/main.py` не существует или не готов — сообщи, какие FEAT нужно реализовать.

### Проверка результата

- Решение завершилось без ошибок?
- $r_b(t)$ — монотонно растёт?
- $S_{g,w}(t) \in [0, 1]$?
- $\Delta T_w(t) < 0$ (охлаждение)?
- Нет NaN / Inf?

### Визуализация

1. **rb(t)** — радиус зоны разгазирования
2. **p(r)** при $t = [100, 1000, 10000, 86400]$ с
3. **Sg(r)** при тех же $t$
4. **T(r)** при тех же $t$

Сохранить в `method_of_moments/results/`.

### Физическая проверка

- $p(r_w) \to p_{wf}$, $p(R_{ext}) \to p_0$ (при ранних $t$)?
- $S_g(r > r_b) = 0$?
- $T(r_w) < T_0$ (охлаждение из-за JT и дегазации)?

---

Если что-то нефизично — сообщи, предложи диагностику. Не подгоняй параметры, чтобы «получилось красиво»: сначала объясни причину.
