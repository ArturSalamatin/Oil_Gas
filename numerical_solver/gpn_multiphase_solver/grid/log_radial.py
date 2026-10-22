"""LogRadialGrid — логарифмическая радиальная сетка.

Ур. (eq:log_grid), (eq:cell_center), (eq:volume), (eq:transmissibility)
problem_statement.tex.
"""

import numpy as np
from .base import Grid


# Грани: geomspace(r_well, R_ext, N+1). Центры: среднее геометрическое граней
# √(r_{j-1/2}·r_{j+1/2}) (eq:cell_center). Проводимости: 2πkh /
# ln(r_center[j+1]/r_center[j]) (eq:transmissibility). Immutable после создания
class LogRadialGrid(Grid):
    """Логарифмическая радиальная сетка: грани — геометрическая прогрессия от r_w до r_e. Ур. (eq:log_grid) problem_statement.tex.

    Центр ячейки — среднее геометрическое её граней, Ур. (eq:cell_center);
    объёмы — Ур. (eq:volume); проводимости граней — Ур. (eq:transmissibility).

    Параметры
    ---------
    r_well : float
        Радиус скважины r_w, м, > 0.
    R_ext : float
        Радиус контура питания r_e, м, > r_w.
    h : float
        Толщина пласта, м, > 0.
    N : int
        Число ячеек, целое ≥ 1.
    k : float, optional
        Абсолютная проницаемость, м², > 0; входит в проводимости граней.
        По умолчанию 1.

    Исключения
    ----------
    ValueError
        Значение вне указанных пределов.
    """

    def __init__(self, r_well: float, R_ext: float, h: float,
                 N: int, k: float = 1.0):
        """Построить грани, центры, объёмы и проводимости; параметры — в докстринге класса."""
        if r_well <= 0:
            raise ValueError(f"r_well must be > 0, got {r_well}")
        if R_ext <= r_well:
            raise ValueError(f"R_ext must be > r_well, got R_ext={R_ext}, r_well={r_well}")
        if h <= 0:
            raise ValueError(f"h must be > 0, got {h}")
        if not isinstance(N, int) or N < 1:
            raise ValueError(f"N must be an integer >= 1, got {N}")
        if k <= 0:
            raise ValueError(f"k must be > 0, got {k}")

        self._N = int(N)
        self._r_well = float(r_well)
        self._R_ext = float(R_ext)
        self._h = float(h)
        self._k = float(k)

        # Грани (eq:log_grid)
        self._r_faces = np.geomspace(r_well, R_ext, N + 1)

        # Центры (eq:cell_center): середина ячейки по ln r — среднее
        # геометрическое граней. Та же формула и тот же порядок операций,
        # что у RadialGrid прототипа (radial_blackoil/grid.py), — центры
        # совпадают побитово, и гидродинамика, энергия и вывод относятся к
        # одним точкам (DEBT-063). Совпадение проверяет
        # tests/test_prototype_adapter.py::TestGridsMatchPrototype.
        self._r_centers = np.sqrt(self._r_faces[:-1] * self._r_faces[1:])

        # Объёмы (eq:volume)
        self._volumes = np.pi * h * (
            self._r_faces[1:] ** 2 - self._r_faces[:-1] ** 2
        )

        # Проводимости внутренних граней (eq:transmissibility)
        kh = k * h
        if N > 1:
            self._trans_internal = (
                2.0 * np.pi * kh
                / np.log(self._r_centers[1:] / self._r_centers[:-1])
            )
        else:
            self._trans_internal = np.empty(0)

        # Проводимость забойной грани
        self._trans_well = (
            2.0 * np.pi * kh
            / np.log(self._r_centers[0] / r_well)
        )

        # Проводимость грани контура
        self._trans_ext = (
            2.0 * np.pi * kh
            / np.log(R_ext / self._r_centers[-1])
        )

        # Логарифмические веса для гармонической интерполяции
        if N > 1:
            faces_inner = self._r_faces[1:-1]  # [N-1]
            self._log_w_left = np.log(faces_inner / self._r_centers[:-1])
            self._log_w_right = np.log(self._r_centers[1:] / faces_inner)
        else:
            self._log_w_left = np.empty(0)
            self._log_w_right = np.empty(0)

    @property
    def N(self) -> int:
        return self._N

    @property
    def r_well(self) -> float:
        return self._r_well

    @property
    def R_ext(self) -> float:
        return self._R_ext

    @property
    def h(self) -> float:
        return self._h

    @property
    def r_faces(self) -> np.ndarray:
        return self._r_faces

    @property
    def r_centers(self) -> np.ndarray:
        return self._r_centers

    @property
    def volumes(self) -> np.ndarray:
        return self._volumes

    @property
    def trans_internal(self) -> np.ndarray:
        return self._trans_internal

    @property
    def trans_well(self) -> float:
        return self._trans_well

    @property
    def trans_ext(self) -> float:
        return self._trans_ext

    @property
    def log_weights_left(self) -> np.ndarray:
        return self._log_w_left

    @property
    def log_weights_right(self) -> np.ndarray:
        return self._log_w_right
