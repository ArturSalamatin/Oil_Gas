---
tags:
  - план
  - физика
date: 2026-07-29
issue: FEAT-002
github: 2
branch: feat/feat-002/corey-relperm
model_level: null
status: в процессе
audit:
  date: 2026-07-29
  found: 0
  auto-fixed: 0
  manual-required: 0
  round: 3
---

# План: FEAT-002 — Относительные фазовые проницаемости (ОФП) Кори

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex` строки 70–83 (eq:mobility, eq:Lambda)
3. Создай ветку: `git checkout -b feat/feat-002/corey-relperm`
4. Активируй venv: `.venv/Scripts/activate`
5. Прогони тесты (baseline): `cd method_of_moments && .venv/Scripts/python -m pytest tests/ -v`
6. Убедись: 31 тест зелёный (FEAT-001)
7. Начни с шага 1

## Мотивация

ОФП — входные данные для уравнений фильтрации Black Oil. Подвижности фаз $\lambda_o$, $\lambda_g$ и суммарная приведённая подвижность $\Lambda$ входят во все последующие модули: профили давления (FEAT-003), интегралы (FEAT-004), коэффициенты ODE (FEAT-005). Без ОФП невозможно собрать правую часть системы.

## Связь формула → код

| Формула | Уравнение в tex | Python-метод | Модуль | Тест |
|---|---|---|---|---|
| $k_{ro}(S_g)$ | входные данные (Кори) | `BlackOilFluid.kro(Sg)` | `src/pvt/black_oil.py` | `test_kro_*` |
| $k_{rg}(S_g)$ | входные данные (Кори) | `BlackOilFluid.krg(Sg)` | `src/pvt/black_oil.py` | `test_krg_*` |
| $\lambda_\alpha = k \cdot k_{r\alpha}(S_g) / \mu_\alpha(p,T)$ | \eqref{eq:mobility} стр. 71–73 | `BlackOilFluid.mobility_o(p,T,Sg,k)`, `mobility_g(...)` | `src/pvt/black_oil.py` | `test_mobility_*` |
| $\Lambda = k/B_g \cdot (k_{ro}/\mu_o + k_{rg}/\mu_g)$ | \eqref{eq:Lambda} стр. 77–83 | `BlackOilFluid.Lambda(p,T,Sg,k)` | `src/pvt/black_oil.py` | `test_Lambda_*` |
| $\lambda_o / B_o$ | вспомогательная, §5 | `BlackOilFluid.mobility_o_over_Bo(p,T,Sg,k)` | `src/pvt/black_oil.py` | `test_mobility_o_over_Bo` |

## Обратная совместимость

- [x] `__init__` расширяется опциональным `relperm_config=None` → дефолты
- [x] Существующие вызовы `BlackOilFluid(pvt_config, p_b, T_0)` без изменений
- [x] Существующие 31 тест не затрагиваются
- [x] Конфиг `baseline.json` уже содержит секцию `relative_permeability`
- [x] Новые методы — дополнение, не замена

## Подводные камни

- ✅ **Размерности:** kro, krg безразмерны; λ [м²/(Па·с)]; Λ [м²/(Па·с)]
- ⚠️ **Граничные случаи:** Sg ≤ Sgc → krg=0; Sg ≥ 1−Sor → kro=0; нормализованная насыщенность за пределами [0,1] → clamp
- ⚠️ **Деление на ноль:** μ_o, μ_g, Bg > 0 при физических p,T — гарантировано PVT
- ✅ **Import-цепочки:** всё внутри `black_oil.py` — circular imports невозможны
- ✅ **Обратная совместимость:** opt-in параметр с дефолтами

---

## Шаги реализации

### Шаг 1: Расширить `__init__` — параметры ОФП

**Цель:** принять параметры модели Кори из конфига (или задать дефолты).

**Файлы:** `method_of_moments/src/pvt/black_oil.py`

**Контекст:**
Текущий `__init__` (строка 9–17) принимает `pvt_config: dict` с `rho_o_st`, `rho_g_st` и скалярные `p_b`, `T_0`. Нужно добавить параметр `relperm_config: dict | None = None`.

**Что сделать:**

1. Добавить параметр `relperm_config=None` в сигнатуру `__init__`
2. Если `relperm_config is None` — задать дефолты:
   ```python
   relperm_config = relperm_config or {}
   self._S_or = relperm_config.get("S_or", 0.2)
   self._S_gc = relperm_config.get("S_gc", 0.05)
   self._n_o = relperm_config.get("n_o", 2.0)
   self._n_g = relperm_config.get("n_g", 2.0)
   self._kro_max = relperm_config.get("k_ro_max", 1.0)
   self._krg_max = relperm_config.get("k_rg_max", 0.8)
   ```
3. Вычислить и сохранить знаменатель нормализации:
   ```python
   self._S_norm = 1.0 - self._S_or - self._S_gc
   ```

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/test_pvt.py -v` → 31 тест зелёный (без изменений)

**Зависимости:** —
**Оценка:** ~10 строк, ~5 минут

---

### Шаг 2: Реализовать `kro(Sg)` и `krg(Sg)`

**Цель:** ОФП по модели Кори — чистые функции от газонасыщенности.

**Файлы:** `method_of_moments/src/pvt/black_oil.py`

**Формулы:**

Нормализованная газонасыщенность:
$$S^* = \frac{S_g - S_{gc}}{1 - S_{or} - S_{gc}}$$

Относительные проницаемости (модель Кори):
$$k_{ro}(S_g) = k_{ro,\max} \cdot (1 - S^*)^{n_o}$$
$$k_{rg}(S_g) = k_{rg,\max} \cdot (S^*)^{n_g}$$

Граничные случаи:
- $S_g \le S_{gc}$: $S^* = 0$, $k_{ro} = k_{ro,\max}$, $k_{rg} = 0$
- $S_g \ge 1 - S_{or}$: $S^* = 1$, $k_{ro} = 0$, $k_{rg} = k_{rg,\max}$

**Что сделать:**

1. Добавить вспомогательный метод `_S_star(Sg)`:
   ```python
   def _S_star(self, Sg):
       """Нормализованная газонасыщенность."""
       return max(0.0, min(1.0, (Sg - self._S_gc) / self._S_norm))
   ```

2. Добавить метод `kro(Sg)`:
   ```python
   def kro(self, Sg):
       """Относительная проницаемость нефти (Кори)."""
       return self._kro_max * (1.0 - self._S_star(Sg)) ** self._n_o
   ```

3. Добавить метод `krg(Sg)`:
   ```python
   def krg(self, Sg):
       """Относительная проницаемость газа (Кори)."""
       return self._krg_max * self._S_star(Sg) ** self._n_g
   ```

**Проверка после шага:**
- Ручная: `kro(0)` → `kro_max`, `krg(0)` → `0`
- Регрессия: `.venv/Scripts/python -m pytest tests/test_pvt.py -v`

**Зависимости:** Требует: шаг 1.
**Оценка:** ~15 строк, ~10 минут

---

### Шаг 3: Реализовать подвижности и Λ

**Цель:** подвижности фаз $\lambda_o$, $\lambda_g$, суммарная приведённая подвижность $\Lambda$ и вспомогательная $\lambda_o / B_o$.

**Файлы:** `method_of_moments/src/pvt/black_oil.py`

**Формулы:**

Подвижность фазы (eq:mobility):
$$\lambda_\alpha = \frac{k \cdot k_{r\alpha}(S_g)}{\mu_\alpha(p,T)}, \quad \alpha \in \{o, g\}$$

Суммарная приведённая подвижность (eq:Lambda):
$$\Lambda(p,T,S_g) = \frac{k}{B_g(p,T)} \left( \frac{k_{ro}(S_g)}{\mu_o(p,T)} + \frac{k_{rg}(S_g)}{\mu_g(p,T)} \right)$$

Вспомогательная (часто встречается в §5):
$$\frac{\lambda_o}{B_o} = \frac{k \cdot k_{ro}(S_g)}{\mu_o(p,T) \cdot B_o(p,T)}$$

**Что сделать:**

1. Метод `mobility_o(p, T, Sg, k)`:
   ```python
   def mobility_o(self, p, T, Sg, k):
       """λ_o = k·kro/μo. Ур. (eq:mobility) moments_method.tex."""
       return k * self.kro(Sg) / self.mu_o(p, T)
   ```

2. Метод `mobility_g(p, T, Sg, k)`:
   ```python
   def mobility_g(self, p, T, Sg, k):
       """λ_g = k·krg/μg. Ур. (eq:mobility) moments_method.tex."""
       return k * self.krg(Sg) / self.mu_g(p, T)
   ```

3. Метод `Lambda(p, T, Sg, k)`:
   ```python
   def Lambda(self, p, T, Sg, k):
       """Λ = (λ_o + λ_g)/Bg. Ур. (eq:Lambda) moments_method.tex."""
       return (self.mobility_o(p, T, Sg, k)
               + self.mobility_g(p, T, Sg, k)) / self.Bg(p, T)
   ```

4. Метод `mobility_o_over_Bo(p, T, Sg, k)`:
   ```python
   def mobility_o_over_Bo(self, p, T, Sg, k):
       """λ_o/B_o — вспомогательная, §5 moments_method.tex."""
       return self.mobility_o(p, T, Sg, k) / self.Bo(p, T)
   ```

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/test_pvt.py -v`

**Зависимости:** Требует: шаг 2.
**Оценка:** ~20 строк, ~10 минут

---

### Шаг 4: Тесты ОФП — `test_relperm.py`

**Цель:** unit-тесты для `kro`, `krg`, `_S_star`, граничные случаи, монотонность.

**Файлы:** `method_of_moments/tests/test_relperm.py` (новый)

**Что сделать:**

Создать `test_relperm.py`. Импорты и параметры тестов:
```python
import json
import pytest
from pathlib import Path
from src.pvt.black_oil import BlackOilFluid

S_OR = 0.2
S_GC = 0.05
N_O = 2.0
N_G = 2.0
KRO_MAX = 1.0
KRG_MAX = 0.8

P = 15e6       # Па
T = 350.0      # К
K_ABS = 1e-13  # м² — абсолютная проницаемость
```

Фикстура:
```python
@pytest.fixture
def fluid():
    return BlackOilFluid(
        {"rho_o_st": 850.0, "rho_g_st": 0.85},
        p_b=18e6, T_0=350.0,
        relperm_config={"S_or": S_OR, "S_gc": S_GC, "n_o": N_O, "n_g": N_G,
                        "k_ro_max": KRO_MAX, "k_rg_max": KRG_MAX})
```

Тесты:

| Тест | Сценарий | Ожидание | Предотвращает |
|---|---|---|---|
| `test_kro_at_Sg_zero` | Sg=0 | kro = kro_max = 1.0 | ошибка нормализации при Sg < Sgc |
| `test_krg_at_Sg_zero` | Sg=0 | krg = 0 | утечка газовой подвижности |
| `test_kro_at_Sg_max` | Sg = 1−Sor = 0.8 | kro = 0 | нефть при полном вытеснении |
| `test_krg_at_Sg_max` | Sg = 1−Sor = 0.8 | krg = krg_max = 0.8 | неправильный максимум |
| `test_kro_at_Sgc` | Sg = Sgc = 0.05 | kro = kro_max | граница: S*=0 |
| `test_krg_at_Sgc` | Sg = Sgc = 0.05 | krg = 0 | граница: S*=0 |
| `test_kro_monotone_decreasing` | Sg от 0 до 0.8 (20 точек) | kro[i] >= kro[i+1] | немонотонность |
| `test_krg_monotone_increasing` | Sg от 0 до 0.8 (20 точек) | krg[i] <= krg[i+1] | немонотонность |
| `test_kro_krg_in_01` | Sg от 0 до 0.8 | 0 ≤ kro ≤ kro_max, 0 ≤ krg ≤ krg_max | выход за диапазон |
| `test_kro_clamp_below_zero` | Sg = −0.01 | kro = kro_max (clamp) | отрицательная насыщенность |
| `test_krg_clamp_above_max` | Sg = 0.95 > 1−Sor | krg = krg_max (clamp) | выход за допустимый диапазон |
| `test_kro_known_value` | Sg = 0.425 (S*=0.5) | kro = 1.0·0.5² = 0.25 | ошибка формулы |
| `test_krg_known_value` | Sg = 0.425 (S*=0.5) | krg = 0.8·0.5² = 0.2 | ошибка формулы |

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_relperm.py -v` → 13 тестов зелёные
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` → 44 теста зелёные

**Зависимости:** Требует: шаги 1–2.
**Оценка:** ~80 строк, ~20 минут

---

### Шаг 5: Тесты подвижностей и Λ

**Цель:** unit-тесты для `mobility_o`, `mobility_g`, `Lambda`, `mobility_o_over_Bo`.

**Файлы:** `method_of_moments/tests/test_relperm.py` (дополнить)

**Параметры тестов:**
```
p = 15e6 Па, T = 350 К, Sg = 0.1, k = 1e-13 м²
```

Тесты:

| Тест | Сценарий | Ожидание | Формула |
|---|---|---|---|
| `test_mobility_o_formula` | p, T, Sg, k | λ_o = k·kro(Sg)/μo(p,T) (прямая проверка) | \eqref{eq:mobility} |
| `test_mobility_g_formula` | p, T, Sg, k | λ_g = k·krg(Sg)/μg(p,T) (прямая проверка) | \eqref{eq:mobility} |
| `test_mobility_o_positive` | p, T, Sg=0.1, k | λ_o > 0 (Sg < 1−Sor) | физика |
| `test_mobility_g_positive` | p, T, Sg=0.1, k | λ_g > 0 (Sg > Sgc) | физика |
| `test_mobility_g_zero_below_Sgc` | Sg=0 | λ_g = 0 | krg=0 → λ_g=0 |
| `test_Lambda_formula` | p, T, Sg, k | Λ = (λ_o + λ_g)/Bg (прямая проверка) | \eqref{eq:Lambda} |
| `test_Lambda_positive` | p, T, Sg=0.1, k | Λ > 0 | физика |
| `test_Lambda_single_phase` | Sg=0, k | Λ = kro_max·k/(Bg·μo) (однофазный предел, стр. 854; при kro_max=1 совпадает с Λ₀) | eq:diffusion |
| `test_mobility_o_over_Bo_formula` | p, T, Sg, k | = mobility_o / Bo | определение |
| `test_mobility_o_over_Bo_positive` | p, T, Sg=0.1, k | > 0 | физика |

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_relperm.py -v` → 23 теста зелёные
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` → 54 теста зелёные

**Зависимости:** Требует: шаги 1–3.
**Оценка:** ~60 строк, ~15 минут

---

### Шаг 6: Тест загрузки из `baseline.json`

**Цель:** интеграционный тест — `BlackOilFluid` с параметрами ОФП из конфига.

**Файлы:** `method_of_moments/tests/test_relperm.py` (дополнить)

**Что сделать:**

```python
def test_baseline_config_relperm():
    config_path = Path(__file__).parent.parent / "configs" / "baseline.json"
    with open(config_path) as f:
        config = json.load(f)
    fluid = BlackOilFluid(
        config["pvt"],
        config["initial_conditions"]["p_b"],
        config["initial_conditions"]["T_0"],
        relperm_config=config["relative_permeability"])
    k = config["rock"]["k"]
    p = config["initial_conditions"]["p_0"]
    T = config["initial_conditions"]["T_0"]
    # Однофазный случай (Sg=0):
    assert fluid.kro(0.0) == pytest.approx(config["relative_permeability"]["k_ro_max"])
    assert fluid.krg(0.0) == 0.0
    assert fluid.Lambda(p, T, 0.0, k) > 0
```

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_relperm.py -v` → 24 теста
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` → 55 тестов

**Зависимости:** Требует: шаги 1–3.
**Оценка:** ~15 строк, ~5 минут

---

### Шаг 7: Тест дефолтов (без relperm_config)

**Цель:** проверить, что существующий код с `BlackOilFluid(pvt_config, p_b, T_0)` работает и ОФП доступны с дефолтами.

**Файлы:** `method_of_moments/tests/test_relperm.py` (дополнить)

**Что сделать:**

```python
def test_default_relperm_config():
    """BlackOilFluid без relperm_config — дефолтные параметры Кори."""
    fluid = BlackOilFluid({"rho_o_st": 850.0, "rho_g_st": 0.85}, 18e6, 350.0)
    assert fluid.kro(0.0) == pytest.approx(1.0)
    assert fluid.krg(0.0) == 0.0
    assert fluid._S_or == 0.2
    assert fluid._S_gc == 0.05
```

**Проверка после шага:**
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v` → 56 тестов

**Зависимости:** Требует: шаги 1–2 (тест вызывает `kro`/`krg`).
**Оценка:** ~8 строк, ~3 минут

---

## Тестовая стратегия (сводка)

| Категория | Количество | Примеры |
|---|---|---|
| Unit (отдельные формулы) | 13 | kro/krg при известных Sg |
| Аналитические | 2 | kro, krg при S*=0.5 — проверка степенной формулы |
| Предельные случаи | 4 | Sg=0, Sg=Sgc, Sg=1−Sor, Sg вне диапазона |
| Монотонность / инвариант | 3 | kro↓, krg↑, kro/krg ∈ [0, max] |
| Согласованность формул | 4 | Λ = (λo+λg)/Bg, λo/Bo |
| Однофазный предел | 1 | Λ(Sg=0) = k/(Bg·μo) |
| Интеграция (конфиг) | 2 | baseline.json, дефолты |

**Итого:** ~25 новых тестов.

## Критерии завершения

- [ ] `kro`, `krg`, `_S_star` реализованы с clamp
- [ ] `mobility_o`, `mobility_g`, `Lambda`, `mobility_o_over_Bo` реализованы
- [ ] Каждый метод имеет однострочный docstring с ссылкой на уравнение
- [ ] ~25 тестов зелёные (`test_relperm.py`)
- [ ] 31 существующий тест зелёный (`test_pvt.py`) — обратная совместимость
- [ ] Конфиг `baseline.json` → `BlackOilFluid` → ОФП работает
- [ ] Vault обновлён (статус FEAT-002)
- [ ] GitHub issue #2 прокомментирован

## Оценка

- **Файлов:** 2 (1 модификация + 1 новый)
- **Строк кода:** ~45 в `black_oil.py`, ~150 в `test_relperm.py`
- **Тестов:** ~25
- **Время:** ~60 минут
