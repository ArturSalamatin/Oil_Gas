---
tags:
  - план
  - рефакторинг
date: 2026-10-03
issue: DEBT-026
github: 56
branch: refactor/debt-026/rs-check-any-pressure-history
status: готов к реализации
---

# DEBT-026: проверка $R_s$, верная при любой истории давления

**Подтип:** рефакторинг проверочного модуля примеров (`numerical_solver/examples/rs_analytics.py`) + документация. Ядро решателя (`gpn_multiphase_solver/`) и прототип (`HydroSolverPrototype/`) **не меняются**.

**Решения пользователя (2026-10-03, при планировании):**

| Вопрос | Решение |
|---|---|
| Условие для однофазных ячеек | $R_s \le R_s^{eq}(p)$ (вариант 2). Число ячеек с $R_s > R_{s,0}$ печатается отдельной строкой как наблюдение, не как нарушение |
| Наложение на `rs_profiles.png` | Кружки $R_s^{eq}(p)$ **только в двухфазных ячейках** + прежняя линия $R_{s,0}$ |
| Вертикальная линия «фронт $r_b$» | Подпись по ситуации: если множества «$p < p_b$» и `regime == 1` совпадают — прежняя «фронт $r_b$ = … м»; иначе «изобара $p_b$: $r$ = … м» |
| Какие README править | Только где проверка ломается или где описан меняющийся рисунок: сводный `examples/README.md`, 03 (описание рисунка), 04, 04a, 05, 12, 13b. Фразы «$R_s = \min(\ldots)$ с точностью …» в 03 (§3), 19, 20, 21 **не трогать** — при падающем давлении они верны. Плюс одна фраза докстринга `pvt_plot._physical_rs` |

---

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-026 в `vault/roadmap/известные баги и технический долг.md` (секция `### DEBT-026`) и issue: `gh issue view 56 --repo ArturSalamatin/Oil_Gas`.
3. Создай ветку от базовой ветки направления (в `master` каталога `numerical_solver/` нет):
   ```powershell
   git checkout numerical_scheme/implementation
   git checkout -b refactor/debt-026/rs-check-any-pressure-history
   ```
4. Все команды pytest — из `numerical_solver/`; Python — `.venv\Scripts\python`.
5. Baseline:
   ```powershell
   cd numerical_solver
   .venv\Scripts\python -m pytest tests/ --collect-only -q            # ожидается 1210
   .venv\Scripts\python -m pytest tests/ -m "not slow" --collect-only -q  # ожидается 987/1210
   .venv\Scripts\python -m pytest tests/ -m "not slow" -q              # быстрый уровень, ~70 с, зелёный
   ```
   Замер при планировании (2026-10-03, HEAD `779b78a`): 1210 тестов всего, 987 в быстром уровне. Запомни время быстрого уровня.
6. Прототип не меняется — его тесты и регрессию не запускать.
7. Начни с шага 1. После каждого шага — тест шага и регресс по полю «Регресс»; полный прогон — в конце (`/implement` §3.1).

---

## 1. Суть проблемы (для читателя без контекста)

### Физика

В модели Black Oil газосодержание $R_s$ (м³ст газа на м³ст нефти) не имеет собственной кинетики. Равновесие задаёт его по-разному в двух режимах ячейки. Режим хранится в `SimulationState.regime` (`numerical_solver/gpn_multiphase_solver/state.py:23`): `1` — двухфазная (свободный газ есть, $S_g$ — неизвестная, $R_s = R_s^{eq}(p)$), `2` — однофазная ($S_g = 0$, $R_s$ — неизвестная).

- **Двухфазная ячейка:** нефть насыщена, $R_s = R_s^{eq}(p)$ — равенство.
- **Однофазная ячейка:** растворённый газ переносится с нефтью, $R_s$ — самостоятельная переменная. Равновесие даёт только неравенство $R_s \le R_s^{eq}(p)$: недонасыщенность допустима, пересыщение — нет.

### Что делает код сейчас

`numerical_solver/examples/rs_analytics.py` (151 строка) сравнивает численное $R_s$ последней записи с $\min(R_s^{eq}(p), R_{s,0})$ **во всех ячейках** и требует, чтобы множества «$p < p_b$» и «$S_g > 10^{-12}$» совпадали. Формула верна, только пока давление в каждой ячейке падает: однофазная нефть тогда исходная, с $R_{s,0}$.

При восстановлении давления (переменный режим скважины) свободный газ растворяется обратно лишь в пределах своего запаса. Когда запас кончается, нефть остаётся **недонасыщенной и ниже $p_b$**: $S_g = 0$, $R_s < R_s^{eq}(p)$. Решатель это воспроизводит; проверка печатает «совпадают: False» и ошибку.

| Пример | Последняя запись | $\max\lvert\Delta R_s\rvert$ сейчас | ячеек $p<p_b$ / $S_g>0$ | Причина |
|---|---|---|---|---|
| 12 | 15 сут | $2.5\cdot10^{-2}$ | 47 / 46 | одна ячейка (117.9 м) за стационарным фронтом теряет газ при возврате давления |
| 13b | 30 сут, 10.75 МПа после суток при 6 МПа | 2.437 (8.1 % $R_{s,0}$) | 44 / 14 | 30 ячеек недонасыщенной нефти на 0.9–75 м |
| 04a | 3 сут | $9.9\cdot10^{-14}$ | 65 / 70 | газ остался в 5 ячейках с $p > p_b$ (остаток переходного процесса; там таблица даёт $R_s^{eq} = R_{s,0}$) |

### Почему не $R_s \le \min(R_s^{eq}(p), R_{s,0})$

$R_{s,0}$ — не верхняя граница. Газ подвижнее нефти и копится у забоя (GOR выше $R_{s,0}$). Если затем давление поднимется выше $p_b(R_{s,0})$, а PVT допускает $R_s^{eq}(p) > R_{s,0}$ (Стендинг: `numerical_solver/gpn_multiphase_solver/pvt/standing.py:85` — без ограничения сверху), газ растворится до $R_s > R_{s,0}$. В текущих примерах этого нет (у табличных PVT $R_s^{eq} \le R_{s,0}$, у Стендинга нет восстановления давления), но условие с $R_{s,0}$ дало бы ложное «нарушение» на первом же таком сценарии.

### Почему отбор по `regime`, а не по $S_g > 0$

Прототип обнуляет малую отрицательную $S_g$ в активной (двухфазной) ячейке, оставляя её двухфазной: `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/blackoil.py:327` (`tiny=mask&(trial.sg<0)&(trial.sg>=-self.sg_switch_tol); trial.sg[tiny]=0.0`). Отбор по $S_g > 10^{-12}$ отнёс бы такую ячейку к однофазным, и равенство $R_s = R_s^{eq}(p)$ в ней перестало бы проверяться. Тот же выбор сделан в `tests/test_examples.py::TestPwfAlternating::test_repressurization_leaves_undersaturated_oil` (стр. 1988–2019). Режим в `SimulationState` пишет единственный гидро-путь — `PrototypeHydroAdapter` (`gpn_multiphase_solver/hydro/prototype_adapter.py:113`: `regime=np.where(new_proto.gas_active, 1, 2)`).

---

## 2. Текущее состояние (baseline)

### Код

| Функция в `numerical_solver/examples/rs_analytics.py` | Строки | Что делает | Кто вызывает |
|---|---|---|---|
| докстринг модуля | 1–29 | «$R_s$ алгебраически следует за давлением», $\min(\ldots)$ | — |
| `rs_expected(config, pvt, p)` | 36–38 | $\min(R_s^{eq}(p), R_{s,0})$ | `rs_error`, `_draw_rs`, **`tests/test_examples.py:911,919`** (`test_physical_branch_matches_rs_analytics` — сверка с `pvt_plot._physical_rs`) |
| `rs_error(config, history, pvt)` | 41–52 | (max_abs, max_rel) по всем ячейкам | `report_rs` |
| `_degassed_cells(config, history, pvt)` | 55–59 | маска $p < p_b$ и $p_b$ | `front_radius`, `report_rs` |
| `front_radius(config, history, grid, pvt)` | 62–82 | интерполяция изобары $p = p_b$ по $\ln r$ | `_draw_rs`, **`examples/04_table_table/grid_convergence.py:59`** |
| `make_overlay_rs(config)` | 85–94 | замыкание config для хука | `examples/example_runner.py:70,176` |
| `_draw_rs(ax, history, grid, simulator, config)` | 97–121 | кружки $\min(\ldots)$ во всех ячейках, линия $R_{s,0}$, линия «фронт $r_b$» | `make_overlay_rs` |
| `report_rs(config, history, pvt) -> dict` | 124–150 | печать + сравнение множеств; возвращает dict | `examples/example_runner.py:233` (возврат не используется); шпион в `tests/test_examples.py:584` |

Ни одна пример-папка не подменяет наложение `"Rs"` (grep `"Rs"` в `examples/*/main.py` — пусто). Выходы примеров (`examples/*/output/`) в git не хранятся.

### Тесты, покрывающие затронутый код

| Тест | Файл:строки | Уровень | Что проверяет |
|---|---|---|---|
| `test_steady_state_false_skips_steady_analytics` (шпионы `report_rs` и др.) | `tests/test_examples.py:551–597` | быстрый | `report_rs` вызывается при `steady_state=False` |
| `test_gas_active_cells_match_pressure` | `tests/test_examples.py:1854` (14), `:2147` (19–21) | slow | у примеров с падающим давлением активные ячейки совпадают с $p < p_b$ — косвенно подтверждает, что подпись «фронт» у них сохранится |
| `test_physical_branch_matches_rs_analytics` | `tests/test_examples.py:901–921` | slow | `pvt_plot._physical_rs` побитово = `rs_expected` |
| `test_rho_matches_formula` | `tests/test_examples.py:923–` | slow | использует `pvt_plot._physical_rs` |
| `test_repressurization_leaves_undersaturated_oil` | `tests/test_examples.py:1988–2019` | slow | 13b: недонасыщенная нефть ниже $p_b$, в `regime == 1` $R_s = R_s^{eq}(p)$ с `atol=1e-10` |

**Пробел:** ни один тест не проверяет, что `rs_error` мала у всех примеров. Проверка работала только как печать в консоль.

### Зона неприкосновенности

- `rs_expected` — семантика $\min(R_s^{eq}(p), R_{s,0})$ сохраняется (её использует `pvt_plot._physical_rs` через тест побитовой сверки). Меняется только докстринг.
- `front_radius`, `_degassed_cells` — алгоритм не меняется (на них опирается `04_table_table/grid_convergence.py`).
- `make_overlay_rs`, сигнатура `report_rs(config, history, pvt)` — не меняются (вызов в `example_runner.py:233` остаётся как есть).
- `gpn_multiphase_solver/`, `HydroSolverPrototype/` — не трогать.

---

## 3. Целевое состояние

- `report_rs` печатает (формат зафиксирован в шаге 2):
  1. двухфазные ячейки: их число и $\max\lvert R_s - R_s^{eq}(p)\rvert$ (абс. и в % от $R_{s,0}$);
  2. однофазные ячейки: их число, число пересыщенных ($R_s > R_s^{eq}(p) + 10^{-10}$), число ячеек ниже $p_b$ (недонасыщенная нефть); при пересыщении — наибольшее превышение;
  3. диапазон $R_s$, $R_{s,0}$, $p_b$ и число ячеек с $R_s > R_{s,0}$ (наблюдение).
- Сравнение множеств «$p<p_b$» и «$S_g>0$» из печати убрано.
- `rs_error` — только по двухфазным ячейкам; новая `rs_supersaturation` — по однофазным; константа `RS_TOL = 1e-10`.
- `_draw_rs` — кружки $R_s^{eq}(p)$ только в `regime == 1`; подпись вертикальной линии по ситуации.
- Новые тесты: `tests/test_rs_analytics.py` (быстрый уровень, синтетические состояния) и `TestSharedChecks::test_rs_check_all_two_phase_examples` (slow, все примеры с газом).
- README: на 12, 13b объяснение «совпадают: False» больше не нужно.

**Ожидаемые числа после реализации** (проверяются в шаге 5): у всех 18 примеров с газом пересыщенных 0, ошибка в двухфазных $\le 10^{-10}$ (прежние глобальные значения $7\cdot10^{-15}$ … $4\cdot10^{-13}$ у монотонных); однофазных ниже $p_b$: 12 → 1, 13b → 30, остальные → 0; подпись «изобара» ровно у 04a, 12, 13b.

---

## 4. Варианты решения (итог анализа issue #56)

| Вариант | Суть | Решение |
|---|---|---|
| 1 | Разделение по `regime`; однофазные $R_s \le \min(R_s^{eq}(p), R_{s,0})$ | отклонён: $R_{s,0}$ не инвариант Black Oil (§1) |
| **2** | Разделение по `regime`; однофазные $R_s \le R_s^{eq}(p)$; $R_s > R_{s,0}$ — наблюдение | **выбран пользователем** |
| 3 | Оставить формулу, отключать проверку при немонотонном давлении | отклонён: на 12, 13b пропала бы и верная двухфазная часть |

Критерии DEBT: минимальный diff (один модуль + тесты + документы), обратная совместимость (`report_rs`, `rs_expected`, `front_radius`, `make_overlay_rs` — те же имена и сигнатуры), тестируемость (появляются автоматические тесты, которых не было).

---

## 5. Подводные камни (чеклист 2.5)

| Пункт | Статус | Комментарий |
|---|---|---|
| Все call sites найдены | ✅ | grep `rs_analytics\|report_rs\|rs_error\|rs_expected\|_draw_rs\|front_radius` по `numerical_solver/` (§2). Возврат `report_rs` никто не читает |
| Зависимости пакетов | ✅ | новых нет |
| Обратная совместимость API | ✅ | имена и сигнатуры прежние; меняются ключи возвращаемого словаря `report_rs` — потребителей нет |
| Состояние при ошибке | ✅ | функции чистые; пустые маски обработаны явно (нет двухфазных / нет однофазных) — `pvt.Rs_eq` на пустом массиве не вызывается |
| Тесты | ⚠️ | шпион `report_rs` (стр. 584) не зависит от вывода; `test_physical_branch_matches_rs_analytics` зависит от `rs_expected` — не меняем семантику |
| Circular imports | ✅ | импорт-граф не меняется |
| Docstrings / `\eqref` | ✅ | ссылок на уравнения нет; докстринг модуля переписывается |
| Configs | ✅ | не меняются |
| Связь с другими задачами | ✅ | FEAT-019 (переменный режим) — выигрывает; FEAT-028 (`pvt_plot.py`) влит, меняется только докстринг `_physical_rs`. DEBT-035 (#57, план готов) правит README 19, 21 (стр. 191–200) и докстринг `TestStandingCoreyCooling.test_config_follows_decisions` в `tests/test_examples.py` — с этим планом не пересекается (README 19, 21 здесь не трогаются; вставка — в `TestSharedChecks`); при влитии второй из веток возможен только текстовый конфликт соседства, не по смыслу |
| Производительность | ✅ | одна проверка на последней записи |
| Прототип | ✅ | не меняется |
| **`regime` и $S_g$ расходятся на монотонных примерах** | ⚠️ | если у примера с падающим давлением есть ячейка `regime == 1` с $S_g \le 10^{-12}$ (обнулённая отрицательная $S_g$ на фронте), подпись линии сменится на «изобара» без физической причины. **Проверяется замером в шаге 1** (гейт) |
| **`front_radius` при немонотонном $p$** | ⚠️ | `np.searchsorted` корректен, если ячейки с $p<p_b$ образуют префикс (все левее изобары). Для 13b после роста давления профиль немонотонен. **Проверяется замером в шаге 1** (столбец «префикс») |
| Допуск `RS_TOL` | ⚠️ | на табличном PVT при $p \ge p_b$ ветвь $R_s^{eq}(p) = R_{s,0}$ горизонтальна, однофазная $R_s = R_{s,0}$ лежит ровно на границе; шум $\sim10^{-13}$. $10^{-10}$ — запас 3 порядка, тот же порог, что `atol` в тесте 13b |

---

## 6. Шаги

### Шаг 1: Скрипт замера и замер до правки (гейт)

**Цель:** зафиксировать числа прежней и новой проверки на всех примерах с газом и подтвердить предпосылки (маски `regime`/$S_g$, префикс $p<p_b$) до правки кода.

**Файлы:**
- новый `vault/issues/debt-026/probes/rs_check_numbers.py`
- новый `vault/issues/debt-026/probes/rs_check_before.txt` (вывод)

**Контекст:** README и реестр содержат числа прежней проверки; новые числа ещё никто не мерил. Скрипт считает новую проверку **независимо от `rs_analytics`** (прямыми формулами) — поэтому одним и тем же скриптом можно мерить и до, и после правки модуля, а в конце он печатает вывод `rs_analytics.report_rs` — ровно то, что печатает пример. Прецедент расположения — `vault/issues/feat-023/probes/plan_numbers.py`. Скрипты вне pytest должны сами подключать прототип через `sys.path` (`tests/conftest.py` делает это только для pytest).

**Что сделать:**
1. Создать `vault/issues/debt-026/probes/rs_check_numbers.py`:

```python
"""DEBT-026: числа проверки R_s на всех примерах с газом (до и после правки).

Для каждого примера с Rs0 > 0 — расчёт штатного конфига; на последней записи:
  прежняя проверка: max|Rs - min(Rs_eq(p), Rs0)| по всем ячейкам,
    ячеек p < pb и ячеек Sg > 1e-12;
  новая — считается здесь прямыми формулами, независимо от rs_analytics:
    ячеек regime == 1 и max|Rs - Rs_eq(p)| в них; однофазных (regime == 2),
    пересыщенных из них (Rs > Rs_eq(p) + 1e-10) и наибольшее Rs - Rs_eq(p);
    однофазных с p < pb; ячеек Rs > Rs0 + 1e-10;
  предпосылки плана:
    mask(p < pb) == mask(regime == 1)   — подпись линии «фронт» или «изобара»;
    mask(regime == 1) == mask(Sg > 1e-12) — режим и насыщенность не расходятся;
    ячейки p < pb образуют префикс      — front_radius (searchsorted) корректен;
  затем вывод rs_analytics.report_rs — как его печатает пример.

Запуск (из numerical_solver), все примеры ~4 мин:
    .venv\\Scripts\\python ..\\vault\\issues\\debt-026\\probes\\rs_check_numbers.py [--out файл] [папка ...]
--out — копия вывода в файл UTF-8. Перенаправление «| Out-File» в
PowerShell 5.1 не годится: оно перекодирует вывод через кодировку консоли
и портит кириллицу.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOLVER = HERE.parents[3] / "numerical_solver"
for p in (SOLVER, SOLVER / "examples",
          SOLVER / "HydroSolverPrototype" / "Prototype_1.0.3"):
    sys.path.insert(0, str(p))

# Консоль Windows (cp1251) не печатает «≤», «…», «³» — BUG-009.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8")

from gpn_multiphase_solver.factory import SimulatorFactory  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
import rs_analytics  # noqa: E402

EXAMPLES = SOLVER / "examples"
TOL = 1e-10          # тот же допуск, что RS_TOL в rs_analytics (после правки)


def _is_prefix(mask: np.ndarray) -> bool:
    """True, если True-ячейки маски идут подряд от забоя (или их нет)."""
    k = int(np.count_nonzero(mask))
    return bool(np.all(mask[:k]) and not np.any(mask[k:]))


def probe(name: str) -> None:
    cfg = load_config(EXAMPLES / name / "config.json")
    Rs0 = cfg.initial_conditions.Rs0
    if Rs0 <= 0.0:
        return
    sim, init = SimulatorFactory.from_config(cfg)
    hist = sim.run(init)
    pvt = sim._energy._pvt          # тот PVT, что передаёт report_rs пример
    st = hist.states[-1]
    pb = float(pvt.pb(np.array([Rs0]))[0])

    below = st.p < pb
    gas = st.Sg > 1e-12
    two = st.regime == 1
    one = st.regime == 2
    rs_eq = pvt.Rs_eq(st.p)

    old = float(np.abs(np.minimum(rs_eq, Rs0) - st.Rs).max())
    err2 = float(np.abs(rs_eq[two] - st.Rs[two]).max()) if two.any() else 0.0
    exc = (st.Rs - rs_eq)[one]
    n_bad = int(np.count_nonzero(exc > TOL))
    exc_max = float(exc.max()) if exc.size else float("nan")
    n_under = int(np.count_nonzero(one & below))
    n_above = int(np.count_nonzero(st.Rs > Rs0 + TOL))

    print(f"\n=== {name}  (t = {st.t / 86400:.3f} сут, N = {st.p.size}) ===")
    print(f"  прежняя: max|Rs - min(Rs_eq, Rs0)| = {old:.3e}; "
          f"p<pb: {int(below.sum())}, Sg>1e-12: {int(gas.sum())}")
    print(f"  новая: двухфазных {int(two.sum())}, max|Rs - Rs_eq(p)| = {err2:.3e}; "
          f"однофазных {int(one.sum())}, пересыщенных {n_bad} "
          f"(max Rs - Rs_eq = {exc_max:.3e}), ниже pb {n_under}; Rs > Rs0: {n_above}")
    print(f"  предпосылки: (p<pb)==(regime 1): {np.array_equal(below, two)}; "
          f"(regime 1)==(Sg>1e-12): {np.array_equal(two, gas)}; "
          f"префикс p<pb: {_is_prefix(below)}")
    print("  --- report_rs ---")
    rs_analytics.report_rs(cfg, hist, pvt)


class _Tee:
    """Печать одновременно в консоль и в файл UTF-8."""

    def __init__(self, path):
        self._console = sys.stdout
        self._file = open(path, "w", encoding="utf-8")

    def write(self, s):
        self._console.write(s)
        self._file.write(s)

    def flush(self):
        self._console.flush()
        self._file.flush()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--out"]:
        sys.stdout = _Tee(args[1])
        args = args[2:]
    names = args or sorted(
        d.name for d in EXAMPLES.iterdir() if (d / "config.json").is_file())
    for n in names:
        probe(n)
    sys.stdout.flush()
```

2. Запустить, сохранить вывод (файл пишет сам скрипт, UTF-8):
   ```powershell
   cd numerical_solver
   .venv\Scripts\python ..\vault\issues\debt-026\probes\rs_check_numbers.py --out ..\vault\issues\debt-026\probes\rs_check_before.txt
   ```
   (`timeout` ≥ 600 с; 18 примеров с газом, 01 и 02 пропускаются.)

**Гейт — сверить с ожиданием; при расхождении остановиться и сообщить пользователю, план не продолжать:**

| Проверка | Ожидание |
|---|---|
| «прежняя» совпадает с таблицей `examples/README.md:409–425` | 03 $1.4\cdot10^{-14}$ (16/16), 04/07–09 $2.1\cdot10^{-14}$ (26/26), 04a $9.9\cdot10^{-14}$ (65/70), 05 $7.1\cdot10^{-15}$ (6/6), 06 $2.5\cdot10^{-14}$ (26/26), 10 $1.4\cdot10^{-14}$ (29/29), 11 $7.1\cdot10^{-15}$ (50/50), 12 $2.5\cdot10^{-2}$ (47/46), 13a $6.8\cdot10^{-14}$ (47/47), 13b 2.437 (44/14), 14 $2.6\cdot10^{-13}$ (47/47), 15 $3.5\cdot10^{-13}$ (46/46), 19 $5.7\cdot10^{-14}$ (334/334), 20 $4.0\cdot10^{-13}$ (289/289), 21 $2.8\cdot10^{-14}$ (328/328) — порядок величины и счётчики |
| `(regime 1)==(Sg>1e-12)` | **True у всех 18**. Если False у какого-то примера — подпись линии и число двухфазных в README зависят от выбора критерия; решение за пользователем |
| `(p<pb)==(regime 1)` | True у всех, кроме 04a, 12, 13b (там False) |
| `префикс p<pb` | True у всех (включая 13b). Если False — `front_radius` рисует линию не там; зафиксировать в «Обнаруженных проблемах», сообщить пользователю |
| новая: пересыщенных | 0 у всех |
| новая: ниже pb | 12 → 1, 13b → 30, остальные → 0 |
| новая: двухфазных | 04a → 70, 12 → 46, 13b → 14; у остальных = число $p<p_b$ |
| новая: max\|Rs − Rs_eq(p)\| | $\le 10^{-10}$ у всех |
| Rs > Rs0 | 0 у всех |

**Проверка после этого шага:**
- Регресс: `--collect-only -q` (код решателя и тесты не менялись) — 1210.

**Подводные камни:** скрипт печатает и старый `report_rs` (до правки) — это ожидаемо; после шага 2 тот же скрипт напечатает новый формат.

**Зависимости:** блокирует шаги 2–7.

**Оценка:** ~80 строк, ~10 мин (из них ~4 мин расчёт).

---

### Шаг 2: Новая проверка в `rs_analytics.py` + модульные тесты (быстрый уровень)

**Цель:** проверка разделена по режиму ячейки; добавлены быстрые тесты на синтетических состояниях.

**Файлы:**
- `numerical_solver/examples/rs_analytics.py` (переписать докстринг модуля, `rs_expected` — только докстринг, `rs_error`, новая `rs_supersaturation`, `front_radius` — только первая строка докстринга, `_draw_rs`, `report_rs`)
- новый `numerical_solver/tests/test_rs_analytics.py`

**Контекст:** см. §1. Тесты пишутся первыми: создать `tests/test_rs_analytics.py`, запустить — убедиться, что падают на старом коде (нет `rs_supersaturation`, `RS_TOL`, ключей `n_supersaturated` и т. д.), затем переписать модуль. Синтетические состояния строятся на настоящем PVT примеров (`_create_pvt(load_config(...))` — без расчёта, доли секунды), поэтому тесты попадают в быстрый уровень (фикстура `results` не используется). PVT примера 04 — таблица, $R_{s,0} = 30$, $p_b = 15$ МПа, при $p \ge 15$ МПа $R_s^{eq} = 30$. PVT примера 03 — Стендинг, $R_{s,0} = 50$, $R_s^{eq}(p)$ без ограничения сверху.

**Что сделать:**

1. Создать `numerical_solver/tests/test_rs_analytics.py`:

```python
"""Проверка R_s общего модуля examples/rs_analytics.py (DEBT-026).

Проверка обязана быть верной при любой истории давления:
  двухфазная ячейка (regime == 1): Rs = Rs_eq(p);
  однофазная (regime == 2):        Rs <= Rs_eq(p) — недонасыщенность допустима.
Прежняя формула Rs = min(Rs_eq(p), Rs0) во всех ячейках верна только при
монотонно падающем давлении и на примерах 12, 13b печатала «не совпадают».

Состояния синтетические, PVT — настоящий, примеров 04 (таблица, Rs0 = 30,
pb = 15 МПа) и 03 (Стендинг, Rs0 = 50). Расчёта нет — быстрый уровень.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gpn_multiphase_solver.factory import _create_pvt  # noqa: E402
from gpn_multiphase_solver.io.config import load_config  # noqa: E402
from gpn_multiphase_solver.state import SimulationState  # noqa: E402

# Модуль примеров, не пакета: путь только до examples/ (как в
# test_energy_balance_examples.py).
_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

import rs_analytics  # noqa: E402

MPA = 1e6
R = np.geomspace(0.1, 100.0, 6)        # центры ячеек, м (только для рисунка)


def _case(name):
    """(config, pvt) примера без расчёта."""
    cfg = load_config(_EXAMPLES / name / "config.json")
    return cfg, _create_pvt(cfg)


def _history(p_mpa, Rs, regime):
    """История из одного состояния: rs_analytics читает только states[-1]."""
    p = np.asarray(p_mpa, float) * MPA
    regime = np.asarray(regime, int)
    Sg = np.where(regime == 1, 0.1, 0.0)   # в проверку Sg не входит
    st = SimulationState(p=p, Sg=Sg, Rs=np.asarray(Rs, float),
                         T=np.full(p.size, 350.0), regime=regime, t=0.0)
    return SimpleNamespace(states=[st])


def _report(cfg, hist, pvt, capsys):
    """report_rs без засорения вывода теста."""
    rep = rs_analytics.report_rs(cfg, hist, pvt)
    capsys.readouterr()
    return rep


# ── Падающее давление: прежняя и новая проверки согласны ──

def test_monotone_pressure_passes(capsys):
    """Фронт на 15 МПа: левее газ (Rs = Rs_eq), правее исходная нефть (Rs0).

    Ожидание: ошибка в двухфазных ровно 0 (одна функция от одного p),
    нарушений нет, однофазных ниже pb нет.
    """
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = [1, 1, 1, 1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[4:] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_two_phase"] == 4
    assert rep["n_supersaturated"] == 0
    assert rep["n_single_below_pb"] == 0


# ── Восстановление давления: случай DEBT-026 ──

def test_repressurization_undersaturated_is_not_violation(capsys):
    """Однофазная нефть ниже pb с Rs < Rs_eq(p) — допустимое состояние.

    Картина 13b на конце 30 сут: газ только у забоя, дальше до изобары
    недонасыщенная нефть. Прежняя формула min(Rs_eq, Rs0) дала бы здесь
    ошибку 2 — это и проверяется первой строкой, чтобы тест не стал
    тавтологией. Новая: нарушений нет, три ячейки ниже pb учтены.
    """
    cfg, pvt = _case("04_table_table")
    p = [10.75, 11, 12, 13, 16, 18]
    regime = [1, 2, 2, 2, 2, 2]
    p_pa = np.array(p, float) * MPA
    Rs = pvt.Rs_eq(p_pa)
    Rs[1:4] -= 2.0                         # недонасыщенность 2 м³ст/м³ст
    Rs[4:] = 30.0
    hist = _history(p, Rs, regime)
    old = np.abs(rs_analytics.rs_expected(cfg, pvt, p_pa) - Rs).max()
    assert old == pytest.approx(2.0)       # прежняя проверка «не совпадают»
    rep = _report(cfg, hist, pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_supersaturated"] == 0
    assert rep["n_single_below_pb"] == 3


# ── Что проверка обязана ловить ──

def test_supersaturated_single_phase_is_violation(capsys):
    """Однофазная ячейка с Rs > Rs_eq(p) — газ растворился сверх равновесия."""
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 16]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] += 0.5
    Rs[2] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 1
    assert rep["max_excess"] == pytest.approx(0.5)


def test_two_phase_mismatch_is_reported(capsys):
    """Двухфазная ячейка с Rs != Rs_eq(p): задержка выделения или чужой PVT."""
    cfg, pvt = _case("04_table_table")
    p = [10, 12, 16]
    regime = [1, 1, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1] -= 1e-3
    Rs[2] = 30.0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["max_abs"] == pytest.approx(1e-3)
    assert rep["max_rel"] == pytest.approx(1e-3 / 30.0)


def test_tolerance_on_flat_branch(capsys):
    """На табличном PVT при p >= pb Rs_eq = Rs0: шум 1e-12 — не нарушение.

    Однофазная Rs = Rs0 лежит ровно на границе Rs <= Rs_eq(p); без допуска
    RS_TOL шум Ньютона ~1e-13 давал бы ложные «пересыщения».
    """
    cfg, pvt = _case("04_table_table")
    p = [10, 16, 18]
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1:] += 1e-12
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 0


def test_rs_above_rs0_is_observation_not_violation(capsys):
    """Стендинг, p выше pb(Rs0): Rs0 < Rs < Rs_eq(p) — допустимо.

    Газ, скопившийся у забоя, при росте давления растворяется сверх Rs0.
    Условие Rs <= min(Rs_eq, Rs0) сочло бы это нарушением (вариант 1,
    отклонён); здесь — только счётчик наблюдения.
    """
    cfg, pvt = _case("03_standing_corey")
    Rs0 = cfg.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    p = np.array([0.5, 1.5, 1.5]) * pb / MPA
    regime = [1, 2, 2]
    Rs = pvt.Rs_eq(p * MPA)
    assert Rs[1] > Rs0 + 1.0               # предпосылка: у Стендинга есть запас
    Rs[1] = Rs0 + 1.0
    Rs[2] = Rs0
    rep = _report(cfg, _history(p, Rs, regime), pvt, capsys)
    assert rep["n_supersaturated"] == 0
    assert rep["n_above_rs0"] == 1


def test_no_two_phase_cells(capsys):
    """Газа нет нигде: двухфазная мера — ноль, без вызова Rs_eq на пустом массиве."""
    cfg, pvt = _case("04_table_table")
    rep = _report(cfg, _history([16, 18], [30.0, 30.0], [2, 2]), pvt, capsys)
    assert rep["max_abs"] == 0.0
    assert rep["n_two_phase"] == 0


# ── Рисунок rs_profiles.png ──

def _draw(cfg, pvt, hist):
    """Наложение на пустые оси; возвращает (кружки, подписи линий)."""
    fig, ax = plt.subplots()
    grid = SimpleNamespace(r_centers=R[:hist.states[-1].p.size])
    sim = SimpleNamespace(_energy=SimpleNamespace(_pvt=pvt))
    rs_analytics._draw_rs(ax, hist, grid, sim, cfg)
    marks = [ln for ln in ax.get_lines() if ln.get_marker() == "o"]
    labels = [ln.get_label() for ln in ax.get_lines()]
    plt.close(fig)
    return marks, labels


def test_overlay_marks_only_two_phase_and_front_label():
    """Падающее давление: кружки только в двухфазных ячейках, линия — «фронт»."""
    cfg, pvt = _case("04_table_table")
    p = [8, 10, 12, 14, 16, 18]
    regime = np.array([1, 1, 1, 1, 2, 2])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[4:] = 30.0
    marks, labels = _draw(cfg, pvt, _history(p, Rs, regime))
    assert len(marks) == 1
    np.testing.assert_array_equal(marks[0].get_xdata(), R[regime == 1])
    assert any(lb.startswith("фронт") for lb in labels)


def test_overlay_isobar_label_after_repressurization():
    """Восстановление давления: газ у забоя, ниже pb однофазная нефть — «изобара».

    Изобара p = pb стоит между 13 и 16 МПа, а граница газа — у первой ячейки:
    называть линию фронтом разгазирования нельзя.
    """
    cfg, pvt = _case("04_table_table")
    p = [10.75, 11, 12, 13, 16, 18]
    regime = np.array([1, 2, 2, 2, 2, 2])
    Rs = pvt.Rs_eq(np.array(p, float) * MPA)
    Rs[1:4] -= 2.0
    Rs[4:] = 30.0
    marks, labels = _draw(cfg, pvt, _history(p, Rs, regime))
    np.testing.assert_array_equal(marks[0].get_xdata(), R[regime == 1])
    assert any(lb.startswith("изобара") for lb in labels)
    assert not any(lb.startswith("фронт") for lb in labels)


def test_overlay_without_gas_has_no_marks():
    """Газа нет: кружков нет (пустая линия дала бы пункт легенды без точек)."""
    cfg, pvt = _case("04_table_table")
    marks, _labels = _draw(cfg, pvt, _history([16, 18], [30.0, 30.0], [2, 2]))
    assert marks == []
```

Примечание к `test_overlay_without_gas_has_no_marks`: при всех $p \ge p_b$ `front_radius` возвращает `nan` (`searchsorted` даёт `j = 0`), вертикальная линия не рисуется — тест это неявно покрывает (падения нет).

2. Запустить новый файл на старом коде — ожидаются падения (`AttributeError`/`KeyError`):
   ```powershell
   .venv\Scripts\python -m pytest tests/test_rs_analytics.py -q
   ```

3. Заменить `numerical_solver/examples/rs_analytics.py` целиком на:

```python
"""Аналитическая проверка Rs(r) — общая для всех примеров с растворённым газом.

В модели Black Oil газосодержание не имеет собственной динамики: нет ни
уравнения релаксации, ни кинетики выделения. Равновесие задаёт Rs
по-разному в двух режимах ячейки (state.regime):

    двухфазная (regime == 1):  Rs = Rs_eq(p)   — нефть насыщена, рядом газ;
    однофазная (regime == 2):  Rs <= Rs_eq(p)  — недонасыщенность допустима,
                                                 пересыщение — нет (с точностью
                                                 до допуска решателя RS_TOL).

Rs_eq — равновесное газосодержание насыщенной нефти (корреляция Стендинга
или интерполяция ветвей PVTO-таблицы — по модели PVT). В однофазной ячейке
Rs — самостоятельная переменная: растворённый газ переносится с нефтью.

Почему не Rs = min(Rs_eq(p), Rs0) во всех ячейках (так было до DEBT-026).
Формула верна, пока давление в каждой ячейке только падает: однофазная
нефть тогда исходная, с Rs0. При восстановлении давления свободный газ
растворяется обратно лишь в пределах своего запаса; когда он кончается,
нефть остаётся недонасыщенной и при p < pb: Sg = 0, Rs < Rs_eq(p)
(примеры 12, 13b). Rs0 — тоже не верхняя граница: газ подвижнее нефти и
копится у забоя, и при росте давления выше pb(Rs0) он растворится до
Rs > Rs0, если PVT это допускает (у Стендинга Rs_eq(p) > Rs0 при p > pb).
Такие ячейки печатаются как наблюдение, не как нарушение.

Режим берётся из state.regime, а не из Sg > 0: прототип обнуляет малую
отрицательную Sg, оставляя ячейку двухфазной (blackoil.py, _advance_phases:
trial.sg[tiny] = 0.0), и отбор по Sg вывел бы её из-под проверки равенства.

Проверка НЕ ЗАВИСИТ ОТ ВИДА ОФП и от тепловых параметров: в неё входят
только PVT, поле давления и режим ячеек. Поэтому один и тот же код
применим ко всем сценариям с Rs0 > 0 — и с аналитическим PVT, и с табличным.

Что она ловит:
  * схема выделяет газ не мгновенно (появилась паразитная релаксация либо
    рассогласование Rs с p внутри шага Ньютона) — нарушено равенство в
    двухфазных ячейках;
  * PVT в энергетическом блоке отличается от PVT гидродинамики — тогда
    Rs_eq(p), посчитанное здесь, не совпадёт с тем, что применил решатель;
  * газ растворился сверх равновесия — пересыщенная однофазная ячейка.

Чего не ловит: неверную величину недонасыщения (газ «потерялся» при
переходе ячейки в однофазный режим). Это задача баланса массы газового
компонента, а не алгебраической проверки.

Ожидаемая точность равенства — уровень машинного нуля (1e-13 и ниже):
обе величины считаются одной и той же функцией от одного и того же p.
"""

from __future__ import annotations

import numpy as np

# Допуск пересыщения однофазной ячейки, м³ст/м³ст, — допуск переключения фаз
# решателя rs_switch_tol. Прототип включает газ в ячейке только при
# Rs > Rs_eq(p) + rs_switch_tol (blackoil.py, _advance_phases; по умолчанию
# 1e-5, фабрика его не задаёт — поле NumericsConfig.rs_switch_tol прототипу
# не передаётся, брать допуск из конфига нельзя). Однофазная ячейка с
# пересыщением до 1e-5 — принятое решателем состояние, а не дефект; проверка
# строже решателя давала бы ложные нарушения. Тот же порог у проверки
# начального состояния (factory._RS0_SUPERSAT_TOL, BUG-017). Шум ~1e-13 на
# горизонтальной ветви таблицы (Rs_eq = Rs0 при p >= pb) он покрывает тоже.
RS_TOL = 1e-5


def rs_expected(config, pvt, p):
    """Rs при монотонно падающем давлении: min(Rs_eq(p), Rs0), [N].

    Физическая кривая PVT-графика (pvt_plot._physical_rs сверяется с ней
    побитово). Для проверки решения при произвольной истории давления не
    годится — см. докстринг модуля.
    """
    return np.minimum(pvt.Rs_eq(p), config.initial_conditions.Rs0)


def rs_error(config, history, pvt):
    """Отклонение Rs от Rs_eq(p) в двухфазных ячейках (regime == 1).

    Возвращает (max_abs, max_rel). Относительная нормируется на Rs0, а не
    поячеечно: у фронта Rs -> Rs0, а не к нулю, поэтому деление на Rs0 даёт
    устойчивую меру. Двухфазных ячеек нет — проверять нечего, (0.0, 0.0).
    """
    st = history.states[-1]
    two = st.regime == 1
    if not np.any(two):
        return 0.0, 0.0
    d = np.abs(pvt.Rs_eq(st.p[two]) - st.Rs[two])
    Rs0 = config.initial_conditions.Rs0
    return float(d.max()), float(d.max() / Rs0) if Rs0 > 0 else 0.0


def rs_supersaturation(history, pvt):
    """Пересыщение однофазных ячеек (regime == 2): Rs > Rs_eq(p) + RS_TOL.

    Возвращает (max_excess, n_bad): наибольшее Rs - Rs_eq(p) по однофазным
    ячейкам (отрицательное — запас до насыщения; nan, если однофазных нет)
    и число ячеек сверх допуска.
    """
    st = history.states[-1]
    one = st.regime == 2
    if not np.any(one):
        return float("nan"), 0
    excess = st.Rs[one] - pvt.Rs_eq(st.p[one])
    return float(excess.max()), int(np.count_nonzero(excess > RS_TOL))


def _degassed_cells(config, history, pvt):
    """Маска ячеек, где газ выделился (p < pb), и само pb."""
    Rs0 = config.initial_conditions.Rs0
    pb = float(pvt.pb(np.array([Rs0]))[0])
    return history.states[-1].p < pb, pb


def front_radius(config, history, grid, pvt):
    """Радиус изобары p = pb (фронта разгазирования при падающем давлении).

    Брать центр последней ячейки с p < pb нельзя: фронт лежит ВНУТРИ ячейки,
    и такая оценка систематически занижает r_b. На логарифмической сетке
    ячейки к периферии широкие, и при фронте в несколько метров занижение
    доходит до ~10 %. Поэтому интерполируем ln r по p между соседними
    ячейками — профиль логарифмичен, интерполяция именно по ln r.

    np.interp здесь не годится: он требует возрастающий массив узлов, а p
    и ln r монотонны в противоположные стороны, и он молча вернёт мусор.
    """
    p = history.states[-1].p
    r = grid.r_centers
    _below, pb = _degassed_cells(config, history, pvt)

    j = int(np.searchsorted(p, pb))          # p возрастает с ростом r
    if not (0 < j < len(p)):
        return np.nan
    w = (pb - p[j - 1]) / (p[j] - p[j - 1])
    return float(np.exp(np.log(r[j - 1]) + w * (np.log(r[j]) - np.log(r[j - 1]))))


def make_overlay_rs(config):
    """Собрать overlay-функцию для example_runner, замкнув на неё config.

    Хук вызывается как overlay(ax, history, grid, simulator) и своего config
    не получает, а Simulator его не хранит — поэтому конфиг замыкается здесь.
    Так один и тот же код годится для любого примера без обёрток в нём.
    """
    def overlay(ax, history, grid, simulator):
        _draw_rs(ax, history, grid, simulator, config)
    return overlay


def _draw_rs(ax, history, grid, simulator, config):
    """Наложить Rs_eq(p) двухфазных ячеек на профиль газосодержания.

    Вызывается после отрисовки численных кривых, поэтому отдельного PNG
    не создаётся — точки ложатся в rs_profiles.png.
    """
    pvt = simulator._energy._pvt

    st = history.states[-1]
    Rs0 = config.initial_conditions.Rs0
    two = st.regime == 1

    # Кружки — только в двухфазных ячейках: там Rs обязано равняться
    # Rs_eq(p). В однофазных равенства нет — нефть может быть недонасыщена
    # (DEBT-026), численная кривая там ограничена сверху, а не задана.
    # Без газа линию не строим: пустая дала бы пункт легенды без точек.
    if np.any(two):
        ax.semilogx(grid.r_centers[two], pvt.Rs_eq(st.p[two]), 'ko',
                    markersize=4, markerfacecolor='none', zorder=5,
                    label=r"$R_s = R_s^{eq}(p)$, двухфазные ячейки")

    # Линия Rs0: при падающем давлении правее фронта нефть исходная и Rs
    # строго равно Rs0, левее — идёт разгазирование.
    ax.axhline(Rs0, color='gray', linestyle='-.', linewidth=1.0,
               label=rf"$R_{{s,0}}$ = {Rs0:.0f} м³ст/м³ст")

    # Изобара p = pb. Фронтом разгазирования она является, только если
    # свободный газ есть ровно в ячейках с p < pb. После восстановления
    # давления (12, 13b) газ остаётся лишь у забоя, а ниже pb лежит и
    # недонасыщенная нефть; у 04a газ остался и за изобарой. Тогда линия
    # подписывается тем, что она есть, — изобарой.
    r_b = front_radius(config, history, grid, pvt)
    if np.isfinite(r_b):
        below, _pb = _degassed_cells(config, history, pvt)
        if np.array_equal(below, two):
            label = rf"фронт $r_b$ = {r_b:.3f} м"
        else:
            label = rf"изобара $p_b$: $r$ = {r_b:.3f} м"
        ax.axvline(r_b, color='gray', linestyle=':', linewidth=1.5,
                   label=label)


def report_rs(config, history, pvt) -> dict:
    """Печать проверки Rs в консоль. Возвращает сводку."""
    Rs0 = config.initial_conditions.Rs0
    if Rs0 <= 0.0:
        print("── Rs: сценарий однофазный (Rs0 = 0), проверять нечего ──")
        return dict(max_abs=0.0, max_rel=0.0)

    st = history.states[-1]
    d_abs, d_rel = rs_error(config, history, pvt)
    excess, n_bad = rs_supersaturation(history, pvt)
    below, pb = _degassed_cells(config, history, pvt)
    two = st.regime == 1
    one = st.regime == 2
    # Однофазная нефть ниже pb бывает только недонасыщенной: газ ушёл из
    # ячейки потоком или растворился весь при росте давления (12, 13b).
    # При монотонно падающем давлении таких ячеек нет.
    n_under = int(np.count_nonzero(one & below))
    # Rs > Rs0 — не нарушение: скопившийся у забоя газ при росте давления
    # выше pb(Rs0) растворяется сверх Rs0, если PVT это допускает.
    n_above = int(np.count_nonzero(st.Rs > Rs0 + RS_TOL))

    print("── Rs: равновесие Black Oil без кинетики ──")
    print(f"  двухфазные ячейки ({int(two.sum())}): "
          f"max|Rs_числ - Rs_eq(p)| = {d_abs:.3e} м³ст/м³ст "
          f"({d_rel * 100:.2e} % от Rs0)")
    print(f"  однофазные ячейки ({int(one.sum())}): пересыщенных "
          f"(Rs > Rs_eq(p)) — {n_bad}, ниже pb (нефть недонасыщена) — {n_under}")
    if n_bad:
        print(f"    наибольшее Rs - Rs_eq(p) = {excess:.3e} м³ст/м³ст")
    print(f"  Rs: {st.Rs.min():.4f} … {st.Rs.max():.4f} при Rs0 = {Rs0:.1f}, "
          f"pb = {pb / 1e6:.4f} МПа; ячеек с Rs > Rs0: {n_above}")

    return dict(max_abs=d_abs, max_rel=d_rel, n_two_phase=int(two.sum()),
                n_supersaturated=n_bad, max_excess=excess,
                n_single_below_pb=n_under, n_above_rs0=n_above, pb=pb)
```

Отличия от старой версии, которые важно не потерять при переносе: `_degassed_cells`, тело `front_radius` и `make_overlay_rs` — без изменений; у `front_radius` поменялась только первая строка докстринга; `rs_expected` — только докстринг.

4. Запустить новый файл — зелёный; затем быстрый уровень.

**Изменения (старый → новый, ключевое):**
- До: `rs_error` — `Rs_ana = rs_expected(config, pvt, st.p); d = np.abs(Rs_ana - st.Rs)` по всем ячейкам.
  После: только `st.regime == 1`, сравнение с `pvt.Rs_eq(st.p[two])`.
- До: `report_rs` печатает `ячеек с p < pb: …, с Sg > 0: … — совпадают: {same}`.
  После: строки «двухфазные ячейки», «однофазные ячейки», «Rs: … ячеек с Rs > Rs0».
- До: `_draw_rs` — кружки `rs_expected` во всех ячейках, подпись `$R_s = \min(R_s^{eq}(p),\ R_{s,0})$`, линия «фронт $r_b$».
  После: кружки `Rs_eq(p)` в `regime == 1`, подпись линии по ситуации.

**Проверка после этого шага:**
- `.venv\Scripts\python -m pytest tests/test_rs_analytics.py -q` — 10 passed.
- Регресс: быстрый (`-m "not slow" -q`) — ожидается 987 + 10 = 997 passed. В нём и шпион `report_rs` (`test_examples.py:551–597`, пример 05 со `steady_state=False`).

**Подводные камни:** `rs_expected` не трогать по семантике (тест побитовой сверки с `pvt_plot._physical_rs`, slow — проверится в шаге 3). Ключи словаря `report_rs` меняются — потребителей нет (§2).

**Зависимости:** требует шаг 1 (гейт); блокирует 3, 5.

**Оценка:** ~200 строк (модуль ~210, тесты ~200), ~40 мин.

---

### Шаг 3: Общий slow-тест проверки $R_s$ на всех примерах с газом

**Цель:** закрыть пробел — проверка $R_s$ впервые проверяется автоматически на штатных конфигах всех 18 примеров с газом, включая 12 и 13b.

**Файлы:** `numerical_solver/tests/test_examples.py` — класс `TestSharedChecks` (стр. 625–782), новый метод после `test_energy_balance_reported_for_all_examples` (заканчивается на стр. 781, перед разделителем `# J. Графики PVT` на стр. 784).

**Контекст:** фикстура `results` уже считает все примеры для других slow-тестов, поэтому новый тест расчётов не добавляет. PVT берётся `_pvt_of_config` (`test_examples.py:816`, фабрика по конфигу — тот же приём, что в `test_physical_branch_matches_rs_analytics`); функция определена ниже по файлу, но вызывается во время теста — порядок определения не важен. Метка `slow` ставится автоматически хуком `tests/conftest.py` (тест использует `results`).

**Что сделать:** добавить метод:

```python
    def test_rs_check_all_two_phase_examples(self, results):
        """Проверка R_s проходит у всех примеров с газом, включая 12 и 13b (DEBT-026).

        Двухфазные ячейки (regime == 1): |Rs - Rs_eq(p)| <= 1e-10 (замер
        2026-10-03: не больше ~4e-13). Однофазные: пересыщенных нет.
        У 12 и 13b на последней записи есть однофазные ячейки ниже p_b —
        недонасыщенная нефть после восстановления давления (замер: 1 и 30).
        Прежняя проверка min(Rs_eq(p), Rs0) печатала на них «не совпадают»;
        условие >= 1 гарантирует, что тест действительно проходит через
        этот случай, а не только через падающее давление.
        Ловит: возврат к формуле min(...) во всех ячейках, задержку
        выделения газа и рассогласование PVT (ошибка в двухфазных),
        растворение газа сверх равновесия (пересыщение).
        """
        import contextlib
        import io
        import sys
        sys.path.insert(0, str(EXAMPLES_DIR))
        from rs_analytics import report_rs

        reps = {}
        for name in TWO_PHASE:
            r = results[name]
            pvt = _pvt_of_config(r["config"])
            # report_rs печатает отчёт примера — в выводе теста он не нужен.
            with contextlib.redirect_stdout(io.StringIO()):
                reps[name] = report_rs(r["config"], r["history"], pvt)

        bad = {n: (rep["max_abs"], rep["n_supersaturated"])
               for n, rep in reps.items()
               if rep["max_abs"] > 1e-10 or rep["n_supersaturated"] > 0}
        assert not bad, f"проверка R_s не прошла (max_abs, пересыщенных): {bad}"

        for name in ("12_large_drainage_radius", "13b_pwf_alternating"):
            assert reps[name]["n_single_below_pb"] >= 1, (
                f"{name}: нет недонасыщенной нефти ниже p_b — тест больше не "
                f"проверяет случай восстановления давления")
```

**Проверка после этого шага:**
- Целевой прогон slow-тестов модуля (~4 мин, считаются все примеры):
  ```powershell
  .venv\Scripts\python -m pytest tests/test_examples.py -q -k "rs_check_all_two_phase or physical_branch_matches_rs_analytics or rho_matches_formula or repressurization_leaves_undersaturated"
  ```
  Ожидается 4 passed.
- Регресс: быстрый — 997 passed (новый тест в быстрый уровень не входит).

**Подводные камни:** если порог `1e-10` нарушен у какого-то примера — это не повод поднимать порог: замер шага 1 показал, что нарушать нечему; разобрать.

**Зависимости:** требует шаг 2.

**Оценка:** ~40 строк, ~10 мин (+4 мин прогона).

---

### Шаг 4: Докстринг `pvt_plot._physical_rs`

**Цель:** убрать ложное утверждение «газосодержание, реально бывшее в расчёте».

**Файл:** `numerical_solver/examples/pvt_plot.py:93–101`.

**Контекст:** `_physical_rs` рисует физическую кривую PVT и считает опорные точки сводки (стр. 251) по $\min(R_s^{eq}(p), R_{s,0})$. У 12 и 13b в расчёте была и недонасыщенная нефть ниже $p_b$, которой на этой кривой нет. Код не меняется — решение пользователя: только фраза докстринга.

**Изменения:**
До:
```python
    """Газосодержание, реально бывшее в расчёте: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    Та же формула, что в rs_analytics.rs_expected; ядро считает её само,
    здесь она нужна для сводки и для ординат узлов таблицы.
    """
```
После:
```python
    """Газосодержание при падающем давлении: min(Rs_eq(p), Rs0).

    p >= p_b — нефть недонасыщена, весь газ растворён, Rs держится на Rs0;
    p <  p_b — нефть насыщена, избыток выделился, Rs = Rs_eq(p).
    После восстановления давления в расчёте бывает и недонасыщенная нефть
    ниже p_b (примеры 12, 13b; DEBT-026) — этой кривой она не описывается.
    Та же формула, что в rs_analytics.rs_expected; ядро считает её само,
    здесь она нужна для сводки и для ординат узлов таблицы.
    """
```

**Проверка после этого шага:** Регресс: `--collect-only -q` (только докстринг) — 1221.

**Зависимости:** нет (можно делать в любом порядке после шага 1).

**Оценка:** 2 строки, ~3 мин.

---

### Шаг 5: Замер после правки и визуальная проверка `rs_profiles.png`

**Цель:** получить числа для README и убедиться, что рисунок соответствует решению пользователя.

**Файлы:** новый `vault/issues/debt-026/probes/rs_check_after.txt`; `examples/*/output/` (в git не хранятся).

**Что сделать:**
1. Повторить замер шага 1 тем же скриптом:
   ```powershell
   .venv\Scripts\python ..\vault\issues\debt-026\probes\rs_check_numbers.py --out ..\vault\issues\debt-026\probes\rs_check_after.txt
   ```
2. Сверить: блоки «прежняя», «новая», «предпосылки» **побитово совпадают** с `rs_check_before.txt` (решатель не менялся); блок `report_rs` — новый формат, его числа совпадают с блоком «новая» (двухфазных, max|Rs − Rs_eq(p)|, пересыщенных, ниже pb, Rs > Rs0).
3. Запустить примеры, у которых меняется рисунок, и посмотреть `output/rs_profiles.png` (Read по PNG):
   ```powershell
   .venv\Scripts\python examples\03_standing_corey\main.py
   .venv\Scripts\python examples\04a_high_gas_saturation\main.py
   .venv\Scripts\python examples\12_large_drainage_radius\main.py
   .venv\Scripts\python examples\13b_pwf_alternating\main.py
   ```
   Ожидание: 03 — кружки только левее фронта, линия «фронт $r_b$ = … м»; 04a — кружки в 70 ячейках, в том числе в пяти за линией, подпись «изобара $p_b$: …»; 12 — подпись «изобара»; 13b — кружки только у забоя (14 ячеек ближе 0.9 м), подпись «изобара» на ~75 м. Легенда не перекрывает кривые сильнее прежнего.
4. Из консоли 13b скопировать блок `── Rs: равновесие Black Oil без кинетики ──` (4 строки) — пойдёт в README 13b дословно. Из консоли 12 — строки для README 12.

**Проверка после этого шага:** Регресс: `--collect-only -q` — 1221 (код не менялся).

**Зависимости:** требует шаги 2–3; блокирует шаг 6.

**Оценка:** ~15 мин (расчёт ~4 мин + 4 примера).

---

### Шаг 6: README

**Цель:** документация описывает новую проверку; объяснения «совпадают: False» убраны.

**Файлы:**
- `numerical_solver/examples/README.md` (стр. 228, 393–440, 620)
- `numerical_solver/examples/03_standing_corey/README.md` (стр. 297–300)
- `numerical_solver/examples/04_table_table/README.md` (стр. 124–125, 320–321)
- `numerical_solver/examples/04a_high_gas_saturation/README.md` (стр. 229, 431)
- `numerical_solver/examples/05_standing_table_rp/README.md` (стр. 104, 107)
- `numerical_solver/examples/12_large_drainage_radius/README.md` (стр. 168–173)
- `numerical_solver/examples/13b_pwf_alternating/README.md` (стр. 162–181)

**Не трогать** (решение пользователя): `03_standing_corey/README.md` §3 (стр. 167–170), `19_rs150_cooling/README.md:148`, `20_rs300_cooling/README.md:163–167`, `21_rs100_cooling/README.md:148` — утверждения о решении при падающем давлении остаются верными.

Числа вида `‹…›` — из `rs_check_after.txt` (шаг 5). Стиль README — без англицизмов (CLAUDE.md, раздел LaTeX/«Без англицизмов»).

**Изменения:**

**6.1. `examples/README.md:228`**
До:
```
| `rs_profiles.png` | $R_s(r)$ + аналитика $\min(R_s^{eq}(p), R_{s,0})$ — только у сценариев с $R_{s,0} > 0$ (все, кроме 01–02); в 01–02 газа нет |
```
После:
```
| `rs_profiles.png` | $R_s(r)$ + $R_s^{eq}(p)$ в двухфазных ячейках — только у сценариев с $R_{s,0} > 0$ (все, кроме 01–02); в 01–02 газа нет |
```

**6.2. `examples/README.md:393–440`** — раздел «Проверка $R_s$ — во всех сценариях с газом» целиком (от заголовка до строки «другое не видно на профилях $p$ и $S_g$.» включительно; следующий раздел «### Баланс энергии — во всех сценариях без исключения» не трогать). После:

```
### Проверка $R_s$ — во всех сценариях с газом

В модели Black Oil газосодержание не имеет собственной динамики — ни
релаксации, ни кинетики выделения. В ячейке со свободным газом нефть
насыщена, и $R_s$ задан давлением; в ячейке без газа равновесие даёт
только верхнюю границу:

$$\text{двухфазная ячейка: } R_s = R_s^{eq}(p), \qquad
\text{однофазная: } R_s \le R_s^{eq}(p).$$

Однофазная нефть может быть недонасыщена: исходная правее фронта
($R_s = R_{s,0}$) или оставшаяся после восстановления давления, когда
свободный газ растворился весь, а давление ещё ниже $p_b$. Пересыщенной
она быть не может. Формула $R_s = \min(R_s^{eq}(p), R_{s,0})$ верна только
при монотонно падающем давлении.

Модуль [rs_analytics.py](rs_analytics.py) проверяет оба условия на
последней записи у всех сценариев с $R_{s,0} > 0$ и печатает в консоль
расхождение в двухфазных ячейках, число пересыщенных однофазных ячеек и
число однофазных ячеек ниже $p_b$. Режим ячейки берётся у решателя, а не
по $S_g > 0$. На `rs_profiles.png` кружки — $R_s^{eq}(p)$ в двухфазных
ячейках; вертикальная линия — изобара $p = p_b$. Она подписана «фронт
$r_b$», если свободный газ есть ровно в ячейках с $p < p_b$, и «изобара
$p_b$» иначе.

Проверка зависит только от PVT, поля давления и режима ячеек, поэтому
применима и к аналитическому PVT (03, 05, 19–21), и к табличному
(остальные с газом):

| пример | PVT | $R_s$ диапазон | двухфазных ячеек | $\max\|R_s^{числ}-R_s^{eq}(p)\|$ | однофазных с $p<p_b$ | пересыщенных |
|---|---|---|---|---|---|---|
| 03 | Standing | 41.48 … 50 | ‹16› | ‹…› | 0 | 0 |
| 04, 07–09 | таблица | 9.50 … 30 | ‹26› | ‹…› | 0 | 0 |
| 04a | таблица | 0 … 30 | ‹70› | ‹…› | 0 | 0 |
| 05 | Standing | 42.00 … 50 | ‹6› | ‹…› | 0 | 0 |
| 06 | таблица | 9.52 … 30 | ‹26› | ‹…› | 0 | 0 |
| 10 | таблица | 3.61 … 30 | ‹29› | ‹…› | 0 | 0 |
| 11 | таблица | 3.35 … 29.95 | ‹50› | ‹…› | 0 | 0 |
| 12 | таблица | 3.37 … 30 | ‹46› | ‹…› | ‹1› | 0 |
| 13a | таблица | 3.37 … 30 | ‹47› | ‹…› | 0 | 0 |
| 13b | таблица | 17.41 … 30 | ‹14› | ‹…› | ‹30› | 0 |
| 14 | таблица | 10.40 … 150 | ‹47› | ‹…› | 0 | 0 |
| 15 | таблица | 3.76 … 30 | ‹46› | ‹…› | 0 | 0 |
| 19 | Standing | 13.25 … 150 | ‹334› | ‹…› | 0 | 0 |
| 20 | Standing | 36.17 … 300 | ‹289› | ‹…› | 0 | 0 |
| 21 | Standing | 13.10 … 100 | ‹328› | ‹…› | 0 | 0 |

Однофазные ячейки ниже $p_b$ есть только у сценариев с восстановлением
давления. У 12 это ячейка за стационарным фронтом: свободный газ ушёл из
неё, пока давление возвращалось, но было ещё ниже $p_b$, и растворять
обратно нечего. У 13b последняя запись сделана при 10.75 МПа после суток
при 6 МПа: свободного газа на обратное растворение не хватило, и на
0.9–75 м нефть недонасыщена. У 04a свободный газ остался и в пяти ячейках
с $p > p_b$ — остаток переходного процесса; таблица даёт там
$R_s^{eq}(p) = R_{s,0}$, и равенство выполняется. У этих трёх сценариев
линия на `rs_profiles.png` подписана «изобара $p_b$».

Точность в двухфазных ячейках машинная, потому что обе величины — одна и
та же функция от одного и того же $p$. Проверка не избыточна: расхождение
означало бы либо паразитную релаксацию в схеме (газ выделяется не
мгновенно), либо рассогласование PVT энергетического блока с PVT
гидродинамики, а пересыщение — растворение газа сверх равновесия. Ничего
из этого не видно на профилях $p$ и $S_g$.
```

Столбец «$R_s$ диапазон» — из прежней таблицы (числа решения не менялись; сверить с `Rs: … …` в `rs_check_after.txt`). Если у 04 и 07–09 значения в шаге 5 различаются — разбить строку.

**6.3. `examples/README.md:620`**
До:
```
| [rs_analytics.py](rs_analytics.py) | $R_s = \min(R_s^{eq}(p), R_{s,0})$ | — |
```
После:
```
| [rs_analytics.py](rs_analytics.py) | $R_s = R_s^{eq}(p)$ в двухфазных ячейках, $R_s \le R_s^{eq}(p)$ в однофазных | — |
```

**6.4. `03_standing_corey/README.md:297–300`**
До:
```
- `rs_profiles.png` — $R_s(r)$ с изломом ровно на фронте: слева
  газосодержание падает по корреляции Стендинга, справа держится на
  $R_{s,0} = 50$. Кружки — $R_s = \min(R_s^{eq}(p), R_{s,0})$, совпадение
  $1.4\cdot10^{-14}$.
```
После:
```
- `rs_profiles.png` — $R_s(r)$ с изломом ровно на фронте: слева
  газосодержание падает по корреляции Стендинга, справа держится на
  $R_{s,0} = 50$. Кружки — $R_s^{eq}(p)$ в двухфазных ячейках, совпадение
  ‹…›.
```

**6.5. `04_table_table/README.md:124–125`**
До:
```
| $R_s = \min(R_s^{eq}(p), R_{s,0})$ | $2.1\cdot10^{-14}$ |
| ячейки с $p < p_b$ и с $S_g > 0$ | совпадают (26) |
```
После:
```
| $R_s = R_s^{eq}(p)$ в двухфазных ячейках | ‹…› (‹26› ячеек) |
| однофазные ячейки: пересыщенных / ниже $p_b$ | 0 / 0 |
```

**6.6. `04_table_table/README.md:320–321`**
До:
```
- `rs_profiles.png` — $R_s(r)$ с изломом на фронте; кружки —
  $R_s = \min(R_s^{eq}(p), R_{s,0})$.
```
После:
```
- `rs_profiles.png` — $R_s(r)$ с изломом на фронте; кружки —
  $R_s^{eq}(p)$ в двухфазных ячейках.
```

**6.7. `04a_high_gas_saturation/README.md:229`**
До:
```
$R_s = \min(R_s^{eq}(p), R_{s,0})$ выполняется с точностью $10^{-13}$.
```
После:
```
$R_s = R_s^{eq}(p)$ в ‹70› двухфазных ячейках выполняется с точностью
‹…›, в том числе в пяти за изобарой $p_b$: там $R_s^{eq}(p) = R_{s,0}$.
```

**6.8. `04a_high_gas_saturation/README.md:431`**
До:
```
- `rs_profiles.png` — $R_s(r)$: ноль у забоя, $R_{s,0}$ за фронтом.
```
После:
```
- `rs_profiles.png` — $R_s(r)$: ноль у забоя, $R_{s,0}$ за фронтом.
  Вертикальная линия подписана «изобара $p_b$»: свободный газ остался и в
  пяти ячейках за ней (см. «Газ за фронтом» выше).
```

**6.9. `05_standing_table_rp/README.md:104` и `:107`**
До (стр. 104):
```
| ячейки $p<p_b$ и ячейки $S_g>0$ | совпадают |
```
После:
```
| однофазные ячейки: пересыщенных / ниже $p_b$ | 0 / 0 |
```
До (стр. 107):
```
| $R_s = \min(R_s^{eq}(p), R_{s,0})$ | $\max\|\Delta R_s\| = 7.1\times10^{-15}$ |
```
После:
```
| $R_s = R_s^{eq}(p)$ в двухфазных ячейках | $\max\|\Delta R_s\| = ‹…›$ (‹6› ячеек) |
```

**6.10. `12_large_drainage_radius/README.md:168–173`**
До:
```
Поэтому проверка $R_s$ в консоли на 15 сут печатает «ячеек с p < pb: 47,
с Sg > 0: 46 — совпадают: False» и $\max\lvert R_s - R_s^{равн}\rvert =
0.025$ м³ст/м³ст. Проверка предполагает $R_s = \min(R_s^{eq}(p), R_{s,0})$
и не учитывает восстановление давления без свободного газа. Это поведение
модели Black Oil, а не ошибка. По той же причине число двухфазных ячеек в
таблице выше убывает с 47 до 46 на 13 сут.
```
После:
```
Проверка $R_s$ в консоли на 15 сут это состояние допускает: равенство
$R_s = R_s^{eq}(p)$ проверяется в ‹46› двухфазных ячейках (‹…›
м³ст/м³ст), а для однофазных — только отсутствие пересыщения; ячейка за
фронтом попадает в строку «ниже pb (нефть недонасыщена) — ‹1›». По той
же причине число двухфазных ячеек в таблице выше убывает с 47 до 46 на
13 сут, а вертикальная линия на `rs_profiles.png` подписана «изобара
$p_b$», а не «фронт».
```

**6.11. `13b_pwf_alternating/README.md:162–181`** — раздел «## Проверка газосодержания $R_s$» до строки «ячеек (46 и 46).» включительно (следующий раздел «## Стационарная аналитика отключена» не трогать). После:

````
## Проверка газосодержания $R_s$

Общий модуль `rs_analytics.py` проверяет на последней записи равновесие
Black Oil: в двухфазных ячейках $R_s = R_s^{eq}(p)$, в однофазных
$R_s \le R_s^{eq}(p)$. Консоль печатает:

```
‹4 строки блока «── Rs: равновесие Black Oil без кинетики ──» из консоли 13b, шаг 5›
```

Равенство выполняется в ‹14› двухфазных ячейках у забоя. ‹30› однофазных
ячеек ниже $p_b$ — недонасыщенная нефть на 0.9–75 м (см. выше), а не
расхождение: давление поднялось после суток при 6 МПа, и свободного газа
на обратное растворение не хватило. На `rs_profiles.png` кружки стоят
только в двухфазных ячейках; вертикальная линия подписана «изобара
$p_b$» — она на ~75 м, а свободный газ только ближе 0.9 м.
````

(Внешняя ограда в плане — четыре обратных апострофа только для отображения; в README — обычный блок кода в три апострофа, как сейчас на стр. 168–173.)

**Проверка после этого шага:**
- Регресс: быстрый — 997 passed (`TestReadme` — быстрый уровень, проверяет разделы «Как модифицировать», «увеличить газонасыщенность», имена классов; ни один из них правками не затрагивается).
- grep контроля: `совпадают: False` и `задача DEBT-026` в `numerical_solver/examples/**/README.md` — пусто; `min(R_s^{eq}` остаётся только в 03 (§3), 19, 20, 21 и в новом тексте сводного README (фраза «верна только при монотонно падающем давлении»).

**Подводные камни:** `‹…›` не оставлять в тексте — grep `‹` по `numerical_solver/examples` после шага должен быть пуст.

**Зависимости:** требует шаг 5.

**Оценка:** ~90 строк текста, ~30 мин.

---

### Шаг 7: Vault

**Цель:** знания и реестр отражают новое состояние.

**Файлы:**
- `vault/knowledge/science/давление и газонасыщенность выходят на стационар вместе — различается амплитуда.md` (стр. 69–71)
- `vault/roadmap/известные баги и технический долг.md` — секция `### DEBT-026`

**Что сделать:**
1. В заметке о стационаре стр. 70–71: «Проверка `rs_analytics` ($R_s = \min(R_s^{eq}(p), R_s^0)$) такие ячейки не учитывает и печатает расхождение.» → «До [[DEBT-026]] проверка `rs_analytics` ($R_s = \min(R_s^{eq}(p), R_s^0)$ во всех ячейках) такие ячейки не учитывала и печатала расхождение; теперь в однофазных ячейках проверяется только $R_s \le R_s^{eq}(p)$.»
2. Реестр DEBT-026: статус и строка о результате — по контракту `/implement` (влитие, коммит, число тестов).

**Проверка после этого шага:** `--collect-only -q` — 1221.

**Зависимости:** требует шаги 2–6.

**Оценка:** ~5 строк, ~5 мин.

---

## 7. Тестовая стратегия

| Тест | Файл | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|---|
| `test_monotone_pressure_passes` | `tests/test_rs_analytics.py` (новый, быстрый) | падающее давление, фронт на 15 МПа | `max_abs == 0`, нарушений 0, ниже pb 0 | ложные срабатывания на штатных примерах |
| `test_repressurization_undersaturated_is_not_violation` | то же | картина 13b | прежняя формула даёт 2.0; новая — нарушений 0, ниже pb 3 | возврат к $\min(\ldots)$ во всех ячейках |
| `test_supersaturated_single_phase_is_violation` | то же | однофазная $R_s = R_s^{eq} + 0.5$ | `n_supersaturated == 1`, `max_excess ≈ 0.5` | проверка перестала ловить пересыщение |
| `test_two_phase_mismatch_is_reported` | то же | двухфазная $R_s = R_s^{eq} - 10^{-3}$ | `max_abs ≈ 1e-3`, `max_rel ≈ 1e-3/30` | двухфазная часть ослабла |
| `test_tolerance_on_flat_branch` | то же | шум $10^{-12}$ на горизонтальной ветви таблицы | нарушений 0 | ложные пересыщения от шума Ньютона |
| `test_rs_above_rs0_is_observation_not_violation` | то же | Стендинг, $R_{s,0} < R_s < R_s^{eq}(p)$ | нарушений 0, `n_above_rs0 == 1` | возврат к варианту 1 |
| `test_no_two_phase_cells` | то же | газа нет | `max_abs == 0`, `n_two_phase == 0` | падение на пустой маске |
| `test_overlay_marks_only_two_phase_and_front_label` | то же | рисунок, падающее давление | кружки = `r[regime == 1]`, подпись «фронт» | рисунок разошёлся с проверкой; смена подписи у штатных примеров |
| `test_overlay_isobar_label_after_repressurization` | то же | рисунок, картина 13b | подпись «изобара», «фронт» нет | ложная подпись «фронт» |
| `test_overlay_without_gas_has_no_marks` | то же | газа нет | кружков нет | пустой пункт легенды |
| `test_rs_check_all_two_phase_examples` | `tests/test_examples.py::TestSharedChecks` (slow) | штатные конфиги 18 примеров | `max_abs ≤ 1e-10`, пересыщенных 0; 12 и 13b — ниже pb ≥ 1 | регресс проверки на реальных решениях; пробел «проверка только печатается» |

Существующие тесты, которые должны остаться зелёными без изменений: шпион `report_rs` (`test_examples.py:551–597`, быстрый), `test_physical_branch_matches_rs_analytics`, `test_rho_matches_formula`, `test_repressurization_leaves_undersaturated_oil` (slow, прогоняются в шаге 3 целевым запуском и в итоговом полном).

Число тестов: 1210 → 1221. В `tests/test_rs_analytics.py` 10 тестов (быстрый уровень), в `test_examples.py` +1 (slow). Быстрый уровень: 987 → 997.

Предпосылки синтетических тестов проверены при планировании (2026-10-03) на настоящем PVT: пример 04 — $R_{s,0} = 30$, $p_b = 15.0$ МПа, $R_s^{eq}$ при 8 / 10 / 10.75 / 12 / 14 / 16 / 18 МПа = 9 / 15 / 17.25 / 21 / 27 / 30 / 30; пример 03 — $R_{s,0} = 50$, $p_b = 9.43$ МПа, $R_s^{eq}(1.5\,p_b) = 80.9$; `pvt.Rs_eq(np.array([]))` возвращает пустой массив без ошибки.

---

## 8. Критерии завершения

- [ ] Шаги 1–7 выполнены; гейт шага 1 пройден (или расхождения согласованы с пользователем).
- [ ] `tests/test_rs_analytics.py` — 10 passed; `test_rs_check_all_two_phase_examples` — passed.
- [ ] Полный прогон зелёный: 1221 passed (итоговый прогон `/implement`).
- [ ] `rs_check_after.txt`: блоки «прежняя/новая/предпосылки» побитово равны `rs_check_before.txt`; у всех 18 примеров пересыщенных 0, ошибка в двухфазных $\le 10^{-10}$; ниже pb: 12 → 1, 13b → 30, остальные 0.
- [ ] Визуальная проверка `rs_profiles.png` у 03, 04a, 12, 13b пройдена (шаг 5).
- [ ] README: grep `совпадают: False`, `задача DEBT-026`, `‹` по `numerical_solver/examples` — пусто.
- [ ] `gpn_multiphase_solver/` и `HydroSolverPrototype/` не изменены (`git diff --stat numerical_scheme/implementation -- numerical_solver/gpn_multiphase_solver numerical_solver/HydroSolverPrototype` — пусто).
- [ ] Vault обновлён (заметка о стационаре, реестр).
- [ ] Issue #56 прокомментирован с результатом (`vault/issues/debt-026/05-comment-done.md`).

---

## 9. Обнаруженные проблемы

1. **Список `SHARED_CHECK_MODULES` в `tests/test_examples.py:610–616` неполон.** Защита «общий модуль не скопирован в папку примера» (копия в папке молча перекрывает общий модуль — механизм BUG-004) охватывает только модули FEAT-016 и `pvt_plot.py`. `rs_analytics.py`, `closed_form.py`, `relperm_plot.py` (вынесены раньше FEAT-016) и `figure_io.py` не защищены. Текущую задачу не блокирует. Зарегистрировано как [[DEBT-037]].
2. Фразы «Проверка $R_s = \min(R_s^{eq}(p), R_{s,0})$ и баланс энергии остаются» в README 19 и 21 (стр. 148) называют проверку по прежней формуле. Решение пользователя — не трогать (при падающем давлении утверждение верно). Не регистрируется.

---

## Связанные заметки

- Запись: `vault/roadmap/известные баги и технический долг.md` → `### DEBT-026`
- Issue: [#56](https://github.com/ArturSalamatin/Oil_Gas/issues/56); тело и комментарии — `vault/issues/debt-026/`
- Замер, на котором обнаружено: `vault/issues/feat-023/probes/plan_numbers.py`
- [[давление и газонасыщенность выходят на стационар вместе — различается амплитуда]] — пример 12, недонасыщенная нефть за фронтом
- [[проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП]] — почему `rs_analytics.py` общий
- Связанные задачи: [[FEAT-019]], [[FEAT-021]] (#39), [[FEAT-023]] (#40), [[BUG-014]] (#42)
