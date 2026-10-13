## Реализация завершена

**Ветка:** `refactor/debt-057/energy-porosity-pressure` (worktree `.worktrees/debt-057`, от `numerical_scheme/implementation` `080d3ba`)
**План:** `vault/plans/debt-057 energy-porosity-pressure.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-057/energy-porosity-pressure`

### Изменения
- `numerical_solver/doc/problem_statement.tex`: новая метка `eq:porosity` — $\varphi(p) = \varphi_0 e^{c_r(p - p_0)}$, «постоянная пористость» убрана из допущений, обозначений, упрощения гидродинамики и невязок (`eq:residual_oil/gas` — с $\varphi^{n+1}$, $\varphi^n$, как считает прототип); `eq:main_rhocpeff`, `eq:lambda_eff` — скелет и замыкание с $\varphi_0$; `eq:main_Qad_muJT`, `eq:Qad_muJT` — без членов $c_r(p + (\rho c_p)_s T)$; вывод энергии (`app:energy_derivation`): работа флюида над стенками пор $p\,\partial_t\varphi$ и постоянная масса скелета, абзац «Проверка: обратимое адиабатическое сжатие».
- `energy/tridiag.py`: `TridiagEnergySolver(grid, pvt, rock, p_ref=None)` (при $c_r \ne 0$ `p_ref` обязателен) и `porosity(p)`; флюид — $\varphi(p^{n+1})$ в $(\rho c_p)_{eff}$, $Q_{ad}$ и временной части $\dot m$ (`compute_degassing(..., p=p)`), скелет и $\lambda_{eff}$ — $\varphi_0$; при $c_r = 0$ — прежний скаляр.
- `factory.py`: энергия получает `p_ref = initial_conditions.p0` — то же, что порода прототипа.
- `tests/test_energy_matrix_examples.py`: эталон сверки матрицы энергии — `_ref_porosity` по `eq:porosity`.
- `tests/test_energy_porosity.py` (новый, 9 тестов): закон $\varphi(p)$ против `CompressibleRock`, отказ без `p_ref`, где стоит $\varphi(p)$ и где $\varphi_0$, поровый объём энергии = прототипа на конфиге 18, $\dot m$ против выделения газа гидродинамикой (первые сутки примера 18).
- Комментарии `io/config.py`, `energy/balance.py`; `examples/verify_balance_vs_solver.py` — вызов как в `solve`.
- Пример 18: `test_wellbore_cools`, README 18 (таблица $T(r_w) - T_0$, баланс энергии, абзац о пористости), `examples/README.md` (невязка).

### Тесты
- Было: 1912 тестов
- Стало: 1921 (+9 новых)
- Все зелёные: ✅ — полный прогон 1921 passed (535 с), быстрый уровень 1648 passed

### Метрики (пример 18 — единственный конфиг с $c_r \ne 0$)
| Метрика | Значение | Ожидание плана | Статус |
|---|---|---|---|
| отпечаток истории $T$ | `fd040715fc926897` | `fd040715fc926897` (проба B) | ✅ |
| $T(r_w) - T_0$: min / конец | −0.6419 / −0.4887 К (было −0.6431 / −0.4892) | ±2e-3 к −0.6419 / −0.4887 | ✅ |
| $\max|\Delta T(r_w)|$ к прежнему коду | 1.29 мК | — (шаг 1800 с против 3600 с — до 2.2 мК) | — |
| невязка баланса энергии | 5.53e-15 | ≤ 1e-12 | ✅ |
| $\dot m$ − выделение газа − остаток DEBT-066, первые сутки | −9.5e-10 (было 6.7e-4) | < 1e-7 | ✅ |
| снимок 23 примеров | 22 побайтно; у 18 — 5 строк баланса энергии и файлы с $T$ | то же | ✅ |

Прототип не менялся. Остаток правила Лейбница во времени в $\dot m$ — DEBT-066, знак $c_r$ — DEBT-068.
