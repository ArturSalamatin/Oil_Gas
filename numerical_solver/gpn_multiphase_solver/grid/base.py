"""ABC Grid — абстрактная пространственная сетка."""

from abc import ABC, abstractmethod
import numpy as np


class Grid(ABC):
    """Абстрактная радиальная сетка.

    Immutable после создания. Передаётся по ссылке во все модули.
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
        """Мощность пласта, м."""
        ...

    @property
    @abstractmethod
    def r_faces(self) -> np.ndarray:
        """Грани. Массив [N+1]. r_faces[0]=r_well, r_faces[N]=R_ext."""
        ...

    @property
    @abstractmethod
    def r_centers(self) -> np.ndarray:
        """Центры ячеек. Массив [N]."""
        ...

    @property
    @abstractmethod
    def volumes(self) -> np.ndarray:
        """Объёмы ячеек V_j, м³. Массив [N]."""
        ...

    @property
    @abstractmethod
    def trans_internal(self) -> np.ndarray:
        """Проводимости внутренних граней, м³. Массив [N-1]."""
        ...

    @property
    @abstractmethod
    def trans_well(self) -> float:
        """Проводимость забойной грани, м³."""
        ...

    @property
    @abstractmethod
    def trans_ext(self) -> float:
        """Проводимость грани контура, м³."""
        ...

    @property
    @abstractmethod
    def log_weights_left(self) -> np.ndarray:
        """ln(r_face[f+1] / r_center[f]) для внутренних граней. [N-1]."""
        ...

    @property
    @abstractmethod
    def log_weights_right(self) -> np.ndarray:
        """ln(r_center[f+1] / r_face[f+1]) для внутренних граней. [N-1]."""
        ...
