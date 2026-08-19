---
tags:
  - план
  - вычисление
date: 2026-07-30
issue: FEAT-004
github: 4
branch: feat/feat-004/analytical-integrals
status: реализован
audit:
  date: 2026-07-30
  found: 0
  auto-fixed: 0
  manual-required: 0
---

# FEAT-004: Аналитические интегралы I_Φ^(n), I_S^(n), J^(m)

## Как начать работу по этому плану

1. Прочитай этот файл целиком
2. Прочитай `moments_method.tex` §5.4 (строки 769–778) — определения интегралов
3. Прочитай `moments_method.tex` §4.4 (строки 595–600) — определение J^(m)
4. Создай ветку: `git checkout -b feat/feat-004/analytical-integrals`
5. Прогони тесты (baseline): `cd method_of_moments && .venv\Scripts\python -m pytest tests/ -v` — ожидай 100 passed
6. Начни с шага 1. После каждого шага: pytest

---

## Подтип

**Вычисление** — три замкнутые формулы, чистая математика. Не вводят новой физики, не меняют ODE-систему. Подготавливают «кирпичи» для FEAT-005 (коэффициенты).

## Связь формула → код

| Формула | Уравнение в tex | Python-функция | Модуль | Тест |
|---|---|---|---|---|
| $I_\Phi^{(n)} = \frac{1}{n\gamma + 1}$ | `\eqref{eq:IPhi}` | `I_Phi(n, gamma)` | `method_of_moments/src/integrals.py` | `test_I_Phi_*` |
| $I_S^{(n)} = I_\Phi^{(n)} - \frac{1}{n\gamma + \beta + 1}$ | `\eqref{eq:IS}` | `I_S(n, gamma, beta)` | `method_of_moments/src/integrals.py` | `test_I_S_*` |
| $J^{(m)} = \frac{2}{m+1} - \frac{1}{m+\sigma+1}$ | `\eqref{eq:IPsi}` | `J(m, sigma)` | `method_of_moments/src/integrals.py` | `test_J_*` |

## Обратная совместимость

- [x] Существующие тесты пройдут без изменений — новый модуль, ничего не меняем
- [x] Существующие конфиги работают без изменений — модуль не подключается к солверу
- [x] API существующих функций не меняется
- [x] ODE система не затрагивается

**`TemperatureProfile.J(m)`** уже реализован в `src/profiles/temperature.py:50–52`. Решение: оставить как есть (метод использует `self.sigma` экземпляра). Новая функция `J(m, sigma)` в `integrals.py` — каноническая реализация с явным параметром `sigma`. `TemperatureProfile.J(m)` делегирует к ней (шаг 4). Это не ломает обратную совместимость — интерфейс `TemperatureProfile.J(m)` не меняется.

## Варианты решения

### Вариант A: Три чистые функции

Три free-функции `I_Phi`, `I_S`, `J` в `integrals.py`. Без классов, без состояния. Каждая принимает все параметры явно.

- Плюсы: минимальный код, прозрачность, легко тестировать
- Минусы: нет — для трёх формул класс избыточен
- Трудоёмкость: ~30 строк

### Вариант B: Класс MomentIntegrals

Класс хранит `gamma`, `beta`, `sigma`, вычисляет все интегралы. Удобен для FEAT-005 — передаёшь один объект.

- Плюсы: инкапсуляция параметров
- Минусы: лишняя абстракция для трёх формул, привязка к состоянию
- Трудоёмкость: ~50 строк

### Выбор: Вариант A

Три формулы — три функции. Класс не нужен: параметры (`gamma`, `beta`, `sigma`) не связаны друг с другом и приходят из разных объектов (`PressureProfile`, `SaturationProfile`, `TemperatureProfile`). При необходимости FEAT-005 может обернуть вызовы.

## Подводные камни

- ✅ **Размерности:** интегралы безразмерные — всё корректно
- ⚠️ **Граничные случаи:** `gamma = 0` даёт `I_Phi = 1/(0·0 + 1) = 1` — корректно. `n·gamma = -1` — полюс; физически невозможно (`gamma > 0`, `n >= 0`), но нужен guard
- ⚠️ **Численная устойчивость:** при `n·gamma + beta + 1` близко к 0 — деление. Физически `beta >= 0`, `gamma >= 0`, `n >= 0`, поэтому знаменатель >= 1. Безопасно, но assert полезен
- ✅ **Import-цепочки:** новый модуль, circular imports невозможны
- ✅ **Производительность:** O(1), три деления
- ✅ **Связь с другими задачами:** не конфликтует
- ⚠️ **math vs numpy:** в профилях (`pressure.py`, `saturation.py`, `temperature.py`) используется `math` вместо `numpy`. Правило CLAUDE.md требует `numpy`. В `integrals.py` использовать `numpy` нельзя — тут только арифметика (`/`, `+`), numpy не нужен. Но для `TemperatureProfile.J(m)` после делегирования это станет вызов из math-модуля в чистый Python-модуль — проблем нет. Миграция `math → numpy` для профилей — отдельная задача DEBT

## Обнаруженные проблемы

**DEBT (неблокирующая):** модули `profiles/pressure.py`, `profiles/saturation.py`, `profiles/temperature.py` используют `import math` вместо `numpy`. Нарушение правила CLAUDE.md. Не блокирует FEAT-004, но нужно зафиксировать как технический долг.

---

## Шаги реализации

### Шаг 1: Создать модуль `integrals.py`

**Цель:** реализовать три аналитические формулы

**Файлы:** `method_of_moments/src/integrals.py` (создать)

**Контекст:**
Интегралы возникают при подстановке параметризованных профилей $p(r)$, $S_g(r)$, $T(r)$ в уравнения баланса массы и энергии и интегрировании по радиусу. При замороженных PVT-свойствах (§5.4 moments_method.tex) интегралы вычисляются аналитически.

**Что сделать:**

1. Создать файл `method_of_moments/src/integrals.py`
2. Реализовать три функции:

```python
"""Аналитические интегралы метода моментов — §5.4 moments_method.tex."""


def I_Phi(n, gamma):
    """I_Φ^(n) = 1/(nγ+1). Ур. (eq:IPhi) moments_method.tex."""
    return 1.0 / (n * gamma + 1.0)


def I_S(n, gamma, beta):
    """I_S^(n) = I_Φ^(n) − 1/(nγ+β+1). Ур. (eq:IS) moments_method.tex."""
    return I_Phi(n, gamma) - 1.0 / (n * gamma + beta + 1.0)


def J(m, sigma):
    """J^(m) = 2/(m+1) − 1/(m+σ+1). Ур. (eq:IPsi) moments_method.tex."""
    return 2.0 / (m + 1.0) - 1.0 / (m + sigma + 1.0)
```

**Формулы:**

$$I_\Phi^{(n)} = \int_0^1 \eta^{n\gamma}\,d\eta = \frac{1}{n\gamma + 1}$$

$$I_S^{(n)} = \int_0^1 (1-\eta^\beta)\,\eta^{n\gamma}\,d\eta = I_\Phi^{(n)} - \frac{1}{n\gamma + \beta + 1}$$

$$J^{(m)} = \int_0^1 \zeta^m\,(2 - \zeta^\sigma)\,d\zeta = \frac{2}{m+1} - \frac{1}{m+\sigma+1}$$

**Проверка после шага:**
- Файл создан, import работает: `.venv/Scripts/python -c "from src.integrals import I_Phi, I_S, J; print(I_Phi(1, 1.0))"`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** нет. Блокирует: шаги 2, 3, 4.
**Оценка:** ~15 строк, ~5 минут

---

### Шаг 2: Unit-тесты — аналитика vs численное интегрирование

**Цель:** проверить замкнутые формулы сравнением с `scipy.integrate.quad`

**Файлы:** `method_of_moments/tests/test_integrals.py` (создать)

**Контекст:**
Каждый интеграл имеет интегральное представление (определённый интеграл от 0 до 1). Сравниваем аналитическую формулу с `scipy.integrate.quad` для различных значений параметров. Допуск: $< 10^{-10}$.

**Что сделать:**

1. Создать файл `method_of_moments/tests/test_integrals.py`
2. Реализовать параметризованные тесты:

```python
"""Тесты аналитических интегралов — FEAT-004."""

import pytest
from scipy.integrate import quad

from src.integrals import I_Phi, I_S, J

TOLERANCE = 1e-10

# Наборы параметров для тестирования
GAMMA_VALUES = [0.5, 1.0, 2.0, 5.0]
BETA_VALUES = [1.0, 2.0, 3.0]
SIGMA_VALUES = [0.5, 1.0, 2.0]
N_VALUES = [0, 1, 2, 3]
M_VALUES = [0, 1, 2, 3]


class TestIPhiQuad:
    """I_Φ^(n) vs scipy.integrate.quad."""

    @pytest.mark.parametrize("n", N_VALUES)
    @pytest.mark.parametrize("gamma", GAMMA_VALUES)
    def test_vs_quad(self, n, gamma):
        expected, _ = quad(lambda eta: eta ** (n * gamma), 0, 1)
        assert abs(I_Phi(n, gamma) - expected) < TOLERANCE


class TestISQuad:
    """I_S^(n) vs scipy.integrate.quad."""

    @pytest.mark.parametrize("n", N_VALUES)
    @pytest.mark.parametrize("gamma", GAMMA_VALUES)
    @pytest.mark.parametrize("beta", BETA_VALUES)
    def test_vs_quad(self, n, gamma, beta):
        expected, _ = quad(
            lambda eta: (1 - eta ** beta) * eta ** (n * gamma), 0, 1
        )
        assert abs(I_S(n, gamma, beta) - expected) < TOLERANCE


class TestJQuad:
    """J^(m) vs scipy.integrate.quad."""

    @pytest.mark.parametrize("m", M_VALUES)
    @pytest.mark.parametrize("sigma", SIGMA_VALUES)
    def test_vs_quad(self, m, sigma):
        expected, _ = quad(
            lambda zeta: zeta ** m * (2 - zeta ** sigma), 0, 1
        )
        assert abs(J(m, sigma) - expected) < TOLERANCE
```

**Тесты:**

| Тест | Сценарий | Ожидание | Формула | Предотвращает |
|---|---|---|---|---|
| `TestIPhiQuad::test_vs_quad` | $n \in \{0,1,2,3\}$, $\gamma \in \{0.5,1,2,5\}$ | $|I_\Phi - \text{quad}| < 10^{-10}$ | `\eqref{eq:IPhi}` | ошибка в замкнутой формуле |
| `TestISQuad::test_vs_quad` | $n \times \gamma \times \beta$ | $|I_S - \text{quad}| < 10^{-10}$ | `\eqref{eq:IS}` | ошибка в связи $I_S$ и $I_\Phi$ |
| `TestJQuad::test_vs_quad` | $m \in \{0,1,2,3\}$, $\sigma \in \{0.5,1,2\}$ | $|J - \text{quad}| < 10^{-10}$ | `\eqref{eq:IPsi}` | ошибка в формуле $J$ |

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_integrals.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** шаг 1. Блокирует: шаг 3.
**Оценка:** ~50 строк, ~10 минут

---

### Шаг 3: Граничные и предельные тесты

**Цель:** проверить корректность на границах диапазона параметров

**Файлы:** `method_of_moments/tests/test_integrals.py` (дополнить)

**Контекст:**
Граничные случаи:
- $n = 0$: $I_\Phi^{(0)} = 1$, $I_S^{(0)} = 1 - 1/(\beta+1) = \beta/(\beta+1)$
- $\gamma \to 0$: $I_\Phi^{(n)} \to 1$ (интеграл от $\eta^0 = 1$)
- $\beta = 0$: $S_g = S_{g,w}(1 - \eta^0) = 0$ всюду — $I_S^{(n)} = 0$
- $m = 0$: $J^{(0)} = 2 - 1/(\sigma+1)$
- $\sigma = 0$: $J^{(m)} = 2/(m+1) - 1/(m+1) = 1/(m+1)$

**Что сделать:**

Добавить в `test_integrals.py`:

```python
class TestIPhiBoundary:
    """Предельные случаи I_Φ^(n)."""

    def test_n_zero(self):
        """I_Φ^(0) = 1 для любого gamma."""
        for gamma in GAMMA_VALUES:
            assert I_Phi(0, gamma) == pytest.approx(1.0)

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_gamma_small(self, n):
        """При gamma → 0: I_Φ^(n) → 1."""
        assert I_Phi(n, 1e-12) == pytest.approx(1.0, abs=1e-10)

    def test_known_value(self):
        """I_Φ^(1) при gamma=1 = 1/2."""
        assert I_Phi(1, 1.0) == pytest.approx(0.5)


class TestISBoundary:
    """Предельные случаи I_S^(n)."""

    @pytest.mark.parametrize("beta", BETA_VALUES)
    def test_n_zero(self, beta):
        """I_S^(0) = beta / (beta + 1)."""
        for gamma in GAMMA_VALUES:
            expected = beta / (beta + 1)
            assert I_S(0, gamma, beta) == pytest.approx(expected)

    @pytest.mark.parametrize("n", N_VALUES)
    @pytest.mark.parametrize("gamma", GAMMA_VALUES)
    def test_beta_zero(self, n, gamma):
        """При beta=0: Sg=0 всюду, I_S^(n) = 0."""
        assert I_S(n, gamma, 0.0) == pytest.approx(0.0, abs=1e-15)

    def test_non_negative(self):
        """I_S^(n) >= 0 (физический смысл: Sg >= 0)."""
        for n in N_VALUES:
            for gamma in GAMMA_VALUES:
                for beta in BETA_VALUES:
                    assert I_S(n, gamma, beta) >= 0.0


class TestJBoundary:
    """Предельные случаи J^(m)."""

    @pytest.mark.parametrize("sigma", SIGMA_VALUES)
    def test_m_zero(self, sigma):
        """J^(0) = 2 − 1/(σ+1)."""
        expected = 2.0 - 1.0 / (sigma + 1.0)
        assert J(0, sigma) == pytest.approx(expected)

    @pytest.mark.parametrize("m", M_VALUES)
    def test_sigma_zero(self, m):
        """При σ=0: Ψ=ζ^0(2−ζ^0)=1, J^(m) = 1/(m+1)."""
        expected = 1.0 / (m + 1.0)
        assert J(m, 0.0) == pytest.approx(expected)

    def test_known_value_sigma1(self):
        """J^(1) при σ=1: 2/2 − 1/3 = 2/3."""
        assert J(1, 1.0) == pytest.approx(2.0 / 3.0)
```

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_integrals.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** шаги 1, 2. Блокирует: шаги 4, 5.
**Оценка:** ~60 строк, ~10 минут

---

### Шаг 4: Экспорт из `src/__init__.py` и тест интеграции

**Цель:** экспортировать интегралы из пакета и проверить эквивалентность с `TemperatureProfile.J(m)` **до** делегирования (шаг 5)

**Файлы:**
- `method_of_moments/src/__init__.py` (дополнить)
- `method_of_moments/tests/test_integrals.py` (дополнить)

**Контекст:**
Тест `test_J_matches_temperature_profile` сравнивает `integrals.J(m, sigma)` с `TemperatureProfile.J(m)` — две **независимые** реализации одной формулы. После шага 5 (делегирования) одна реализация вызывает другую, и тест становится тавтологией. Поэтому тест запускается **до** делегирования.

**Что сделать:**

1. Добавить в `src/__init__.py`:
```python
from .integrals import I_Phi, I_S, J
```

2. Добавить интеграционный тест в `test_integrals.py`:

```python
class TestIntegrationWithProfiles:
    """Интегралы согласованы с параметрами профилей."""

    def test_J_matches_temperature_profile(self):
        """J(m, sigma) совпадает с TemperatureProfile.J(m) (независимые реализации)."""
        from src.profiles.temperature import TemperatureProfile
        tp = TemperatureProfile(r_w=0.1, R_ext=500.0, T_0=350.0, sigma=1.5)
        for m in M_VALUES:
            assert J(m, tp.sigma) == pytest.approx(tp.J(m))

    def test_I_S_decomposition(self):
        """I_S^(n) = I_Φ^(n) − 1/(nγ+β+1) — тождество."""
        for n in N_VALUES:
            for gamma in GAMMA_VALUES:
                for beta in BETA_VALUES:
                    lhs = I_S(n, gamma, beta)
                    rhs = I_Phi(n, gamma) - 1.0 / (n * gamma + beta + 1.0)
                    assert lhs == pytest.approx(rhs)
```

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_integrals.py -v`
- `.venv/Scripts/python -c "from src import I_Phi, I_S, J; print('OK')"` — import из пакета
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** шаги 1–3. Блокирует: шаг 5.
**Оценка:** ~25 строк, ~5 минут

---

### Шаг 5: Делегирование TemperatureProfile.J(m)

**Цель:** `TemperatureProfile.J(m)` делегирует к каноническому `integrals.J(m, sigma)`, устраняя дублирование

**Файлы:** `method_of_moments/src/profiles/temperature.py`

**Контекст:**
`TemperatureProfile.J(m)` (строка 50–52) уже реализован и вычисляет ту же формулу, что `integrals.J(m, sigma)`, используя `self.sigma`. Эквивалентность подтверждена тестом `test_J_matches_temperature_profile` (шаг 4). Теперь устраняем дублирование: метод делегирует к free-функции.

**Что сделать:**

1. Добавить import в `temperature.py` (относительный, внутри пакета `src`):
   ```python
   from ..integrals import J as _J_integral
   ```
2. Заменить тело метода `J(self, m)`:

До:
```python
    def J(self, m: int) -> float:
        r"""Интеграл J^{(m)} = 2/(m+1) − 1/(m+σ+1), \eqref{eq:IPsi}."""
        return 2.0 / (m + 1) - 1.0 / (m + self.sigma + 1)
```
После:
```python
    def J(self, m: int) -> float:
        r"""Интеграл J^{(m)} = 2/(m+1) − 1/(m+σ+1), \eqref{eq:IPsi}."""
        return _J_integral(m, self.sigma)
```

**Вызывающие `TemperatureProfile.J(m)`:**
- `tests/test_profiles.py::TestJIntegral` (строки 239, 245) — тесты, пройдут (сигнатура не менялась)
- `scripts/plot_profiles.py:234` — скрипт визуализации, пройдёт (сигнатура не менялась)

**Проверка после шага:**
- `.venv/Scripts/python -m pytest tests/test_profiles.py::TestJIntegral -v` (тесты J из TemperatureProfile)
- `.venv/Scripts/python -m pytest tests/test_integrals.py -v`
- Регрессия: `.venv/Scripts/python -m pytest tests/ -v`

**Зависимости:** шаги 1, 4. Блокирует: ничего (финальный шаг).
**Оценка:** ~5 строк изменений, ~5 минут

---

## Тестовая стратегия (сводка)

| Категория | Тесты | Файл |
|---|---|---|
| Unit (аналитика vs quad) | `TestIPhiQuad`, `TestISQuad`, `TestJQuad` | `test_integrals.py` |
| Граничные | `TestIPhiBoundary`, `TestISBoundary`, `TestJBoundary` | `test_integrals.py` |
| Согласованность | `TestIntegrationWithProfiles` | `test_integrals.py` |
| Регрессия | все существующие тесты | `tests/` |

Всего: ~76 параметризованных (quad) + ~33 граничных + ~2 интеграционных ≈ 111 тест-кейсов.

## Критерии завершения

- [ ] Три формулы из §5.4 реализованы в `src/integrals.py`
- [ ] Каждая функция имеет docstring с `\eqref{}`
- [ ] Unit-тесты (vs quad) зелёные, tolerance < 1e-10
- [ ] Граничные тесты зелёные
- [ ] `TemperatureProfile.J(m)` делегирует к `integrals.J`
- [ ] Экспорт из `src/__init__.py`
- [ ] Все существующие тесты зелёные
- [ ] Vault обновлён (статус FEAT-004, ссылка на план)
- [ ] GitHub issue #4 прокомментирован

## Оценка

- Файлов: 4 (создать 2, изменить 2)
- Строк нового кода: ~15 (integrals.py)
- Строк тестов: ~135 (test_integrals.py)
- Время: ~35 минут
