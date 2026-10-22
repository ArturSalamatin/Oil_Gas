### План готов

План: `vault/plans/debt-051 config-numeric-fields-finite.md`. Ветка: `refactor/debt-051/config-numeric-fields-finite`. Шагов: 3.

**⚠️ Поправка к описанию issue.** Утверждение «молча неверного расчёта не найдено» опровергнуто красной пробой (`vault/issues/debt-051/probes/red_state.py`, `d3aabff`, вывод `red_state.out.txt`; `configs/baseline.json`, 24 ч):
- `numerics.skin` = ±inf и `history.p_wf` = +inf — расчёт проходит, скважина не добывает ($p$ = 20 МПа во всём пласте);
- `history.min_bhp` = NaN при активном ограничении (1000 м³ст/сут, `min_bhp` = 15 МПа) — ограничение снято молча: забой 7.12 МПа, $S_{g,\max}$ = 0.091 (эталон — 15.03 МПа, газа нет);
- `history.q_oil` = +inf, `time.dt_integration` = +inf — тоже проходят без отказа.

Приоритет в реестре поднят до среднего. Кроме того: NaN в 13 полях — отказ после дробления до dt/512 с советом увеличить `max_retries`; inf в `rho_o_std`, `T0`, `Rs0` — ложное «пересыщено газом»; строка или `null` — `TypeError` без имени; `true` в `permeability` — 1 м².

**Решения пользователя (2026-10-10):**
1. Заодно проверка типа: строка, `null`, `true`/`false` в float-поле → `ValueError` с именем (`null` допустим в `Optional[float]`).
2. Общий проход — по всем секциям, включая `thermal`; цикл конечности DEBT-049 удаляется (стал бы недостижим). Проверки диапазона DEBT-047 и предупреждения о знаке остаются.
3. Существующие сообщения `_validate` не менять.
4. `CoreyRP` не трогать.

**Решение:** поля выбираются по аннотациям dataclass (`float`, `Optional[float]`) — новое поле проверяется без правки кода; `_require_finite_number`, `_check_numeric_fields` в `io/config.py`; вызовы в начале `_validate`, `_validate_interval` (имя `history[i].<поле>`) и в `_expand_history` для `duration`/`dt_out`.

**Шаги:** 1 — тесты (98, `TestValidationNumbers`) и код; 2 — P8 §5, заметка DEBT-049; 3 — зелёный замер, vault.

**Код плана проверен подменой** (`plan_check.py`, вывод `plan_check.out.txt`): 13 правок применимы; новые тесты на текущем коде — 90 failed, 8 passed, на коде с правками — 245 passed (весь `test_config.py`); все 58 испорченных случаев пробы — `load_config: ValueError` с именем поля, четыре эталона без изменений; быстрый уровень существующих тестов — 1244 passed.

Ожидание: 1494 → 1592 тестов, быстрый уровень 1244 → 1342. Прототип не меняется.
