import numpy as np
class CompressibleRock:
    def __init__(self, phi_ref, p_ref_bar, cr_per_bar):
        self.phi_ref=float(phi_ref); self.p_ref_bar=float(p_ref_bar); self.cr=float(cr_per_bar)
    def porosity(self,p_bar):
        return self.phi_ref*np.exp(self.cr*(np.asarray(p_bar,float)-self.p_ref_bar))
    def pore_volume_m3(self,bulk_volumes_m3,p_bar):
        return np.asarray(bulk_volumes_m3,float)*self.porosity(p_bar)
