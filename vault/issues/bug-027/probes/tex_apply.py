"""BUG-027: правки problem_statement.tex из плана (шаги 1–2) — на копии или на месте.

Блоки «до → после» совпадают с планом дословно. Каждое «до» обязано
встретиться в файле ровно один раз, иначе — отказ без записи.

    python tex_apply.py <путь к problem_statement.tex> [<куда писать>]

Без второго аргумента печатает только проверку единственности «до».
"""
import sys
from pathlib import Path

# ── Шаг 1: eq:face_interp ──
A_BEFORE = r"""\begin{equation}\label{eq:face_interp}
  A_{j+\half} = \frac{1}{\dfrac{\ln(r_{j+\half}/r_j)}{A_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{A_{j+1}}}.
\end{equation}
Логарифмические веса корректны для радиальной геометрии
(аналогия с~последовательными сопротивлениями в~кольцевых слоях).
"""
A_AFTER = r"""% BUG-027: до исправления в числителе стояла единица — веса не нормированы,
% при A_j = A_{j+1} = A «среднее» равнялось A/ln(r_{j+1}/r_j), и поток
% eq:heat_cond_disc получал ln^2 в знаменателе (дефект BUG-002 в постановке).
\begin{equation}\label{eq:face_interp}
  A_{j+\half} = \frac{\ln(r_{j+1}/r_j)}{\dfrac{\ln(r_{j+\half}/r_j)}{A_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{A_{j+1}}}.
\end{equation}
Логарифмы $w_L = \ln(r_{j+\half}/r_j)$ и~$w_R = \ln(r_{j+1}/r_{j+\half})$
в~сумме дают $\ln(r_{j+1}/r_j)$, поэтому веса $w_L/(w_L + w_R)$
и~$w_R/(w_L + w_R)$ нормированы на~единицу: при~$A_j = A_{j+1} = A$
среднее равно~$A$, в~общем случае оно лежит между~$A_j$ и~$A_{j+1}$.
Логарифмические веса корректны для радиальной геометрии
(аналогия с~последовательными сопротивлениями в~кольцевых слоях).
"""

# ── Шаг 2а: eq:heat_cond_disc и среднее под ним ──
B_BEFORE = r"""\begin{equation}\label{eq:heat_cond_disc}
  Q_{\lambda,j+\half} = \frac{2\pi\,h}{\ln(r_{j+1}/r_j)}\,
    {\leff}^{j+\half}\,(T_j - T_{j+1}),
\end{equation}
$Q_\lambda > 0$~--- поток тепла от~скважины (в~сторону роста~$r$).
где~${\leff}^{j+\half}$~--- гармоническое среднее
с~логарифмическими весами (ср.~\eqref{eq:face_interp}):
\[
  {\leff}^{j+\half} =\left( \dfrac{\ln(r_{j+\half}/r_j)}{{\leff}_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{{\leff}_{j+1}}\right)^{-1}.
\]
"""
B_AFTER = r"""\begin{equation}\label{eq:heat_cond_disc}
  Q_{\lambda,j+\half} = \frac{2\pi\,h}{\ln(r_{j+1}/r_j)}\,
    {\leff}^{j+\half}\,(T_j - T_{j+1}),
\end{equation}
где~${\leff}^{j+\half}$~--- гармоническое среднее
с~логарифмическими весами~\eqref{eq:face_interp}:
\[
  {\leff}^{j+\half} = \ln(r_{j+1}/r_j)
    \left( \dfrac{\ln(r_{j+\half}/r_j)}{{\leff}_j}
    + \dfrac{\ln(r_{j+1}/r_{j+\half})}{{\leff}_{j+1}}\right)^{-1};
\]
$Q_\lambda > 0$~--- поток тепла от~скважины (в~сторону роста~$r$).
Подстановка среднего в~\eqref{eq:heat_cond_disc} сокращает
$\ln(r_{j+1}/r_j)$:
\[
  Q_{\lambda,j+\half}
  = \frac{2\pi h\,(T_j - T_{j+1})}
    {\ln(r_{j+\half}/r_j)/{\leff}_j + \ln(r_{j+1}/r_{j+\half})/{\leff}_{j+1}},
\]
то~есть тепловые сопротивления двух кольцевых слоёв
$[r_j, r_{j+\half}]$ и~$[r_{j+\half}, r_{j+1}]$ складываются
последовательно. При~однородной теплопроводности поток совпадает
с~потоком стационарного решения $T = C_1\ln r + C_2$ в~кольце
$[r_j, r_{j+1}]$:
\[
  Q_{\lambda,j+\half} = \frac{2\pi h\,\leff\,(T_j - T_{j+1})}{\ln(r_{j+1}/r_j)};
\]
так~же, с~одним логарифмом, записан поток через контур
(раздел~\ref{ssec:bc_disc}).
"""

# ── Шаг 2б: проводимость под eq:tridiag_d — знак ln для левой грани ──
C_BEFORE = r"""Здесь $Q_{\lambda,j\pm\half}^T = 2\pi h\,{\leff}^{j\pm\half}/
\ln(r_{j\pm 1}/r_j)$~--- кондуктивная проводимость ($>0$);
"""
C_AFTER = r"""Здесь $Q_{\lambda,j+\half}^T = 2\pi h\,{\leff}^{j+\half}/
\ln(r_{j+1}/r_j)$~--- кондуктивная проводимость грани~$j{+}\half$ (\mbox{$>0$});
для~грани~$j{-}\half$~--- то~же с~заменой $j \to j-1$, знаменатель
$\ln(r_j/r_{j-1})$ тоже положителен;
"""

EDITS = [("A eq:face_interp", A_BEFORE, A_AFTER),
         ("B eq:heat_cond_disc", B_BEFORE, B_AFTER),
         ("C проводимость под eq:tridiag_d", C_BEFORE, C_AFTER)]

src = Path(sys.argv[1])
text = src.read_text(encoding="utf-8")
ok = True
for name, before, after in EDITS:
    n = text.count(before)
    line = text[:text.find(before)].count("\n") + 1 if n else None
    print(f"{name}: «до» найдено {n} раз, строка {line}")
    ok &= n == 1
    text = text.replace(before, after)
if not ok:
    sys.exit("отказ: «до» не единственно — ничего не записано")
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(text, encoding="utf-8")
    print(f"записано: {sys.argv[2]}")
