## Реализация завершена

**Ветка:** `refactor/debt-014/compact-history-configs` (worktree `.worktrees/debt-014`, от `numerical_scheme/implementation` `0c8f059`)
**План:** `vault/plans/debt-014 compact-history-configs.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-014/compact-history-configs`

| Коммит | Шаг |
|---|---|
| `2486c65` | 1 — `_run_schedule` отбрасывает все ключи времени |
| `c5a4cfe` | 2 — 22 конфига в краткой форме, `test_baseline_as_blocks` |
| `02d7564` | 3 — 19 README, `rewrite_history.py` удалён |
| `73c79da` | 4 — `json-config-schema.md` |

### Изменения
- 22 конфига (`examples/01…15, 19, 21`, `configs/baseline.json`, `configs/table_pvt/config.json`, `configs/val001.json`): `time.history` — объект `{duration, dt_out, <управление>}` на этап; 2337 → 80 объектов, `+174 −11724` строк. Скрипт `vault/issues/debt-014/probes/compact_history.py`; `--verify` против `0c8f059` — у всех 22 развёрнутые списки интервалов и остальной конфиг прежние.
- `tests/test_energy_balance_examples.py`: `_run_schedule` отбрасывает `_HISTORY_TIME_KEYS`, а не только `dt`.
- `tests/test_config.py`: `test_baseline_as_blocks` сверяет baseline с явными 96 объектами и проверяет, что сам конфиг — краткой формой; комментарий `TestBaselineTime`.
- `examples/04a_high_gas_saturation/rewrite_history.py` удалён; 19 README — где сказано, какое поле расписания править (скрипт `fix_readmes.py`, 39 замен).
- `vault/knowledge/decisions/json-config-schema.md`: абзац о форме конфигов репозитория.

Не тронуты: примеры 16, 17, 20 (уже краткие), 18 (конфиг пишет конвертер книги прототипа), `tests/data/*`, пакет `gpn_multiphase_solver/`, прототип.

### Тесты
- Было: 1688 (база с влитым VAL-004)
- Стало: 1687 (−1: параметризация `test_script_names_resolve` по удалённому `rewrite_history.py`)
- Быстрый уровень: 1416 passed; полный прогон: 1687 passed (678 с)
- Все зелёные: ✅
