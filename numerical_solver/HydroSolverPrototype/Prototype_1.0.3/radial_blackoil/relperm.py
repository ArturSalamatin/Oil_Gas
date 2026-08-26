import numpy as np
class TabulatedRelPerm:
    def __init__(self, sg, kro, krg):
        self.sg=np.asarray(sg,float); self.kro_tab=np.asarray(kro,float); self.krg_tab=np.asarray(krg,float)
        if len(self.sg)<2 or np.any(np.diff(self.sg)<=0): raise ValueError('RELPERM Sg must be strictly increasing with >=2 rows')
        if np.any(self.kro_tab<0) or np.any(self.krg_tab<0): raise ValueError('RELPERM values must be non-negative')
    def kro(self,sg): return np.interp(np.asarray(sg,float),self.sg,self.kro_tab)
    def krg(self,sg): return np.interp(np.asarray(sg,float),self.sg,self.krg_tab)
