"""Аудит FEAT-023, шаг 2 плана: вставки в постановку на копии + сборка.

Вставки из плана добавляются в копию doc/problem_statement.tex после
якорных строк (каждая встречается ровно один раз). Копия — tex/ рядом с
пробой; сборку pdflatex запускать там же (см. команду ниже).

Запуск (из numerical_solver):
    .venv\\Scripts\\python ..\\vault\\issues\\feat-023\\probes\\audit_tex.py
    cd ..\\vault\\issues\\feat-023\\probes\\tex
    pdflatex -interaction=nonstopmode problem_statement.tex   (дважды)
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[3] / "numerical_solver" / "doc" / "problem_statement.tex"

CONT = r"""

\paragraph{Закрытие скважины.}
Скважина только добывающая: закачка через~забой исключена.
Условие~\eqref{eq:bc_p_well} действует, пока при~$p(\rw, t) = \pwf$
пласт отдаёт флюид. Если давление у~забоя не~выше заданного
(например, после скачка~$\pwf$ вверх), скважина закрыта: дебит
нефти $q_{o,\text{ст}} = -G^{o}\big|_{r = \rw}$ равен нулю, а~давление
на~забое определяет пласт. Оба случая описывает условие
дополнительности
\begin{equation}\label{eq:bc_pwf_shutin}
  q_{o,\text{ст}} \ge 0, \qquad
  p(\rw, t) \le \pwf(t), \qquad
  q_{o,\text{ст}}\,\bigl[\pwf(t) - p(\rw, t)\bigr] = 0:
\end{equation}
при~открытой скважине ($q_{o,\text{ст}} > 0$) выполняется
\eqref{eq:bc_p_well}, при~закрытой ($q_{o,\text{ст}} = 0$) потоки
компонентов через~забой равны нулю, а~$p(\rw, t) \le \pwf(t)$.
Скважина открывается снова, когда давление у~забоя поднимается
до~$\pwf$."""

DISC = r"""

\paragraph{Закрытие скважины.}
Потоки~\eqref{eq:bc_flux_well}, \eqref{eq:bc_flux_well_gas}
берутся только при~$p_0 \ge \pwf$. При~$p_0 < \pwf$ они дали бы
$G_{\half} > 0$~--- закачку через~забой, которую
исключает~\eqref{eq:bc_pwf_shutin}. Поэтому при~$p_0 \le \pwf$
скважина закрыта: потоки через~забой равны нулю,
$G_{\half}^{o} = G_{\half}^{g} = 0$, а~фактическое $\pwf$ шага
равно~$p_0$. Какая ветвь действует, определяется по~$p_0$
на~новом слое: решение шага согласовано, если открытой скважине
отвечает $p_0 \ge \pwf$, а~закрытой~--- $p_0 \le \pwf$.
Втекания через~забой нет ни на~одной ветви, поэтому условие
для~температуры на~забое не~меняется."""

text = SRC.read_text(encoding="utf-8")
for anchor, block in (("образуется двухфазная зона.\n", CONT),
                      ("$q_{o,\\text{ст}} = -G_{\\half}^o > 0$.\n", DISC)):
    n = text.count(anchor)
    print(f"якорь {anchor.strip()[:40]!r}: {n} раз")
    assert n == 1
    text = text.replace(anchor, anchor.rstrip("\n") + block + "\n")

out = HERE / "tex"
out.mkdir(exist_ok=True)
(out / "problem_statement.tex").write_text(text, encoding="utf-8")
print("записано", out / "problem_statement.tex")
