---
tags:
  - план
  - валидация
  - аналитический
date: 2026-08-29
issue: VAL-001
github: 16
branch: val/val-001/dupuit-steady-state
status: готов к реализации
audit:
  date: 2026-08-29
  found: 0
  auto-fixed: 0
  manual-required: 0
---

# VAL-001: Однофазный стационарный приток (формула Дюпюи)

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Создай ветку: `git checkout -b val/val-001/dupuit-steady-state`
3. Прогони тесты (baseline): `cd numerical_solver && .venv\Scripts\python -m pytest tests/ -v`
4. Начни с шага 1. После каждого шага — pytest

## Подтип

**Аналитический.** Точное решение для однофазного стационарного радиального потока.

## Эталонное решение

### Условия применимости

- Sg = 0 (однофазный, только нефть)
- co = 0 (Bo не зависит от p)
- p > pb(Rs0) = 9.4 МПа во всех ячейках (однофазная зона)
- Стационарный режим (∂/∂t = 0)
- μ_JT = 0, L = 0 (нет тепловых источников)

При этих условиях mob_o = kro/(μ_o·Bo) = 1/(μ_o·Bo) = const → формулы **точные**.

### Формулы

**Дебит (Дюпюи):**
```
q_o_std = 2πkh · mob_o · (p_ext − p_wf) / ln(R_ext/r_w)
```
где mob_o = 1/(μ_o · Bo).

**Профиль давления:**
```
p(r) = p_wf + (p_ext − p_wf) · ln(r/r_w) / ln(R_ext/r_w)
```

**Скорость фильтрации:**
```
u_o(r) · r = const = Q_o / (2πh)
```

**Температура:**
```
T → T_ext (конвекция + теплопроводность вымывают начальное отклонение)
```

### Параметры

| Параметр | Значение | Единицы | Примечание |
|---|---|---|---|
| r_w | 0.1 | м | |
| R_ext | 50.0 | м | |
| h | 10.0 | м | |
| k | 1e-13 | м² | |
| φ | 0.2 | — | |
| p_ext | 20e6 | Па | = p0 |
| p_wf | 15e6 | Па | > pb = 9.4 МПа |
| T0 | 350.0 | К | |
| Rs0 | 50.0 | м³ст/м³ст | |
| ρ_o_ст | 850.0 | кг/м³ | |
| ρ_g_ст | 0.85 | кг/м³ | |
| co | 0.0 | 1/Па | Bo = const |
| μ_JT_oil | 0.0 | К/Па | нет JT |
| μ_JT_gas | 0.0 | К/Па | нет JT |
| L_degas | 0.0 | Дж/кг | нет дегазации |
| N | 20 | — | число ячеек |
| dt | 3600 | с | шаг интегрирования |
| T_simulation | 86400 | с | 1 сутки (давление) |
| T_simulation_T | 1800000 | с | 500 часов (температура, R=5 м) |

### Вычисленные эталоны

| Величина | Значение | Единицы |
|---|---|---|
| Bo | 1.1672031562304623 | — |
| μ_o | 0.0009478980461738412 | Па·с |
| mob_o | 903.8407518315244 | 1/(Па·с) |
| q_o_std | 4.5690724516e-03 | м³ст/с |
| q_o_std | 394.77 | м³ст/сут |
| G_o | −4.5690724516e-03 | м³ст/с |
| pb(Rs0) | 9 426 155 | Па |

## Метрики

| Метрика | Формула | Tolerance | Обоснование |
|---|---|---|---|
| Дебит | q_o_std vs Дюпюи | rel = 1e-10 | mob_o = const → точная формула |
| Давление | p(r_j) vs лог-формула | rel = 1e-12 | AnalyticalHydroSolver строит точный профиль |
| Стационарность | G_o = const на всех гранях | rel = 1e-12 | mob = const, стационар |
| Сохранение массы | G_o[j+1] − G_o[j] = 0 | нормированная < 1e-12 | стационар |
| u_o · r = const | max|u·r − u·r[0]| / |u·r[0]| | < 1e-10 | закон сохранения в цилиндрических координатах |
| Температура | max|T − T_ext| | < 1.0 К | конвекция + теплопроводность, маленькая сетка |
| GOR | −G_g[0] / (−G_o[0]) | = Rs0 ± rel 1e-12 | весь газ растворён (Sg=0) |

## Подводные камни

- ✅ **p_wf > pb** — однофазность гарантирована (15 МПа > 9.4 МПа)
- ✅ **co = 0** — Bo = const (Standing: Bo не зависит от p, только от Rs). Формула Дюпюи точная
- ✅ **μ_o = const** — Beggs-Robinson: μ_o зависит только от Rs. При Rs=Rs0=const → μ_o=const → mob_o=const
- ✅ **μ_JT = L = 0** — температурный эталон T → T_ext
- ⚠️ **Конвергенция T медленная при R=50 м.** Решение: маленькая сетка R=5 м для температурного теста (шаг 4 создаёт Simulator вручную, не через val001.json)
- ⚠️ **AnalyticalHydroSolver не решает задачу, а подставляет p(r).** VAL-001 верифицирует инфраструктуру (грани, проводимости, upstream, знаки), не гидродинамику
- ✅ **Знаки потоков** — G_o < 0 при добыче, q_o_std = -G_o[0] > 0. См. [[конвенции-знаков]]
- ✅ **Воспроизводимость** — детерминированный результат, нет random seed
- ✅ **Время расчёта** — < 5 с для 24 шагов (давление) + ~2 с для 500 шагов (температура)

**Ключевые vault-заметки:**
- [[конвенции-знаков]] — положительное направление = от скважины
- [[словарь-код-физика]] — соответствие переменных кода и физики
- [[контейнер-simulation-history]] — структура SimulationHistory

## Этапы

### Шаг 1: Создать configs/val001.json

**Цель:** конфиг с параметрами из таблицы выше.
**Файлы:** `numerical_solver/configs/val001.json`

**Что сделать:**
1. Скопировать baseline.json, изменить:
   - `"co_undersaturated": 0.0` — явно указать (default и так 0, но для самодокументирования)
   - thermal: `"mu_JT_oil": 0.0`, `"mu_JT_gas": 0.0`, `"L_degas": 0.0`
   - time.history: **один** интервал `{"dt": 86400, "control": "pressure", "p_wf": 15e6}` (убрать второй)
   - grid.N = 20
2. Проверить: `load_config("configs/val001.json")` не падает

**Проверка:** `python -c "from gpn_multiphase_solver.io.config import load_config; load_config('configs/val001.json')"`

### Шаг 2: Создать tests/test_val001.py — дебит и давление

**Цель:** проверить q_o_std и p(r) через Factory → run.
**Файлы:** `numerical_solver/tests/test_val001.py`
**Шаблон:** `numerical_solver/tests/test_simulator.py` (строки 1–70) — паттерн import'ов и создания Simulator.

**Все import'ы файла** (для шагов 2–5):
```python
from pathlib import Path
import numpy as np
import pytest

from gpn_multiphase_solver.io.config import load_config, RockConfig
from gpn_multiphase_solver.factory import SimulatorFactory
from gpn_multiphase_solver.io.output import save_npz
from gpn_multiphase_solver.pvt.standing import StandingFullPVT
from gpn_multiphase_solver.pvt.relperm import CoreyRP
from gpn_multiphase_solver.grid.log_radial import LogRadialGrid
from gpn_multiphase_solver.hydro.analytical import AnalyticalHydroSolver
from gpn_multiphase_solver.energy.tridiag import TridiagEnergySolver
from gpn_multiphase_solver.state import SimulationState, BoundaryConditions
from gpn_multiphase_solver.bc import PressureControl
from gpn_multiphase_solver.simulator import Simulator, TimeSchedule, ScheduleInterval
```
Шаги 2, 3, 5 используют первый блок (Factory-path). Шаг 4 использует всё (ручное создание Simulator).

**Что сделать:**
1. Загрузить val001.json: `config = load_config(VAL001_PATH)`, `simulator, initial_state = SimulatorFactory.from_config(config)`
2. Запустить: `history = simulator.run(initial_state)`
3. Вычислить эталонный mob_o. Два подхода (выбрать один):
   - **Через PVT из simulator:** `pvt = simulator._pvt`, `Bo = pvt.Bo(np.array([20e6]), np.array([50.0]))[0]`, `mu = pvt.mu_o(np.array([20e6]), np.array([50.0]))[0]`, `mob_o = 1.0 / (mu * Bo)` — verifies that PVT работает (Bo не зависит от p, можно подставить любое)
   - **Из эталонных констант (таблица выше):** `mob_o = 903.8407518315244` — тест будет независимым от PVT. **Предпочтительнее**, если цель — верифицировать инфраструктуру потоков, а не PVT
4. Эталонный дебит: `q_exact = 2*np.pi*k*h * mob_o * (p_ext - p_wf) / np.log(R_ext/r_w)`
5. Сравнить: `history.well_data[-1].q_o_std == approx(q_exact, rel=1e-10)`
6. Эталонное давление: `p_exact = p_wf + (p_ext - p_wf) * np.log(r/r_w) / np.log(R_ext/r_w)` — вычислить на `simulator._grid.r_centers`
7. Сравнить: `np.allclose(history.states[-1].p, p_exact, rtol=1e-12)`
8. Потоки: G_o = `history.hydro_results[-1].G_o` — массив [N+1] на гранях. Проверить `allclose(G_o, G_o[0], rtol=1e-12)`.
   **Конвенция знаков:** G_o < 0 при добыче (поток к скважине). q_o_std = -G_o[0] > 0. См. `vault/knowledge/decisions/конвенции-знаков.md`.
9. Проверить u·r = const: `u_o = history.hydro_results[-1].u_o`, `r_faces = simulator._grid.r_faces`, `u_r = u_o * r_faces`, `allclose(u_r, u_r[0], rtol=1e-10)`

**Проверка:** `pytest tests/test_val001.py -v`

### Шаг 3: Добавить тест баланса масс и GOR

**Цель:** проверить инварианты.
**Файлы:** `numerical_solver/tests/test_val001.py` (расширить)

**Что сделать:**
1. Баланс: `G_o[j+1] − G_o[j]` ≈ 0 для каждой ячейки
2. GOR: `−G_g[0] / (−G_o[0])` = Rs0

**Проверка:** `pytest tests/test_val001.py -v`

### Шаг 4: Добавить тест температуры

**Цель:** T → T_ext при μ_JT=0, L=0.
**Файлы:** `numerical_solver/tests/test_val001.py` (расширить)

**Важно:** Этот тест **не использует val001.json** (R=50 м слишком большое для конвергенции T). Создать Simulator вручную в тесте, как `_make_simulator()` в `test_simulator.py` (строка 50).

**Что сделать:**
1. `grid = LogRadialGrid(r_well=0.1, R_ext=5.0, h=10.0, N=5, k=1e-13)`
2. `pvt = StandingFullPVT(rho_o_std=850.0, rho_g_std=0.85, T0=350.0, Rs0=50.0, co_undersaturated=0.0, mu_JT_oil_val=0.0, mu_JT_gas_val=0.0, L_degas_val=0.0)`
3. `rp = CoreyRP(0.2, 0.05, 2.0, 2.0)`
4. `hydro = AnalyticalHydroSolver(grid, pvt, rp)`
5. `rock = RockConfig(porosity=0.2, permeability=1e-13)` — **нужен import RockConfig из io.config**
6. `energy = TridiagEnergySolver(grid, pvt, rock)`
7. BC: `bc = BoundaryConditions(well=PressureControl(15e6), p_ext=20e6, T_ext=350.0, Rs_ext=50.0, Sg_ext=0.0)`
8. `schedule = TimeSchedule(dt_integration=3600.0, intervals=[ScheduleInterval(dt=1800000.0, bc=bc)])` — 500 шагов по 3600 с = 1800000 с
9. `sim = Simulator(grid=grid, hydro=hydro, energy=energy, pvt=pvt, schedule=schedule)`
10. Начальное состояние: `SimulationState(p=np.full(5, 20e6), Sg=np.zeros(5), Rs=np.full(5, 50.0), T=np.full(5, 340.0), regime=np.full(5, 2, dtype=int), t=0.0)` — **T=340 ≠ T_ext=350**
11. `history = sim.run(initial_state)`
12. Проверить: `np.max(np.abs(history.states[-1].T - 350.0)) < 1.0`

**Подводный камень:** при R=50 м конвекция не успевает за 500 часов → маленькая сетка R=5 м.

**Проверка:** `pytest tests/test_val001.py -v`

### Шаг 5: Сквозной pipeline-тест

**Цель:** JSON → Factory → run → save_npz → load → проверка.
**Файлы:** `numerical_solver/tests/test_val001.py` (расширить)
**Шаблон:** `numerical_solver/tests/test_output.py`, класс `TestPipelineRoundtrip` (~строка 250) — аналогичный тест для baseline.json.

**Что сделать:**
1. `config = load_config(VAL001_PATH)`, `simulator, initial = SimulatorFactory.from_config(config)`
2. `history = simulator.run(initial)`
3. `save_npz(history, simulator._grid, tmp_path / "val001.npz")`
4. `data = np.load(tmp_path / "val001.npz")`
5. Проверить: `data['times'][-1] == pytest.approx(86400.0)` (один интервал 86400 с)
6. Проверить: `data['q_o_std'][-1] > 0` (ненулевой дебит)
7. Проверить: `data['p'].shape == (N_saved, 20)` (20 ячеек)

**Проверка:** `pytest tests/test_val001.py -v`

### Шаг 6: Обновить vault

**Цель:** зафиксировать результаты.
**Файлы:** `vault/roadmap/валидационные кейсы.md`, GitHub issue #16

**Что сделать:**
1. Обновить статус VAL-001: 🔴 → ✅ ПРОЙДЕН
2. Добавить комментарий к issue #16 с результатами
3. Закрыть issue

## Критерии завершения

- [ ] val001.json создан и загружается
- [ ] Дебит совпадает с Дюпюи (rel=1e-10)
- [ ] Давление = лог-профиль (rel=1e-12)
- [ ] G_o = const (стационар)
- [ ] u·r = const (сохранение массы)
- [ ] T → T_ext (atol=1 К)
- [ ] GOR = Rs0
- [ ] Pipeline: JSON → npz → load ОК
- [ ] Все 532+ существующих теста зелёные
- [ ] Vault и GitHub обновлены
