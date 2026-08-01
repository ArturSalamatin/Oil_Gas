---
tags:
  - план
  - инфраструктура
date: 2026-07-31
issue: FEAT-008
github: 11
branch: feat/feat-008/cli-visualization
status: готов к реализации
audit:
  date: 2026-07-31
  found: 0
  auto-fixed: 0
  manual-required: 0
---

# FEAT-008: CLI и визуализация

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Создай ветку: `git checkout -b feat/feat-008/cli-visualization`
3. Прогони тесты (baseline):
   ```powershell
   cd d:\Lessons\Grants\2026\GPN\Oil_Gas\method_of_moments
   .venv\Scripts\python -m pytest tests/ -v
   ```
4. Проверь baseline: 311 тестов, все зелёные
5. Начни с шага 1. После каждого шага: pytest

## Подтип

**Инфраструктура** — CLI-точка входа, парсинг конфига, визуализация результатов. Новой физики / формул нет.

## Обзор

CLI-модуль `main.py` — единственная точка входа для запуска метода моментов из командной строки. Принимает JSON-конфиг, собирает объекты Python, вызывает `solve_moments` + `reconstruct_profiles`, сохраняет CSV и строит графики PNG.

## Зависимости

- **FEAT-007b** (#10) — ✅ ГОТОВО. `solve_moments` и `reconstruct_profiles` в `src/solver.py`.
- Внешние: `numpy`, `scipy`, `matplotlib` — уже в `pyproject.toml`.
- Стандартная библиотека: `json`, `argparse`, `pathlib`, `sys`.

## Обратная совместимость

- [x] Существующие тесты пройдут без изменений — `main.py` новый файл, не трогает существующие
- [x] Существующие конфиги работают без изменений — `baseline.json` используется as-is
- [x] API существующих функций не меняется
- [x] ODE система не затрагивается

## Варианты решения

### Вариант A: набор функций в одном файле

- `load_config`, `build_objects`, `save_csv`, `plot_dynamics`, `plot_profiles`, `run` — функции в `main.py`
- `argparse` в `if __name__ == "__main__"`
- **Плюсы:** простота, соответствует стилю проекта (solver.py — тоже функции)
- **Минусы:** при росте файла >200 строк — трудно поддерживать
- **Трудоёмкость:** ~120 строк

### Вариант B: разделить на `config.py` + `main.py` + `plotting.py`

- Конфигурация, визуализация, CLI — в разных файлах
- **Плюсы:** модульность, можно тестировать `build_objects` отдельно
- **Минусы:** избыточная структура для 120 строк; CLAUDE.md: «не добавляй абстракции сверх задачи»
- **Трудоёмкость:** ~150 строк (три файла)

### Выбор: **Вариант A**

Один файл `main.py`. Функция `build_objects` экспортируется — тесты и будущие VAL-кейсы могут её импортировать. Если файл вырастет — рефакторинг тривиален.

## Предлагаемый API

### Вход

```
cd method_of_moments
.venv\Scripts\python -m src.main configs\baseline.json --output-dir results\baseline
```

- Аргумент 1: путь к JSON-конфигу (обязательный)
- `--output-dir`: директория для результатов (по умолчанию `results/`)

### Функции модуля

| Функция | Сигнатура | Назначение |
|---|---|---|
| `load_config` | `(path: str \| Path) -> dict` | JSON → dict |
| `build_objects` | `(cfg: dict) -> tuple[BlackOilFluid, dict, PressureProfile, TemperatureProfile, SaturationProfile, dict]` | dict → (fluid, rock, p_profile, t_profile, s_profile, solver_opts) |
| `save_csv` | `(sol: OdeResult, path: Path) -> None` | t, r_b, Sg_w, dT_w → CSV |
| `plot_dynamics` | `(sol: OdeResult, path: Path) -> None` | r_b(t) → PNG |
| `plot_profiles` | `(sol: OdeResult, p_profile, t_profile, s_profile, fluid, r_w, r_e, path: Path) -> None` | p(r), Sg(r), T(r) → PNG |
| `run` | `(config_path: str, output_dir: str) -> OdeResult` | Полный pipeline |

### Выход

1. `<output_dir>/solution.csv` — столбцы: `t`, `r_b`, `Sg_w`, `dT_w`
2. `<output_dir>/rb_vs_t.png` — график $r_b(t)$
3. `<output_dir>/profiles.png` — 3 subplots: $p(r)$, $S_g(r)$, $T(r)$ на последний момент

## Связь конфиг → конструкторы

Маппинг из `baseline.json` в конструкторы Python-объектов:

```
cfg["pvt"]                   → BlackOilFluid(pvt_config=...,
cfg["initial_conditions"]["p_b"]      p_b=...,
cfg["initial_conditions"]["T_0"]      T_0=...,
cfg["relative_permeability"]          relperm_config=...)

cfg["geometry"]["r_w"]       → PressureProfile(r_w=...,
cfg["geometry"]["R_ext"]               R_ext=...,
cfg["boundary_conditions"]["p_wf"]     p_wf=...,
cfg["initial_conditions"]["p_0"]       p_0=...)

cfg["geometry"]["r_w"]       → SaturationProfile(r_w=...,
cfg["profiles"]["beta"]                beta=...)

cfg["geometry"]["r_w"]       → TemperatureProfile(r_w=...,
cfg["geometry"]["R_ext"]               R_ext=...,
cfg["initial_conditions"]["T_0"]       T_0=...,
cfg["profiles"]["sigma"]               sigma=...)

cfg["rock"]                  → rock (dict, передаётся как есть)

cfg["solver"]                → solver_opts (dict: t_epsilon, t_end, method, rtol, atol)
```

Этот маппинг дублируется в `test_solver.py:41–69`, `test_coefficients.py:36–49`, `test_ode_system.py:35–48`. После реализации `build_objects` тесты смогут его импортировать (DEBT, за рамками FEAT-008).

## Подводные камни

- ✅ **Import-цепочки:** `main.py` импортирует `solver`, `black_oil`, `profiles` — линейно, без циклов
- ✅ **Размерности:** CSV хранит r_b в метрах, Sg_w безразмерную, dT_w в Кельвинах — совпадает с `solve_ivp` output
- ⚠️ **`reconstruct_profiles` принимает скаляры:** `r_b, Sg_w, dT_w` — одна точка. Для графиков на последний момент времени берём `sol.y[:, -1]`
- ⚠️ **`IntegrationWarning`:** при t_eps ≈ 0 solver может выдать предупреждения — подавляем `warnings.filterwarnings` в тестах, но не в CLI (пользователь должен видеть)
- ⚠️ **`matplotlib.use("Agg")`:** обязательно перед `import matplotlib.pyplot` — CLI без дисплея (серверный режим). Паттерн уже есть в `scripts/plot_profiles.py:14–15`
- ✅ **Обратная совместимость:** `main.py` — новый файл, ничего не ломает
- ⚠️ **`sol.status`:** если `solve_ivp` не сошлась (`sol.success == False`), нужно вывести предупреждение, но всё равно сохранить результаты (частичное решение полезно для отладки)
- ✅ **Формулы vs код:** нет новых формул, только вызов существующих
- ⚠️ **Путь к конфигу:** `main.py` запускается из `method_of_moments/`, пути в конфиге относительные — `Path` обрабатывает корректно
- ✅ **Связь с другими задачами:** VAL-001..003 будут использовать `build_objects` и `run`
- ⚠️ **`comment` в JSON-секциях:** `baseline.json` содержит поля `"comment"` в каждой секции. Они безвредны: `rock["comment"]` просто игнорируется кодом, `solver_opts["comment"]` не передаётся в `solve_moments` (план берёт поля по одному). Но если кто-то передаст `solver_opts` как `**kwargs` в `solve_ivp` — получит ошибку
- ⚠️ **Пустой результат solver:** если `sol.t.size == 0`, вызов `sol.t[0]` в `print` → `IndexError`. Guard добавлен в `run()`
- ✅ **`argparse` — lazy import:** импортируется только внутри `if __name__ == "__main__"`, чтобы `from src.main import build_objects` в тестах не тянул argparse
- ⚠️ **Запуск только через `-m`:** `main.py` использует относительные импорты (`from .pvt.black_oil`), поэтому `python src/main.py` → `ImportError`. Правильно: `python -m src.main configs/baseline.json`. Паттерн аналогичен `solver.py` (тоже относительные импорты, не запускается напрямую)
- ⚠️ **Длинный интервал интегрирования:** `baseline.json` задаёт `t_end=86400` (1 сутки), тогда как существующие тесты solver работают с `t_end=0.1` (6 порядков разницы). Smoke-тест с `run()` — первый запуск solver на длинном интервале. Возможные проблемы: (1) медленное выполнение (минуты), (2) event `_event_rb_reached` может сработать раньше `t_end`, (3) сходимость Radau на жёсткой системе при больших t. Если тест слишком долгий — создать `configs/test_short.json` с `t_end ≈ 10–100` с для быстрых тестов, а `baseline.json` оставить для ручной верификации (шаг 7)

---

## Этапы реализации

### Шаг 1: `load_config` и `build_objects`

**Цель:** парсинг JSON-конфига и создание всех Python-объектов, необходимых для `solve_moments`.

**Файлы:** `method_of_moments/src/main.py` (новый)

**Контекст:**
Сейчас создание объектов из `baseline.json` дублируется в трёх тестовых файлах (`test_solver.py:41–69`, `test_coefficients.py:36–49`, `test_ode_system.py:35–48`). Функция `build_objects` унифицирует этот код.

Маппинг конфиг → конструкторы описан в секции «Связь конфиг → конструкторы» выше.

**Что сделать:**

1. Создать файл `method_of_moments/src/main.py`
2. Импорты: `json`, `pathlib.Path`, `sys`, `numpy as np` (без `argparse` — он импортируется только внутри `if __name__ == "__main__"` в шаге 5, чтобы не нагружать импорт модуля из тестов)
3. Импорты из проекта:
   ```python
   from .pvt.black_oil import BlackOilFluid
   from .profiles.pressure import PressureProfile
   from .profiles.temperature import TemperatureProfile
   from .profiles.saturation import SaturationProfile
   from .solver import solve_moments, reconstruct_profiles
   ```
4. Функция `load_config(path)`:
   ```python
   def load_config(path):
       """JSON-конфиг → dict."""
       with open(path) as f:
           return json.load(f)
   ```
5. Функция `build_objects(cfg)`:
   ```python
   def build_objects(cfg):
       """Конфиг → (fluid, rock, p_profile, t_profile, s_profile, solver_opts)."""
       fluid = BlackOilFluid(
           pvt_config=cfg["pvt"],
           p_b=cfg["initial_conditions"]["p_b"],
           T_0=cfg["initial_conditions"]["T_0"],
           relperm_config=cfg["relative_permeability"],
       )
       rock = cfg["rock"]

       geo = cfg["geometry"]
       ic = cfg["initial_conditions"]
       bc = cfg["boundary_conditions"]
       prof = cfg["profiles"]

       p_profile = PressureProfile(geo["r_w"], geo["R_ext"],
                                   bc["p_wf"], ic["p_0"])
       t_profile = TemperatureProfile(geo["r_w"], geo["R_ext"],
                                      ic["T_0"], prof["sigma"])
       s_profile = SaturationProfile(geo["r_w"], prof["beta"])

       solver_opts = cfg["solver"]

       return fluid, rock, p_profile, t_profile, s_profile, solver_opts
   ```

**Проверка после шага:**
```
cd method_of_moments
.venv\Scripts\python -c "from src.main import load_config, build_objects; cfg = load_config('configs/baseline.json'); print(build_objects(cfg))"
```

**Зависимости:** нет (первый шаг)
**Оценка:** ~40 строк, ~10 минут

---

### Шаг 2: `save_csv`

**Цель:** сохранение результатов `solve_ivp` в CSV.

**Файлы:** `method_of_moments/src/main.py`

**Контекст:**
`solve_ivp` возвращает `OdeResult` с полями:
- `sol.t` — массив моментов времени (shape: (N,))
- `sol.y` — массив решений (shape: (3, N)): `y[0] = r_b`, `y[1] = Sg_w`, `y[2] = dT_w`
- `sol.success` — bool

**Что сделать:**

```python
def save_csv(sol, path):
    """OdeResult → CSV с колонками t, r_b, Sg_w, dT_w."""
    data = np.column_stack([sol.t, sol.y.T])
    header = "t,r_b,Sg_w,dT_w"
    np.savetxt(path, data, delimiter=",", header=header, comments="")
```

**Проверка после шага:** модуль импортируется без ошибок; CSV создаётся в шаге 5.
**Зависимости:** Требует: шаг 1.
**Оценка:** ~5 строк, ~5 минут

---

### Шаг 3: `plot_dynamics`

**Цель:** график $r_b(t)$ — динамика радиуса двухфазной зоны.

**Файлы:** `method_of_moments/src/main.py`

**Контекст:**
$r_b(t)$ — ключевая выходная величина метода моментов. Монотонно растёт от $r_w$ до $R_{ext}$. Физический смысл: граница зоны разгазирования расширяется по мере снижения давления.

Паттерн графиков — из `scripts/plot_profiles.py:44–51`:
```python
matplotlib.use("Agg")
plt.rcParams.update({"font.size": 11, "axes.grid": True, ...})
```

**Что сделать:**

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def plot_dynamics(sol, path):
    """r_b(t) → PNG."""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sol.t, sol.y[0])
    ax.set_xlabel("$t$, с")
    ax.set_ylabel("$r_b$, м")
    ax.set_title("Динамика радиуса двухфазной зоны")
    ax.grid(True, alpha=0.3)
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
```

Важно: `matplotlib.use("Agg")` и `import matplotlib.pyplot` — на уровне модуля, **до** определения функций. Размещаются **после** остальных импортов, **перед** определением функций.

**Проверка после шага:** модуль импортируется; график создаётся в шаге 5.
**Зависимости:** Требует: шаг 1.
**Оценка:** ~15 строк, ~10 минут

---

### Шаг 4: `plot_profiles`

**Цель:** графики $p(r)$, $S_g(r)$, $T(r)$ на последний момент времени решения.

**Файлы:** `method_of_moments/src/main.py`

**Контекст:**
Паттерн из `scripts/plot_profiles.py:193–224` (`plot_combined`):
- 3 subplots в одном figure (p, Sg, T), общая ось x (semilogx)
- `r` на геометрической сетке: `np.geomspace(r_w, R_ext, 500)`
- Вертикальная линия $r_b$
- Горизонтальная линия $p_b^*$ на графике давления

Для восстановления профилей вызывается `reconstruct_profiles(r_b, Sg_w, dT_w, ...)` из `solver.py:58–68`. Она принимает скаляры и массив `r_grid`.

**Что сделать:**

```python
def plot_profiles(sol, p_profile, t_profile, s_profile, fluid,
                  r_w, r_e, path):
    """p(r), Sg(r), T(r) на последний момент → PNG."""
    r_b, Sg_w, dT_w = sol.y[:, -1]
    r_grid = np.geomspace(r_w, r_e, 500)
    p_arr, Sg_arr, T_arr = reconstruct_profiles(
        r_b, Sg_w, dT_w, p_profile, t_profile, s_profile,
        fluid, r_grid)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 12),
                                         sharex=True)
    ax1.semilogx(r_grid, p_arr / 1e6)
    ax1.axvline(r_b, color="k", ls="--", lw=0.8, label=f"$r_b$ = {r_b:.1f} м")
    ax1.set_ylabel("$p$, МПа")
    ax1.set_title("Профили на последний момент времени")
    ax1.legend()

    ax2.semilogx(r_grid, Sg_arr)
    ax2.axvline(r_b, color="k", ls="--", lw=0.8)
    ax2.set_ylabel("$S_g$")

    ax3.semilogx(r_grid, T_arr)
    ax3.axvline(r_b, color="k", ls="--", lw=0.8)
    ax3.set_xlabel("$r$, м")
    ax3.set_ylabel("$T$, К")

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
```

**Подводные камни:**
- `reconstruct_profiles` принимает скаляры `r_b, Sg_w, dT_w`, не массивы
- `sol.y[:, -1]` — последняя точка решения
- Если `sol.y.shape[1] == 0` (solver не сделал ни одного шага) — нужно пропустить

**Проверка после шага:** модуль импортируется; график создаётся в шаге 5.
**Зависимости:** Требует: шаг 1.
**Оценка:** ~30 строк, ~15 минут

---

### Шаг 5: `run` и `__main__`

**Цель:** полный pipeline и CLI-точка входа.

**Файлы:** `method_of_moments/src/main.py`

**Контекст:**
Функция `run` объединяет все предыдущие шаги: load → build → solve → save → plot.
`__main__` блок использует `argparse` для CLI.

**Что сделать:**

```python
def run(config_path, output_dir="results"):
    """JSON-конфиг → решение → CSV + графики."""
    cfg = load_config(config_path)
    fluid, rock, p_profile, t_profile, s_profile, solver_opts = build_objects(cfg)

    geo = cfg["geometry"]
    bc = cfg["boundary_conditions"]
    p_wf = bc["p_wf"]
    r_w = geo["r_w"]
    r_e = geo["R_ext"]

    sol = solve_moments(
        fluid, rock, p_profile, t_profile, s_profile,
        p_wf, r_e, solver_opts["t_end"],
        t_eps=solver_opts["t_epsilon"],
        method=solver_opts.get("method", "Radau"),
        rtol=solver_opts.get("rtol", 1e-6),
        atol=solver_opts.get("atol", 1e-9),
    )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not sol.success:
        print(f"Предупреждение: solver не сошёлся — {sol.message}", file=sys.stderr)

    if sol.t.size == 0:
        print("Предупреждение: solver не вернул ни одной точки.", file=sys.stderr)
        return sol

    save_csv(sol, out / "solution.csv")
    plot_dynamics(sol, out / "rb_vs_t.png")
    plot_profiles(sol, p_profile, t_profile, s_profile, fluid,
                  r_w, r_e, out / "profiles.png")

    print(f"Результаты: {out}/")
    print(f"  solution.csv  ({sol.t.shape[0]} точек, t ∈ [{sol.t[0]:.2e}, {sol.t[-1]:.2e}] с)")
    print(f"  rb_vs_t.png")
    print(f"  profiles.png")
    return sol


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Метод моментов — решатель двухфазной фильтрации Black Oil")
    parser.add_argument("config", help="путь к JSON-конфигу")
    parser.add_argument("--output-dir", default="results",
                        help="директория для результатов (по умолчанию: results/)")
    args = parser.parse_args()
    run(args.config, args.output_dir)
```

**Подводные камни:**
- `solver_opts` содержит `t_epsilon`, `t_end`, `method`, `rtol`, `atol` — передаются в `solve_moments` через именованные аргументы и `**ivp_kwargs`
- Поля `method`, `rtol`, `atol` передаются через `**ivp_kwargs` (solver.py:53 делает `defaults.update(ivp_kwargs)`)
- `t_epsilon` → параметр `t_eps` в `solve_moments`
- `comment` в JSON — игнорируется (не совпадает ни с одним именованным аргументом)

**Проверка после шага:**
```
cd method_of_moments
.venv\Scripts\python -m src.main configs\baseline.json --output-dir results\test_run
```
Ожидание: директория `results/test_run/` с файлами `solution.csv`, `rb_vs_t.png`, `profiles.png`.

**Зависимости:** Требует: шаги 1–4. Блокирует: шаг 6.
**Оценка:** ~40 строк, ~15 минут

---

### Шаг 6: Smoke-тест

**Цель:** автоматическая проверка, что pipeline работает без ошибок.

**Файлы:** `method_of_moments/tests/test_main.py` (новый)

**Контекст:**
Smoke-тест — критерий готовности FEAT-008. Проверяет: `baseline.json → solve → .csv + .png без ошибок`.

**Что сделать:**

```python
"""Smoke-тесты CLI — FEAT-008."""

from pathlib import Path

import numpy as np
import pytest

from src.main import load_config, build_objects, run


CONFIGS = Path(__file__).resolve().parent.parent / "configs"


class TestLoadConfig:
    def test_loads_baseline(self):
        cfg = load_config(CONFIGS / "baseline.json")
        assert "geometry" in cfg
        assert "pvt" in cfg
        assert "solver" in cfg

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.json")


class TestBuildObjects:
    def test_builds_from_baseline(self):
        cfg = load_config(CONFIGS / "baseline.json")
        fluid, rock, p_prof, t_prof, s_prof, solver_opts = build_objects(cfg)
        assert fluid.p_b == cfg["initial_conditions"]["p_b"]
        assert p_prof.r_w == cfg["geometry"]["r_w"]
        assert t_prof.T_0 == cfg["initial_conditions"]["T_0"]
        assert s_prof.beta == cfg["profiles"]["beta"]
        assert "t_end" in solver_opts


@pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")
class TestRun:
    def test_smoke_baseline(self, tmp_path):
        sol = run(str(CONFIGS / "baseline.json"), str(tmp_path))
        assert sol.success
        assert sol.y.shape[0] == 3
        assert sol.y[0, -1] > sol.y[0, 0]  # r_b растёт

        assert (tmp_path / "solution.csv").exists()
        assert (tmp_path / "rb_vs_t.png").exists()
        assert (tmp_path / "profiles.png").exists()

    def test_csv_columns(self, tmp_path):
        run(str(CONFIGS / "baseline.json"), str(tmp_path))
        csv_path = tmp_path / "solution.csv"
        with open(csv_path) as f:
            header = f.readline().strip()
        assert header == "t,r_b,Sg_w,dT_w"

    def test_csv_values_physical(self, tmp_path):
        run(str(CONFIGS / "baseline.json"), str(tmp_path))
        data = np.loadtxt(tmp_path / "solution.csv", delimiter=",",
                          skiprows=1)
        r_b = data[:, 1]
        Sg_w = data[:, 2]
        assert np.all(r_b > 0.1)         # r_b > r_w = 0.1 м
        assert np.all(Sg_w >= 0)          # Sg_w ≥ 0
        assert np.all(Sg_w <= 1)          # Sg_w ≤ 1
```

**Тестовая стратегия:**

| Тест | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|
| `test_loads_baseline` | load_config с валидным JSON | dict с ключами | неверный парсинг |
| `test_missing_file_raises` | несуществующий файл | FileNotFoundError | тихий сбой |
| `test_builds_from_baseline` | build_objects из baseline | объекты с корректными атрибутами | неверный маппинг конфиг→объект |
| `test_smoke_baseline` | полный pipeline | sol.success, файлы созданы, r_b растёт | интеграционная регрессия |
| `test_csv_columns` | CSV header | "t,r_b,Sg_w,dT_w" | неверный формат CSV |
| `test_csv_values_physical` | физические ограничения | r_b > r_w, 0 ≤ Sg_w ≤ 1 | нефизичные результаты |

**Проверка после шага:**
```
cd method_of_moments
.venv\Scripts\python -m pytest tests/test_main.py -v
.venv\Scripts\python -m pytest tests/ -v   # регрессия
```

**Подводный камень:** три теста `TestRun` вызывают `run()` независимо — это 3 полных прогона `solve_ivp`. При длительном `t_end=86400` тесты могут занять несколько минут. Если это проблема — объединить в один тест с несколькими assert, или создать фикстуру `@pytest.fixture(scope="class")` с `tmp_path_factory`.

**Зависимости:** Требует: шаг 5.
**Оценка:** ~50 строк, ~15 минут

---

### Шаг 7: Ручная верификация

**Цель:** визуальная проверка графиков и физических инвариантов.

**Файлы:** нет новых файлов

**Что сделать:**

1. Запуск:
   ```
   cd method_of_moments
   .venv\Scripts\python -m src.main configs\baseline.json --output-dir results\baseline
   ```

2. Проверить `rb_vs_t.png`:
   - $r_b$ монотонно растёт
   - Начинается вблизи $r_w = 0.1$ м
   - Порядок $r_b$ в конце: метры–десятки метров (зависит от t_end = 86400 с = 1 сутки)

3. Проверить `profiles.png`:
   - $p(r)$: монотонно растёт от $p_{wf} = 15$ МПа до $p_0 = 20$ МПа
   - $S_g(r)$: максимум на забое, обращается в ноль при $r = r_b$
   - $T(r)$: минимум на забое ($T_0 - \Delta T_w$), возвращается к $T_0$ при $r \to R_{ext}$

4. Проверить `solution.csv`:
   - Открыть, убедиться в корректности формата
   - Последняя строка: разумные значения

**Зависимости:** Требует: шаг 5.
**Оценка:** ~10 минут

---

## Затронутые файлы

| Файл | Действие | Строки |
|---|---|---|
| `method_of_moments/src/main.py` | создать | ~120 |
| `method_of_moments/tests/test_main.py` | создать | ~55 |
| `method_of_moments/configs/baseline.json` | без изменений | — |
| `method_of_moments/src/solver.py` | без изменений | — |
| `method_of_moments/src/pvt/black_oil.py` | без изменений | — |
| `method_of_moments/src/profiles/*.py` | без изменений | — |

## Критерии завершения

- [ ] `main.py` создан, все 6 функций реализованы
- [ ] `build_objects` корректно маппит baseline.json → объекты
- [ ] `run` выполняет полный pipeline без ошибок
- [ ] CSV содержит 4 колонки (t, r_b, Sg_w, dT_w)
- [ ] Графики PNG создаются (`rb_vs_t.png`, `profiles.png`)
- [ ] Smoke-тесты зелёные (`test_main.py`)
- [ ] Все существующие тесты зелёные (регрессия)
- [ ] Визуальная проверка графиков пройдена
- [ ] Vault обновлён
- [ ] GitHub issue #11 прокомментирован

## Обнаруженные проблемы

**Неблокирующие (после FEAT-008):**

1. **DEBT (потенциальный):** Дублирование `build_objects` в тестах. Три файла (`test_solver.py`, `test_coefficients.py`, `test_ode_system.py`) содержат одинаковый код создания объектов из `baseline.json`. После FEAT-008 можно вынести в `conftest.py` и импортировать `build_objects` из `main.py`. За рамками текущей задачи — CLAUDE.md: «не добавляй абстракции сверх задачи».

## Связанные заметки

- [[планируемые фичи]] — запись FEAT-008
- [[roadmap реализации]] — фаза 6
- [[feat-007b solver-wrapper]] — план предыдущей задачи (solver API)
