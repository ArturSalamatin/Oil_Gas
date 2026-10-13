"""DEBT-055, аудит 1: шаг 1 плана на копии problem_statement.tex — сборка и переполнение строк.

Копия с заменой абзаца (текст «После» шага 1 плана, вариант из аргумента) пишется в
tex/ рядом со скриптом, собирается pdflatex дважды; печатаются ошибки и Overfull \\hbox
у строк новой вставки. Выходы pdflatex (tex/) в git не идут — удалить после проверки.

Запуск из любого каталога:
    python tex_check.py [вариант]      вариант: plan (по умолчанию) | fixed
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[4] / "numerical_solver" / "doc" / "problem_statement.tex"
OUT = HERE / "tex"
OUT.mkdir(exist_ok=True)

OLD = ("Порог заметно ниже $\\sim\\varepsilon_{\\text{маш}}(R_{\\text{ext}}/r_w)^2$ не~достигается\n"
       "из-за округлений, и~шаги дробятся.\n")

EQ_PLAN = r"""\begin{equation}\label{eq:newton_cell_floor}
  m_{\text{окр}} = \max_j \frac{\Delta t}{V_{p,j}}
    \max\Bigl(\sum_k \Bigl|\frac{\partial F_j^{\text{oil}}}{\partial z_k}\Bigr|
      \operatorname{ulp}(z_k),\
      \frac{1}{s_g}\sum_k \Bigl|\frac{\partial F_j^{\text{gas}}}{\partial z_k}\Bigr|
      \operatorname{ulp}(z_k)\Bigr).
\end{equation}
"""

EQ_FIXED = r"""\begin{equation}\label{eq:newton_cell_floor}
  m_{\text{окр}} = \max_j \frac{\Delta t}{V_{p,j}}
    \max\Bigl(\sum_k \Bigl|\frac{\partial F_j^{\text{oil}}}{\partial z_k}\Bigr|
      \operatorname{ulp}(z_k),\
      \frac{1}{s_g}\sum_k \Bigl|\frac{\partial F_j^{\text{gas}}}{\partial z_k}\Bigr|
      \operatorname{ulp}(z_k)\Bigr).
\end{equation}
"""

TAIL_PLAN = r"""В~замерах Ньютон останавливается на~$0.1$--$0.4\,m_{\text{окр}}$. Предел задают давления
в~потоках через грани~\eqref{eq:flux_oil}, \eqref{eq:flux_gas}:
$m_{\text{окр}} \sim \varepsilon_{\text{маш}}\,p_j\,\mathcal{T}_{j\pm\half}\,
\lambda\,\Delta t/V_{p,j}$, где $\lambda$~--- подвижность компонента на~грани
(например, $k_{ro}/(\mu_o B_o)$). Поэтому предел растёт пропорционально~$\Delta t$,
а~у~забоя логарифмической сетки~--- как $\mathcal{T}_{j+\half}/V_{p,j} \propto
N^2/\ln^2(R_{\text{ext}}/r_w)$. С~отношением поровых объёмов крайних ячеек
$\sim(R_{\text{ext}}/r_w)^2$ он не~растёт: при том~же~$N$ с~ростом $R_{\text{ext}}$
предел убывает как $\ln^{-2}(R_{\text{ext}}/r_w)$. В~отличие от~предела абсолютного
условия~\eqref{eq:newton_abs_tol}, который растёт с~уменьшением шага, этот растёт
с~его увеличением. Шаг, на~котором порог ниже предела, отвергается и~дробится, пока
предел не~опустится ниже порога; в~расчётах проекта с~порогом по~умолчанию так было
лишь при $N = 350$ и~суточном шаге.
"""

HEAD = r"""Порог не~достижим ниже предела округления. Неизвестные $z_k$ ($p$, $S_g$ или~$R_s$
ячеек) представимы лишь с~шагом $\operatorname{ulp}(z_k) \approx
\varepsilon_{\text{маш}}|z_k|$, и~невязку ячейки нельзя сделать меньше доли
изменения, которое даёт сдвиг каждой неизвестной на~этот шаг. Оценка этого изменения
сверху (сумма модулей вкладов):
"""

variant = sys.argv[1] if len(sys.argv) > 1 else "plan"
# orig — без замены: есть ли переполнение у тех же строк до правки
new = OLD if variant == "orig" else HEAD + (EQ_PLAN if variant == "plan" else EQ_FIXED) + TAIL_PLAN
src = SRC.read_text(encoding="utf-8")
assert src.count(OLD) == 1, "цитата «До» шага 1 не найдена ровно один раз"
src = src.replace(OLD, new)
if variant == "orig":
    HEAD = OLD
tex = OUT / "ps_check.tex"
tex.write_text(src, encoding="utf-8")
# Строки вставки в копии — чтобы отфильтровать Overfull только у них
start = src[: src.index(HEAD)].count("\n") + 1
end = start + new.count("\n")
for run in (1, 2):
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                       cwd=OUT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"прогон {run}: код {r.returncode}")
log = (OUT / "ps_check.log").read_text(encoding="utf-8", errors="replace")
errors = [l for l in log.splitlines() if l.startswith("! ")]
print(f"вставка: строки {start}-{end}; ошибок {len(errors)}: {errors[:3]}")
for m in re.finditer(r"Overfull \\hbox \(([\d.]+)pt too wide\) (?:in paragraph|detected) at lines? (\d+)(?:--(\d+))?", log):
    a, b = int(m.group(2)), int(m.group(3) or m.group(2))
    if b >= start and a <= end:
        print(f"  Overfull {m.group(1)} pt у строк {a}-{b} (в вставке)")
undef = re.findall(r"Reference `([^']+)' on page \d+ undefined", log)
print(f"неопределённых ссылок: {sorted(set(undef))}")
