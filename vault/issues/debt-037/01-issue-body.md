## Описание

Тест-защита от копий общих модулей примеров (`TestSharedChecks.test_no_duplicate_helper_scripts`) проверяет только пять модулей из ручного списка `SHARED_CHECK_MODULES`. Шесть общих модулей из `numerical_solver/examples/`, которые импортируются примерами, не защищены. Среди них `example_runner.py`: его импортирует `main.py` каждого из 20 примеров. Приоритет низкий: сейчас ни одной копии нет (проверено 2026-10-07).

## Текущее состояние

`numerical_solver/tests/test_examples.py:620-626`:

```python
SHARED_CHECK_MODULES = [
    "energy_balance.py",
    "energy_balance_convergence.py",
    "temperature_asymptotics.py",
    "two_phase_analytics.py",
    "pvt_plot.py",
]
```

- `test_no_duplicate_helper_scripts` (стр. 728-741) параметризован этим списком. Для каждого модуля он проверяет, что в `examples/*/` нет файла с тем же именем.
- `test_shared_modules_exist` (стр. 743-747) проверяет, что `SHARED_CHECK_MODULES + ["convergence.py"]` лежат в `examples/`.

Чем опасна копия общего модуля в папке примера, зависит от порядка `sys.path`, а он у скриптов разный (проверено 2026-10-07). В записи реестра сказано «`main.py` ставит папку примера впереди `examples/`», но это верно только для части файлов:

| Порядок | Файлы | Что делает копия |
|---|---|---|
| сначала `examples/`, затем папка примера, и папка оказывается впереди | `main.py` примеров 01, 02, 03, 05 (`03_standing_corey/main.py:38, 40`); `04_table_table/grid_convergence.py:50-51`, `04a_high_gas_saturation/grid_convergence.py:46-48`, `05_standing_table_rp/closed_form_convergence.py:36-37` | **молча перекрывает** общий модуль |
| вставляется только `examples/`, и он оказывается впереди каталога скрипта (`sys.path[0]` при запуске `python main.py`) | `main.py` остальных 16 примеров (04, 04a, 06–21), `01_single_phase_no_jt/spatial_convergence.py`, `02_single_phase_jt/check_slopes.py`, `04a_high_gas_saturation/plot_profiles_50k.py` | **молча игнорируется**: правка копии ни на что не влияет |

Оба исхода молчаливые. Перекрытие к тому же транзитивно: копия `figure_io.py` в папке 05 подменит модуль и для `example_runner.py`, `energy_balance.py`, `pvt_plot.py`, `relperm_plot.py`, `convergence.py`, потому что все они делают `from figure_io import ...` через тот же `sys.path`. Именно так четыре разошедшиеся копии `energy_balance.py` дали BUG-004 (#21).

Без защиты (все 15 файлов `examples/*.py`, кроме пяти из списка):

| Модуль | Кто импортирует | Откуда взялся |
|---|---|---|
| `example_runner.py` | `main.py` всех 20 примеров, `04_table_table/grid_convergence.py`, `04a_high_gas_saturation/grid_convergence.py` | — (наличие проверяется отдельно, `test_examples.py:161`) |
| `figure_io.py` | `example_runner.py`, `energy_balance.py`, `energy_balance_convergence.py`, `pvt_plot.py`, `relperm_plot.py`, `convergence.py`, `main.py` 01, 02, 05 и скрипты 01, 02, 04a, 05 | FEAT-026 (#47) |
| `rs_analytics.py` | `example_runner.py`, `04_table_table/grid_convergence.py` | до FEAT-016 |
| `closed_form.py` | `example_runner.py`, `two_phase_analytics.py`, `grid_convergence.py` 04 и 04a | до FEAT-016 |
| `relperm_plot.py` | `example_runner.py`, `05_standing_table_rp/main.py` | до FEAT-016 |
| `convergence.py` | `energy_balance_convergence.py`, `04a_high_gas_saturation/grid_convergence.py` | — (проверяется только на наличие, `test_examples.py:745`) |
| `run_all.py`, `compare_script_copies.py`, `check_energy_balance_all.py`, `verify_balance_vs_solver.py` | никто: это скрипты, не модули | — |

Проблема в механизме, а не в отдельной недосмотренной строке. Список ведётся вручную, и при выносе нового общего модуля его забывают дополнить. `figure_io.py` появился в FEAT-026 уже после FEAT-016 и в список не попал.

## Целевое состояние

- Копия любого общего модуля `examples/*.py` в папке примера роняет быстрый уровень тестов и называет модуль и папку.
- Новый общий модуль попадает под защиту без ручной правки списка.
- Комментарий над списком (стр. 614-619) описывает все общие модули, а не только модули проверок FEAT-016.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `numerical_solver/tests/test_examples.py` | 610-626 | заголовок раздела I, комментарий, `SHARED_CHECK_MODULES` |
| `numerical_solver/tests/test_examples.py` | 728-741 | `test_no_duplicate_helper_scripts` |
| `numerical_solver/tests/test_examples.py` | 743-747 | `test_shared_modules_exist` |
| `numerical_solver/tests/test_examples.py` | 161 | отдельная проверка наличия `example_runner.py` |
| `numerical_solver/examples/{01,02,03,05}_*/main.py`, три скрипта сходимости 04, 04a, 05 | см. таблицу порядка `sys.path` | порядок `sys.path.insert` — источник перекрытия (вариант 3) |

Строки в записи реестра (610-616) сдвинулись: список теперь на 620-626.

## Анализ вариантов решения

### Вариант 1: дополнить ручной список

- **Суть.** Добавить в `SHARED_CHECK_MODULES` `rs_analytics.py`, `closed_form.py`, `relperm_plot.py`, `figure_io.py`, `convergence.py`, `example_runner.py`, а `+ ["convergence.py"]` в `test_shared_modules_exist` убрать.
- **Изменения.** `test_examples.py:620-626`, 745, комментарий 614-619.
- **Плюсы.** Минимальная правка. Список явный, его видно при чтении.
- **Минусы.** Механизм, из-за которого появился этот долг, остаётся: следующий вынесенный модуль снова забудут. `test_shared_modules_exist` начинает дублировать проверку на стр. 161 и ImportError. Сейчас `example_runner.py` импортирует четыре модуля на уровне модуля, и при отсутствии любого из них все примеры падают с ImportError.

### Вариант 2: список для проверки копий строится по `examples/*.py` (рекомендуется)

- **Суть.** Параметр `test_no_duplicate_helper_scripts` вычисляется при сборке тестов: `sorted(p.name for p in EXAMPLES_DIR.glob("*.py"))`, то есть все 15 файлов верхнего уровня `examples/`. Ручной `SHARED_CHECK_MODULES` остаётся только для `test_shared_modules_exist`. Там glob бесполезен: файл, найденный glob-ом, существует по построению.
- **Изменения.** `test_examples.py`: новая константа рядом со стр. 620, параметризация на 728, комментарий 614-619. Решить в плане, дополнять ли список наличия (см. минусы варианта 1).
- **Плюсы.** Новый общий модуль защищён автоматически, без правки списка, то есть причина долга устранена. Ложных срабатываний сейчас нет: ни одно из 15 имён в `examples/*/` не встречается. Тесты быстрые, фикстура `results` не нужна, метку `slow` хук `conftest.py:35-40` не ставит.
- **Минусы.** Под проверку попадают и 4 скрипта (`run_all.py` и др.), хотя их копия ничего не перекрывает. Это лишняя строгость без ложных срабатываний. Если когда-нибудь понадобится локальный модуль с именем общего, его придётся явно исключить. Идентификаторы параметров теста меняются.

### Вариант 3: убрать перекрытие в корне, поменяв порядок `sys.path`

- **Суть.** В 7 файлах из первой строки таблицы порядка поменять местами вставки: `examples/` впереди папки примера, как уже сделано у остальных 16 `main.py`. Тогда общий модуль выигрывает у копии.
- **Изменения.** `main.py` 01, 02, 03, 05 и три скрипта сходимости 04, 04a, 05.
- **Плюсы.** Порядок `sys.path` становится единым, и перекрытие общего модуля исчезает.
- **Минусы.** Ошибка не исчезает, а меняет вид: копия молча игнорируется, как сейчас у 16 примеров, и разошедшаяся копия по-прежнему никого не насторожит. Понадобится проверить, что у этих четырёх примеров нет собственных модулей с именами общих: сейчас их нет. Новый скрипт со старым порядком вернёт проблему, тест этого не ловит. Вариант 3 дополняет вариант 2, но не заменяет его.

**Рекомендация:** вариант 2. Тест ловит копию при любом порядке `sys.path`, то есть и в случае перекрытия, и в случае игнорирования. Вариант 3 решить в плане как необязательный: единый порядок полезен, но без теста не защищает. Дополнять ли список наличия, тоже решается в плане.

## План решения

1. **Подготовка (baseline).** Из `numerical_solver/`:
   - `.venv\Scripts\python -m pytest tests/ --collect-only -q`: число тестов;
   - `.venv\Scripts\python -m pytest tests/test_examples.py -k "duplicate_helper or shared_modules_exist" -q`: сейчас 5 + 1 passed.
2. **Реализация.**
   - Константа со списком `examples/*.py` и параметризация `test_no_duplicate_helper_scripts` по ней.
   - Комментарий над списками: защищаются все общие модули, перекрытие транзитивно, почему glob, а не ручной список (DEBT-037).
   - `test_shared_modules_exist`: по решению плана.
3. **Верификация.**
   - Отрицательная проверка вручную: скопировать `figure_io.py` в папку `01_single_phase_no_jt/`. Тест должен упасть с именем модуля и папки. Копию удалить.
   - Быстрый уровень `pytest tests/ -m "not slow" -q` зелёный. Число тестов выросло на 10 (5 → 15 параметров), если список наличия не меняется.
   - Полный прогон не нужен: изменение не затрагивает решатель и примеры.

## Ветка

`refactor/debt-037/shared-modules-copy-guard`

## Связанные issues

Related: #56 (DEBT-026: при его планировании обнаружено, затрагивался `rs_analytics.py`), #22 (FEAT-016), #21 (BUG-004), #47 (FEAT-026: `figure_io.py`)

## Связанные заметки в vault

- `vault/roadmap/известные баги и технический долг.md`, запись DEBT-037
- `vault/knowledge/decisions/проверка выносится в общий модуль если не зависит от комбинации PVT и ОФП.md`: таблица вынесенных модулей
