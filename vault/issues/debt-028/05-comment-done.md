## Реализация завершена

**Ветка:** `refactor/debt-028/compute-fluxes-shutin-upwind` (worktree `.worktrees/debt-028`, от `38df988`)
**План:** `vault/plans/debt-028 compute-fluxes-shutin-upwind.md`
**Коммиты:** `git log --oneline numerical_scheme/implementation..refactor/debt-028/compute-fluxes-shutin-upwind`

```
4bf5fbf vault: DEBT-028 реализован — …; DEBT-021 закрыт
e66f97c refactor: адаптер прототипа считает Q, u, m, Gm общим шагом phase_fluxes_from_components; ячейка выше по потоку — по перепаду давления
ee13c81 refactor: общий шаг Q, u, m, Gm из G — fluxes.phase_fluxes_from_components; compute_fluxes считает только G; rho_g на контуре — rho_g(p_ext)
1bc3860 fix: compute_fluxes закрывает скважину при p[0] <= p_wf по eq:bc_pwf_shutin
d1e932e test: двухфазная фикстура test_fluxes — добыча при p_wf = 6 МПа
925a7f5 vault: DEBT-028 начало реализации
```

### Изменения
- `gpn_multiphase_solver/fluxes.py`: новая `phase_fluxes_from_components` — шаг «Q, u, m, Gm из G» для обоих гидро-путей; ячейка выше по потоку — по $\Delta p$ (как в прототипе); на контуре при притоке $\rho_g(p_{ext})$ (DEBT-021). `compute_fluxes` считает только $G$ по Дарси и закрывает скважину при $p[0] \le p_{wf}$ (`eq:bc_pwf_shutin`), `p_wf = p[0]`.
- `gpn_multiphase_solver/hydro/prototype_adapter.py`: `_build_result` — $G$ от прототипа + общая функция (−75 строк).
- `gpn_multiphase_solver/energy/tridiag.py`: два комментария (ссылки на строки `fluxes.py` → на функции).
- Тесты: `test_fluxes.py` — фикстура на добычу, `TestWellShutIn` (14), `TestPhaseFluxesFromComponents` (3), эталон с закрытием и $\rho_g(p_{ext})$; `test_prototype_adapter.py` — `TestUpstreamWithZeroKro` (1), правило выбора ячейки в 4 тестах; `test_energy.py`, `test_energy_matrix_examples.py` — устаревшие ссылки на DEBT-019.

### Проверки
- Новые тесты сначала красные: `TestWellShutIn` 12 failed; `TestUpstreamWithZeroKro` — $Q_g[1] = -0.23951$ ($G\cdot B_g[0]$, ячейка ниже по потоку) вместо $-0.23777$, 0.73 % — расхождение адаптера с прототипом при $k_{ro} = 0$ подтверждено.
- Истории 20 примеров (код worktree до/после): **20 × побитово** по $p, S_g, R_s, T, G, Q, u, m$.
- Прототип не менялся.

### Тесты
- Было: 1223
- Стало: 1241 (+18)
- Полный прогон: 1241 passed, 527 с ✅; быстрый уровень 1017 passed

DEBT-021 закрыт этой веткой.
