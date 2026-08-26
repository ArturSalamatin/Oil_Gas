import numpy as np
from .units import MD_TO_M2

class RadialGrid:
    def __init__(self, rw_m, re_m, h_m, n, permeability_md):
        self.rw_m=float(rw_m); self.re_m=float(re_m); self.h_m=float(h_m); self.n=int(n); self.permeability_md=float(permeability_md)
        if not (0 < self.rw_m < self.re_m and self.n >= 1 and self.h_m > 0 and self.permeability_md > 0):
            raise ValueError('invalid radial grid parameters')
        self.faces_m=np.geomspace(self.rw_m,self.re_m,self.n+1)
        self.centers_m=np.sqrt(self.faces_m[:-1]*self.faces_m[1:])
        self.bulk_volumes_m3=np.pi*self.h_m*(self.faces_m[1:]**2-self.faces_m[:-1]**2)
        kh=self.permeability_md*MD_TO_M2*self.h_m
        if self.n>1:
            self.internal_transmissibility_m3=2*np.pi*kh/np.log(self.centers_m[1:]/self.centers_m[:-1])
        else:
            self.internal_transmissibility_m3=np.empty(0)
        self.outer_transmissibility_m3=2*np.pi*kh/np.log(self.re_m/self.centers_m[-1])
        self._kh=kh

    def well_transmissibility_m3(self, skin=0.0):
        return 2*np.pi*self._kh/(np.log(self.centers_m[0]/self.rw_m)+float(skin))
