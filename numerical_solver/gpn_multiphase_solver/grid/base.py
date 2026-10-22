"""ABC Grid — абстрактная пространственная сетка."""

from abc import ABC, abstractmethod
import numpy as np


class Grid(ABC):
    """Радиальная сетка — базовый класс; неизменна после создания, один объект на все модули.

    Ячейки нумеруются от забоя (0) к контуру питания (N − 1), грани — от 0
    (забой, r_w) до N (контур, r_e). Проводимости граней — геометрические,
    с проницаемостью и толщиной пласта (2πkh, делённое на логарифм
    отношения радиусов), м³.
    """

    @property
    @abstractmethod
    def N(self) -> int:
        """Число ячеек."""
        ...

    @property
    @abstractmethod
    def r_well(self) -> float:
        """Радиус скважины, м."""
        ...

    @property
    @abstractmethod
    def R_ext(self) -> float:
        """Радиус контура питания, м."""
        ...

    @property
    @abstractmethod
    def h(self) -> float:
        """Толщина пласта, м."""
        ...

    @property
    @abstractmethod
    def r_faces(self) -> np.ndarray:
        """Радиусы граней ячеек, м; массив длины N + 1: ``r_faces[0]`` = r_w, ``r_faces[N]`` = r_e."""
        ...

    @property
    @abstractmethod
    def r_centers(self) -> np.ndarray:
        """Радиусы центров ячеек, м; массив длины N, индекс 0 — ячейка у забоя."""
        ...

    @property
    @abstractmethod
    def volumes(self) -> np.ndarray:
        """Объёмы ячеек V_j, м³; массив длины N."""
        ...

    @property
    @abstractmethod
    def trans_internal(self) -> np.ndarray:
        """Проводимости внутренних граней, м³; массив длины N − 1."""
        ...

    @property
    @abstractmethod
    def trans_well(self) -> float:
        """Проводимость забойной грани (от r_w до центра ячейки 0), м³."""
        ...

    @property
    @abstractmethod
    def trans_ext(self) -> float:
        """Проводимость грани контура (от центра ячейки N − 1 до r_e), м³."""
        ...

    @property
    @abstractmethod
    def log_weights_left(self) -> np.ndarray:
        """Логарифм отношения радиуса внутренней грани к центру ячейки слева; массив длины N − 1."""
        ...

    @property
    @abstractmethod
    def log_weights_right(self) -> np.ndarray:
        """Логарифм отношения центра ячейки справа к радиусу внутренней грани; массив длины N − 1."""
        ...
