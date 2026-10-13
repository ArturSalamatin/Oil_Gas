### План готов

План: `vault/plans/feat-030 run-command-from-config.md`. Ветка: `feat/feat-030/run-command-from-config`. Шагов: 10 (0–9). Модель: — (инфраструктура, новых формул нет).

**Решения пользователя (2026-10-13):**
- параметры примера — поля секции `output` конфига: `title`, `n_profiles`, `steady_state`, `closed_form_overlays`; флаги `--title`, `--profiles` их переопределяют;
- `steady_state` по умолчанию `false`: замкнутое решение и асимптотика $T$ — пределы $t \to \infty$ одного режима; 15 примеров, где аналитика работает, получают явное `true`;
- каталог вывода очищается целиком, как сейчас; отказ с кодом 2 до расчёта, если внутри каталога вывода лежит конфиг или его CSV;
- EMF — как сейчас (`GPN_EXAMPLES_EMF`, `INKSCAPE`);
- `python -m gpn_multiphase_solver run config.json [--output DIR] [--title T] [--profiles N]` и `gpn-solver run …`; коды возврата 0 / 1 (решатель отказал) / 2 (аргументы или конфиг).

**Устройство:** `examples/example_runner.py` → `gpn_multiphase_solver/report/pipeline.py` (`run_case`, `CaseResult` с решателем); семь модулей печати и рисунков → `report/`; `figure_io.py` → `io/figures.py`; модули пакета не трогают matplotlib и консоль при импорте — это делает `cli.configure_batch_run()`. `main.py` остаются у 01–05 и 18 (своя логика, без второго `Simulator`), у 17 примеров удаляются.

**Проверка неизменности:** снимок вывода 23 примеров (печать + побайтно `output/`) до переноса, после шага 5 (через временную обёртку `run_example` → `run_case`) и после шага 7 (17 примеров — командой). Приёмка: колёса → новое окружение → команда из постороннего каталога, коды 0/2, `gpn-solver.exe`.

**Тесты:** ≈ N0 − 25 (+36 новых: `test_cli.py` 13, `test_figures.py` 3 — в том числе поведение без Inkscape, поля `output` 14, `run_case` 4, примеры 2; −61 параметр за удалённые скрипты `examples/`).

**Порядок:** начинать после влития DEBT-065 (#106) и FEAT-032 (#103) — они правят те же README, конфиги 16/17, `config.py`.

Пробы: `vault/issues/feat-030/probes/` — `factory_warnings.py` (второй `Simulator` в 01–05/18 предупреждений не печатает), `add_output_fields.py` (поля `output` в 23 конфигах, проверено без записи), `snapshot_examples.py`.
