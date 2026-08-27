# CONTEXT HANDOFF — Prototype 1.0.3

**Project:** «расчет температуры в пласте»  
**Subsystem:** собственный 1D radial black-oil solver, изотермическая гидродинамика нефть+газ  
**Current baseline:** **Prototype 1.0.3 — FINAL / CURRENT RELEASE**  
**Release date:** 2026-08-25  
**Validated numerical-core build:** `1.0.3-prebeta-final-regression-20260825a`  
**Input format version:** `1.0.3`  
**Release archive:** `Prototype_1.0.3.zip`  
**Release archive SHA256:** `73adc810cf1e634bf4636527ec12fbdaa2e640c02cb0dbd1379b50fbf7824647`

---

## 0. Инструкция для нового чата

Этот файл предназначен для переноса полного рабочего контекста в новый чат.

Если этот файл и `Prototype_1.0.3.zip` загружены в новый чат, считать содержимое архива **актуальным зафиксированным baseline**.  
Не восстанавливать код по памяти и не использовать более старые версии вместо архива.

Ключевое правило дальнейшей разработки:

> **Не изменять математическое/физическое ядро Prototype 1.0.3 без отдельного решения о новой версии и последующего regression.**

Если задача касается только интерфейса, документации или presentation/output layer, отдельно оценивать, затрагивает ли изменение численный результат.  
Если затрагивается residual, PVT, relperm, grid, well model, schedule semantics, nonlinear solve, Jacobian, timestep controller, material balance equations или state logic — это уже изменение расчетного ядра и требует новой версии/полного regression.

---

# 1. Номенклатура проекта

Зафиксированные названия:

- собственный Python black-oil solver — **Prototype / Прототип**;
- актуальный релиз — **Prototype 1.0.3**;
- синтетические PVT/relperm и связанные исходные данные — **Набор 1**;
- эталонный black-oil кейс CMG — **IMEX 1**;
- не использовать прежнее ошибочное название `GEM 1` для текущего black-oil benchmark.

CMG IMEX используется как **внешний benchmark**, но не считается абсолютной истиной.  
Цель — физически и численно корректный универсальный solver, а не tuning ради совпадения с CMG.

---

# 2. Назначение Prototype 1.0.3

Prototype 1.0.3 — исследовательский и инженерный Python solver для:

- 1D радиальной модели;
- вертикальной скважины;
- полной толщины пласта;
- двухфазной black-oil постановки:
  - oil;
  - free gas;
  - dissolved gas через `Rs`;
- без воды;
- изотермический расчет.

Основная цель текущего solver — выдавать гидродинамическое распределение и well response, пригодные как база для дальнейшей тепловой постановки.

---

# 3. Физическая постановка

## 3.1 Геометрия

- 1D radial finite-volume grid.
- Параметры:
  - `rw`;
  - `re`;
  - `N`;
  - `h`.
- Сетка строится автоматически через геометрическое распределение radial faces.
- Пользователь custom face coordinates сейчас не задает.
- Homogeneous isotropic permeability.
- Constant porosity reference with rock compressibility law.

Типовая/рекомендуемая конфигурация после convergence study:

- `N = 100`;
- `DTMAX = 60 min`.

---

## 3.2 Фазы и компоненты

Black-oil:

- oil phase;
- gas phase;
- oil component;
- gas component;
- растворенный газ учитывается через `Rs`.

Начальное состояние benchmark:
- обычно без свободного газа;
- oil может быть undersaturated;
- typical initial pressure около 200 bar;
- bubble-point regime зависит от конкретного PVT benchmark.

---

## 3.3 Rock

Используется rock pore-volume/compressibility law с параметрами типа:

- `phi_ref`;
- `p_ref`;
- `cr`.

В тестах есть независимая проверка pore volume geometry и rock law.

---

# 4. Численная схема

## 4.1 Дискретизация

- finite volume;
- radial geometry;
- fully implicit backward Euler;
- nonlinear Newton solve;
- state variables организованы через pressure + gas saturation / solution-gas logic;
- phase appearance/disappearance обрабатывается active-set логикой.

---

## 4.2 Linear solver

Production configuration:

- sparse matrix;
- sparse solver;
- CSC / sparse LU (`splu`-style implementation);
- dense/reference path сохранен для тестирования и сопоставления.

Sparse implementation была введена в Prototype 1.0.2 без изменения физики.

---

## 4.3 Jacobian

Есть:

- `grouped` Jacobian — production/reference default;
- reference mode для тестирования.

В Prototype 1.0.3 добавлена важная numerical-robustness correction:

### PVTO kink / max-Rs Jacobian protection

T05 convergence выявил failure около:
- gas-active cell;
- `Sg ~ 1e-7`;
- pressure около верхнего saturated PVTO knot.

Причина:
- finite-difference pressure perturbation могла пересечь kink / saturated-branch clamp.

Исправление:
- для gas-active cells pressure finite-difference step выбирается односторонне;
- perturbation остается на той же saturated-PVTO branch/segment;
- residual equations не менялись;
- PVT equations не менялись;
- active-set tolerances не менялись;
- timestep controller не менялся;
- well model не менялся.

После fix T05 полностью прошел.

---

# 5. Well model и controls

Поддерживаются:

- `BHP`;
- `OIL_RATE`;
- `OIL_RATE` с minimum-BHP constraint;
- автоматический `RATE -> BHP` switch.

## 5.1 Producer-only semantics

В Prototype 1.0.3 введена защита producer от reverse injection.

Для BHP-controlled producer:

- если локальное состояние не дает положительной добычи при target BHP;
- well flow ограничивается нулем;
- producer не превращается в injector;
- effective BHP может стать равным local pressure;
- когда reservoir pressure снова становится достаточным, скважина автоматически reopens.

Аналогичная producer-only protection действует для rate-control при активном minimum-BHP.

Это было выявлено тестом T08.

---

# 6. SCHEDULE semantics — КРИТИЧЕСКИ ВАЖНО

Каждая строка `SCHEDULE` одновременно является:

1. **точной integration boundary**;
2. **mandatory report time**;
3. **control definition для следующего интервала**.

То есть SCHEDULE — не просто список output dates.

## 6.1 Control change

При строке изменения control:

- состояние **в точной boundary time** сохраняется еще при предыдущем control;
- новый control начинает действовать на следующем timestep.

Пример T07:

- до day 5 — BHP 150 bar;
- состояние ровно `5.000000 d` относится к предыдущему control;
- после day 5 начинает действовать BHP 120 bar.

То же самое на day 15:
- boundary state еще относится к 120 bar;
- затем начинает действовать 100 bar.

---

## 6.2 Report times

Solver обрезает timestep так, чтобы точно попасть в каждую SCHEDULE boundary.

**Interpolation report states не используется.**

Повторенная строка с тем же control:
- добавляет mandatory integration/report boundary;
- не меняет физический control.

Это используется, например, для временного разрешения transient через:
- +10 s;
- +20 s;
- +30 s;
- +40 s;
- +50 s;
- +60 s.

---

# 7. PVT semantics

## 7.1 OIL_PVT — PVTO convention

Используется ECLIPSE/tNavigator-style PVTO:

- данные задаются fixed-`Rs` branches;
- первый / минимальный-pressure row каждого `Rs` branch = saturated point `Pb(Rs)`;
- более высокие давления в том же branch = undersaturated oil at fixed `Rs`;
- `Rs` повторяется в каждой строке branch.

Saturated functions строятся по branch-start points:

- `Rs_sat(P)`;
- `Bo_sat(P)`;
- `mu_o_sat(P)`.

---

## 7.2 Запрещена линейная extrapolation

Финальная утвержденная политика Prototype 1.0.3:

> **NO LINEAR EXTRAPOLATION outside supplied PVT/relperm tables.**

Если состояние выходит за заданный табличный диапазон:

- используется ближайшее endpoint value / endpoint branch (**clamp**);
- calculation continues;
- `run_summary` получает явный `WARNING`;
- инженер должен расширить таблицу, если warning систематически важен.

Пример warning:

`OIL_PVT saturated locus above table: gas-active max P=182.14005 bar, max Pb=180 bar. Endpoint Rs used; no extrapolation.`

Важно:
- machine-roundoff превышения типа `50.00000000001 > 50` не должны давать ложный warning;
- для этого в диагностике введена tolerance.

---

## 7.3 T08c extended PVTO

Оригинальный T08 подтвердил:
- producer shut-in/reopening logic работает;
- но позднее сравнение было невалидно, потому что IMEX extrapolated `Rs` выше max branch, а Prototype clamp-ил.

Для корректного comparison создан **T08c**:
- PVTO расширен до `Rs = 60`;
- extension сделан прозрачно, не tuning к Prototype;
- reverse dissolution остается внутри table range.

T08c считается корректным benchmark, оригинальный T08 — mechanism test, superseded by T08c для late-time comparison.

---

# 8. RELPERM

- tabular relperm;
- таблица является authoritative input;
- out-of-range policy также endpoint clamp + warning;
- физические тесты проверяют phase mobility / Sgc behavior.

---

# 9. Boundary conditions

Основная модель:

- inner boundary — well;
- outer reservoir boundary — constant pressure.

В validation отдельно контролируется корректность outer-boundary behavior.

---

# 10. Input Excel contract

Главный инженерный input — Excel workbook.

Стандартные листы:

- `MODEL`;
- `SCHEDULE`;
- `OIL_PVT`;
- `GAS_PVT`;
- `RELPERM`;
- `COMMENTS`.

Parser работает:
- по sheet names;
- по header/parameter names;
- не зависит от hard-coded row numbers.

`COMMENTS` solver игнорирует как расчетный input.

В `COMMENTS` финального `INPUT_TEMPLATE.xlsx` зафиксированы:
- SCHEDULE semantics;
- PVTO semantics;
- no-extrapolation policy;
- clamp + warning behavior;
- automatic OUTPUT behavior;
- basic workflow.

---

# 11. INPUT_TEMPLATE.xlsx

Финальный `INPUT_TEMPLATE.xlsx` основан на T07.

Он выбран специально, потому что демонстрирует одновременно:

- degassing;
- BHP control;
- два BHP changes;
- transient behavior;
- SCHEDULE report boundaries;
- pressure / Sg / Rs evolution.

Основная sequence:

- BHP 150 bar;
- day 5 -> 120 bar;
- day 15 -> 100 bar.

В template включены дополнительные report/integration boundaries:
- +10 s;
- +20 s;
- +30 s;
- +40 s;
- +50 s;
- +60 s

после control changes.

Template — пользовательский пример.  
Он **не является frozen regression input**.

Regression T07 хранится отдельно в `regression/inputs/`.

---

# 12. Рекомендуемый пользовательский workflow

Структура:

```text
Prototype_1.0.3/
├── INPUT_TEMPLATE.xlsx
├── INPUT/
├── OUTPUT/
├── radial_blackoil/
├── tests/
├── regression/
├── docs/
├── run_prototype.py
└── run.bat
```

Пользователь:

1. копирует `INPUT_TEMPLATE.xlsx`;
2. кладет копию в `INPUT/`;
3. редактирует Excel;
4. запускает solver.

Пример PowerShell:

```powershell
python .\run_prototype.py .\INPUT\My_Model.xlsx
```

Если `--output` не указан, автоматически создается:

```text
OUTPUT\My_Model\
```

Можно явно задать output:

```powershell
python .\run_prototype.py .\INPUT\My_Model.xlsx --output "D:\Results\My_Model"
```

Input Excel технически может находиться где угодно; `INPUT/` — рекомендуемая структура, не жесткое ограничение.

---

# 13. Финальный OUTPUT contract

Prototype 1.0.3 создает в standard OUTPUT:

```text
profiles.csv
rates.csv
material_balance.csv
step_log.csv
run_summary.json
run_summary.txt
summary.json

results.xlsx

oil_rate.png
gas_rate.png
GOR.png
BHP.png
pressure_profiles.png
Sg_profiles.png
Rs_profiles.png
```

---

## 13.1 results.xlsx

Три листа:

- `rates`;
- `profiles`;
- `material_balance`.

Данные соответствуют одноименным CSV.

---

## 13.2 PNG

Rates:
- `oil_rate.png`;
- `gas_rate.png`;
- `GOR.png`;
- `BHP.png`.

Profiles:
- `pressure_profiles.png`;
- `Sg_profiles.png`;
- `Rs_profiles.png`.

Profile PNG:
- содержат **все report times из SCHEDULE**;
- radial axis logarithmic.

Важно:
- начальный rate at `t=0` может быть очень высоким, потому что rate рассчитывается для initial reservoir state сразу после применения well BHP;
- после BHP changes короткие transient points могут выглядеть как почти вертикальные spikes;
- это физический/temporal transient, а не plotting bug.

По решению проекта ничего дополнительно сглаживать в 1.0.3 не нужно.

---

# 14. run_summary

Каждый production run имеет run passport.

Содержит как минимум:

- status;
- Prototype version;
- build ID;
- input format version;
- input filename/path;
- input SHA256;
- output path;
- wall time;
- N;
- simulation time;
- DT initial;
- DT minimum;
- DTMAX;
- Jacobian mode;
- linear solver;
- accepted steps;
- rejected steps;
- max Pb / PVT range diagnostics;
- requested report times;
- actual report times;
- warnings;
- QC.

QC:

- `report_times_pass`;
- `state_and_control_pass`;
- `material_balance_pass`.

---

# 15. Runtime sanity checks

Cheap production checks include минимум:

- `P > 0`;
- `0 <= Sg <= 1`;
- `Rs >= 0`;
- no NaN/Inf;
- report times completeness;
- producer does not reverse-flow;
- well control consistency;
- material balance.

Не внедрялась чрезмерно тяжелая система runtime invariants.

---

# 16. Material balance

В Prototype 1.0.3 реализован component material balance.

Для каждого report time учитываются:

## Oil component
- initial inventory;
- current inventory;
- cumulative well production;
- outer-boundary net flux;
- balance error.

## Gas component
Учитывается весь gas component:

- dissolved gas;
- free gas;
- initial gas inventory;
- current total gas inventory;
- cumulative well production;
- outer-boundary net flux;
- balance error.

Файл:
- `material_balance.csv`.

QC tolerance:

\[
10^{-4}\% \text{ от initial component inventory}
\]

Во final regression фактические ошибки были на много порядков ниже tolerance.

---

# 17. Validation philosophy

Три разных уровня проверки:

## 17.1 Unit / physics / contract tests

Папка `tests/`.

Проверяет отдельные куски математического/production core:
- grid;
- geometry;
- pore volume;
- rock law;
- PVT;
- PVTO;
- relperm;
- phase appearance;
- reverse dissolution;
- producer-only;
- BHP;
- rate;
- RATE -> BHP;
- Jacobian;
- sparse/dense behavior;
- schedule;
- output contract;
- CLI;
- material balance;
- invariants;
- reproducibility.

Текущий результат на validated numerical core:

**80 / 80 PASS**

до и после final regression.

---

## 17.2 Production regression

Папка `regression/`.

Acceptance runs проходят строго через:

```text
production Excel
-> production parser
-> run_prototype.py
-> standard OUTPUT
```

Не допускается direct Python model call для acceptance regression.

---

## 17.3 External benchmark

CMG IMEX fully implicit comparison.

IMEX benchmark был приведен к truly fully implicit mode:

- `AIM OFF`;
- `AIMSET CON 1`.

Это важно: прежняя конфигурация только с `AIM OFF` не делала все reservoir blocks implicit и создавала numerical gas/GOR oscillations.

---

# 18. Критическая IMEX находка

Старые IMEX decks:

- `AIM OFF`;
- без `AIMSET CON 1`.

IMEX log показывал:
- average implicitness около 0.010;
- максимум 1 из 101 blocks implicit.

Это создавало gas/GOR limit cycles и ложное впечатление расхождения Prototype.

После:
- `AIM OFF`;
- `AIMSET CON 1`;

IMEX стал truly fully implicit, и основные расхождения резко уменьшились.

**Нельзя возвращаться к старым non-FI IMEX reference как к эталону.**

---

# 19. IMEX profile cell alignment

CMG IMEX profile export содержит 101 block.

Интерпретация:

- первые 100 = physical cells;
- 101-й = outer large constant-pressure buffer.

При comparison:

- Prototype 100 cells сравниваются **cell-by-cell с первыми 100 IMEX cells**;
- 101-й IMEX cell исключается.

IMEX `Distance (m)`:
- начинается с 0;
- это relative line-export distance;
- не использовать nearest-radius matching против absolute Prototype radius.

Для plots используется Prototype cell-center radius.

---

# 20. Final production regression T00–T11

Final result:

> **PASS WITH DOCUMENTED NOTES**

Exact numerical-core build:

`1.0.3-prebeta-final-regression-20260825a`

Unit suite:
- before final regression: **80/80 PASS**;
- after final regression: **80/80 PASS**.

Все report/control/material-balance QC — PASS.

---

## 20.1 T00

Status: **PASS**

- max |ΔP| = **0.118775 bar**
- max Sg RMSE = **0.00158127**
- max |ΔRs| = **0.0544311**
- max |Δqo| = **0.399654 %**
- max |Δqg| = **0.355778 %**
- max |ΔGOR| = **0.092815 %**
- max |ΔBHP| = **0 bar**

Base fully implicit benchmark.

---

## 20.2 T01

Status: **PASS WITH NOTE**

- max |ΔP| = **0.130188 bar**
- max Sg RMSE = **0.00162366**
- max |ΔRs| = **0.0421973**
- max |Δqo| = **0.180003 %**
- max |Δqg| = **2.15727 %**
- max |ΔGOR| = **1.97372 %**
- max |ΔBHP| = **0 bar**

Stable gas/GOR difference около 2%, принят как documented benchmark note.

---

## 20.3 T02

Status: **PASS**

- max |ΔP| = **0.633760 bar**
- max Sg RMSE = **0.00632294**
- max |ΔRs| = **0.205225**
- max |Δqo| = **1.19412 %**
- max |Δqg| = **2.25638 %**
- max |ΔGOR| = **1.08464 %**
- max |ΔBHP| = **0 bar**

Benchmark с delayed gas mobility / Sgc.

---

## 20.4 T03

Status: **PASS**

- max |ΔP| = **0.184066 bar**
- max Sg RMSE = **0.00186592**
- max |ΔRs| = **0.0596605**
- max |Δqo| = **0.488391 %**
- max |Δqg| = **2.04640 %**
- max |ΔGOR| = **1.67099 %**
- max |ΔBHP| = **0 bar**

Corrected fully implicit IMEX gas/GOR smooth; старые oscillations были IMEX numerical artifact.

---

## 20.5 T04

Status: **PASS WITH NOTE**

- max |ΔP| = **0.234057 bar**
- max Sg RMSE = **0.00238333**
- max |ΔRs| = **0.0728216**
- max |Δqo| = **0.624713 %**
- max |Δqg| = **1.57638 %**
- max |ΔGOR| = **1.21097 %**

Combined hard case.

---

# 21. T05 convergence

Status: **PASS**

## 21.1 Spatial convergence

### N=50 -> N=100

- max |ΔP| = **0.110725 bar**
- max Sg RMSE = **1.82955e-4**
- max |ΔRs| = **0.0358886**
- max |Δqo| = **0.370754 %**
- max |Δqg| = **2.71064 %**
- max |ΔGOR| = **2.40411 %**

### N=100 -> N=200

- max |ΔP| = **0.0600136 bar**
- max Sg RMSE = **8.75005e-5**
- max |ΔRs| = **0.0254538**
- max |Δqo| = **0.229182 %**
- max |Δqg| = **1.07626 %**
- max |ΔGOR| = **1.28225 %**

Вывод:
- convergence подтверждается;
- `N=100` принят как default engineering compromise.

---

## 21.2 Temporal convergence

### DTMAX 60 -> 10 min

- max |ΔP| = **0.0935951 bar**
- max Sg RMSE = **9.42684e-5**
- max |ΔRs| = **0.0303364**
- max |Δqo| = **0.184702 %**
- max |Δqg| = **0.319991 %**
- max |ΔGOR| = **0.135040 %**

### DTMAX 10 -> 5 min

- max |ΔP| = **0.0117528 bar**
- max Sg RMSE = **1.02637e-5**
- max |ΔRs| = **0.00380935**
- max |Δqo| = **0.0223993 %**
- max |Δqg| = **0.0614938 %**
- max |ΔGOR| = **0.0603454 %**

### DTMAX 5 -> 3 min

- max |ΔP| = **0.00484758 bar**
- max Sg RMSE = **3.93137e-6**
- max |ΔRs| = **0.00157121**
- max |Δqo| = **0.0090542 %**
- max |Δqg| = **0.108938 %**
- max |ΔGOR| = **0.107670 %**

### Default 60 min -> fine 3 min

- max |ΔP| = **0.110161 bar**
- max Sg RMSE = **1.07809e-4**
- max |ΔRs| = **0.0357058**
- max |Δqo| = **0.216215 %**
- max |Δqg| = **0.373641 %**
- max |ΔGOR| = **0.157086 %**

Вывод:
- `DTMAX=60 min` принят как standard default;
- near abrupt control transients при необходимости нужно добавлять finer SCHEDULE boundaries / снижать timestep.

---

# 22. T06

Status: **PASS**

Near-bubble-point case:

- max |ΔP| = **0.0148302 bar**
- max Sg RMSE = **0.000930611**
- max |ΔRs| = **0.00330375**
- max |Δqo| = **0.248769 %**
- max |Δqg| = **0.247837 %**
- max |ΔGOR| = **0.060727 %**

Agreement tight.

---

# 23. T07 — BHP schedule transient

Status: **PASS WITH TRANSIENT NOTE**

BHP sequence:

- 150 bar;
- day 5 -> 120 bar;
- day 15 -> 100 bar.

Stable comparison:

- max |ΔP| = **0.137414 bar**
- max Sg RMSE = **0.00226923**
- max |ΔRs| = **0.0445407**
- max |Δqo| = **0.508234 %**
- max |Δqg| = **2.52208 %**
- max |ΔGOR| = **2.55687 %**
- BHP exact on stable comparison.

Documented note:

- point exactly ~1 min after abrupt BHP change is timestep-sensitive;
- 10-second diagnostic strongly reduced discrepancy;
- this establishes temporal discretization as primary cause;
- physics/control semantics не менялись ради matching.

---

# 24. T08 / T08c

## Original T08

Purpose:
- shut-in / reopening;
- reverse-flow protection;
- reverse dissolution.

Found:
- old Prototype could reverse-inject under producer BHP logic;
- fixed with producer-only protection.

Mechanism:
- PASS.

But late comparison invalid:
- IMEX extrapolated Rs above table max;
- Prototype clamped.

Therefore original T08 late-time benchmark superseded.

---

## T08c

Status:

**PASS WITH REOPENING / LOCAL GAS-FRONT NOTE**

Extended PVTO to `Rs=60`.

Before BHP change:
- qo difference ~0.18%;
- qg ~2.15%;
- GOR ~1.97%;
- profiles close.

At `5 d + 1 min`:
- both wells shut;
- Prototype producer-only behavior confirmed.

Day 6 reopening:
- transient rate difference is relatively large:
  - qo ~ -17.5%;
  - qg ~ -16.4%;
- but GOR difference small (~1.4%);
- reservoir state profiles remain close.

Day 14 / day 30:
- well rates return to tight agreement;
- late Sg difference is localized in gas-front position.

Final stable summary:

- max |ΔP| = **0.129270 bar**
- max Sg RMSE = **0.00407102**
- max |ΔRs| = **0.659907**
- max |Δqo| stable = **0.433545 %**
- max |Δqg| stable = **2.14904 %**
- max |ΔGOR| stable = **1.96538 %**
- reported transient max |ΔBHP| around **1.3254 bar** during shut/reopening comparison.

No PVT warning in T08c because extended table contains reverse dissolution range.

---

# 25. T09

Status: **PASS**

OIL_RATE = 2 Sm3/day, minimum BHP 100 bar not active.

- max |ΔP| = **0.234452 bar**
- max Sg RMSE = **0.00243321**
- max |ΔRs| = **0.0727936**
- max |Δqo| = **0 %**
- max |Δqg| = **0.545174 %**
- max |ΔGOR| = **0.545174 %**
- max |ΔBHP| = **0.244886 bar**

---

# 26. T10 — rate schedule

Status: **PASS WITH TRANSIENT NOTE**

Rate sequence:

- 2 Sm3/day;
- day 5 -> 3;
- day 15 -> 1.5;
- minimum BHP 100 bar.

Stable metrics:

- max |ΔP| = **0.200136 bar**
- max Sg RMSE = **0.00281046**
- max |ΔRs| = **0.329823**
- max |Δqo| = **0 %**
- max |Δqg| = **1.94939 %**
- max |ΔGOR| = **1.94939 %**
- max |ΔBHP| = **0.209007 bar**

1-minute post-rate-step gas/GOR transient remains documented timestep note.

---

# 27. T11 — RATE -> BHP constraint

Status: **PASS**

- OIL_RATE = 2.5 Sm3/day;
- minimum BHP = 125 bar;
- rate branch active initially;
- BHP floor activates between day 18 and day 19.

Metrics:

- max |ΔP| = **0.222732 bar**
- max Sg RMSE = **0.00210415**
- max |ΔRs| = **0.0691557**
- max |Δqo| = **0.333604 %**
- max |Δqg| = **1.30121 %**
- max |ΔGOR| = **0.970616 %**
- max |ΔBHP| = **0.236651 bar**

RATE -> BHP logic reproduced.

---

# 28. Material-balance validation results

Final regression tolerance:

`1e-4 % of initial component inventory`.

All T00–T11:
- PASS.

Largest errors remained far below tolerance.

Representative / maximum-scale errors:
- oil ~ `1e-7 %` or smaller in standard cases;
- gas ~ `1e-7 %` order in worst convergence cases;
- many benchmark cases are around `1e-9 ... 1e-11 %`.

Conclusion:
- conservation implementation is numerically very strong.

---

# 29. Windows clean-room handoff

Performed by user on a real Windows computer.

Beta test:
- manual copy/edit of `INPUT_TEMPLATE.xlsx`;
- edited `DTMAX`;
- added SCHEDULE row;
- launched through `run_prototype.py`;
- automatic OUTPUT created;
- SUCCESS;
- all QC PASS;
- material balance PASS;
- manual report time present.

Result:

**CLEAN-ROOM HANDOFF — PASS**

This verifies real engineer-facing workflow outside development environment.

---

# 30. Final release 1.0.3 Windows rerun

After adding final-release-only output layer:
- `results.xlsx`;
- PNGs;

user reran `CleanRoom_T07.xlsx` on Windows.

Run summary:

- status: `SUCCESS`;
- version: `1.0.3`;
- build: `1.0.3-prebeta-final-regression-20260825a`;
- `N=100`;
- `DTMAX=60 min`;
- sparse solver;
- grouped Jacobian;
- accepted steps: **787**;
- rejected steps: **0**;
- wall time: **19.46 s** on user's Windows machine;
- all 24 requested report times written;
- report/state/material QC all PASS.

Material balance:
- oil error = **6.95e-11 % initial**
- gas error = **1.22e-9 % initial**

Physical ranges in final CleanRoom result:
- pressure approximately **100.71–200 bar**;
- `Sg` approximately **0–0.08796**;
- `Rs` approximately **25.24–50**;
- no NaN/Inf.

Numerical behavior:
- max timestep = 3600 s;
- max Newton iterations observed = 8;
- max active-set iterations = 2;
- final residuals around `1e-11` scale.

Final output artifacts on Windows:
- CSV — PASS;
- JSON/TXT summary — PASS;
- `results.xlsx` — PASS;
- all 7 PNG — PASS.

This final rerun is the last user acceptance check before freezing 1.0.3.

---

# 31. Final release-only changes after numerical regression

После final T00–T11 numerical regression были сделаны **только output/package changes**:

1. `results.xlsx`;
2. automatic PNG;
3. test fixtures moved from root `data/` to `tests/fixtures/`;
4. documentation updated;
5. requirements updated for output dependencies.

**Numerical core не менялся.**

Short smoke check showed old numerical CSV outputs remain identical for same short input.

User then reran final 1.0.3 on Windows and accepted results.

---

# 32. Final dependency set

Pinned requirements:

```text
numpy==2.3.5
scipy==1.17.0
XlsxWriter==3.2.9
matplotlib==3.10.8
```

---

# 33. Package contents

Important root files:

- `run_prototype.py`;
- `run.bat`;
- `run_tests.bat`;
- `VERSION.txt`;
- `BUILD.txt`;
- `requirements.txt`;
- `INPUT_TEMPLATE.xlsx`;
- `PACKAGE_MANIFEST_SHA256.txt`;
- `README.md`.

Core code:

- `radial_blackoil/blackoil.py`;
- `grid.py`;
- `pvt.py`;
- `relperm.py`;
- `rock.py`;
- `state.py`;
- `schedule.py`;
- `simulation.py`;
- `runner.py`;
- `input_reader.py`;
- `xlsxio.py`;
- `diagnostics.py`;
- `output_artifacts.py`;
- `build_info.py`;
- `units.py`.

Tests:
- `tests/`;
- test fixtures inside `tests/fixtures/`.

Regression:
- `regression/inputs/`;
- `regression/golden/`;
- `regression/reference_imex_xlsx/`;
- `regression/reference_imex_normalized/`;
- `regression/evidence/`;
- `regression/figures/`;
- `regression/run_regression.py`;
- `regression/run_regression.bat`.

---

# 34. Regression execution rules

Full regression:

```powershell
python .\regression\run_regression.py
```

Quick regression:

```powershell
python .\regression\run_regression.py --quick
```

Single case:

```powershell
python .\regression\run_regression.py --case T00
```

Golden outputs correspond to validated numerical-core build.

If future code changes mathematical behavior:
- do not silently update golden outputs;
- first inspect why difference changed;
- rerun external validation as appropriate;
- only then intentionally replace golden data under a new version.

---

# 35. Unit tests

Typical command:

```powershell
python -m unittest discover -s tests -v
```

Validated baseline:
- **80/80 PASS**.

Historical note:
- Prototype 1.0.1: dense baseline, 42/42;
- Prototype 1.0.2: sparse implementation, 48/48;
- during early 1.0.3 branch only 16 tests were visible;
- this was audited;
- documented old coverage was restored/expanded;
- current suite = 80 tests.

Do not interpret test-count alone as quality metric; coverage is the key criterion.

---

# 36. Known accepted notes / limitations

## 36.1 Short transient sensitivity

Abrupt BHP/rate changes:
- first seconds/minutes can be timestep-sensitive;
- use finer SCHEDULE boundaries or smaller DTMAX if transient detail matters.

Do not alter physics merely to match IMEX first-minute values.

---

## 36.2 Gas-front position

T08c:
- late well response can match strongly while localized Sg-front location differs somewhat between simulators;
- accepted documented note;
- not evidence of broad conservation or control failure.

---

## 36.3 PVT range warnings

Many benchmark cases intentionally reach slightly outside max saturated locus.

Current policy:
- clamp;
- warning;
- no extrapolation.

For engineering studies:
- prefer extending input PVT table if warning is materially relevant.

---

## 36.4 Negative/invalid Excel acceptance tests

**DEFERRED BY PROJECT DECISION.**

Not a blocker for current released 1.0.3.

Future hardening may include:
- missing sheets;
- missing columns;
- `N=0`;
- `rw >= re`;
- negative permeability;
- malformed PVTO;
- non-monotonic schedule;
- missing control targets;
- invalid relperm;
- unsupported mode;
- etc.

Do not retroactively describe these as already validated.

---

## 36.5 Water

Current solver:
- **no water phase**.

Future addition of water = significant new physics/version.

---

## 36.6 Thermal physics

Current solver:
- **isothermal**.

Thermal solver is future work and should use hydrodynamic fields from BO solver as input/coupling state.

---

# 37. Performance note

Final CleanRoom T07:
- 30 days;
- N=100;
- DTMAX=60 min;
- 787 accepted steps;
- 0 rejected;
- ~19.5 s on user's Windows machine.

Earlier run with `DTMAX=30 min`:
- ~32.4 s;
- 1482 accepted;
- 0 rejected.

This is empirical performance on the user's machine, not a universal hardware guarantee.

---

# 38. Important future thermal-coupling context

Long-term project goal includes temperature calculation in reservoir.

For thermal work, likely useful BO solver fields include per timestep/report:

- pressure;
- oil saturation;
- gas saturation;
- dissolved gas `Rs`;
- phase/component properties;
- pressure/saturation temporal changes;
- phase fluxes / rates.

Need separately decide exactly which derivatives/flux fields the thermal equation requires.

Do not assume the thermal model is already implemented in 1.0.3.

---

# 39. GEM context

Current validation benchmark is IMEX because solver is black-oil.

Future GEM work may be used to:
- create a simplified compositional fluid;
- export/derive an equivalent black-oil PVT;
- feed that BO PVT into Prototype;
- compare derived BO representation with compositional reference.

Do not directly compare a mismatched arbitrary GEM fluid against current synthetic BO fluid and interpret mismatch as solver error.

---

# 40. Current release status

**Prototype 1.0.3 is the current accepted release and baseline.**

Acceptance evidence:

- physics/numerics unit suite — PASS;
- 80/80 current tests — PASS;
- sparse solver — validated;
- T05 convergence — PASS;
- T00–T11 external production regression — PASS WITH DOCUMENTED NOTES;
- material balance — PASS;
- SCHEDULE semantics — validated;
- BHP and RATE controls — validated;
- RATE -> BHP — validated;
- producer-only protection — validated;
- reverse dissolution — validated with T08c;
- PVT clamp/warning — validated;
- automatic OUTPUT — validated;
- Windows clean-room — PASS;
- final `results.xlsx` — verified;
- final PNG output — verified;
- final Windows rerun — PASS.

---

# 41. Version-control rule for future work

Treat `Prototype_1.0.3.zip` as immutable release artifact.

Recommended future process:

### If only docs change
Can remain documentation update, provided executable package is not silently replaced.

### If only output formatting changes
Assess whether numerical CSV/state values remain unchanged.
At minimum smoke-test output equivalence.

### If parser/input semantics change
New patch version + parser/production regression.

### If numerical or physical core changes
New version +:
- unit tests;
- convergence as relevant;
- full production regression;
- selected external IMEX comparison;
- clean-room if package behavior changes.

---

# 42. What NOT to do in a new chat

Do not:

- rename IMEX 1 to GEM 1;
- treat old non-FI IMEX results as current benchmark;
- compare Prototype physical 100 cells against IMEX 101st buffer cell;
- extrapolate PVT silently;
- allow producer to reverse-inject;
- change SCHEDULE semantics;
- interpolate report states instead of hitting boundaries;
- tune solver solely to reduce CMG discrepancies;
- update golden regression outputs simply because a new code gives different results;
- call Negative Excel tests completed;
- assume thermal physics is already implemented;
- overwrite Prototype 1.0.3 baseline without explicit version decision.

---

# 43. Recommended first actions in a new development chat

When continuing from this handoff:

1. inspect `Prototype_1.0.3.zip`;
2. confirm version/build;
3. read:
   - `README.md`;
   - `docs/RELEASE_NOTES_1.0.3.md`;
   - `docs/VALIDATION_STATUS.md`;
   - `docs/INPUT_OUTPUT_CONTRACT.md`;
   - `docs/TESTING.md`;
4. run or inspect unit suite before code changes;
5. understand whether requested change touches:
   - output only;
   - parser;
   - physics;
   - numerics;
   - controls;
6. if math/core changes, plan version bump before implementation.

---

# 44. Short baseline statement for future messages

Use the following compact statement when needed:

> **Prototype 1.0.3 is the frozen current release of the 1D radial isothermal oil-gas black-oil solver. Its numerical core build `1.0.3-prebeta-final-regression-20260825a` passed 80/80 unit/physics/contract tests, T05 spatial/temporal convergence, fully implicit IMEX production regression T00–T11 with documented transient notes, component material-balance QC, and Windows clean-room validation. Final output includes CSV, run summaries, results.xlsx and seven PNG figures. No PVT/relperm linear extrapolation is allowed: endpoint clamp + warning. The release archive is the baseline for all future work.**

---

# 45. Authoritative artifact

The authoritative code artifact is:

`Prototype_1.0.3.zip`

SHA256:

`73adc810cf1e634bf4636527ec12fbdaa2e640c02cb0dbd1379b50fbf7824647`

If code reconstructed from chat text differs from the ZIP, **the ZIP wins**.

---

**END OF CONTEXT HANDOFF — Prototype 1.0.3**
