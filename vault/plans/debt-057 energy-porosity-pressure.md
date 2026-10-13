---
tags:
  - план
  - рефакторинг
date: 2026-10-13
issue: DEBT-057
github: 108
branch: refactor/debt-057/energy-porosity-pressure
status: в процессе
worktree: .worktrees/debt-057
audit:
  date: 2026-10-13
  round: 1
  found: 7
  auto-fixed: 7
  manual-required: 0
---

# DEBT-057: энергия берёт ту же пористость φ(p), что гидродинамика; члены $c_r$ в $Q_{ad}$ убраны из постановки как артефакт вывода

Подтип: **рефакторинг** — согласование двух блоков одного шага. Поведение меняется только при $c_r \ne 0$ (из 23 примеров — только 18); при $c_r = 0$ код идёт прежним путём, побитово.

## 0. Решения пользователя (2026-10-13, при планировании)

1. **Вариант B.** Флюид — $\varphi(p^{n+1})$: в $\varphi\sum S_\alpha\rho_\alpha c_{p,\alpha}$ эффективной теплоёмкости, в $Q_{ad}$, во временной части $\dot m$. Скелет — $(1-\varphi_0)(\rho c_p)_s$: масса скелета в ячейке постоянна. $\lambda_{eff}$ — эмпирическое замыкание при $\varphi_0$. Отвергнуты: A ($\varphi(p)$ везде, включая скелет и $\lambda_{eff}$; отличается от B на 0.3 мК, но скелет при этом «теряет массу»), 0 (код не трогать).
2. **Члены $c_r\,(p + (\rho c_p)_s T)$ убрать из постановки и переписать вывод** в приложении `app:energy_derivation`: работа флюида над стенками пор, постоянная масса скелета, проверка энтропией.
3. **DEBT-066 зарегистрирована** (находка вне задачи: остаток правила Лейбница во времени в $\dot m$, раздел 2.6). В DEBT-057 не входит.

## 1. Сводка

- **Суть.** `TridiagEnergySolver` получает опорное давление пористости `p_ref` (фабрика передаёт `initial_conditions.p0` — то же, что породе прототипа) и метод `porosity(p)` = $\varphi_0 e^{c_r(p - p_0)}$ (`eq:porosity`). В трёх местах `rock.porosity` заменяется по варианту B. При $c_r = 0$ `porosity` возвращает тот же скаляр `rock.porosity` — операции прежние, побитово.
- **Постановка.** Новая метка `eq:porosity` в допущениях; $\varphi = \mathrm{const}$ убрано из допущений, таблицы обозначений, упрощения гидродинамики и невязок; `eq:main_rhocpeff`, `eq:lambda_eff` — с $\varphi_0$; `eq:main_Qad_muJT`, `eq:Qad_muJT` — без членов $c_r$; вывод в приложении — с работой флюида над стенками пор и постоянной массой скелета; абзац «Проверка: обратимое адиабатическое сжатие».
- **Числа.** Пример 18: $\max|\Delta T(r_w)|$ = 1.29 мК (сразу после смены $p_{wf}$), в конце +0.52 мК; отпечаток истории $T$ `fddab42a74adde09` → `fd040715fc926897`. Остальные 22 примера — побитово (снимок до/после). Расхождение $\dot m$ с выделением газа в гидродинамике на первых сутках примера 18: $6.7\cdot10^{-4}$ → $-9.5\cdot10^{-10}$ (после вычета остатка DEBT-066).
- **Шагов:** 7 (0 — подготовка, 6 — итог).
- **Тесты:** +9 в новом `numerical_solver/tests/test_energy_porosity.py` (быстрый уровень, ~2 с). Переписан эталон сверки матрицы энергии (`tests/test_energy_matrix_examples.py`): $\varphi(p)$ вместо $\varphi_0$. Перемер `test_wellbore_cools` (пример 18).
- **Код:** ~45 строк в `energy/tridiag.py` (половина — комментарии), 5 строк в `factory.py`, комментарии `io/config.py`, `energy/balance.py`, вызов в `examples/verify_balance_vs_solver.py`; ~40 строк эталона в тестах; ~240 строк нового файла тестов; ~120 строк `.tex`.
- **Прототип не меняется.**
- **Все правки шагов 1–3 проверены при планировании на копиях** (пробы `tex_apply.py`, `apply_code.py`, раздел 2.3): все «было» найдены, копия `.tex` собирается без ошибок, на копии пакета 59 passed (новые 9 + `test_energy.py` + сверка матрицы 18 и 03), отпечаток $T$ примера 18 = вариант B пробы.

## 2. Контекст

### 2.1. Что не так

Гидродинамика (прототип `radial_blackoil`) считает поровый объём ячейки $V\varphi(p)$, $\varphi(p) = \varphi_{ref}\,e^{c_r(p - p_{ref})}$ (`numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/rock.py:5-8`); фабрика передаёт $\varphi_{ref}$ = `rock.porosity`, $p_{ref} = p_0$ (`numerical_solver/gpn_multiphase_solver/factory.py:413-420`). Запасы компонентов — `blackoil.py:213-214` (`pv*so/bo`, `pv*(rs*so/bo+sg/bg)` с `pv = pore_volume_m3(bulk, p)`).

Энергия до DEBT-057 берёт постоянную `rock.porosity` (номера строк — на `3f3df63`):

| Величина | Код | $\varphi$ сейчас | $\varphi$ после (вариант B) |
|---|---|---|---|
| $(\rho c_p)_{eff}$, флюидная часть | `energy/tridiag.py:216, 228-229` | $\varphi_0$ | $\varphi(p^{n+1})$ |
| $(\rho c_p)_{eff}$, скелет | там же | $1-\varphi_0$ | $1-\varphi_0$ (без изменений) |
| $\lambda_{eff}$ | `energy/tridiag.py:232-233` | $\varphi_0$ | $\varphi_0$ (без изменений) |
| $Q_{ad}$ | `energy/tridiag.py:450-454` | $\varphi_0$ | $\varphi(p^{n+1})$ |
| $\dot m$, временная часть | `energy/tridiag.py:488-493` | $\varphi_0$ | $\varphi(p^{n+1})$ |
| эталон сверки матрицы | `tests/test_energy_matrix_examples.py:143, 570, 617` | $\varphi_0$ | как в коде |

$c_r \ne 0$ — только у примера 18 (`numerical_solver/examples/18_prototype_input/config.json:18`, $c_r$ = 4.5e-10 1/Па, книга прототипа, [[VAL-005]]): $p_0$ = 20 МПа, $p_{wf}$ ступенями 15 → 12 → 10 МПа, $\max|\varphi(p)/\varphi_0 - 1|$ = 4.46e-3. У остальных 22 примеров `compressibility` не задано — 0.0 по умолчанию (`io/config.py:55`).

Расхождение не видит ни одна проверка: баланс энергии ([[DEBT-043]]) суммирует те же члены, что ставит решатель; баланс массы ([[DEBT-039]]) считает прототип по $\varphi(p)$; эталон сверки матрицы повторяет $\varphi_0$.

Постановка `numerical_solver/doc/problem_statement.tex`:
- допущение «$\phi = \mathrm{const}$, $c_r = 0$» (`:275-279`) пример 18 нарушает, нигде, кроме комментария `io/config.py:50-54`, это не сказано;
- непрерывная `eq:main_Qad_muJT` (`:399-408`) и `eq:Qad_muJT` (`:2771-2780`) содержат член $c_r\,(p + (\rho c_p)_s T)$, которого нет ни в `eq:Qad_disc` (`:1492-1501`, «при $c_r = 0$»), ни в коде. Член пришёл из `eq:rock_dt` (`:2694-2702`).

### 2.2. Физика: почему вариант B и почему членов $c_r$ в $Q_{ad}$ нет

Вывод уравнения энергии (`app:energy_derivation`) берёт энергию элемента $E = (1-\varphi)(\rho c_p)_s T + \varphi\sum S_\alpha\rho_\alpha e_\alpha$ и полагает $\dot W_{внешн} = 0$. При $\varphi(p)$ это даёт в `eq:rock_dt` два лишних члена.

1. **$-(\rho c_p)_s T\,\partial\varphi/\partial t$** — из $(1-\varphi(p))(\rho c_p)_s T$. Так было бы, если бы скелет уходил из элемента при росте пор и уносил энергию $(\rho c_p)_s T$. Член пропорционален абсолютной $T$: при отсчёте энергии скелета от $T_{ref}$ решение зависело бы от $T_{ref}$. Это признак несохранения массы. Тепловая энергия скелета в элементе — его масса, умноженная на удельную теплоёмкость; масса постоянна, множитель — $1-\varphi_0$ при любом $p$ (как бы ни была устроена деформация — сжатие зёрен или изменение размеров элемента, которое модель Black Oil не описывает).
2. **$-p\,\partial\varphi/\partial t$** — из $\partial(\varphi p)/\partial t$ (связь $e = h - p/\rho$). При растущих порах флюид совершает работу $p\,\partial\varphi/\partial t$ над стенками; при упругой деформации она запасается упругой энергией скелета и в тепло не переходит. В балансе тепловой энергии она стоит справа со знаком минус: $\dot W_{внешн} = p\,\partial\varphi/\partial t$. Тогда $-\partial(\varphi p)/\partial t + p\,\partial\varphi/\partial t = -\varphi\,\partial p/\partial t$ — член $c_r p$ сокращается.

**Проверка энтропией** (войдёт в приложение). Без течения, теплопроводности и дегазации насыщенная упругая порода сжимается обратимо и адиабатически, энтропия элемента постоянна:
- флюид: $\varphi\rho\,ds = \varphi\rho c_p\,dT/T - \varphi\alpha\,dp$ (Максвелл: $(\partial s/\partial p)_T = -\alpha/\rho$);
- скелет: $(1-\varphi_0)(\rho c_p)_s\,dT/T$.

Сумма — ноль: $[(1-\varphi_0)(\rho c_p)_s + \varphi\rho c_p]\,dT = \varphi\alpha T\,dp$. Это ровно форма кода с $\varphi = \varphi(p)$ (вариант B): $(\rho c_p)_{eff}\,\partial T/\partial t = Q_{ad}$, $Q_{ad} = \varphi\,(1 + \rho c_p\mu_{JT})\,\partial p/\partial t = \varphi\alpha T\,\partial p/\partial t$. С членом $c_r(p + (\rho c_p)_s T)$ энтропия в обратимом процессе менялась бы на $\varphi c_r (p/T + (\rho c_p)_s)\,dp$ — при одном из знаков $dp$ убывала бы.

$\lambda_{eff}$ (`eq:lambda_eff`) — эмпирическое объёмно-взвешенное замыкание; истинная объёмная доля пор деформированной среды — ни $\varphi(p)$, ни $\varphi_0$. Поправка от $\varphi(p)$ — около $c_r\Delta p\,\varphi_0\,|\lambda_s - \lambda_o|/\lambda_{eff}$ ≈ 0.1 % на примере 18. Решение: $\varphi_0$.

### 2.3. Замер (пробы при планировании, база `4dc9165`; код с тех пор не менялся — `3f3df63`)

**Аудит 1 (2026-10-13) повторил пробы на `b487f80`** — после влития FEAT-032 (`90b5c80`) и DEBT-065 (`aff802a`): все пары `tex_apply.py` и `apply_code.py` найдены, на копии пакета 59 passed, отпечатки базы `fddab42a74adde09` и варианта B `fd040715fc926897` прежние. Новая проба `audit_tree.py` — все правки шагов 1–3 на копии `numerical_solver/` (пакет, тесты, примеры без вывода, конфиги, `.tex`): `test_eq_references.py`, `test_example_scripts.py`, `test_energy_porosity.py`, `test_config.py` — 408 passed.

**Сверка после влития FEAT-030 (2026-10-13, `eb904eb`):** FEAT-030 правила `problem_statement.tex`, `io/config.py`, пример 18 (`main.py`, `config.json`, README), `examples/README.md`, `test_examples.py`, `test_example_scripts.py`. Все 33 пары `.tex` и 22 пары кода/тестов найдены, копия `.tex` собрана чисто; на копии пакета 59 passed, отпечаток B `fd040715fc926897`; `audit_tree.py` — 404 passed; отпечаток базы `fddab42a74adde09` — история примера 18 после FEAT-030 прежняя. Тестов 1912. Обновлены номера строк шага 4 и проба снимка (шаги 0.5, 4.7).

Пробы — `vault/issues/debt-057/probes/`, выводы — `*.out.txt` там же.

**`phi_energy.py`** — пример 18, 30 сут, подмена методов `TridiagEnergySolver` на время расчёта:

| вариант | $\max|\Delta T(r_w)|$ к коду | $T(r_w)-T_0$: min / конец, К | невязка баланса энергии | $\dot m$ − гидродинамика, отн. | отпечаток $T$ |
|---|---|---|---|---|---|
| код (`base`, $\varphi_0$) | — | −0.64313 / −0.48920 | 4.86e-15 | +6.2e-4 | `fddab42a74adde09` |
| **B** | **1.29 мК** | **−0.64186 / −0.48867** | 5.53e-15 | −1.08e-4 | **`fd040715fc926897`** |
| A ($\varphi(p)$ везде) | 1.58 мК (A−B 0.30 мК) | −0.64157 / −0.48857 | 6.7e-16 | −1.08e-4 | `548af5edb4f504da` |
| шаг 1800 с (масштаб погрешности шага) | 2.2 мК (1 сут), 0.55 мК после смены $p_{wf}$ | −0.64283 / −0.48903 | 9.9e-15 | +6.6e-4 | — |
| $c_r = 0$ | — | −0.65439 / −0.49789 | 6.4e-15 | −1.04e-4 | — |

- Эффект B сравним с погрешностью шага по времени 3600 с, а сразу после смены $p_{wf}$ (шаг 10 с) — больше её.
- Члены баланса энергии за 30 сут, B: $\Delta E$ = −1.2231e10, адиабатика −1.1864e10, дегазация −8.9305e8, ДТ +4.5515e8, конвекция +6.5481e7, теплопроводность +5.0247e6 Дж (код: −1.2235e10 / −1.1867e10 / −8.9370e8 / +4.5515e8 / +6.5560e7 / +5.0247e6).
- Остаток расхождения $\dot m$ (−1.08e-4 при $\varphi(p)$, −1.04e-4 при $c_r = 0$) равен $-\sum V\,\Delta R_s\,\Delta a$ до шестого знака — это DEBT-066, раздел 2.6.

**`mdot_short.py`** — первые 2 и 5 интервалов примера 18: (ṁ − гидродинамика − остаток)/гидродинамика = +6.70e-4 (код) против −9.5e-10 (B) на 2 интервалах (0.8 с расчёта); +4.69e-4 против −8.8e-10 на 5. Основа теста `test_mdot_matches_hydro_gas_release` (порог 1e-7).

**`t_fingerprint.py`** — отпечаток истории $T$ примера 18 штатным кодом пакета: на базе `fddab42a74adde09`; на копии пакета с кодом плана `fd040715fc926897` (= B пробы), $T(r_w)-T_0$ на записях 1 / 11 / 20 / 22: −0.53336 / −0.62847 / −0.64186 / −0.48867 К.

**`tex_apply.py`** — 33 пары правок `.tex` шага 1: все «было» найдены нужное число раз; копия собрана двумя проходами `pdflatex` без ошибок, неопределённых команд и ссылок; `eq:porosity` в `.aux`. Остаток `(1 - \phi)\,(\rho c_p)_s` — одна строка: пояснение, почему так писать нельзя.

**`apply_code.py`** — правки шагов 2–3 на копии пакета (`check/pkg`, pytest из `check/` с `PYTHONPATH`): 59 passed — 9 новых, `tests/test_energy.py`, `test_matrix_matches_reference[18_prototype_input]` и `[03_standing_corey]`. На неизменённом пакете новые тесты — 9 failed; `test_mdot_matches_hydro_gas_release` — `AssertionError: 6.703e-04` (по существу, а не из-за отсутствия API).

### 2.4. Что не меняется (зона неприкосновенности)

- Прототип `HydroSolverPrototype/` — не трогать; регрессия прототипа не нужна.
- Гидродинамика всех примеров — та же (энергия на гидродинамику не влияет; `test_thermal_does_not_affect_hydro`). Сверка VAL-005 (`TestPrototypeInput::test_matches_prototype`, `test_matches_imex_t07`) — без изменений.
- Примеры с $c_r = 0$ (22 из 23) — побитово: `porosity` возвращает скаляр `rock.porosity`, выражения $(1-\varphi_0)(\ldots) + \varphi(\ldots)$ при `phi0 is phi` — те же операции. Проверка — снимок вывода всех примеров до/после (шаги 0 и 4) и отпечаток.
- Сигнатуры: `TridiagEnergySolver(grid, pvt, rock)` — работает как прежде при $c_r = 0$ (новый `p_ref` — необязательный ключ); `compute_degassing(..., Rs_ext)` — так же (новый `p=None`). 40+ вызовов в тестах (`test_energy.py`, `test_val001.py`, `test_val002.py`, `test_simulator.py`, `test_output.py`) не меняются: у них $c_r = 0$.
- `TridiagEnergySolver(grid, None, None)` в `test_energy_matrix_examples.py:360, 552` — конструктор не трогает породу при `rock is None`.

### 2.5. Связь с другими задачами

| Задача | Состояние на 2026-10-13 | Пересечение |
|---|---|---|
| [[DEBT-066]] | зарегистрирована | Зависит от DEBT-057: метод `porosity(p)` нужен для запаса старого слоя. Тест `test_mdot_matches_hydro_gas_release` вычитает остаток DEBT-066 — после DEBT-066 его переписать на прямое равенство |
| [[FEAT-032]] | **влит** `90b5c80` | `simulator.py`, `factory.py:655` (не место правки), конфиги и README 16, 17; история примера 18 побитово прежняя (отпечаток базы на `b487f80` — `fddab42a74adde09`). Сдвинул строки `tests/test_examples.py` (+19 у `TestPrototypeInput`) и `examples/README.md` (+5 у таблицы баланса) — номера в шаге 4 обновлены аудитом 1 |
| [[DEBT-065]] | **влит** `aff802a` | `diagnostics/`, пример 11 — не пересекается |
| [[FEAT-030]] | **влит** `9a5b924` (2026-10-13) | Команда `python -m gpn_multiphase_solver run`, конвейер — `gpn_multiphase_solver/report/` (пористость там не используется — grep). `main.py` остались у всех 23 примеров (решение 6: у 17 — обёртка команды), у 18 — `run_case` + сверка с прототипом, команда шага 4.1 прежняя. Снимок примеров — пробой FEAT-030 (`vault/issues/feat-030/probes/snapshot_examples.py`, копия пробы DEBT-011 с запуском и командой). Сдвинула строки `tests/test_examples.py` и `examples/README.md` — номера шага 4 обновлены. Сверка после влития (`eb904eb`): все пары проб найдены, 59 passed, отпечатки прежние, `audit_tree.py` — 404 passed |
| [[DEBT-055]] | реализуется (`2b2ddbd` — материалы задачи) | `problem_statement.tex` (сходимость Ньютона, `eq:newton_cell_floor`) и прототип — разделы `.tex` не пересекаются с парами шага 1; если влита раньше — шаг 0.2 (`tex_apply.py`) проверит, что все пары находятся |
| [[BUG-025]] | реализуется (`7b636eb` — материалы задачи) | прототип; по её плану истории всех 23 примеров побитово прежние (наименьшее κ* = 63.1 — пример 18, шаг 10 с, порог 4) — отпечатки этого плана не меняются |
| [[VAL-005]] | влит | пример 18 — меняются только числа $T$ |
| [[DEBT-043]], [[DEBT-016]] | влиты | порог невязки 1e-12 и сверка матрицы — эталон переписывается в шаге 3 |

Если до реализации в базу влита задача, меняющая историю примера 18 или энергию, числа шага 4 (README, `test_wellbore_cools`) переснять по выводу, а отпечатки — сверить заново (шаг 0.4: отпечаток базы ≠ `fddab42a74adde09` → B-отпечаток плана неприменим, критерий — снимок и тесты).

### 2.6. Обнаруженные проблемы

1. **[[DEBT-066]]** (зарегистрирована 2026-10-13, решение пользователя): временная часть $\dot m$ берёт запас нефти нового слоя $a^{n+1}$, пространственная — $R_s^{n+1}$; дискретное правило Лейбница во времени даёт остаток $-\sum V\,\Delta R_s\,\Delta a$ на шаг. Пример 18: $-1.08\cdot10^{-4}$ выделившегося газа за 30 сут, $-2.0\cdot10^{-3}$ за первые сутки. Не блокирует DEBT-057. Утверждение «форма воспроизводит дискретное правило Лейбница точно» (`tridiag.py`, докстринг `compute_degassing`; `.tex`, абзац «Где берётся $B_o$») — только про пространственную часть; правится в DEBT-066.
2. **[[DEBT-068]]** (зарегистрирована 2026-10-13, решение пользователя): `rock.compressibility` не проверяется на знак (`io/config.py`, `_validate`; DEBT-051 проверяет только конечность). $c_r < 0$ физически бессмысленна, при $c_r < -c_o$ даёт $C_p < 0$ (механизм BUG-019); загрузчик книги прототипа её отвергает (`radial_blackoil/input_reader.py:49`), путь GPN — нет. Не блокирует DEBT-057: закон $\varphi(p)$ в энергии работает при любом знаке.

## 3. Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. Прочитай запись DEBT-057 в `vault/roadmap/известные баги и технический долг.md` и тело issue `vault/issues/debt-057/01-issue-body.md`. Раздел 2.2 — физическое обоснование; его же шаг 1 переносит в постановку.
3. Worktree по контракту `/implement`: `.worktrees/debt-057`, ветка `refactor/debt-057/energy-porosity-pressure` от `numerical_scheme/implementation`. Ниже `<W>` — корень worktree, `<M>` — основной каталог `D:\Lessons\Grants\2026\GPN\Oil_Gas`.
4. Python — из основного каталога (в worktree `.venv` нет):
   ```powershell
   $PY = "D:\Lessons\Grants\2026\GPN\Oil_Gas\numerical_solver\.venv\Scripts\python.exe"
   cd <W>\numerical_solver
   $env:PYTHONPATH = "<W>\numerical_solver"
   ```
   pytest берёт пакет worktree сам (`pythonpath` в `pyproject.toml`). Скрипты вне pytest (пробы, `main.py` примеров) без `PYTHONPATH` берут пакет **основного каталога** — каждая проба печатает путь пакета, сверять с `<W>`. Исключение — `apply_code.py` в режиме проверки: он сам ставит `PYTHONPATH` на свою копию.
5. Пробы плана лежат в `<W>\vault\issues\debt-057\probes\` (в базе с коммитом материалов задачи). Их выходы — `probes/check/`, `probes/tex/`, `probes/audit_tree/`, `probes/out/` — не коммитить, удалить в шаге 6.
6. Базовый замер (шаг 0.3):
   ```powershell
   & $PY -m pytest tests/ --collect-only -q          # N0 — всего тестов
   & $PY -m pytest tests/ -m "not slow" -q           # N0f — быстрый уровень, время
   ```
   Ориентир: 1912 тестов на `eb904eb` (после FEAT-030; на `3f3df63` было 1826, на `b487f80` — 1879). В базу могут прийти BUG-025, DEBT-055 — число будет больше. Итог DEBT-057 — N0 + 9.
7. Затем шаги 0.4–0.5 и шаг 1. После каждого шага — тест шага и регресс по полю «Регресс».

## 4. Шаги

### Шаг 0: подготовка — сверка мест правки, базовый замер, снимок «до»

**Цель:** убедиться, что база совпадает с планом; снять отпечаток и вывод примеров на неизменённом коде.

**Файлы:** пробы `vault/issues/debt-057/probes/*.py`, `vault/issues/debt-011/probes/snapshot_examples.py` (в базе с DEBT-011, не меняется).

**Что сделать:**
1. **Сверка правок кода и тестов** (из `<W>\numerical_solver`, ~1 мин):
   ```powershell
   & $PY ..\vault\issues\debt-057\probes\apply_code.py
   ```
   Ожидание: все пары «применено»/«найдено» без `AssertionError`; `пакет pytest:` — путь `...\probes\check\pkg\...`; `59 passed`; отпечаток `fd040715fc926897`. Иначе — база ушла: найти, какой файл изменился (`git log 3f3df63..HEAD -- <файл>`), поправить пары пробы и блоки шагов 2–3 плана; если изменилась энергия или история примера 18 — отпечаток B недействителен, сообщить пользователю.
2. **Сверка правок `.tex`** (~30 с):
   ```powershell
   & $PY ..\vault\issues\debt-057\probes\tex_apply.py
   ```
   Ожидание: «пар применено: 33», «журнал сборки: чисто», «eq:porosity в .aux: да».
   **Сторожа на всех правках сразу** (~30 с):
   ```powershell
   & $PY ..\vault\issues\debt-057\probes\audit_tree.py
   ```
   Ожидание: все пары применены, `408 passed` (на `b487f80`; число зависит от базы, падений быть не должно) — `test_eq_references.py`, `test_example_scripts.py`, `test_energy_porosity.py`, `test_config.py` на копии дерева с правками шагов 1–3.
3. Базовый замер: N0, N0f и время быстрого уровня (раздел 3, п. 6).
4. Отпечаток базы:
   ```powershell
   & $PY ..\vault\issues\debt-057\probes\t_fingerprint.py base
   ```
   Ожидание: `пакет = <W>\numerical_solver\gpn_multiphase_solver`, отпечаток `fddab42a74adde09`, $T(r_w)-T_0$ на записях 1 / 11 / 20 / 22: −0.53422 / −0.62970 / −0.64313 / −0.48920 К.
5. Снимок вывода всех примеров «до» (~12 мин, EMF выключен пробой) — пробой FEAT-030 (копия пробы DEBT-011, запускает `main.py` примера, а без него — команду пакета; так снимала FEAT-030 на этой базе):
   ```powershell
   New-Item -ItemType Directory -Force ..\vault\issues\debt-057\probes\out | Out-Null
   & $PY -X utf8 ..\vault\issues\feat-030\probes\snapshot_examples.py snap --tree . --out ..\vault\issues\debt-057\probes\out\snap_before.json
   ```
   Проба сама ставит `PYTHONPATH` на дерево и печатает путь пакета — сверить с `<W>`.

**Проверка:** пп. 1–2 — по ожиданиям; дерево `<W>` не изменилось (`git status --short` — только `probes/check`, `probes/tex`, `probes/audit_tree`, `probes/out`, они не коммитятся).

**Зависимости:** блокирует все шаги.

**Оценка:** ~16 мин машинного времени.

### Шаг 1: постановка — `eq:porosity`, вариант B в уравнении энергии, вывод без членов $c_r$

**Цель:** документ описывает то, что будет в коде: пористость $\varphi(p)$, скелет с $\varphi_0$, $Q_{ad}$ без $c_r$, вывод с работой над стенками пор.

**Файлы:** `numerical_solver/doc/problem_statement.tex`.

**Контекст:** тест-сторож `tests/test_eq_references.py` требует, чтобы каждая метка из кода и тестов была объявлена в `.tex`. Шаги 2–3 ссылаются на новую `eq:porosity` — поэтому `.tex` первым.

**Что сделать:** 33 пары правок, 36 замен (пара первого слагаемого четырёх уравнений вывода — четыре вхождения). В таблице ниже пары сгруппированы по местам (P1–P30; у P13, P15, P22 — по две пары). Точный текст «было/стало» — список `PAIRS` в `vault/issues/debt-057/probes/tex_apply.py` (проверен при планировании). Применить пробой:
```powershell
& $PY ..\vault\issues\debt-057\probes\tex_apply.py --inplace
```
или вручную Edit-ами по тем же парам. Результат обязан совпасть с парами (`git diff doc/problem_statement.tex`). Что меняется:

| Пары | Где (строки на `3f3df63`) | Суть |
|---|---|---|
| P1, P2 | таблица обозначений `:152, :154` | $\phi$ — $\phi(p)$ `eq:porosity`, $\phi_0 = \phi(p_0)$; $c_r = (1/\phi)\,d\phi/dp$ вместо «$=0$ в данной модели» |
| P3 | допущения `:275-279` | «Постоянная пористость» → «Сжимаемость порового пространства» с **новым `eq:porosity`**: $\phi(p) = \phi_0 e^{c_r(p - \ppl)}$; величины — на начальный объём элемента, изменение его размеров не учитывается, масса скелета постоянна |
| P4 | `eq:main_rhocpeff` `:378-380` | $(1-\phi_0)(\rho c_p)_s + \phi(\ldots)$ |
| P5 | `eq:main_Qad_muJT` `:399-408` | без строки `+ c_r\!\left(p + (\rho c_p)_s\,T\right)`; абзац после: сжимаемость — только через $\phi(p)$, скелет — $1-\phi_0$, ссылка на `eq:rock_dt` |
| P6 | сводная таблица `:481-484` | свойства породы $\phi(p)$ ($\phi_0$, $c_r$); $\leff$ с $\phi_0$ |
| P7 | свойства породы `:639` | $\phi(p)$ по `eq:porosity` |
| P8 | `eq:lambda_eff` `:649-656` | $\phi_0$ в замыкании + оценка поправки ~0.1 % |
| P9–P12 | упрощение гидродинамики `:806-831` | без «$c_r = 0$» и «$\phi = \mathrm{const}$»; `eq:mass_oil_simplified`, `eq:mass_gas_simplified` — $\phi(p)$ под производной |
| P13, P14 | `eq:residual_oil`, `eq:residual_gas` `:1066-1089` | $V_j(\phi_j^{n+1}[\ldots]^{n+1} - \phi_j^n[\ldots]^n)/\Delta t$, «где $\phi_j^n = \phi(p_j^n)$» — так считает прототип (`blackoil.py:213`) |
| P15 | `eq:Qad_disc` `:1492-1501` | $\phi_j^{n+1}$, без «при $c_r = 0$»; абзац: та же пористость, что в запасах гидродинамики, скелет — $1-\phi_0$ |
| P16, P17 | «Где берётся $B_o$» `:1545`, `eq:mdot_disc` `:1582` | $\phi_j^{n+1}$ в запасе временной части |
| P18–P20 | `eq:first_law_open` и пояснения `:2301-2325` | величины — на начальный объём элемента, масса скелета постоянна, изменение размеров не учитывается; $E_{total}$ без упругой энергии; $\dot W_{внешн} = p\,\partial\phi/\partial t$ — работа флюида над стенками пор |
| P21, P22 | `eq:energy_cons`, `eq:E_expanded`, после `eq:F_total` `:2330-2345` | правая часть $-p\,\partial\phi/\partial t$; $(1-\phi_0)(\rho c_p)_s T$; абзац о массе скелета и нуле отсчёта энтальпии |
| P23 | первое слагаемое `eq:energy_cons_der`, `_derived`, `_derived2`, `_derived3` `:2582, 2628, 2648, 2679` | $\partial_t((1-\phi_0)(\rho c_p)_s T - \phi p) + p\,\partial_t\phi$ |
| P24 | `eq:rock_dt` `:2694-2702` | $= (1-\phi_0)(\rho c_p)_s\,\partial_t T - \phi\,\partial_t p$; абзац о сокращении |
| P25, P26 | `eq:energy_cons_derived4` `:2706, 2709` | $(1-\phi_0)$; в скобке при $\partial_t p$ — $-\phi$ вместо $-(\rho c_p)_s T\phi c_r - \phi(1 + pc_r)$ |
| P27, P28 | определения после вывода `:2718-2728` | $(1-\phi_0)$; $\Qad = \phi\,T\sum_\alpha S_\alpha\alpha_\alpha\,\partial_t p$ |
| P29 | `eq:Qad_muJT` `:2771-2780` | без строки с $c_r$ |
| P30 | после `eq:Qad_muJT` | новый `\paragraph{Проверка: обратимое адиабатическое сжатие.}` (раздел 2.2 плана) |

Ключевые новые тексты (полностью — в `PAIRS`):
```latex
  \item \textbf{Сжимаемость порового пространства.}
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
        постоянна, $\phi = \phi_0$.
```
Формулировка «отнесены к начальному объёму … изменение размеров не учитывается» (аудит 1), а не «размеры неизменны»: при неизменном объёме элемента и постоянной массе скелета рост пор означал бы сжатие зёрен — модель Black Oil механизм деформации не описывает, она лишь пренебрегает изменением геометрии.
```latex
\begin{equation}\label{eq:rock_dt}
  \pdt{}\!\left[
    (1-\phi_0)\,(\rho c_p)_s\,T-\phi\,p
  \right] + p\,\pdt{\phi}
  = (1-\phi_0)\,(\rho c_p)_s\,\pdt{T}
    - \phi\,\pdt{p}.
\end{equation}
```

Не трогать: `:591-594` ($C_p$ гидродинамики — там $c_r$ уже стоит в общем виде, «при $c_r = 0$» относится к условию «тогда и только тогда»), приложение `app:expansion` (`:2793` и далее — уже с $c_r \ne 0$).

**Проверка после шага:**
- Сборка (из `<W>\numerical_solver\doc`): `1..2 | ForEach-Object { pdflatex -interaction=nonstopmode problem_statement.tex | Out-Null }`; `Select-String -Path problem_statement.log -Pattern "^!|Undefined control|undefined references"` — пусто. `.aux`, `.log`, `.pdf` не коммитятся.
- `& $PY -m pytest tests/test_eq_references.py -q` — зелёный (метки не удалены).
- Регресс: `--collect-only -q` (шаг меняет только документ) — N0.

**Подводные камни:** окончания строк — CRLF в рабочей копии (`core.autocrlf = true`); проба их сохраняет. Edit-ами — то же автоматически.

**Зависимости:** требует шаг 0; блокирует шаги 2–3 (`eq:porosity`).

**Оценка:** ~120 строк `.tex`, ~15 мин.

### Шаг 2: тесты — новый `tests/test_energy_porosity.py` (красные)

**Цель:** зафиксировать вариант B тестами до кода.

**Файлы:** `numerical_solver/tests/test_energy_porosity.py` (новый).

**Что сделать:** файл — дословно `vault/issues/debt-057/probes/test_energy_porosity_draft.py` (проверен на копии пакета). Применить:
```powershell
& $PY ..\vault\issues\debt-057\probes\apply_code.py --inplace newtest
```
(пишет файл с CRLF; путь к примеру 18 в файле — `Path(__file__).parent.parent / "examples"`, верный для `tests/`). Содержание — раздел 5.

**Проверка после шага:**
- `& $PY -m pytest tests/test_energy_porosity.py -q` — **9 failed** (ожидаемо): 8 — `AttributeError`/`TypeError` (нет `porosity`, нет `p_ref`, нет `p=`), `test_mdot_matches_hydro_gas_release` — `AssertionError: 6.70e-04` (порог 1e-7).
- `& $PY -m pytest tests/test_eq_references.py -q` — зелёный (метки `eq:porosity`, `eq:main_rhocpeff`, `eq:lambda_eff`, `eq:Qad_disc`, `eq:mdot_disc`, `eq:rock_dt` объявлены после шага 1).
- Регресс: `--collect-only -q` — N0 + 9.

**Зависимости:** требует шаг 1; блокирует шаг 3.

**Оценка:** ~240 строк, 5 мин.

### Шаг 3: код — `porosity(p)` в энергии, фабрика передаёт $p_0$, эталон сверки матрицы

**Цель:** энергия считает флюид с $\varphi(p^{n+1})$, скелет и $\lambda_{eff}$ — с $\varphi_0$; эталон сверки — так же.

**Файлы:**
- `numerical_solver/gpn_multiphase_solver/energy/tridiag.py`
- `numerical_solver/gpn_multiphase_solver/factory.py`
- `numerical_solver/gpn_multiphase_solver/io/config.py` (комментарий)
- `numerical_solver/gpn_multiphase_solver/energy/balance.py` (комментарий)
- `numerical_solver/examples/verify_balance_vs_solver.py` (вызов повторяет `solve`)
- `numerical_solver/tests/test_energy_matrix_examples.py` (эталон)

**Контекст:** код и эталон меняются **одним шагом**: эталон с $\varphi(p)$ при коде с $\varphi_0$ (или наоборот) роняет `test_matrix_matches_reference[18_prototype_input]`.

**Что сделать:** блоки E1–E10 и R1–R8 ниже — те же, что пары `CODE` и `TESTS` в `apply_code.py`. Применить пробой:
```powershell
& $PY ..\vault\issues\debt-057\probes\apply_code.py --inplace code
```
или Edit-ами по блокам.

**E1 — конструктор** (`tridiag.py:67-70`)

До:
```python
    def __init__(self, grid: Grid, pvt: FullPVT, rock: RockConfig):
        self._grid = grid
        self._pvt = pvt
        self._rock = rock
```
После:
```python
    def __init__(self, grid: Grid, pvt: FullPVT, rock: RockConfig,
                 p_ref: float | None = None):
        self._grid = grid
        self._pvt = pvt
        self._rock = rock
        # Опорное давление закона пористости φ(p) = φ0·exp(c_r·(p − p_ref))
        # (eq:porosity): rock.porosity задана при p_ref. Фабрика передаёт
        # начальное p0 — то же, что получает порода прототипа (factory.py,
        # CompressibleRock): энергия и гидродинамика считают один поровый
        # объём (DEBT-057). При c_r = 0 пористость от p_ref не зависит.
        # rock = None допустим: тесты сверки матрицы создают решатель только
        # ради методов, которым порода не нужна.
        if rock is not None and rock.compressibility != 0.0 and p_ref is None:
            raise ValueError(
                f"TridiagEnergySolver: rock.compressibility = {rock.compressibility} "
                "≠ 0 — нужно p_ref, давление, при котором задана rock.porosity "
                "(фабрика передаёт initial_conditions.p0)")
        self._p_ref = p_ref
```

**E6 — `solve` передаёт давление в `compute_degassing`** (`tridiag.py:135-136`)

До:
```python
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext)
```
После:
```python
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext,
            p=p)
```

**E2 — метод `porosity` и пористость в `compute_cell_properties`** (`tridiag.py:205-216`)

До:
```python
    # ──────────────────────────────────────────────────────
    # Подшаг 1–2: PVT + эффективные свойства в ячейках
    # ──────────────────────────────────────────────────────

    def compute_cell_properties(self, p, Sg, Rs, So, T_old):
        """Тепловые PVT и вспомогательные величины в ячейках.

        Ур. (eq:main_rhocpeff), (eq:lambda_eff).
        """
        pvt = self._pvt
        rock = self._rock
        phi = rock.porosity
```
После:
```python
    # ──────────────────────────────────────────────────────
    # Пористость φ(p) — поровый объём гидродинамики (DEBT-057)
    # ──────────────────────────────────────────────────────

    def porosity(self, p):
        """Пористость φ(p) = φ0·exp(c_r·(p − p_ref)) в ячейках. Ур. (eq:porosity)."""
        rock = self._rock
        # c_r = 0: скаляр rock.porosity — те же операции, что до DEBT-057,
        # поэтому расчёты с c_r = 0 побитово прежние; p не нужно.
        if rock.compressibility == 0.0:
            return rock.porosity
        if p is None:
            raise ValueError(
                "TridiagEnergySolver.porosity: при rock.compressibility ≠ 0 "
                "нужно давление p в ячейках")
        # Та же формула, что у CompressibleRock прототипа (там в барах):
        # запасы компонентов гидродинамики — V·φ(p)·S_α/B_α
        return rock.porosity * np.exp(rock.compressibility * (p - self._p_ref))

    # ──────────────────────────────────────────────────────
    # Подшаг 1–2: PVT + эффективные свойства в ячейках
    # ──────────────────────────────────────────────────────

    def compute_cell_properties(self, p, Sg, Rs, So, T_old):
        """Тепловые PVT и вспомогательные величины в ячейках.

        Ур. (eq:main_rhocpeff), (eq:lambda_eff).
        """
        pvt = self._pvt
        rock = self._rock
        # Флюид — поровый объём φ(p^{n+1}), как в запасах гидродинамики;
        # скелет — (1 − φ0)(ρc_p)_s: его масса в ячейке постоянна, и от p
        # теплоёмкость скелета не зависит (DEBT-057, eq:rock_dt).
        # λ_eff — эмпирическое замыкание при φ0 (eq:lambda_eff).
        phi0 = rock.porosity
        phi = self.porosity(p)
```

**E3 — $(\rho c_p)_{eff}$ и $\lambda_{eff}$** (`tridiag.py:228-233`)

До:
```python
        rho_cp_eff = ((1 - phi) * rock.rho_cp_solid
                      + phi * (So * rho_o * c_p_o + Sg * rho_g * c_p_g))

        # Эффективная теплопроводность (eq:lambda_eff), Вт/(м·К)
        lambda_eff = ((1 - phi) * rock.lambda_solid
                      + phi * (So * rock.lambda_oil + Sg * rock.lambda_gas))
```
После:
```python
        rho_cp_eff = ((1 - phi0) * rock.rho_cp_solid
                      + phi * (So * rho_o * c_p_o + Sg * rho_g * c_p_g))

        # Эффективная теплопроводность (eq:lambda_eff), Вт/(м·К)
        lambda_eff = ((1 - phi0) * rock.lambda_solid
                      + phi0 * (So * rock.lambda_oil + Sg * rock.lambda_gas))
```
Порядок операций во флюидной части — как в пробе B: отпечаток `fd040715fc926897` побитово.

**E4 — $Q_{ad}$** (`tridiag.py:444-450`)

До:
```python
    # Подшаг 5b: адиабатический эффект (eq:Qad_disc — форма при c_r = 0, DEBT-057)
    # ──────────────────────────────────────────────────────

    def compute_adiabatic(self, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                            mu_JT_o, mu_JT_g, p, p_old, dt):
        """Q_ad[j] = φ · Σ_α S_α · (1 + ρ_α·cp_α·μ_JT_α) · dp/dt, Вт/м³."""
        phi = self._rock.porosity
```
После:
```python
    # Подшаг 5b: адиабатический эффект (eq:Qad_disc; φ = φ(p^{n+1}), DEBT-057)
    # ──────────────────────────────────────────────────────

    def compute_adiabatic(self, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                            mu_JT_o, mu_JT_g, p, p_old, dt):
        """Q_ad[j] = φ(p)·Σ_α S_α·(1 + ρ_α·cp_α·μ_JT_α)·dp/dt, Вт/м³. Ур. (eq:Qad_disc)."""
        # Сжимаемость породы — только через φ(p): членов c_r·(p + (ρc_p)_s·T)
        # в Q_ad нет (eq:rock_dt, DEBT-057)
        phi = self.porosity(p)
```

**E5 — $\dot m$** (`tridiag.py:461`, `:486-488`)

До:
```python
    def compute_degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext):
```
После:
```python
    def compute_degassing(self, So, Sg, Rs, Rs_old, Bo, G_o, L, dt, N, Rs_ext,
                          p=None):
```
До:
```python
        Rs_ext — состав притока с контура (eq:bc_Sg_ext): R_s|_ext = R_s^0.
        """
        phi = self._rock.porosity
```
После:
```python
        Rs_ext — состав притока с контура (eq:bc_Sg_ext): R_s|_ext = R_s^0.
        """
        # Запас нефти во временной части — с пористостью φ(p^{n+1}) (eq:porosity),
        # как в запасах гидродинамики (DEBT-057); при c_r = 0 p не нужно.
        phi = self.porosity(p)
```
Докстринг `compute_degassing` (абзац «Форма воспроизводит дискретное правило Лейбница точно») не трогать — это DEBT-066.

**E7 — фабрика** (`factory.py:70`)

До:
```python
        energy = TridiagEnergySolver(grid, pvt, config.rock)
```
После:
```python
        # p_ref = p0: пористость конфига задана при начальном давлении — так же
        # фабрика строит породу прототипа (_create_prototype_hydro): поровый
        # объём энергии и гидродинамики один (DEBT-057)
        energy = TridiagEnergySolver(grid, pvt, config.rock,
                                     p_ref=config.initial_conditions.p0)
```

**E8 — комментарий конфига** (`io/config.py:54`)

До: `    # Энергия берёт постоянную porosity (energy/tridiag.py) — при c_r ≠ 0 см. DEBT-057.`

После:
```python
    # Энергия (energy/tridiag.py, DEBT-057): флюид — φ(p) по тому же закону,
    # скелет и λ_eff — porosity при p0 (масса скелета в ячейке постоянна).
```

**E9 — комментарий баланса** (`energy/balance.py:235`)

До: `        # Q_ad = φ Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt, Вт/м³ (eq:Qad_disc, c_r = 0).`

После: `        # Q_ad = φ(p) Σ_α S_α (1 + ρ_α cp_α μ_JT,α) dp/dt, Вт/м³ (eq:Qad_disc, DEBT-057).`

**E10 — инструмент сверки баланса** (`examples/verify_balance_vs_solver.py:87-88`; он повторяет `solve`, иначе при $c_r \ne 0$ дал бы ложную невязку)

До:
```python
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext)
```
После:
```python
        # p — как в solve: пористость временной части ṁ φ(p) (DEBT-057)
        Q_deg = self.compute_degassing(
            So, Sg, Rs, Rs_old, props['Bo'], G_o, props['L'], dt, N, Rs_ext,
            p=p)
```

**R1–R8 — эталон сверки матрицы** (`tests/test_energy_matrix_examples.py`). Эталон следует документу, а не коду (шапка файла): своя `_ref_porosity` по `eq:porosity`.

R1+R3 (`:133-143`). До:
```python
def _ref_cell_properties(pvt, rock, p, Sg, Rs, T_old):
    """Эффективные свойства в ячейках. eq:main_rhocpeff, eq:lambda_eff.

    (ρcp)_eff = (1-φ)·(ρcp)_s + φ·Σ_α S_α·ρ_α·c_pα   [Дж/(м³·К)]
    λ_eff     = (1-φ)·λ_s     + φ·Σ_α S_α·λ_α        [Вт/(м·К)]

    So берётся как 1 - Sg, как в ядре: тождество So + Sg = 1 обязано
    выполняться точно.
    """
    So = 1.0 - Sg
    phi = rock.porosity
```
После:
```python
def _ref_porosity(rock, p, p_ref):
    """Пористость в ячейках. eq:porosity.

    φ(p) = φ0·exp(c_r·(p − p0)), φ0 = rock.porosity задана при начальном
    давлении p0 = p_ref — так же фабрика строит породу прототипа (DEBT-057).
    При c_r = 0 — φ0 в каждой ячейке, p_ref не нужен.
    """
    if rock.compressibility == 0.0:
        return np.full(np.shape(p), rock.porosity)
    return rock.porosity * np.exp(rock.compressibility * (p - p_ref))


def _ref_cell_properties(pvt, rock, phi, p, Sg, Rs, T_old):
    """Эффективные свойства в ячейках. eq:main_rhocpeff, eq:lambda_eff.

    (ρcp)_eff = (1-φ0)·(ρcp)_s + φ(p)·Σ_α S_α·ρ_α·c_pα   [Дж/(м³·К)]
    λ_eff     = (1-φ0)·λ_s     + φ0·Σ_α S_α·λ_α          [Вт/(м·К)]

    φ0 = rock.porosity — скелет (масса в ячейке постоянна) и замыкание λ_eff;
    φ = φ(p^{n+1}) (_ref_porosity) — флюид (DEBT-057).

    So берётся как 1 - Sg, как в ядре: тождество So + Sg = 1 обязано
    выполняться точно.
    """
    So = 1.0 - Sg
    phi0 = rock.porosity
```
R2 (`:158-163`). До:
```python
    props['rho_cp_eff'] = ((1.0 - phi) * rock.rho_cp_solid
                           + phi * (So * props['rho_o'] * props['c_p_o']
                                    + Sg * props['rho_g'] * props['c_p_g']))
    props['lambda_eff'] = ((1.0 - phi) * rock.lambda_solid
                           + phi * (So * rock.lambda_oil
                                    + Sg * rock.lambda_gas))
```
После:
```python
    props['rho_cp_eff'] = ((1.0 - phi0) * rock.rho_cp_solid
                           + phi * (So * props['rho_o'] * props['c_p_o']
                                    + Sg * props['rho_g'] * props['c_p_g']))
    props['lambda_eff'] = ((1.0 - phi0) * rock.lambda_solid
                           + phi0 * (So * rock.lambda_oil
                                     + Sg * rock.lambda_gas))
```
R4 (`:557-562`, `:569-572`). До:
```python
def _ref_adiabatic(rock, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                   mu_JT_o, mu_JT_g, p, p_old, dt):
    """Адиабатический эффект. eq:Qad_disc (при c_r = 0).

    ФОРМА ДОКУМЕНТА — единица ВНЕ суммы:
```
После:
```python
def _ref_adiabatic(phi, So, Sg, rho_o, rho_g, c_p_o, c_p_g,
                   mu_JT_o, mu_JT_g, p, p_old, dt):
    """Адиабатический эффект. eq:Qad_disc.

    ФОРМА ДОКУМЕНТА — единица ВНЕ суммы, φ = φ(p^{n+1}) (DEBT-057):
```
До:
```python
    dp_dt = (p - p_old) / dt
    return rock.porosity * (1.0
                            + So * rho_o * c_p_o * mu_JT_o
                            + Sg * rho_g * c_p_g * mu_JT_g) * dp_dt
```
После:
```python
    dp_dt = (p - p_old) / dt
    return phi * (1.0
                  + So * rho_o * c_p_o * mu_JT_o
                  + Sg * rho_g * c_p_g * mu_JT_g) * dp_dt
```
R5 (`:575`, `:617-619`). `def _ref_degassing(grid, pvt, rock, So, ...` → `def _ref_degassing(grid, pvt, phi, So, ...`; строку `    phi = rock.porosity` перед `    V = grid.volumes` заменить комментарием:
```python
    # phi — φ(p^{n+1}) (_ref_porosity): запас нефти временной части — с тем же
    # поровым объёмом, что у гидродинамики (DEBT-057)
```
R6 (`:758-759`, конец докстринга и `:776`). Сигнатура: `T_ref=0.0, with_scale=False):` → `T_ref=0.0, with_scale=False, p_ref=None):`. В конец докстринга — абзац:
```
    p_ref — давление, при котором задана rock.porosity (начальное p0);
    нужно при c_r ≠ 0 (DEBT-057).
```
Вызов свойств. До:
```python
    props = _ref_cell_properties(pvt, rock, st.p, st.Sg, st.Rs, state_prev.T)
```
После:
```python
    # Пористость φ(p^{n+1}): флюид в (ρc_p)_eff, Q_ad и временной части ṁ
    phi = _ref_porosity(rock, st.p, p_ref)
    props = _ref_cell_properties(pvt, rock, phi, st.p, st.Sg, st.Rs, state_prev.T)
```
R7 (`:797`, `:803`): `_ref_adiabatic(rock, props['So'], ...` → `_ref_adiabatic(phi, props['So'], ...`; `_ref_degassing(grid, pvt, rock, props['So'], ...` → `_ref_degassing(grid, pvt, phi, props['So'], ...`.

R8 (`:854-856`, `test_matrix_matches_reference`). До:
```python
            hydro_result, state_prev, dt, bc, T_ref=T_ref, with_scale=True)
```
После:
```python
            hydro_result, state_prev, dt, bc, T_ref=T_ref, with_scale=True,
            p_ref=cfg.initial_conditions.p0)
```

**Проверка после шага:**
- `& $PY -m pytest tests/test_energy_porosity.py -q` — **9 passed**.
- Регресс: **быстрый** — `& $PY -m pytest tests/ -m "not slow" -q` — N0f + 9 passed.
- Выборочно slow (сверка матрицы и тесты примера 18 ловят ошибку шага только они; полный прогон — в шаге 6):
  ```powershell
  & $PY -m pytest "tests/test_energy_matrix_examples.py::test_matrix_matches_reference[18_prototype_input]" "tests/test_energy_matrix_examples.py::test_matrix_matches_reference[03_standing_corey]" -q
  & $PY -m pytest tests/test_examples.py -k TestPrototypeInput -q
  ```
  Ожидание: всё зелёное; `test_wellbore_cools` проходит со старыми числами (−0.6431 против −0.64186 — внутри допуска 2e-3), числа обновляет шаг 4.
- Отпечаток: `& $PY ..\vault\issues\debt-057\probes\t_fingerprint.py B` — `пакет = <W>\...`, `fd040715fc926897`; $T(r_w)-T_0$ на записях 1 / 11 / 20 / 22: −0.53336 / −0.62847 / −0.64186 / −0.48867 К.

**Подводные камни:**
- `compute_degassing` без `p` при $c_r \ne 0$ — `ValueError` (тест `test_degassing_requires_p_when_compressible`), а не молчаливая $\varphi_0$. Все вызовы вне `solve` — в тестах с $c_r = 0$ и в `verify_balance_vs_solver.py` (E10).
- `rock is None` в конструкторе — не трогать породу (вызовы `TridiagEnergySolver(grid, None, None)` в `test_energy_matrix_examples.py:360, 552`).
- `test_example_scripts.py::test_no_private_solver_access` проверяет скрипты `examples/`: E10 приватного доступа не добавляет (`self` — сам решатель в подменённом методе, как и раньше).

**Зависимости:** требует шаги 1–2; блокирует шаг 4.

**Оценка:** ~90 строк, ~20 мин.

### Шаг 4: числа примера 18 — тест, README, сводный README; снимок «после»

**Цель:** тексты и тесты примера 18 — по новому расчёту; доказать, что остальные 22 примера не изменились.

**Файлы:**
- `numerical_solver/tests/test_examples.py` (`TestPrototypeInput.test_wellbore_cools`, `:3245-3260` на `eb904eb`; искать `def test_wellbore_cools(self, results):` внутри `class TestPrototypeInput` — тест с тем же именем, параметризованный `name`, к примеру 18 не относится)
- `numerical_solver/examples/18_prototype_input/README.md`
- `numerical_solver/examples/README.md` (таблица невязки баланса энергии, строка `| **18** |`, `:632` на `eb904eb`)

**Что сделать:**
1. Расчёт примера 18 штатно (~40 с):
   ```powershell
   & $PY examples\18_prototype_input\main.py
   ```
   Печать — источник чисел. Сверить путь пакета в печати (`PYTHONPATH` стоит, раздел 3).
2. `test_wellbore_cools` — числа по новому расчёту (ожидаемые — из пробы B):
   - докстринг: «от −0.6431 К (запись 20, 15 сут + 60 с) до −0.1994 К (запись 5, 5 сут); на 30 сут −0.4892 К» → «от −0.6419 К (запись 20, 15 сут + 60 с) до −0.1992 К (запись 5, 5 сут); на 30 сут −0.4887 К»; балансовые числа докстринга (−1.19e10, −8.9e8, +4.6e8) не меняются;
   - `assert dT.min() == pytest.approx(-0.6431, abs=2e-3)` → `-0.6419`; `assert dT[-1] == pytest.approx(-0.4892, abs=2e-3)` → `-0.4887`. Допуск не менять.
3. README 18, таблица «Ожидаемое поведение», столбец $T(r_w) - T_0$ (ожидаемое по пробе — сверить с печатью):

   | момент | было | стало |
   |---|---|---|
   | 1 мин | −0.534 | −0.533 |
   | 1 сут | −0.263 | −0.263 |
   | 5 сут | −0.199 | −0.199 |
   | 5 сут + 1 мин | −0.630 | −0.628 |
   | 6 сут | −0.481 | −0.480 |
   | 15 сут | −0.368 | −0.367 |
   | 15 сут + 1 мин | −0.643 | −0.642 |
   | 16 сут | −0.598 | −0.597 |
   | 30 сут | −0.489 | −0.489 |

   Остальные столбцы (гидродинамика) не меняются.
4. README 18, абзац «Баланс энергии за 30 сут» (`:163-168`): конвекция $+6.6\cdot10^{7}$ → $+6.5\cdot10^{7}$ (6.5481e7), невязка $4.9\cdot10^{-15}$ → $5.5\cdot10^{-15}$ (5.53e-15); $\Delta E$, адиабатика, теплота выделения газа, ДТ, теплопроводность, баланс массы, проверка $R_s$ — прежние (сверить с печатью).
5. README 18, раздел «Описание» — после второго абзаца (кончается «проверка — баланс энергии.») новый абзац:
   ```markdown
   Пористость книги задана при $p_0$, сжимаемость породы $c_r = 4.5\cdot10^{-5}$
   1/бар. Поровый объём $\varphi(p) = \varphi_0 e^{c_r(p - p_0)}$ один в
   гидродинамике и в уравнении энергии: у флюида — $\varphi(p)$, у скелета —
   $\varphi_0$ (его масса в ячейке постоянна).
   ```
6. `examples/README.md`, строка `| **18** |` таблицы баланса энергии (`:632`): невязка $4.9\cdot10^{-15}$ → $5.5\cdot10^{-15}$; $E_{конд}$ $+5.02\cdot10^{6}$ — прежнее. Строка 18 таблицы «Вход прототипа» (`:198`, $T(r_w)$ = 349.511 К) — прежняя (350 − 0.48867 = 349.51133).
7. Снимок «после» и сравнение (~12 мин; та же проба FEAT-030, что в шаге 0.5):
   ```powershell
   & $PY -X utf8 ..\vault\issues\feat-030\probes\snapshot_examples.py snap --tree . --out ..\vault\issues\debt-057\probes\out\snap_after.json
   & $PY -X utf8 ..\vault\issues\feat-030\probes\snapshot_examples.py compare ..\vault\issues\debt-057\probes\out\snap_before.json ..\vault\issues\debt-057\probes\out\snap_after.json
   ```
   Ожидание: 22 примера совпадают побайтно (печать и все файлы `output/`). У 18 — отличия только в печати строк с $T$ и балансом энергии и в файлах с температурой и энергией (`temperature_profiles.png`, `wellbore_dynamics.png`, `energy_balance.png`, CSV истории с $T$); файлы прототипа с временем выполнения (`TIME_FILES` пробы) — не в счёт. Отличие у другого примера — стоп, разбор (ошибка в ветке $c_r = 0$).

**Проверка после шага:**
- `& $PY -m pytest tests/test_examples.py -k TestPrototypeInput -q` — зелёный.
- Регресс: быстрый.

**Зависимости:** требует шаг 3; блокирует шаг 6.

**Оценка:** ~25 строк текстов, ~20 мин (+12 мин снимка).

### Шаг 5: vault — физика в заметку, словарь и заметки решений

**Цель:** знание о членах $c_r$ и о пористости энергии — в vault; заметки не противоречат коду.

**Файлы:**
1. **Новая заметка** `vault/knowledge/science/сжимаемость породы входит в уравнение энергии только через поровый объём φ(p) — члены c_r в Q_ad были артефактом вывода.md`. Формат — как соседние в `knowledge/science/` (frontmatter `tags`, `date`, `source`). Содержание: раздел 2.2 плана (оба лишних члена и их происхождение в `eq:rock_dt`, работа над стенками пор, масса скелета, проверка энтропией, $\lambda_{eff}$ при $\varphi_0$); замер раздела 2.3 (таблица вариантов, 1.29 мК против погрешности шага); ссылки — `eq:porosity`, `eq:rock_dt`, `eq:Qad_muJT`, [[DEBT-057]], [[DEBT-066]], [[VAL-005]].
2. `vault/knowledge/decisions/словарь-код-физика.md`:
   - `:89` (`component_inventories`): $\phi$ → $\phi(p)$;
   - `:235`, `:242`, `:255-256` (невязки): `V[j]·φ·(... - ...)` → `V[j]·(φ(p)·... − φ(p_prev)·...)`;
   - `:298` (`rho_cp_eff`): в столбце смысла — «скелет с (1−φ0), флюид с φ(p)»;
   - `:341`, `:344` (раздел 5.6): `Q_ad[j] = φ(p[j]) · Σ_α ...`; вместо «Это форма при $c_r = 0$ … см. DEBT-057» — «$\varphi = \varphi(p^{n+1})$ (`TridiagEnergySolver.porosity`, `eq:porosity`). Членов $c_r\,(p + (\rho c_p)_s T)$ нет: они были артефактом вывода (`eq:rock_dt`, DEBT-057)»;
   - `:350` (раздел 5.7): `V[j]·φ·(1 − Sg[j])/Bo[j]` → `V[j]·φ(p[j])·(1 − Sg[j])/Bo[j]`;
   - раздел 9 (`:444`): `rock.porosity` — «φ0 = φ(p0)»; новые строки `rock.compressibility` | $c_r$ | 1/Па и `TridiagEnergySolver.porosity(p)` | $\varphi(p)$, `eq:porosity` | —.
3. `vault/knowledge/decisions/hydro-prototype-анализ.md`: `:71` «В нашей постановке c_r = 0, но прототип поддерживает c_r ≠ 0.» → «Постановка — φ(p) по `eq:porosity` (DEBT-057); энергия берёт тот же закон (`TridiagEnergySolver.porosity`, фабрика передаёт тот же p0).»; `:211` строка таблицы «CompressibleRock | **нет** — у нас c_r = 0, простой скаляр φ» → «CompressibleRock | тот же закон в энергии — `TridiagEnergySolver.porosity(p)` (DEBT-057)».
4. `vault/knowledge/decisions/json-config-schema.md:50` (`compressibility`): в конец описания — «; энергия: флюид — $\varphi(p)$, скелет и $\lambda_{eff}$ — `porosity` (DEBT-057)».
5. `vault/knowledge/decisions/модули-energy-tridiag.md` (порядок подшагов `solve`): `:71` — `compute_cell_properties` берёт $\varphi_0$ у скелета и в `lambda_eff`, `porosity(p)` у флюида; `:75` — «`compute_degassing` (с `bc.Rs_ext` и `p=p` — пористость временной части, DEBT-057)»; в описание конструктора (если его нет — одной строкой рядом с перечнем подшагов) — `p_ref` (фабрика передаёт `initial_conditions.p0`, при $c_r \ne 0$ обязателен).
6. `vault/knowledge/decisions/P6-тепловые-свойства.md:36` ($\lambda_{eff}$): после формулы — «φ здесь — `rock.porosity` = $\varphi_0$ (пористость при $p_0$); при $c_r \ne 0$ замыкание остаётся на $\varphi_0$ (DEBT-057)».
7. `vault/00-home/index.md` — ссылка на новую заметку в списке заметок физики (после строки `[[после останова из развитой газовой зоны забой прогревается теплопроводностью, а не притоком тёплой нефти]]`, ~`:43`), одной строкой: суть и числа (1.29 мК на примере 18; проверка энтропией).

Реестр, issue и итоговый комментарий — по контракту `/implement`.

**Проверка:** `--collect-only -q` (код не меняется).

**Зависимости:** требует шаг 4 (числа).

**Оценка:** ~60 строк, 20 мин.

### Шаг 6: итог — полный прогон, уборка

**Цель:** всё зелёное, выходы проб убраны.

**Что сделать:**
1. Полный прогон: `& $PY -m pytest tests/ -q` — N0 + 9 passed (сверка матрицы всех 23 примеров с новым эталоном, `test_energy_balance_all_examples` — невязка 18 ≤ 1e-12).
2. Удалить выходы проб: `probes/check`, `probes/tex`, `probes/audit_tree`, `probes/out` (сначала выйти из этих каталогов — заметка «Worktree remove и cwd»).
3. `git status --short` — изменены только файлы шагов 1–5 и новый `tests/test_energy_porosity.py`; `.aux/.log/.pdf` не в индексе.

**Оценка:** ~12 мин машинного времени.

## 5. Тестовая стратегия

Новый файл `numerical_solver/tests/test_energy_porosity.py` (текст — `vault/issues/debt-057/probes/test_energy_porosity_draft.py`). Параметры: $N = 5$, $\varphi_0 = 0.2$, $p_0$ = 20 МПа, $c_r$ = 4.5e-10 1/Па, $p$ = 10…20 МПа.

| Тест | Сценарий | Ожидание | Ловит |
|---|---|---|---|
| `TestPorosityLaw::test_matches_prototype_rock` | `porosity(p)` против `CompressibleRock(φ0, p0[бар], c_r[1/бар]).porosity(p[бар])` | rtol 1e-14 (замер 2.2e-16) | знак, опорное давление, единицы $c_r$ |
| `TestPorosityLaw::test_zero_compressibility_returns_phi0` | $c_r = 0$, `p_ref=None` | скаляр, `== 0.2` | ветка $c_r = 0$ стала массивом — угроза побитовости 22 примеров |
| `TestPorosityLaw::test_compressible_requires_p_ref` | $c_r \ne 0$, `p_ref=None` | `ValueError` с «p_ref» | молчаливая опора не $p_0$ |
| `TestEnergyTerms::test_rho_cp_eff_fluid_phi_p_skeleton_phi0` | свойства при $S_g$ = 0…0.1 | $(\rho c_p)_{eff} = (1-\varphi_0)(\rho c_p)_s + \varphi(p)\sum$ (rtol 1e-14); $\lambda_{eff}$ = как при $c_r = 0$ побитово | $\varphi(p)$ у скелета или в $\lambda_{eff}$ |
| `TestEnergyTerms::test_adiabatic_scales_with_phi_p` | $p^n = p^{n+1} + 1$ МПа | $Q_{ad} = Q_{ad}^{c_r=0}\varphi(p)/\varphi_0$ | $\varphi_0$, $\varphi(p^n)$, член $c_r$ |
| `TestEnergyTerms::test_degassing_time_part_scales_with_phi_p` | $G^o = 0$, $\Delta R_s = -5$ | $Q_{deg} = Q_{deg}^{c_r=0}\varphi(p)/\varphi_0$ | $\varphi_0$ во временной части $\dot m$ |
| `TestEnergyTerms::test_degassing_requires_p_when_compressible` | `compute_degassing` без `p`, $c_r \ne 0$ | `ValueError` с «давление» | молчаливая $\varphi_0$ при забытом `p` |
| `TestHydroConsistency::test_energy_pore_volume_equals_prototype` | фабрика на конфиге 18 | $V\varphi(p)$ энергии = `pore_volume_m3` прототипа (rtol 1e-14) | фабрика не передала $p_0$; разные объёмы ячеек |
| `TestHydroConsistency::test_mdot_matches_hydro_gas_release` | конфиг 18, первые 2 интервала (~1 с) | $|(\dot m - \text{гидр.} - \text{остаток})/\text{гидр.}| < 10^{-7}$ (замер −9.5e-10; с $\varphi_0$ — 6.7e-4) | $\varphi_0$ в $\dot m$, разная пористость блоков |

Существующие тесты, покрывающие изменённый код (все остаются зелёными):
- `tests/test_energy.py` — 48 тестов решателя энергии при $c_r = 0$ (на копии пакета — зелёные);
- `tests/test_energy_matrix_examples.py::test_matrix_matches_reference` (slow, 23 примера) — эталон переписан в шаге 3;
- `tests/test_examples.py` — `TestPrototypeInput` (пример 18), `test_energy_balance_all_examples` (невязка ≤ 1e-12), `test_thermal_does_not_affect_hydro`;
- `tests/test_eq_references.py` — метки `.tex`;
- `tests/test_example_scripts.py` — имена и приватный доступ в `examples/*.py` (E10).

## 6. Подводные камни (чеклист)

| Пункт | Оценка | Комментарий |
|---|---|---|
| Все места `rock.porosity` найдены | ✅ | grep: `tridiag.py:216, 450, 488`; `factory.py:417` (прототип — без изменений); эталон `:143, 570, 617` |
| Вызовы `TridiagEnergySolver(...)` | ✅ | фабрика — `p_ref=p0`; 45 вызовов в тестах — $c_r = 0$, без изменений; `(grid, None, None)` — `rock is None` |
| Вызовы `compute_degassing(...)` | ✅ | `solve` — `p=p`; `verify_balance_vs_solver.py` — E10; `test_energy.py`, `test_val002.py` — $c_r = 0$ |
| Обратная совместимость API | ✅ | новые параметры необязательные, по умолчанию прежнее поведение при $c_r = 0$ |
| Состояние при ошибке | ✅ | `ValueError` в конструкторе — до создания объекта; в `porosity` — до вычислений |
| Циклы импорта | ✅ | новых импортов в пакете нет |
| Ссылки на метки | ⚠️ | новая `eq:porosity` — шаг 1 раньше шагов 2–3; `test_eq_references.py` |
| Конфиги | ✅ | имена полей не меняются; `compressibility` уже есть |
| Побитовость при $c_r = 0$ | ⚠️ | скаляр в `porosity`; снимок 23 примеров до/после (шаги 0.5, 4.7) |
| Окончания строк | ⚠️ | CRLF; пробы сохраняют, Edit — тоже |
| Параллельные задачи | ⚠️ | FEAT-032, DEBT-065 в worktree — раздел 2.5; при смене истории 18 в базе — пересчитать числа шага 4 |
| Производительность | ✅ | один `np.exp` на $N$ ячеек на вызов `solve`, только при $c_r \ne 0$ |
| Прототип | ✅ | не меняется — регрессия прототипа не нужна |
| Параллельные пути той же величины | ✅ | аналитика примеров 01, 02 (`main.py`, `check_slopes.py`, `spatial_convergence.py`) считает $(\rho c_p)_{eff}$ и асимптоту с `config.rock.porosity` — у их конфигов $c_r = 0$, $\varphi = \varphi_0$, расхождения нет; `diagnostics/` пористость не использует (аудит 1, grep) |
| Снимок примеров после FEAT-030 | ✅ | FEAT-030 влита, `main.py` есть у всех 23; снимок — её пробой (шаги 0.5, 4.7) |
| Длина строк | ✅ | блоки «После» и новый файл тестов — не длиннее 100 символов (аудит 1 сократил 4 докстринга) |

## 7. Критерии завершения

- [ ] Шаги 0–6 выполнены.
- [ ] Новые 9 тестов зелёные; полный прогон — N0 + 9 passed.
- [ ] Отпечаток $T$ примера 18 = `fd040715fc926897` (если база по энергии и истории 18 не ушла — шаг 0.4).
- [ ] Снимок: 22 примера побайтно как до; у 18 — только $T$ и энергия.
- [ ] `problem_statement.tex` собирается без ошибок; членов $c_r(p + (\rho c_p)_s T)$ в уравнении энергии нет; `eq:porosity` объявлена; «$\phi = \mathrm{const}$» не осталось.
- [ ] README 18, `examples/README.md`, `test_wellbore_cools` — числа по печати `main.py` 18.
- [ ] Vault: новая заметка `knowledge/science/`, словарь, `hydro-prototype-анализ`, `json-config-schema`, `index.md`.
- [ ] Выходы проб удалены, в git не попали.
- [ ] Issue #108 — комментарий с результатом (`/implement`).

## 8. Связь формула → код

| Формула (`problem_statement.tex`) | Код |
|---|---|
| `eq:porosity` — $\phi(p) = \phi_0 e^{c_r(p - p_0)}$ | `TridiagEnergySolver.porosity`; прототип — `CompressibleRock.porosity` (`radial_blackoil/rock.py`); эталон — `_ref_porosity` |
| `eq:main_rhocpeff` — $(1-\phi_0)(\rho c_p)_s + \phi(p)\sum S_\alpha\rho_\alpha c_{p,\alpha}$ | `compute_cell_properties`, `rho_cp_eff` |
| `eq:lambda_eff` — с $\phi_0$ | `compute_cell_properties`, `lambda_eff` |
| `eq:main_Qad_muJT`, `eq:Qad_disc` — $\phi(p^{n+1})[1 + \sum S_\alpha\rho_\alpha c_{p,\alpha}\mu_{JT,\alpha}]\,\Delta p/\Delta t$ | `compute_adiabatic` |
| `eq:mdot_disc` — временная часть с $\phi_j^{n+1}$ | `compute_degassing`, `mdot_time` |
| `eq:residual_oil`, `eq:residual_gas` — $\phi_j^{n+1}$, $\phi_j^n$ | прототип, `blackoil.py:213` (без изменений) |
| `eq:rock_dt` — без $c_r$ | вывод; в коде членов $c_r$ нет |

## 9. Проверка плана

- **Полнота.** Все места `rock.porosity` и все вызовы изменённых методов — в шагах 3 (раздел 6). Каждый шаг — с проверкой; зависимости линейные 0 → 1 → 2 → 3 → 4 → 5 → 6.
- **Корректность.** Все «было» найдены на `3f3df63` и повторно на `b487f80` (аудит 1) пробами `tex_apply.py` (33 пары, 36 замен) и `apply_code.py` (код — 11 пар, тесты — 11 пар); код плана на копии — 59 passed, отпечаток B; `.tex` собран; все правки сразу на копии дерева — сторожа меток и скриптов примеров зелёные (`audit_tree.py`, 408 passed).
- **Автономность.** Полные пути; команды с `$PY` и `PYTHONPATH`; базовый замер (1912 тестов на `eb904eb`); ожидаемые числа и отпечатки; источник точного текста правок — пробы в репозитории.

### Аудит 1 (2026-10-13, база `b487f80`) — найдено 7, исправлено 7

- 🟡 База ушла (FEAT-032, DEBT-065 влиты; FEAT-030 начата): базовый замер 1826 → 1879; строки `test_wellbore_cools` `:3075-3090` → `:3094-3109`, `examples/README.md` `:581/:193` → `:586/:196`; пары проб и отпечатки перепроверены — без изменений.
- 🟡 FEAT-030 удаляет `main.py` у 17 примеров — проба снимка DEBT-011 после её влития упадёт: добавлен запасной путь (проба FEAT-030) в шаги 0.5, 4.7 и строка в 2.5.
- 🟡 Формулировка допущения P3/P18 «размеры элемента неизменны» вместе с «масса скелета постоянна» означала бы сжатие зёрен; заменено на «величины отнесены к начальному объёму, изменение размеров не учитывается» (пробы и план).
- 🔵 Докстринг `compute_adiabatic` (E4) — 103 символа; три докстринга черновика тестов — 103–109: сокращены до ≤ 100.
- 🔵 Аналитика 01/02 с постоянной φ — в чеклист (расхождения нет: $c_r = 0$).
- 🔵 В шаг 5 добавлены `модули-energy-tridiag.md` и `P6-тепловые-свойства.md`.
- 🔵 Шаг 0 — проба `audit_tree.py` (все правки сразу, сторожа меток и скриптов примеров).

Физика перепроверена по коду и выводу: запасы прототипа старого и нового слоя — `pv(p_old)`, `pv(p_new)` (`blackoil.py:213-214, 259-260`); сокращение $p\,\partial\varphi/\partial t$ и вид `eq:energy_cons_derived4` после правок — по знакам; проверка энтропией сходится с $Q_{ad} = \varphi\alpha T\,\partial_t p$ ($\alpha T = 1 + \rho c_p\mu_{JT}$, `eq:alpha_via_muJT`); вывод $\dot m$ (`app:degas_rate`) держит $\varphi$ под производной — верен и при $\varphi(p)$.

## 10. Связанные заметки

- [[известные баги и технический долг]] — DEBT-057, DEBT-066
- [[VAL-005]] — пример 18; [[val-005 prototype-template-example]]
- [[DEBT-008]] — пористость конфига при $p_0$; [[debt-008 dead-config-fields]]
- [[BUG-012]] — форма $\dot m$; [[bug-012 адвективная форма конвекции и JT]]
- [[DEBT-043]], [[DEBT-039]], [[DEBT-016]] — балансы и сверка матрицы
- [[DEBT-063]] — та же природа: два блока шага на разных данных
- [[словарь-код-физика]], [[hydro-prototype-анализ]], [[json-config-schema]]
