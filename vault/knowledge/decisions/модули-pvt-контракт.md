---
name: модули-pvt-контракт
description: "SUPERSEDED by P5-pvt-архитектура.md — старая версия: два ABC (HydroPVT+ThermalPVT). Актуальная: HydroPVT→FullPVT"
metadata:
  type: project
---

# PVT-контракт — два интерфейса

> **SUPERSEDED.** Эта заметка описывает старую архитектуру (HydroPVT + ThermalPVT, множественное наследование). Актуальная архитектура: [[P5-pvt-архитектура]] (HydroPVT → FullPVT, одиночное наследование, PrototypePVTAdapter). Секция RelPermModel по-прежнему актуальна.

## Обоснование разделения

Из problem_statement.tex, splitting (§3):
- **Гидродинамика**: PVT зависят только от p (T = T_пл = const). Нужны значения И производные по p (для якобиана Ньютона).
- **Теплоперенос**: PVT зависят от p и T. Нужны только значения (коэффициенты замораживаются на T^n, итерации не нужны).

Два ABC, а не один — потому что у них разные контракты:
- HydroPVT: каждый метод обязан иметь парный метод производной
- ThermalPVT: производные не нужны

Конкретная реализация (StandingPVT) наследует оба. В Python множественное наследование — штатный механизм.

## HydroPVT — гидродинамические свойства

```python
from abc import ABC, abstractmethod
import numpy as np

class HydroPVT(ABC):
    """Свойства фаз для гидродинамической подсистемы.

    Все функции принимают/возвращают np.ndarray (векторизация по ячейкам).
    В гидродинамике T = T0 = const, поэтому аргумент только p.
    """

    # --- Плотности при стандартных условиях (скаляры, задаются в конструкторе) ---
    rho_o_std: float   # кг/м³
    rho_g_std: float   # кг/м³

    # --- Газосодержание ---
    @abstractmethod
    def Rs_eq(self, p: np.ndarray) -> np.ndarray:
        """Равновесное газосодержание Rs_eq(p). Ур. (3) problem_statement.tex."""
        ...

    @abstractmethod
    def dRs_eq_dp(self, p: np.ndarray) -> np.ndarray:
        """∂Rs_eq/∂p. Нужна для якобиана: третья строка блока в режиме 1."""
        ...

    # --- Объёмный коэффициент нефти ---
    @abstractmethod
    def Bo(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Bo(p, Rs). Ур. (8) problem_statement.tex."""
        ...

    @abstractmethod
    def dBo_dp(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """∂Bo/∂p|_{Rs}. Для co = -(1/Bo)·∂Bo/∂p."""
        ...

    @abstractmethod
    def dBo_dRs(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """∂Bo/∂Rs|_{p}. Для производных членов накопления по Rs."""
        ...

    # --- Объёмный коэффициент газа ---
    @abstractmethod
    def Bg(self, p: np.ndarray) -> np.ndarray:
        """Bg(p)."""
        ...

    @abstractmethod
    def dBg_dp(self, p: np.ndarray) -> np.ndarray:
        """∂Bg/∂p. Для cg = -(1/Bg)·∂Bg/∂p."""
        ...

    # --- Вязкости ---
    @abstractmethod
    def mu_o(self, p: np.ndarray) -> np.ndarray:
        """μ_o(p), Па·с."""
        ...

    @abstractmethod
    def dmu_o_dp(self, p: np.ndarray) -> np.ndarray:
        """∂μ_o/∂p. Для производных потоков по p."""
        ...

    @abstractmethod
    def mu_g(self, p: np.ndarray) -> np.ndarray:
        """μ_g(p), Па·с."""
        ...

    @abstractmethod
    def dmu_g_dp(self, p: np.ndarray) -> np.ndarray:
        """∂μ_g/∂p."""
        ...

    # --- Давление насыщения ---
    @abstractmethod
    def pb(self) -> float:
        """Давление насыщения pb, Па. Скаляр (T фиксировано)."""
        ...

    # --- Вычисляемые (не абстрактные) ---
    def rho_o(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """ρ_o = (ρ_o_ст + Rs·ρ_g_ст) / Bo. Ур. (51) problem_statement.tex."""
        return (self.rho_o_std + Rs * self.rho_g_std) / self.Bo(p, Rs)

    def rho_g(self, p: np.ndarray) -> np.ndarray:
        """ρ_g = ρ_g_ст / Bg."""
        return self.rho_g_std / self.Bg(p)

    # --- Вспомогательные (сжимаемости) ---
    def co(self, p: np.ndarray, Rs: np.ndarray) -> np.ndarray:
        """Изотермическая сжимаемость нефти co = -(1/Bo)·∂Bo/∂p|_{Rs}."""
        return -self.dBo_dp(p, Rs) / self.Bo(p, Rs)

    def cg(self, p: np.ndarray) -> np.ndarray:
        """Изотермическая сжимаемость газа cg = -(1/Bg)·∂Bg/∂p."""
        return -self.dBg_dp(p) / self.Bg(p)
```

## ThermalPVT — тепловые свойства

```python
class ThermalPVT(ABC):
    """Тепловые свойства фаз. Аргументы (p, T) для расширяемости.

    В текущей реализации — постоянные скаляры (п. 1.2 задания).
    ABC принимает (p, T), чтобы не ломать интерфейс при расширении.
    """

    @abstractmethod
    def c_p_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплоёмкость нефти, Дж/(кг·К)."""
        ...

    @abstractmethod
    def c_p_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплоёмкость газа, Дж/(кг·К)."""
        ...

    @abstractmethod
    def mu_JT_oil(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Коэффициент Джоуля-Томсона нефти, К/Па."""
        ...

    @abstractmethod
    def mu_JT_gas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Коэффициент Джоуля-Томсона газа, К/Па."""
        ...

    @abstractmethod
    def L_degas(self, p: np.ndarray, T: np.ndarray) -> np.ndarray:
        """Удельная теплота дегазации, Дж/кг газа."""
        ...
```

## RelPermModel — ОФП (отдельный ABC, подключаемая стратегия)

ОФП — полноценный подключаемый модуль, аналогично PVT. Конкретные реализации:
- CoreyRP — модель Кори (аналитические производные)
- TableRP — табличное задание из CSV (производные — конечные разности или сплайн)
- BrooksCoreyRP, LET_RP — другие модели
- ExternalRP — адаптер для ОФП из модуля коллеги

Производные dkro/dSg, dkrg/dSg нужны для якобиана Ньютона. Они **не** абстрактные — в ABC есть default-реализация через конечные разности. Конкретные модели (Corey) переопределяют аналитически.

```python
class RelPermModel(ABC):
    """Относительные фазовые проницаемости.

    ОФП — подключаемая стратегия. Любая реализация должна предоставить
    kro(Sg) и krg(Sg). Производные — опционально; если не переопределены,
    вычисляются конечными разностями (медленнее, менее точно).
    """

    @abstractmethod
    def kro(self, Sg: np.ndarray) -> np.ndarray:
        """k_ro(Sg). Ур. (6) problem_statement.tex."""
        ...

    @abstractmethod
    def krg(self, Sg: np.ndarray) -> np.ndarray:
        """k_rg(Sg)."""
        ...

    def dkro_dSg(self, Sg: np.ndarray) -> np.ndarray:
        """dk_ro/dSg. Default: конечные разности. Переопределить для аналитики."""
        eps = 1e-8
        return (self.kro(Sg + eps) - self.kro(Sg - eps)) / (2 * eps)

    def dkrg_dSg(self, Sg: np.ndarray) -> np.ndarray:
        """dk_rg/dSg. Default: конечные разности."""
        eps = 1e-8
        return (self.krg(Sg + eps) - self.krg(Sg - eps)) / (2 * eps)
```

Преимущества:
- Коллега может передать ОФП без производных — fallback работает
- Табличная модель использует default — не нужен сплайн сразу
- Corey переопределяет аналитически — быстрее и точнее
- Паттерн Strategy: замена ОФП не затрагивает HydroSolver

## Конкретная реализация: StandingPVT

Наследует HydroPVT и ThermalPVT. Параметры из JSON-секции pvt + thermal.

```python
class StandingPVT(HydroPVT, ThermalPVT):
    def __init__(self, pvt_config, thermal_config):
        self.rho_o_std = pvt_config.rho_o_std
        self.rho_g_std = pvt_config.rho_g_std
        self._mu_JT_o = thermal_config.mu_JT_oil  # скаляр
        self._mu_JT_g = thermal_config.mu_JT_gas
        self._L = thermal_config.L_degas
        self._cp_o = thermal_config.c_p_oil
        self._cp_g = thermal_config.c_p_gas
        # ... параметры корреляций Standing

    def mu_JT_oil(self, p, T):
        return np.full_like(p, self._mu_JT_o)  # скаляр → массив

    def L_degas(self, p, T):
        return np.full_like(p, self._L)
```

## Конкретная реализация: CoreyRP

```python
class CoreyRP(RelPermModel):
    def __init__(self, S_or, S_gc, n_o, n_g, kro_max, krg_max):
        self.S_or = S_or
        self.S_gc = S_gc
        self.n_o = n_o
        self.n_g = n_g
        self.kro_max = kro_max
        self.krg_max = krg_max

    def _S_star(self, Sg):
        return np.clip((Sg - self.S_gc) / (1 - self.S_or - self.S_gc), 0.0, 1.0)

    def kro(self, Sg):
        return self.kro_max * (1 - self._S_star(Sg))**self.n_o

    def krg(self, Sg):
        return self.krg_max * self._S_star(Sg)**self.n_g

    def dkro_dSg(self, Sg):
        S = self._S_star(Sg)
        dS = 1.0 / (1 - self.S_or - self.S_gc)
        return -self.kro_max * self.n_o * (1 - S)**(self.n_o - 1) * dS

    def dkrg_dSg(self, Sg):
        S = self._S_star(Sg)
        dS = 1.0 / (1 - self.S_or - self.S_gc)
        return self.krg_max * self.n_g * S**(self.n_g - 1) * dS
```

## Ключевые решения

1. **Векторизация**: все методы принимают/возвращают np.ndarray. Ньютон вычисляет PVT для N ячеек одновременно. Скалярный вызов в цикле — в 50-100× медленнее.
2. **Аналитические производные**: встроенные модели предоставляют точные производные. Табличные — сплайн с аналитической производной. Кастомные — пользователь реализует; fallback на конечные разности.
3. **rho_o, rho_g, co, cg** — не абстрактные, вычисляются через Bo, Bg. Единая формула, нет риска рассогласования.
4. **np.clip в _S_star**: защита от S* < 0 или S* > 1. Производные dkro/dSg при S* вне [0,1] обнуляются (плоский участок, k=const).

## Связанные заметки

- [[архитектура библиотеки numerical_solver]] — общая архитектура
- [[json-config-schema]] — структура JSON-конфига
- [[модули-hydro-newton]] — использование PVT в якобиане
