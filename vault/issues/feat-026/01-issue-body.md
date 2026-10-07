## Описание

Каждый рисунок, который примеры `numerical_solver/examples/` сохраняют в `output/`, дополнительно сохраняется в формате EMF в папку `output/emf/` с тем же именем и расширением `.emf`. Существующие PNG остаются без изменений.

## Мотивация

Запрос пользователя (2026-10-02). Фаза: примеры и демонстрация. Библиотека `gpn_multiphase_solver` не меняется.

## Физическое/математическое обоснование

Не применимо: задача касается только вывода рисунков.

## Факты на момент открытия

- matplotlib 3.11.1 (`.venv` `numerical_solver`) не пишет EMF. Поддерживаемые форматы: avif, eps, gif, jpeg, jpg, pdf, pgf, png, ps, raw, rgba, svg, svgz, tif, tiff, webp.
- Inkscape 1.4.3 установлен: `C:\Program Files\Inkscape\bin\inkscape.com` (консольный) и `inkscape.exe`. В PATH отсутствует.
- LibreOffice и ImageMagick не установлены.
- `output/` примеров исключён из git (`.gitignore:47`, `numerical_solver/examples/**/output/`); `output/emf/` попадает под то же правило.
- `run_example` удаляет `output/` целиком после расчёта (`example_runner.py:134–136`); `output/emf/` очищается вместе с ним.
- `convergence.plot_convergence` (`convergence.py:128`) ни одним скриптом не вызывается; `convergence.py` импортируют только ради `run_series`.

## Предлагаемый API

Одна функция сохранения рисунка в `examples/` вместо прямых вызовов `fig.savefig(...)`:

```python
save_figure(fig, path, dpi)  # PNG в path, EMF в path.parent / "emf" / (path.stem + ".emf")
```

Окончательная сигнатура, имя модуля и поведение при отсутствии конвертера — на этапе планирования.

## Зависимости

Нет.

## Затронутые файлы

| Файл | Строки | Роль |
|---|---|---|
| `examples/example_runner.py` | 185, 192, 313 | `well_rates.png`, `wellbore_dynamics.png`, профильные графики |
| `examples/energy_balance.py` | 181 | `energy_balance.png` |
| `examples/pvt_plot.py` | 270 | `pvt.png` |
| `examples/relperm_plot.py` | 187 | `relperm.png` |
| `examples/energy_balance_convergence.py` | 197 | `energy_balance_convergence.png` |
| `examples/convergence.py` | 170 | `plot_convergence` (не вызывается) |
| `examples/01_single_phase_no_jt/main.py` | 49, 168 | `pressure_profiles.png`, `temperature_profiles.png` |
| `examples/01_single_phase_no_jt/spatial_convergence.py` | 157 | `spatial_convergence.png` |
| `examples/02_single_phase_jt/main.py` | 77, 268 | `pressure_profiles.png`, `temperature_profiles.png` |
| `examples/02_single_phase_jt/check_slopes.py` | 218 | `slopes.png` |
| `examples/04a_high_gas_saturation/plot_profiles_50k.py` | 70 | профильные графики (в цикле по именам файлов) |
| `examples/05_standing_table_rp/main.py` | 89 | `temperature_profiles.png` |
| `examples/05_standing_table_rp/compare_with_corey.py` | 233 | `compare_with_corey.png` |
| `examples/05_standing_table_rp/closed_form_convergence.py` | 158 | `closed_form_convergence.png` |
| `tests/test_examples.py` | 489–501 | список ожидаемых файлов `run_example` |

Всего 18 вызовов `savefig`; все пишут в `output/` своего примера (кроме `plot_convergence`, путь задаёт вызывающий).

## Анализ вариантов решения

### Вариант 1. matplotlib → SVG → Inkscape → EMF

- **Суть:** рисунок сохраняется в SVG, Inkscape CLI конвертирует его в EMF (`--export-type=emf`).
- **Изменения:** функция сохранения + замена 18 вызовов `savefig`.
- **Плюсы:** векторный EMF; Inkscape уже установлен; качество зависит от зрелого конвертера.
- **Минусы:** внешняя зависимость вне Python; путь к Inkscape не в PATH; запуск процесса на каждый рисунок (или пакетный режим); промежуточный SVG надо где-то держать (в папке проекта, не во временном каталоге) или передавать через `--pipe`.

### Вариант 2. LibreOffice headless

- **Суть:** `soffice --headless --convert-to emf`.
- **Минусы:** LibreOffice не установлен.

### Вариант 3. Собственный EMF-бэкенд matplotlib на Python

- **Суть:** писать EMF из Python без внешних программ (бэкенд EMF в matplotlib давно удалён).
- **Плюсы:** нет внешних зависимостей.
- **Минусы:** разработка и сопровождение бэкенда; доступность и состояние сторонних пакетов требуют проверки.

### Вариант 4. Растровый EMF (PNG внутри метафайла) средствами Windows

- **Минусы:** EMF без векторного содержимого не даёт преимуществ перед PNG.

**Рекомендация:** вариант 1 с единой функцией сохранения рисунка. Поведение при отсутствии Inkscape (ошибка или предупреждение), способ поиска пути, текст как кривые или как текст в SVG — решить при планировании.

## План реализации

1. **Проектирование:** функция сохранения, поиск Inkscape, поведение без конвертера, передача SVG.
2. **Ядро:** функция сохранения + проверка на одном рисунке.
3. **Тесты:** для каждого PNG в `output/` есть одноимённый непустой `.emf` в `output/emf/`; поведение без Inkscape.
4. **Интеграция:** замена 18 вызовов `savefig`, обновление `tests/test_examples.py`, README примеров.
5. **Верификация:** полный набор тестов, прогон примеров, открытие EMF в Word.

## Ветка

`feat/feat-026/emf-figure-export`

## Связанные issues

Нет.

## Связанные заметки в vault

- `vault/roadmap/планируемые фичи.md` — FEAT-026
