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
