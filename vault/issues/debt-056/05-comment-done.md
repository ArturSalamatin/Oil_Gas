## Реализация завершена

**Ветка:** `refactor/debt-056/skin-bhp-range-check` (worktree `.worktrees/debt-056`, от `numerical_scheme/implementation` `595869b`)
**План:** `vault/plans/debt-056 skin-bhp-range-check.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-056/skin-bhp-range-check`

### Изменения
- `numerical_solver/gpn_multiphase_solver/io/config.py`:
  - `_validate`, после проверок породы: `numerics.skin < 0` → `ValueError` «отрицательный скин в проекте не предусмотрен». В сообщении — обход `geometry.r_well` = $r_w e^{-s}$, `skin` = 0 (приведённый радиус скважины: тот же установившийся однофазный приток) и оговорка, что температура забоя тогда относится к $r_w e^{-s}$; при $r_w e^{-s} \ge R_{ext}$ — «обход неприменим» (сравнение в логарифмах, без переполнения при $s = -10^{300}$).
  - `_warn_large_skin`: $s > 50$ → предупреждение с долей установившегося притока $\ln(R_{ext}/r_w)/(\ln(R_{ext}/r_w)+s)$.
  - `_warn_well_shut`: `p_wf` $\ge p_0$ или `min_bhp` $\ge p_0$ при `q_oil > 0` → предупреждение `history[i]: …`, одно на объект `time.history`; `q_oil = 0` (намеренный останов) — без предупреждения. `_expand_history` возвращает ещё пары (место в JSON, образец).
  - Оба предупреждения — после `_validate`: не выдаются перед отказом ни по одному полю.
- `numerical_solver/tests/test_config.py`: класс `TestValidationWell`, 22 теста.
- `numerical_solver/doc/problem_statement.tex`: абзац о скине у проводимости забойной грани, $s \ge 0$, приведённый радиус.
- `vault/knowledge/decisions/P8-формат-ввода-json.md`: §5 переписан по коду (кто проверяет ввод: config, фабрика, прототип только повторяет), пункт «Скважина».
- Две заметки `vault/knowledge/debugging/` — DEBT-056 закрыт.

Прототип не менялся. Расчётный код не менялся.

### Тесты
- Было: 1592 теста (быстрый уровень 1342 passed, 78 с)
- Стало: 1614 (+22); быстрый уровень 1364 passed; полный прогон — 1614 passed (519 с)
- По шагам: красные тесты — 14 failed / 8 passed (как в плане); после скина — 18 / 4 (упали только тесты забоя); после забоя — 22 passed

### Замеры
| Проверка | До | После |
|---|---|---|
| $s$ = −0.01, −0.5, −2 (baseline, 24 ч, проба `skin_range.py`) | −0.01 — расчёт; −0.5, −2 — `RuntimeError` после дробления до dt/512 | `load_config: ValueError: numerics.skin = … < 0` |
| прочие случаи пробы ($s$ = 0, 5, 50, 1e3, 1e6; `p_wf`, `min_bhp` = 25 МПа) | — | числа совпадают построчно (`skin_range_green.out.txt`) |
| конфиги проекта через `load_config` (`configs_scan.py`) | 30, замечаний 0 | 30, замечаний 0 |
| `problem_statement.tex` | собирается | собирается, ошибок и неопределённых ссылок 0 |
