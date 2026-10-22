r"""Проба DEBT-057: правки problem_statement.tex шага 1 плана — к копии, со сборкой pdflatex.

Запуск из numerical_solver/ (копия и вывод сборки — vault/issues/debt-057/probes/tex/, не коммитится):
    <python> ..\vault\issues\debt-057\probes\tex_apply.py            # проверка на копии
    <python> ..\vault\issues\debt-057\probes\tex_apply.py --inplace  # то же + запись в doc/
Каждая пара (было, стало, сколько раз) — ровно блоки шага 1 плана; «было» обязано
найтись заданное число раз. Сборка — два прохода pdflatex; в журнале не должно быть
ошибок, неопределённых команд и ссылок. Метка eq:porosity — в .aux.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOLVER = Path.cwd()
SRC = SOLVER / "doc" / "problem_statement.tex"
OUT = Path(__file__).with_name("tex")

PAIRS = [
    # P1, P2 — таблица обозначений
    (r"""$\phi$        & пористость (постоянная)                   & --- \\""",
     r"""$\phi$        & пористость, $\phi(p)$~\eqref{eq:porosity}; $\phi_0 = \phi(p_0)$ & --- \\""", 1),
    (r"""$c_r$         & сжимаемость порового пространства ($=0$ в данной модели) & Па$^{-1}$ \\""",
     r"""$c_r$         & сжимаемость порового пространства, $(1/\phi)\,d\phi/dp$ & Па$^{-1}$ \\""", 1),
    # P3 — допущение
    (r"""  \item \textbf{Постоянная пористость.}
        $\phi = \mathrm{const}$, сжимаемость породы $c_r = 0$.
        В~разделе~\ref{ssec:equations} формулы записываются в~общем виде
        при $c_r \neq 0$ для полноты; при упрощении
        (раздел~\ref{sec:splitting}) $c_r = 0$.""",
     r"""  \item \textbf{Сжимаемость порового пространства.}
        Пористость зависит только от~давления:
        \begin{equation}\label{eq:porosity}
          \phi(p) = \phi_0\,e^{c_r\,(p - \ppl)},
        \end{equation}
        $\phi_0$~--- пористость при начальном давлении~$\ppl$,
        $c_r$~--- сжимаемость порового пространства (постоянная).
        Деформация скелета учитывается только через поровый объём:
        объёмные величины отнесены к~начальному объёму элемента пласта,
        изменение размеров элемента и~площадей его граней не~учитывается,
        масса скелета в~элементе постоянна. При $c_r = 0$ пористость
        постоянна, $\phi = \phi_0$.""", 1),
    # P4 — eq:main_rhocpeff
    (r"""\begin{equation}\label{eq:main_rhocpeff}
\rhocpeff
    = (1-\phi)\,(\rho c_p)_s""",
     r"""\begin{equation}\label{eq:main_rhocpeff}
\rhocpeff
    = (1-\phi_0)\,(\rho c_p)_s""", 1),
    # P5 — eq:main_Qad_muJT без членов c_r + пояснение
    (r"""      + c_r\!\left(p + (\rho c_p)_s\,T\right)
    \right]\pdt{p}.
  }
\end{equation}
\begin{equation}\label{eq:main_Qdeg}""",
     r"""    \right]\pdt{p}.
  }
\end{equation}
Сжимаемость породы входит в~$\Qad$ и~$\rhocpeff$ только через
пористость~$\phi = \phi(p)$~\eqref{eq:porosity}. Скелет~--- с~множителем
$1 - \phi_0$: его масса в~элементе постоянна. Членов
$c_r\,(p + (\rho c_p)_s T)$ нет: работа флюида над стенками пор уходит
в~упругую энергию скелета, а~не~в~тепло
(приложение~\ref{app:energy_derivation}, \eqref{eq:rock_dt}).
\begin{equation}\label{eq:main_Qdeg}""", 1),
    # P6 — сводная таблица
    (r"""  \item свойства породы: $\phi$, $k$, $(\rho c_p)_s$;
  \item теплопроводность среды~\eqref{eq:lambda_eff}:
        $\leff = (1{-}\phi)\,\hat\lambda_s
        + \phi\,(S_o\,\hat\lambda_o + S_g\,\hat\lambda_g)$.""",
     r"""  \item свойства породы: $\phi(p)$~\eqref{eq:porosity} ($\phi_0$, $c_r$), $k$, $(\rho c_p)_s$;
  \item теплопроводность среды~\eqref{eq:lambda_eff}:
        $\leff = (1{-}\phi_0)\,\hat\lambda_s
        + \phi_0\,(S_o\,\hat\lambda_o + S_g\,\hat\lambda_g)$.""", 1),
    # P7 — свойства породы
    (r"""  \item $\phi$~--- пористость, постоянная.""",
     r"""  \item $\phi(p)$~--- пористость~\eqref{eq:porosity}: $\phi_0$ при~$\ppl$ и~сжимаемость порового пространства~$c_r$.""", 1),
    # P8 — λ_eff при φ0
    (r"""    \leff = (1-\phi)\,\hat\lambda_s + \phi\,(S_o\,\hat\lambda_o + S_g\,\hat\lambda_g).
  }
\end{equation}
Параметры $\hat\lambda_s$, $\hat\lambda_o$, $\hat\lambda_g$~--- постоянные,
задаются в~конфигурационном файле. $\leff$ изменяется по~пласту вместе
с~$S_g$.""",
     r"""    \leff = (1-\phi_0)\,\hat\lambda_s + \phi_0\,(S_o\,\hat\lambda_o + S_g\,\hat\lambda_g).
  }
\end{equation}
Параметры $\hat\lambda_s$, $\hat\lambda_o$, $\hat\lambda_g$~--- постоянные,
задаются в~конфигурационном файле. $\leff$ изменяется по~пласту вместе
с~$S_g$. Пористость в~замыкании~--- начальная~$\phi_0$: модель
эмпирическая, а~поправка от~$\phi(p)$ мала~--- при
$c_r\,|p - \ppl| = 4.5\cdot10^{-3}$, $\phi_0 = 0.2$ и~теплопроводностях
1.5 / 0.14~Вт/(м$\cdot$К) около 0.1\,\%.""", 1),
    # P9–P12 — упрощение гидродинамики
    (r"""При $T = \Tpl = \mathrm{const}$ и~$c_r = 0$ в~уравнениях""",
     r"""При $T = \Tpl = \mathrm{const}$ в~уравнениях""", 1),
    (r"""  \item $\phi = \mathrm{const}$ и~выносится из-под производной по~$t$.""",
     r"""  \item пористость $\phi(p)$~\eqref{eq:porosity}~--- тоже функция только~$p$.""", 1),
    (r"""    \phi\,\pdt{}\!\left(\frac{1 - S_g}{B_o(p)}\right)""",
     r"""    \pdt{}\!\left(\phi(p)\,\frac{1 - S_g}{B_o(p)}\right)""", 1),
    (r"""    \phi\,\pdt{}\!\left(
      \frac{R_s(p)\,(1 - S_g)}{B_o(p)} + \frac{S_g}{B_g(p)}
    \right)""",
     r"""    \pdt{}\!\left(\phi(p)\!\left[
      \frac{R_s(p)\,(1 - S_g)}{B_o(p)} + \frac{S_g}{B_g(p)}
    \right]\right)""", 1),
    # P13, P14 — невязки гидродинамики
    (r"""    F_j^{\text{oil}} = V_j\,\phi\,
      \frac{(1 - S_{g,j}^{n+1})/B_{o,j}^{n+1}
            - (1 - S_{g,j}^n)/B_{o,j}^n}{\Delta t}""",
     r"""    F_j^{\text{oil}} = V_j\,
      \frac{\phi_j^{n+1}(1 - S_{g,j}^{n+1})/B_{o,j}^{n+1}
            - \phi_j^n(1 - S_{g,j}^n)/B_{o,j}^n}{\Delta t}""", 1),
    (r"""где $G_{j+\half}^{o} = \mathcal{T}_{j+\half}\,""",
     r"""где $\phi_j^n = \phi(p_j^n)$~\eqref{eq:porosity}, $G_{j+\half}^{o} = \mathcal{T}_{j+\half}\,""", 1),
    (r"""    F_j^{\text{gas}} = V_j\,\phi\,
      \frac{\left[\frac{R_{s,j}^{n+1}(1-S_{g,j}^{n+1})}{B_{o,j}^{n+1}}
            + \frac{S_{g,j}^{n+1}}{B_{g,j}^{n+1}}\right]
            - \left[\frac{R_{s,j}^n(1-S_{g,j}^n)}{B_{o,j}^n}""",
     r"""    F_j^{\text{gas}} = V_j\,
      \frac{\phi_j^{n+1}\left[\frac{R_{s,j}^{n+1}(1-S_{g,j}^{n+1})}{B_{o,j}^{n+1}}
            + \frac{S_{g,j}^{n+1}}{B_{g,j}^{n+1}}\right]
            - \phi_j^n\left[\frac{R_{s,j}^n(1-S_{g,j}^n)}{B_{o,j}^n}""", 1),
    # P15 — eq:Qad_disc
    (r"""Вычисляется поточечно в~центре ячейки (при~$c_r = 0$,
через~$\mu_{\mathrm{JT}}$~\eqref{eq:main_Qad_muJT}):
\begin{equation}\label{eq:Qad_disc}
  V_j\,{\Qad}_j = V_j\,\phi\,""",
     r"""Вычисляется поточечно в~центре ячейки
(через~$\mu_{\mathrm{JT}}$~\eqref{eq:main_Qad_muJT}):
\begin{equation}\label{eq:Qad_disc}
  V_j\,{\Qad}_j = V_j\,\phi_j^{n+1}\,""", 1),
    (r"""    \frac{p_j^{n+1}-p_j^n}{\Delta t}.
\end{equation}

\paragraph{Теплота дегазации.}""",
     r"""    \frac{p_j^{n+1}-p_j^n}{\Delta t}.
\end{equation}
Пористость $\phi_j^{n+1} = \phi(p_j^{n+1})$~\eqref{eq:porosity}~--- та~же,
что в~запасах гидродинамики~\eqref{eq:residual_oil}; так~же она входит
во~флюидную часть~$\rhocpeff$, скелет~--- с~$1 - \phi_0$.

\paragraph{Теплота дегазации.}""", 1),
    # P16, P17 — ṁ
    (r"""в~ячейке, $\phi(1-S_{g,j})/B_{o,j}$, а~пространственный~---""",
     r"""в~ячейке, $\phi_j^{n+1}(1-S_{g,j})/B_{o,j}$, а~пространственный~---""", 1),
    (r"""    V_j\,\phi\,\frac{1-S_{g,j}^{n+1}}{B_{o,j}^{n+1}}\,""",
     r"""    V_j\,\phi_j^{n+1}\,\frac{1-S_{g,j}^{n+1}}{B_{o,j}^{n+1}}\,""", 1),
    # P18–P20 — первое начало: элемент, E_total, работа над стенками пор
    (r"""Рассмотрим неподвижный элемент пористой среды. Первое начало
термодинамики для открытой системы:""",
     r"""Рассмотрим неподвижный элемент пористой среды; объёмные величины
отнесены к~его начальному объёму. Масса скелета в~элементе постоянна;
при $c_r \ne 0$ меняется поровый объём~\eqref{eq:porosity}, изменение
размеров элемента не~учитывается. Первое начало
термодинамики для открытой системы:""", 1),
    (r"""  \item $E_{\mathrm{total}}$~--- полная внутренняя энергия вещества
        внутри элемента (порода + флюиды), Дж/м$^3$;""",
     r"""  \item $E_{\mathrm{total}}$~--- внутренняя энергия флюидов и~тепловая
        энергия скелета внутри элемента, Дж/м$^3$; упругая энергия
        деформации скелета в~$E_{\mathrm{total}}$ не~входит;""", 1),
    (r"""  \item $\dot{W}_{\text{внешн}}$~--- мощность работы, совершаемой
        системой над~окружением, помимо работы проталкивания
        (в~рассматриваемой задаче $\dot{W}_{\text{внешн}} = 0$:
        нет подвижных стенок и~внешних механических воздействий),
        Вт/м$^3$;""",
     r"""  \item $\dot{W}_{\text{внешн}}$~--- мощность работы, совершаемой
        системой над~окружением, помимо работы проталкивания, Вт/м$^3$.
        Здесь это работа флюида над стенками пор:
        $\dot{W}_{\text{внешн}} = p\,\partial\phi/\partial t$. Она
        запасается упругой энергией скелета и~в~тепло не~переходит
        (упругая деформация обратима). Других механических воздействий
        нет; при $c_r = 0$ $\dot{W}_{\text{внешн}} = 0$;""", 1),
    # P21, P22 — eq:energy_cons, eq:E_expanded + пояснение после eq:F_total
    (r"""  \pdt{E}
  + \divr{F}
  = \divr{\leff\,\pdr{T}},
\end{equation}""",
     r"""  \pdt{E}
  + \divr{F}
  = \divr{\leff\,\pdr{T}} - p\,\pdt{\phi},
\end{equation}""", 1),
    (r"""  E = (1 - \phi)\,(\rho c_p)_s\,T + \phi\sum_\alpha S_\alpha\,\rho_\alpha\,e_\alpha,""",
     r"""  E = (1 - \phi_0)\,(\rho c_p)_s\,T + \phi\sum_\alpha S_\alpha\,\rho_\alpha\,e_\alpha,""", 1),
    (r"""  F = \sum_\alpha \rho_\alpha\,h_\alpha\,u_\alpha, \quad  h_\alpha = e_\alpha + p/\rho_\alpha.
\end{equation}""",
     r"""  F = \sum_\alpha \rho_\alpha\,h_\alpha\,u_\alpha, \quad  h_\alpha = e_\alpha + p/\rho_\alpha.
\end{equation}
Тепловая энергия скелета в~\eqref{eq:E_expanded}~--- его масса
в~элементе, умноженная на~удельную теплоёмкость. Масса постоянна,
поэтому множитель $1 - \phi_0$ от~давления не~зависит. Запись
$(1 - \phi)\,(\rho c_p)_s T$ с~$\phi(p)$ означала~бы, что скелет при
изменении давления уходит из~элемента и~уносит энергию
$(\rho c_p)_s T$~--- величину, которая зависит от~выбора нуля отсчёта
энтальпии.""", 1),
    # P23 — первое слагаемое четырёх уравнений вывода
    (r"""  \pdt{}\left( (1 - \phi)\,(\rho c_p)_s\,T - \phi\,p\right)""",
     r"""  \pdt{}\left( (1 - \phi_0)\,(\rho c_p)_s\,T - \phi\,p\right) + p\,\pdt{\phi}""", 4),
    # P24 — eq:rock_dt
    (r"""Раскроем производные от слагаемых, описывающих теплоёмкость пород и
работу внешних сил
\begin{equation}\label{eq:rock_dt}
  \pdt{}\!\left[
    (1-\phi)\,(\rho c_p)_s\,T-\phi\,p
  \right]
  = (1-\phi)\,(\rho c_p)_s\,\pdt{T}
    - (\rho c_p)_s\,T\,\phi\,c_r\,\pdt{p}-\phi\,(1 + p\,c_r)\,\pdt{p}.
\end{equation}""",
     r"""Раскроем производные от слагаемых, описывающих теплоёмкость скелета
и~работу давления
\begin{equation}\label{eq:rock_dt}
  \pdt{}\!\left[
    (1-\phi_0)\,(\rho c_p)_s\,T-\phi\,p
  \right] + p\,\pdt{\phi}
  = (1-\phi_0)\,(\rho c_p)_s\,\pdt{T}
    - \phi\,\pdt{p}.
\end{equation}
Слагаемое $p\,\partial\phi/\partial t$ из~$\partial(\phi p)/\partial t$
сокращается с~работой флюида над стенками пор~\eqref{eq:energy_cons};
у~скелета производной~$\partial\phi/\partial t$ нет, так как его масса
постоянна. Сжимаемость породы остаётся в~уравнении энергии только
через~$\phi(p)$.""", 1),
    # P25, P26 — eq:energy_cons_derived4
    (r"""  \left[(1-\phi)\,(\rho c_p)_s\, +\phi\,""",
     r"""  \left[(1-\phi_0)\,(\rho c_p)_s\, +\phi\,""", 1),
    (r"""    (\phi\,S_g\,(1 - \alpha_g\,T)+\phi\,S_o\,(1 - \alpha_o\,T)\,-(\rho c_p)_s\,T\,\phi\,c_r-\phi\,(1 + p\,c_r))\,\pdt{p}""",
     r"""    (\phi\,S_g\,(1 - \alpha_g\,T)+\phi\,S_o\,(1 - \alpha_o\,T)-\phi)\,\pdt{p}""", 1),
    # P27, P28 — определения приложения
    (r"""\begin{equation}
\rhocpeff
    = (1-\phi)\,(\rho c_p)_s""",
     r"""\begin{equation}
\rhocpeff
    = (1-\phi_0)\,(\rho c_p)_s""", 1),
    (r"""\Qad = \phi\left[T\,\sum_\alpha S_\alpha\,\alpha_\alpha + (\rho c_p)_s\,T\,c_r + p\,c_r\right]\pdt{p},""",
     r"""\Qad = \phi\,T\sum_\alpha S_\alpha\,\alpha_\alpha\,\pdt{p},""", 1),
    # P29 — eq:Qad_muJT
    (r"""      \sum_\alpha S_\alpha\!\left(1
        + \rho_\alpha\,c_{p,\alpha}\,\mu_{\mathrm{JT},\alpha}\right)
      + c_r\!\left(p + (\rho c_p)_s\,T\right)
    \right]\pdt{p}.""",
     r"""      \sum_\alpha S_\alpha\!\left(1
        + \rho_\alpha\,c_{p,\alpha}\,\mu_{\mathrm{JT},\alpha}\right)
    \right]\pdt{p}.""", 1),
    # P30 — проверка энтропией
    (r"""$\alpha_\alpha = (1 + \rho_\alpha\,c_{p,\alpha}\,
\mu_{\mathrm{JT},\alpha})/T$.""",
     r"""$\alpha_\alpha = (1 + \rho_\alpha\,c_{p,\alpha}\,
\mu_{\mathrm{JT},\alpha})/T$.

\paragraph{Проверка: обратимое адиабатическое сжатие.}
Пусть течения, теплопроводности и~дегазации нет ($u_\alpha = 0$,
$\leff = 0$, $\mdot = 0$), фаза одна. Насыщенная упруго деформируемая
порода сжимается обратимо и~адиабатически~--- энтропия элемента
постоянна. Энтропия флюида меняется на~$\phi\,\rho\,c_p\,dT/T -
\phi\,\alpha\,dp$ (соотношение Максвелла $(\partial s/\partial p)_T =
-\alpha/\rho$), скелета~--- на~$(1-\phi_0)\,(\rho c_p)_s\,dT/T$: его
масса постоянна, упругая деформация энтропии не~меняет. Сумма равна
нулю:
\[
  \bigl[(1-\phi_0)\,(\rho c_p)_s + \phi\,\rho\,c_p\bigr]\,dT
  = \phi\,\alpha\,T\,dp.
\]
Это в~точности~\eqref{eq:energy_cons_derived4} при тех~же условиях:
$\rhocpeff\,\partial T/\partial t = \Qad$,
$\Qad = \phi\,\alpha\,T\,\partial p/\partial t$. С~членом
$c_r\,(p + (\rho c_p)_s T)$ в~$\Qad$ энтропия в~обратимом процессе
менялась~бы на~$\phi\,c_r\,(p/T + (\rho c_p)_s)\,dp$ и~при одном из~знаков
$dp$ убывала~бы, что невозможно.""", 1),
]


def main():
    text = SRC.read_text(encoding="utf-8")
    ok = True
    for k, (old, new, n) in enumerate(PAIRS, 1):
        found = text.count(old)
        if found != n:
            print(f"пара {k}: «было» найдено {found} раз, ожидалось {n}")
            ok = False
            continue
        text = text.replace(old, new)
    if not ok:
        sys.exit(1)
    # Остатки: c_r в уравнении энергии и «φ = const» больше не встречаются
    for pat in (r"c_r\\!\\left\(p \+ \(\\rho c_p\)_s", r"\(1 - \\phi\)\\,\(\\rho c_p\)_s",
                r"\(1-\\phi\)\\,\(\\rho c_p\)_s", r"phi = \\mathrm\{const\}"):
        hits = [i + 1 for i, line in enumerate(text.splitlines()) if re.search(pat, line)]
        print(f"остаток /{pat}/: строки {hits}")
    OUT.mkdir(exist_ok=True)
    (OUT / "problem_statement.tex").write_text(text, encoding="utf-8")
    print(f"пар применено: {len(PAIRS)}; копия: {OUT / 'problem_statement.tex'}")
    if "--inplace" in sys.argv:
        # Окончания строк — как в файле (рабочая копия Windows: CRLF, core.autocrlf)
        crlf = b"\r\n" in SRC.read_bytes()
        SRC.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        print(f"записано в {SRC} ({'CRLF' if crlf else 'LF'})")
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "problem_statement.tex"],
                       cwd=OUT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = (OUT / "problem_statement.log").read_text(encoding="utf-8", errors="replace")
    bad = [l for l in log.splitlines()
           if re.search(r"^!|Undefined control|undefined references|Reference .* undefined", l)]
    print("журнал сборки:", "чисто" if not bad else "\n  " + "\n  ".join(bad[:20]))
    aux = (OUT / "problem_statement.aux").read_text(encoding="utf-8", errors="replace")
    print("eq:porosity в .aux:", "да" if "{eq:porosity}" in aux else "НЕТ")


if __name__ == "__main__":
    main()
