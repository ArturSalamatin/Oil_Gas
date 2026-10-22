## Реализация завершена

**Ветка:** `refactor/debt-080/prototype-analysis-note-sync` (worktree `.worktrees/debt-080`, от `numerical_scheme/implementation` `aca4a5a`)
**План:** `vault/plans/debt-080 prototype-analysis-note-sync.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-080/prototype-analysis-note-sync`

### Изменения
- `vault/knowledge/decisions/hydro-prototype-анализ.md` (238 → 272 строки, +45 −11), вариант 2:
  - плашка в начале: что верно сейчас (§1–§6, §8–§12), что неполно (§7 → раздел «Действующий решатель» `модули-hydro-newton.md`), что история (абзацы «Проблема для интеграции», P1–P8);
  - шапка по коду: 16 файлов, дистрибутив `radial-blackoil 1.0.3+gpn.1`, тесты прототипа (109 на 2026-10-17), регрессия — 12 кейсов, 17 расчётов;
  - §1: имена функций вместо номеров строк; §3: аналитического якобиана в коде нет — он был частью собственного решателя, которого нет и не будет (DEBT-077);
  - §7: плашка «неполно» с перечнем недостающего (ступени 3–4, BUG-025, DEBT-055/067, `sg_activation_cap`, DEBT-040, отчёт отказа); лимит проходов по BUG-028;
  - «Решено —» / «Решено →» у абзацев «Проблема для интеграции» (§1, §2, §8, §10) и у P1–P8 со ссылками на решения;
  - таблица переиспользования: `advance` / `advance_fourth_stage`, диагностика (`pvt_range_warnings` или `relperm_range_warnings`, `Simulator._check_hydro_state`), вывод — свой.
- `vault/knowledge/decisions/открытые вопросы проектирования.md`, Q7 (+2 −2): без «A-retry при расходимости», в перечне ссылок — P6.
- Подписи обратных ссылок (P1, P2, P3, P5, P7, P8, `модули-hydro-newton.md`) проверены — верны, не менялись.

### Тесты
- Было: 2116 тестов (база после FEAT-033; план писался на 2020)
- Стало: 2116 (код не менялся)
- Быстрый уровень 1840 passed; полный 2116 passed (620 с); сторож `test_eq_references.py` 13 passed: ✅
