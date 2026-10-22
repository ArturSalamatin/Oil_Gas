"""DEBT-080: правки hydro-prototype-анализ.md и «открытые вопросы проектирования.md» (вариант 2).

Источник точного текста правок для плана `vault/plans/debt-080 prototype-analysis-note-sync.md`.

Запуск — из корня проекта (основной каталог или worktree):
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-080\\probes\\note_apply.py           # проверка
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-080\\probes\\note_apply.py --apply   # запись
    numerical_solver\\.venv\\Scripts\\python vault\\issues\\debt-080\\probes\\note_apply.py --show    # новый текст заметки

Проверка (без ключа) файлы не меняет: применяет замены в памяти и проверяет
  1) каждый old встречается в файле ровно один раз (иначе замена неоднозначна или текст уехал);
  2) в результате нет устаревших фраз (FORBIDDEN);
  3) каждая wiki-ссылка нового текста — существующая заметка vault или ID из реестров;
  4) каждое имя кода в обратных кавычках из CODE_SYMBOLS определено в коде (def/class/присваивание).
"""
import re
import sys
from pathlib import Path

# Корень — текущий каталог (в worktree — корень worktree, правило памяти о PYTHONPATH)
ROOT = Path.cwd()
if not (ROOT / "vault").is_dir() or not (ROOT / "numerical_solver").is_dir():
    sys.exit(f"запускать из корня проекта: {ROOT} — нет vault/ или numerical_solver/")

NOTE = ROOT / "vault/knowledge/decisions/hydro-prototype-анализ.md"
OQ = ROOT / "vault/knowledge/decisions/открытые вопросы проектирования.md"

# ── Замены: (файл, old, new). old — точный текст на базе 8ddb08d ──
R = []

# R1. description — статус заметки
R.append((NOTE,
"description: Анализ гидродинамического прототипа коллеги v1.0.3 — структура, подходы, единицы, конвенции, проблемы интеграции",
"description: Анализ прототипа radial_blackoil v1.0.3 до интеграции (2026-08) — структура, единицы, 2N, конечно-разностный якобиан, знаки потоков; вопросы интеграции P1–P8 решены; действующий алгоритм advance — в модули-hydro-newton"))

# R2. Плашка + шапка: число файлов, тесты прототипа, дистрибутив
R.append((NOTE,
"""Расположение: `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`
Пакет: `radial_blackoil` (15 .py файлов)
Тесты: 79 (unit) + 12 регрессионных кейсов (T00–T11)""",
"""> **Анализ прототипа v1.0.3 до интеграции (2026-08); сверено с кодом в [[DEBT-080]] (2026-10-17).**
> - **Верно и сейчас:** структура пакета, промысловые единицы (§1), табличные PVT и ОФП (§2, §3), сжимаемая порода (§4), $2N$ неизвестных с переключением переменной (§5), конечно-разностный якобиан (§6), собственный цикл прототипа по времени (§8), знаки потоков (§9), книга ввода прототипа (§10), расписание (§11), вывод (§12).
> - **Неполно:** §7 — алгоритм `advance` дополнялся точечно до BUG-022; действующий — таблица раздела «Действующий решатель: прототип через адаптер» [[модули-hydro-newton]], локальные правки — `CHANGELOG_1.0.3.md`, раздел «Local changes — GPN project».
> - **История:** абзацы «Проблема для интеграции» (§1, §2, §8, §10) и раздел «Проблемы для интеграции» (P1–P8) — вопросы на август 2026; все решены, под каждым — ссылка на решение.

Расположение: `numerical_solver/HydroSolverPrototype/Prototype_1.0.3/`
Пакет: `radial_blackoil` (16 .py файлов); с локальными правками GPN — дистрибутив `radial-blackoil 1.0.3+gpn.1` ([[DEBT-059]])
Тесты прототипа: `pytest tests` в `Prototype_1.0.3` (109 на 2026-10-17; при анализе — 79) + регрессия против эталона `regression/golden/`: 12 кейсов T00–T11 (T05 — 6 вариантов, всего 17 расчётов)"""))

# R3. §1 — номера строк blackoil.py → имена функций
R.append((NOTE,
"Конвертация BAR_TO_PA, CP_TO_PA_S, MD_TO_M2 — в units.py. Конвертация **внутри** формул (blackoil.py, строки 71, 88, 111, 119, 124).",
"Константы BAR_TO_PA, CP_TO_PA_S, MD_TO_M2 — в units.py. Перевод — **внутри** формул: `BAR_TO_PA` — в потоках через забой, внутренние грани и контур (`blackoil.py`: `_well_fluxes`, `face_component_fluxes_sm3s`), `CP_TO_PA_S` — в подвижностях фаз (`_phase_mobilities_surface`), `MD_TO_M2` — в проводимостях граней (`grid.py`, `RadialGrid`)."))

# R4. §1 — проблема для интеграции решена (P1)
R.append((NOTE,
"**Проблема для интеграции:** наша библиотека работает в SI. Adapter должен конвертировать p из Па→бар на входе, из бар→Па на выходе.",
"""**Проблема для интеграции:** наша библиотека работает в SI. Adapter должен конвертировать p из Па→бар на входе, из бар→Па на выходе.

**Решено** — [[P1-адаптер-единицы]]: давление и дебиты переводит `PrototypeHydroAdapter.solve`, проницаемость (мД) и сжимаемость породы (1/бар) — `factory._create_prototype_hydro`."""))

# R5. §2 — тепловые свойства (P5, P6)
R.append((NOTE,
"**Проблема для интеграции:** наша FullPVT (c_p, μ_JT, L) не представлена в прототипе — он не знает про температуру. Для EnergySolver FullPVT нужна отдельная реализация, не из прототипа.",
"""**Проблема для интеграции:** наша FullPVT (c_p, μ_JT, L) не представлена в прототипе — он не знает про температуру. Для EnergySolver FullPVT нужна отдельная реализация, не из прототипа.

**Решено** — [[P5-pvt-архитектура]], [[P6-тепловые-свойства]]: `TableFullPVT` (таблицы прототипа через `PrototypePVTAdapter` + тепловые свойства из конфига) и `StandingFullPVT`; один объект PVT у гидродинамики и энергии."""))

# R6. §3 — аналитического якобиана нет и не будет (DEBT-077)
R.append((NOTE,
"Производные **нужны** для нашего ABC RelPermModel (для аналитического якобиана). Default fallback на конечные разности — совместим.",
"При анализе предполагалось, что производные понадобятся нашему ABC RelPermModel для аналитического якобиана. Аналитического якобиана в коде нет: он был частью собственного решателя (блочный Ньютон), а собственного решателя нет и не будет (решение пользователя 2026-10-15, [[DEBT-077]]); якобиан строит прототип конечными разностями (§6); таблица прототипа подключена обёрткой `PrototypeRPAdapter` ([[P7-офп-без-производных]])."))

# R7. §7 — плашка «неполно» со ссылкой на действующее описание
R.append((NOTE,
"""### 7. Newton с линейным поиском и active-set

""",
"""### 7. Newton с линейным поиском и active-set

> **Неполно** (сверено в [[DEBT-080]]): раздел дополнялся точечно до BUG-022 (2026-10-10). Нет ступени 3 ([[BUG-016]]) и устройства ступени 4 (`advance_fourth_stage`, `_newton_switching`; [[BUG-020]], [[BUG-024]], [[DEBT-048]]), абсолютного допуска не ниже предела округления ([[BUG-025]]), приёмки строки на её пределе округления ([[DEBT-067]]) и меры этого предела в отчёте ([[DEBT-055]]), ограничения $S_g$ включаемой ячейки `sg_activation_cap` ([[BUG-018]]), пропуска ветки «открыта» ([[DEBT-040]]), отчёта отказа и попыток ступеней ([[DEBT-030]], [[DEBT-054]], [[DEBT-069]]). Действующий алгоритм — таблица раздела «Действующий решатель: прототип через адаптер» [[модули-hydro-newton]]; здесь не дублируется.

"""))

# R8. §7 — лимит проходов набора фаз после BUG-028
R.append((NOTE,
"`_advance_phases`: внешний цикл по active set (до 12 итераций). Переключение режимов",
"`_advance_phases`: внешний цикл по набору фаз; лимит `max_active_iter` (по умолчанию 12) с [[BUG-028]] считает только проходы, включающие газ хотя бы в одной ячейке, всего проходов — не больше `max_active_iter` + N. Переключение режимов"))

# R9. §8 — кто управляет шагом (P4, DEBT-015)
R.append((NOTE,
"При интеграции нужно решить: кто управляет dt?",
"""При интеграции нужно решить: кто управляет dt?

**Решено** — [[P4-адаптивный-шаг]], [[DEBT-015]]: адаптер делает один вызов `advance` на подшаг (по памяти ступени 4 — `advance_fourth_stage`, [[DEBT-048]]), не сошедшийся подшаг делит пополам `Simulator._advance`, после удачи подшаг растёт; старт с малого шага после смены управления — [[FEAT-032]]. `simulate_schedule` и `_grow_dt` GPN не вызывает; ими пользуются `run_workbook` (`runner.py`; через `run_prototype.py` — регрессия прототипа) и тесты прототипа."""))

# R10. §10 — формат ввода (P8, FEAT-033…036)
R.append((NOTE,
"**Проблема для интеграции:** наша библиотека использует JSON. Нужен либо конвертер XLSX→JSON, либо поддержка обоих форматов в input_reader.",
"""**Проблема для интеграции:** наша библиотека использует JSON. Нужен либо конвертер XLSX→JSON, либо поддержка обоих форматов в input_reader.

**Решено** — [[P8-формат-ввода-json]]: ввод GPN — JSON, `load_input` прототипа GPN не вызывает. Ввод книгой Excel — [[FEAT-033]]…[[FEAT-036]], разбор собственный: `radial_blackoil.xlsxio` не различает даты, логические значения и формулы без сохранённого значения ([[FEAT-034]])."""))

# R11. Раздел P1–P8 — плашка «все решены»
R.append((NOTE,
"""## Проблемы для интеграции

### P1.""",
"""## Проблемы для интеграции

> Вопросы на август 2026 — все решены (сверено в [[DEBT-080]]). Текст вопросов не менялся; под каждым — ссылка на решение.

### P1."""))

# R12–R19. P1–P8 — «Решено →»
R.append((NOTE,
"Риск: забыть конвертацию в одном месте → ошибка в 10⁵ раз.",
"""Риск: забыть конвертацию в одном месте → ошибка в 10⁵ раз.

**Решено →** [[P1-адаптер-единицы]]: перевод — `PrototypeHydroAdapter.solve` и `factory._create_prototype_hydro`."""))

R.append((NOTE,
"Adapter инвертирует знак **только well** потоков. Подробности: [[P1-адаптер-единицы]].",
"""Adapter инвертирует знак **только well** потоков. Подробности: [[P1-адаптер-единицы]].

**Решено →** [[P2-знаки-потоков-прототип]]."""))

R.append((NOTE,
"- t — нет в прототипе (управляется Simulator)",
"""- t — нет в прототипе (управляется Simulator)

**Решено →** [[P3-маппинг-состояния]]."""))

R.append((NOTE,
"Вариант (B) — самый простой для Adapter. Но прототип может не сойтись при большом dt.",
"""Вариант (B) — самый простой для Adapter. Но прототип может не сойтись при большом dt.

**Решено →** вариант (B) с дроблением снаружи: адаптер делает один `advance`, не сошедшийся подшаг дробит `Simulator._advance` ([[P4-адаптивный-шаг]], [[DEBT-015]])."""))

R.append((NOTE,
"Или: реализовать PVTO-формат в нашем ABC HydroPVT.",
"""Или: реализовать PVTO-формат в нашем ABC HydroPVT.

**Решено →** [[P5-pvt-архитектура]]: табличный путь — `TableFullPVT` поверх `BlackOilPVT` прототипа, путь Стендинга — `StandingFullPVT`, прототипу он передаётся через `HydroPVTtoBlackOilAdapter`; один объект PVT у гидродинамики и энергии; при таблице корреляции не подмешиваются."""))

R.append((NOTE,
"Эти свойства — ответственность нашей библиотеки (FullPVT).",
"""Эти свойства — ответственность нашей библиотеки (FullPVT).

**Решено →** [[P6-тепловые-свойства]] (через P5): c_p, μ_JT, L — в `TableFullPVT` и `StandingFullPVT`; λ — не PVT-свойство, её считает решатель энергии (P6, «Что не входит в PVT»)."""))

R.append((NOTE,
"Совместимо — Adapter обернёт табличные ОФП прототипа в наш ABC.",
"""Совместимо — Adapter обернёт табличные ОФП прототипа в наш ABC.

**Решено →** [[P7-офп-без-производных]]: обёртка `PrototypeRPAdapter`; производные не нужны — якобиан конечно-разностный (§6), собственного решателя с аналитическим якобианом нет и не будет ([[DEBT-077]])."""))

R.append((NOTE,
"Прототип читает Excel. Наша библиотека — JSON. Нужен конвертер или поддержка обоих.",
"""Прототип читает Excel. Наша библиотека — JSON. Нужен конвертер или поддержка обоих.

**Решено →** [[P8-формат-ввода-json]]: JSON; ввод книгой Excel — [[FEAT-033]]…[[FEAT-036]]."""))

# R20–R23. Таблица «Что можно переиспользовать»: две колонки (строки и были в две), advance, диагностика, вывод
R.append((NOTE,
"""| Компонент | Переиспользование | Как |
|---|---|---|""",
"""| Компонент | Переиспользование |
|---|---|"""))

R.append((NOTE,
"| RadialBlackOilModel.advance() | **да** — основной вызов для HydroSolver |",
"| RadialBlackOilModel.advance() | **да** — один вызов на подшаг из `PrototypeHydroAdapter.solve`; при памяти ступени 4 — `advance_fourth_stage` ([[DEBT-048]]) |"))

R.append((NOTE,
"| Диагностика | **да** — state_sanity, pvt_range_warnings полезны |",
"| Диагностика | **частично** — после каждого принятого шага `PrototypeHydroAdapter` вызывает `pvt_range_warnings` (табличный PVT, [[DEBT-027]]) или `relperm_range_warnings` (PVT Стендинга, [[DEBT-071]]); `state_sanity` — нет: принятое состояние проверяет `Simulator._check_hydro_state` ([[DEBT-075]]) |"))

R.append((NOTE,
"| Вывод (CSV, PNG) | **частично** — формат графиков можно адаптировать |",
"| Вывод (CSV, PNG) | **нет** — свой вывод (`gpn_multiphase_solver/io/output.py`) |"))

# R24. Связанные заметки — действующее описание
R.append((NOTE,
"- [[архитектура библиотеки numerical_solver]]\n",
"- [[модули-hydro-newton]] — действующий алгоритм `advance` (раздел «Действующий решатель: прототип через адаптер»)\n- [[архитектура библиотеки numerical_solver]]\n"))

# ── «открытые вопросы проектирования.md», Q7 (решение пользователя 2026-10-17 — попутно) ──
R.append((OQ,
"2. PrototypeHydroAdapter — декоратор единиц + A-retry при расходимости",
"2. PrototypeHydroAdapter — декоратор единиц; один вызов `advance` (или `advance_fourth_stage`, [[DEBT-048]]) на подшаг, не сошедшийся подшаг дробит `Simulator._advance` (A-retry в адаптере убран в [[DEBT-015]])"))

R.append((OQ,
"[[P5-pvt-архитектура]], [[P7-офп-без-производных]]",
"[[P5-pvt-архитектура]], [[P6-тепловые-свойства]], [[P7-офп-без-производных]]"))

# ── Проверки результата ──
FORBIDDEN = {
    NOTE: ["строки 71, 88", "79 (unit)", "15 .py файлов", "state_sanity, pvt_range_warnings полезны",
           "до 12 итераций", "Производные **нужны**", "формат графиков можно адаптировать",
           "основной вызов для HydroSolver"],
    OQ: ["A-retry при расходимости"],
}

# Имена кода из нового текста: должны быть определены (def/class/присваивание) в коде
CODE_SYMBOLS = ["_well_fluxes", "face_component_fluxes_sm3s", "_phase_mobilities_surface",
                "advance_fourth_stage", "_newton_switching", "_sg_activation_cap", "_advance_phases",
                "PrototypeHydroAdapter", "_create_prototype_hydro", "TableFullPVT", "StandingFullPVT",
                "PrototypePVTAdapter", "HydroPVTtoBlackOilAdapter", "PrototypeRPAdapter",
                "_check_hydro_state", "pvt_range_warnings", "relperm_range_warnings", "state_sanity",
                "simulate_schedule", "_grow_dt", "run_workbook", "load_input", "_advance", "RadialGrid",
                "read_workbook_tables", "advance"]
CODE_DIRS = [ROOT / "numerical_solver/gpn_multiphase_solver",
             ROOT / "numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil"]
CODE_FILES = [ROOT / "numerical_solver/gpn_multiphase_solver/io/output.py",
              ROOT / "numerical_solver/HydroSolverPrototype/Prototype_1.0.3/CHANGELOG_1.0.3.md",
              ROOT / "numerical_solver/HydroSolverPrototype/Prototype_1.0.3/run_prototype.py",
              ROOT / "numerical_solver/HydroSolverPrototype/Prototype_1.0.3/radial_blackoil/xlsxio.py"]

REGISTRIES = [ROOT / "vault/roadmap/известные баги и технический долг.md",
              ROOT / "vault/roadmap/планируемые фичи.md",
              ROOT / "vault/roadmap/валидационные кейсы.md"]
ID_RE = re.compile(r"^(BUG|DEBT|FEAT|VAL)-\d{3}$")
LINK_RE = re.compile(r"\[\[([^\]|#]+)")


def read(path):
    """Текст с переводами строк \\n (read_text приводит \\r\\n к \\n) и признак CRLF файла."""
    return path.read_text(encoding="utf-8"), b"\r\n" in path.read_bytes()


def apply_all():
    """Замены в памяти; ошибки — список строк."""
    texts = {NOTE: read(NOTE)[0], OQ: read(OQ)[0]}
    errors = []
    for i, (path, old, new) in enumerate(R, 1):
        n = texts[path].count(old)
        if n != 1:
            errors.append(f"R{i} ({path.name}): old встречается {n} раз — {old[:60]!r}")
            continue
        texts[path] = texts[path].replace(old, new)
    return texts, errors


def check(texts):
    errors = []
    for path, phrases in FORBIDDEN.items():
        for ph in phrases:
            if ph in texts[path]:
                errors.append(f"{path.name}: осталась устаревшая фраза {ph!r}")
    # Wiki-ссылки нового текста
    registry = "\n".join(p.read_text(encoding="utf-8") for p in REGISTRIES)
    notes = {p.stem for p in (ROOT / "vault").rglob("*.md")}
    links = sorted({m.group(1).strip() for _, _, new in R for m in LINK_RE.finditer(new)})
    for name in links:
        if ID_RE.match(name):
            if f"### {name}:" not in registry:
                errors.append(f"ссылка [[{name}]]: нет записи в реестрах")
        elif name not in notes:
            errors.append(f"ссылка [[{name}]]: нет заметки в vault")
    # Имена кода
    code = "\n".join(p.read_text(encoding="utf-8") for d in CODE_DIRS for p in d.rglob("*.py"))
    for f in CODE_FILES:
        if not f.is_file():
            errors.append(f"нет файла {f.relative_to(ROOT)}")
    for s in CODE_SYMBOLS:
        if not re.search(rf"(def|class)\s+{re.escape(s)}\b|^\s*{re.escape(s)}\s*=", code, re.M):
            errors.append(f"имя {s}: не определено в коде")
    return errors, links


def main():
    print(f"ROOT = {ROOT}")
    texts, errors = apply_all()
    errs2, links = check(texts) if not errors else ([], [])
    errors += errs2
    if "--show" in sys.argv:
        print(texts[NOTE])
        return
    old_lines = len(NOTE.read_text(encoding="utf-8").splitlines())
    new_lines = len(texts[NOTE].splitlines())
    print(f"замен: {len(R)} (заметка: {sum(p == NOTE for p, _, _ in R)}, открытые вопросы: {sum(p == OQ for p, _, _ in R)})")
    print(f"строк заметки: {old_lines} -> {new_lines}")
    print(f"wiki-ссылок в новом тексте: {len(links)}: {', '.join(links)}")
    print(f"имён кода проверено: {len(CODE_SYMBOLS)}")
    if errors:
        print("ОШИБКИ:")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    print("проверка: OK")
    if "--apply" in sys.argv:
        for path, text in texts.items():
            # Переводы строк — как были в файле (в рабочем каталоге Windows — CRLF)
            crlf = read(path)[1]
            with open(path, "w", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
                f.write(text)
        print("записано: " + ", ".join(p.name for p in texts))


if __name__ == "__main__":
    main()
