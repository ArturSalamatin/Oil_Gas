"""Граничные условия на забое: стратегии управления скважиной.

Управление — только данные. Читают его модули гидродинамики
(PrototypeHydroAdapter, compute_fluxes, тестовый двойник): они превращают
управление в поток через забойную грань и возвращают фактическое p_wf
в HydroResult. Энергия и Simulator к управлению не обращаются (FEAT-020).
"""


class WellControl:
    """Управление скважиной на одном интервале истории.

    Абстрактных методов нет намеренно: прежний boundary_pressure позволял
    энергии и выводу брать p_wf в обход HydroResult, а при управлении по
    дебиту p_wf до шага неизвестно (FEAT-020).
    """


class PressureControl(WellControl):
    """Задано забойное давление p_wf = const на интервале. Ур. (eq:bc_p_well)."""

    def __init__(self, p_wf: float):
        if p_wf <= 0:
            raise ValueError(f"p_wf должно быть > 0, получено {p_wf}")
        self._p_wf = float(p_wf)

    @property
    def p_wf(self) -> float:
        """Забойное давление, Па."""
        return self._p_wf

    def __eq__(self, other):
        # Управление — значение (FEAT-032): смену управления между интервалами
        # TimeSchedule ищет сравнением граничных условий, а фабрика создаёт на
        # каждый интервал новый объект — без __eq__ сравнение шло бы по
        # тождеству, и сменой считался бы каждый интервал.
        if not isinstance(other, PressureControl):
            return NotImplemented
        return self._p_wf == other._p_wf

    def __hash__(self):
        # Согласован с __eq__: равные управления — равные хеши
        return hash((PressureControl, self._p_wf))


class RateControl(WellControl):
    """Задан дебит нефти q_oil (м³ст/с) при p_wf >= min_bhp (Па). Ур. (eq:bc_rate_well)."""

    def __init__(self, q_oil: float, min_bhp: float):
        # Дебит положителен при добыче (q = -G_o[0]); нагнетания прототип
        # не допускает (blackoil.py, set_oil_rate_control), поэтому q_oil < 0
        # — ошибка.
        if q_oil < 0:
            raise ValueError(f"q_oil должен быть >= 0 (добыча), получено {q_oil}")
        # Без нижней границы p_wf при λ_o -> 0 уходит в -inf (blackoil.py,
        # _well_fluxes: при lo <= 0 требуемое p_bhp = -inf)
        if min_bhp <= 0:
            raise ValueError(f"min_bhp должно быть > 0, получено {min_bhp}")
        self._q_oil = float(q_oil)
        self._min_bhp = float(min_bhp)

    @property
    def q_oil(self) -> float:
        """Дебит нефти при стандартных условиях, м³ст/с."""
        return self._q_oil

    @property
    def min_bhp(self) -> float:
        """Минимальное забойное давление, Па."""
        return self._min_bhp

    def __eq__(self, other):
        # Как у PressureControl (FEAT-032). min_bhp входит в значение: при
        # недостижимом дебите оно и есть управление.
        if not isinstance(other, RateControl):
            return NotImplemented
        return (self._q_oil, self._min_bhp) == (other._q_oil, other._min_bhp)

    def __hash__(self):
        return hash((RateControl, self._q_oil, self._min_bhp))
