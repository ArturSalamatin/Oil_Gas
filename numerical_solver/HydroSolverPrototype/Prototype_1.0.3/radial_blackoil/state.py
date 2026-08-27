from dataclasses import dataclass
import numpy as np

@dataclass
class BlackOilState:
    pressure_bar: np.ndarray
    rs_sm3_sm3: np.ndarray
    sg: np.ndarray
    gas_active: np.ndarray

    @classmethod
    def undersaturated(cls, n, pressure_bar, rs):
        return cls(np.full(n,float(pressure_bar)), np.full(n,float(rs)), np.zeros(n), np.zeros(n,dtype=bool))

    def copy(self):
        return BlackOilState(self.pressure_bar.copy(), self.rs_sm3_sm3.copy(), self.sg.copy(), self.gas_active.copy())
