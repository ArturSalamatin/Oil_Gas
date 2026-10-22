---
tags:
  - план
  - инфраструктура
date: 2026-10-02
issue: FEAT-026
github: 47
branch: feat/feat-026/emf-figure-export
model_level: null
status: реализован
audit:
  date: 2026-10-02
  round: 1
  found: 9
  auto-fixed: 9
  manual-required: 0   # красная база (1) закрыта пользователем: 5a8ef08, 290fbfe
---

# FEAT-026: рисунки примеров дополнительно в SVG и EMF (`output/emf/`)

Реестр: [[планируемые фичи]] → FEAT-026. Issue: [#47](https://github.com/ArturSalamatin/Oil_Gas/issues/47).

## Задача

Каждый рисунок, который примеры `numerical_solver/examples/` сохраняют в `output/`, дополнительно сохраняется в `output/emf/` в двух векторных форматах: `<то же имя>.svg` и `<то же имя>.emf`. PNG не меняются. Библиотека `gpn_multiphase_solver` не меняется. Физики и формул нет — подтип «инфраструктура».

## Решения пользователя (2026-10-02)

1. **Конвертация пакетом в конце скрипта.** `save_figure` пишет PNG и SVG в `output/emf/`; `export_emf` одним запуском Inkscape переводит в EMF все SVG папки, у которых ещё нет EMF.
2. **Текст кривыми** (`svg.fonttype = "path"`) — в SVG и, следовательно, в EMF: вид как в PNG, текст в Word не редактируется.
3. **Inkscape не найден → предупреждение**, PNG и SVG сохраняются, EMF нет, пример не падает.
4. **В тестах EMF не нужен.** «emf нужны только в examples. В обычных тестах — не нужно». Вся сессия pytest идёт с выключенным EMF (`tests/conftest.py`: `GPN_EXAMPLES_EMF=0`) — в тестах не создаются ни SVG, ни EMF, Inkscape не запускается.
5. **SVG сохраняются** (уточнение после первой версии плана): «svg можно оставить. Все версии файлов (svg и emf) должны сохраняться в папке emf». SVG — не промежуточный файл, а такой же результат, как EMF.
6. **Новых тестов не создавать** (уточнение после первой версии плана). Проверка — существующие тесты (регрессия) и ручной прогон примеров с Inkscape (шаг 6). Правка `tests/conftest.py` (выключатель EMF) — не тест и остаётся.

## Факты (замеры 2026-10-02)

| Факт | Источник |
|---|---|
| matplotlib 3.11.1 не пишет EMF: avif, eps, gif, jpeg, jpg, pdf, pgf, png, ps, raw, rgba, svg, svgz, tif, tiff, webp | `plt.figure().canvas.get_supported_filetypes()` в `.venv` |
| Inkscape 1.4.3 установлен: `C:\Program Files\Inkscape\bin\inkscape.com` (консольный) и `inkscape.exe`; в PATH нет | `inkscape.com --version` |
| LibreOffice, ImageMagick не установлены | `Test-Path` |
| SVG → EMF, один рисунок (3 панели, кириллица, mathtext): 3.4 с файлом, 2.4 с через `--pipe` | `vault/issues/feat-026/probes/probe_inkscape_emf.py` |
| Пакет 8 SVG одним запуском: 4.5 с, все 8 EMF созданы рядом с SVG (`a.svg` → `a.emf`) | та же проба |
| Размер: SVG 82 кБ → EMF 157 кБ (`path`); 61 кБ → 188 кБ (`none`) | та же проба |
| EMF → PNG через Inkscape совпадает с исходным рисунком (оба режима текста) | `probe_emf_roundtrip.py`, `probes/out/*_roundtrip.png` |
| GDI+ (`System.Drawing.Imaging.Metafile`) открывает EMF: тип `Emf`, 7.01 × 8.03 дюйма = `figsize=(7, 8)` | PowerShell |
| Повторная конвертация перезаписывает существующий EMF без вопросов | PowerShell, `LastWriteTime` |
| **Inkscape возвращает код 0, даже если файл не открылся** | `inkscape.com nonexistent.svg --export-type=emf` → код 0 |
| Шрифта DejaVu Sans (шрифт matplotlib по умолчанию) в Windows нет | `C:\Windows\Fonts` |
| `output/` примеров в `.gitignore:47` (`numerical_solver/examples/**/output/`); `output/emf/` — под тем же правилом | `git check-ignore` |
| `run_example` удаляет `output/` целиком после расчёта (`example_runner.py:134–136`) — `emf/` уходит вместе с ним | код |
| Код шага 1 плана, извлечённый без правок: 9 рисунков (3 панели) одним пакетом — 4.9 с, 9 SVG + 9 EMF; второй пакет после перестройки 2 рисунков — 2.5 с, перезаписаны ровно 2 EMF; без Inkscape — предупреждение, SVG на месте, следующий вызов доделал EMF; выключено — только PNG, `emf/` нет; в SVG нет `<text` | аудит, `probes/probe_audit_scenarios.py` A–D |

## Варианты (из issue #47) и выбор

| Вариант | Суть | Итог |
|---|---|---|
| 1. matplotlib → SVG → Inkscape → EMF | внешний конвертер | **выбран** (вектор, Inkscape установлен) |
| 2. LibreOffice headless | `soffice --convert-to emf` | не установлен |
| 3. EMF-бэкенд на Python | писать EMF без внешних программ | разработка и сопровождение бэкенда; бэкенд EMF из matplotlib удалён давно |
| 4. Растровый EMF средствами Windows | PNG внутри метафайла | без векторного содержимого смысла нет |

Внутри варианта 1:

| Подвариант | Цена на пример (~9 рисунков) | Итог |
|---|---|---|
| по рисунку, `--pipe` | ≈ +22 с | отклонён (решение 1) |
| **пакетом в конце скрипта** | ≈ +5 с | **выбран** |
| `atexit`-обработчик вместо явного вызова | ≈ +5 с | отклонён (выбор Claude): неявный запуск Inkscape при выходе интерпретатора — в том числе после Ctrl+C и падения; явный вызов в конце скрипта прозрачнее |

## Архитектура

Новый модуль `numerical_solver/examples/figure_io.py` — единственное место, где вызывается `fig.savefig`. Все 18 прежних вызовов `fig.savefig(...)` заменяются на `save_figure(...)`; в конце каждого скрипта, который сохраняет рисунки, — `export_emf(<папка output>)`.

```
save_figure(fig, output/x.png, dpi)      → output/x.png
                                          → output/emf/x.svg
                                          → удаляет output/emf/x.emf прошлого прогона
...
export_emf(output)                        → «ожидающие» = output/emf/*.svg без *.emf рядом
                                          → inkscape.com --export-type=emf <ожидающие>
                                          → output/emf/*.emf  (SVG остаются)
```

**Почему «SVG без EMF» = ожидающий конвертации.** SVG остаются в `emf/` (решение 5), поэтому «все SVG папки» уже не означает «новые». `save_figure` удаляет EMF того же имени при каждом сохранении SVG, так что SVG без пары — ровно те рисунки, что сохранены после последней конвертации. Второй пакет в одном скрипте конвертирует только их; если Inkscape не нашёлся, следующий `export_emf` в той же папке их доконвертирует.

Где вызывается `export_emf`:

| Скрипт | Рисунки до вызова | Место вызова |
|---|---|---|
| `examples/example_runner.py` → `run_example` | 6–7 профилей и динамики, `relperm`, `pvt`, `energy_balance` | после `plot_energy_balance(...)` (стр. 223), до `_print_summary` |
| `examples/01_single_phase_no_jt/main.py` | перестроенные `pressure_profiles`, `temperature_profiles` | конец `if __name__ == "__main__":` |
| `examples/02_single_phase_jt/main.py` | то же | конец `__main__` |
| `examples/05_standing_table_rp/main.py` | перестроенный `temperature_profiles` | конец `__main__` |
| `examples/01_single_phase_no_jt/spatial_convergence.py` | `spatial_convergence` | конец модуля (скрипт без `main()`) |
| `examples/02_single_phase_jt/check_slopes.py` | `slopes` | конец `main()` |
| `examples/04a_high_gas_saturation/plot_profiles_50k.py` | 4 профиля `*_50k` | конец `main()` |
| `examples/05_standing_table_rp/compare_with_corey.py` | `compare_with_corey` | конец `main()` |
| `examples/05_standing_table_rp/closed_form_convergence.py` | `closed_form_convergence` | конец `main()` |
| `examples/energy_balance.py` | `energy_balance` (автономный запуск) | конец `__main__` |
| `examples/energy_balance_convergence.py` | `energy_balance_convergence` (автономный запуск) | в `__main__` перед `raise SystemExit` |
| `examples/convergence.py` → `plot_convergence` | один рисунок | внутри функции, сразу после `save_figure` (у функции нет скрипта-хозяина; сейчас её никто не вызывает) |

`plot_pvt`, `plot_relperm`, `plot_energy_balance` сами `export_emf` не вызывают: их вызывает `run_example`, который делает один пакет на все рисунки. Тесты вызывают `plot_pvt` напрямую — EMF там выключен (решение 4).

**01 и 02 перестраивают `pressure_profiles.png` и `temperature_profiles.png` после `run_example` (05 — `temperature_profiles.png`).** Порядок: `run_example` конвертирует свой пакет (в том числе первые версии этих рисунков) → `main.py` сохраняет новые PNG, `save_figure` перезаписывает SVG и удаляет устаревшие EMF → `export_emf` в конце `main.py` конвертирует только эти 2 (у 05 — 1) SVG без пары. Итог согласован с PNG. Цена — второй запуск Inkscape (≈ 3 с) у 01, 02, 05.

## Обратная совместимость

- [x] Существующие тесты: при `GPN_EXAMPLES_EMF=0` `save_figure` ≡ прежний `fig.savefig(path, dpi=dpi)`; `export_emf` без SVG ничего не делает. Имена и содержимое PNG не меняются.
- [x] Конфиги примеров не меняются.
- [x] Opt-out переменной `GPN_EXAMPLES_EMF=0`; по умолчанию EMF включён (требование пользователя: «все рисунки»).
- [x] API общих модулей (`plot_pvt`, `plot_relperm`, `plot_energy_balance`, `plot_balance_convergence`, `plot_convergence`) не меняется — ни сигнатуры, ни возвращаемые значения.
- [x] Библиотека `gpn_multiphase_solver` не затронута.

## Подводные камни

| # | Риск | Статус | Как адресован |
|---|---|---|---|
| 1 | Inkscape возвращает код 0 при ошибке | ⚠️ | успех = EMF на диске; отсутствующие перечисляются в предупреждении с хвостом stderr |
| 2 | Inkscape не в PATH | ⚠️ | поиск: `INKSCAPE` → `shutil.which("inkscape")` → `C:\Program Files\Inkscape\bin\inkscape.com`/`.exe` |
| 3 | Консоль Windows cp1251: `print` с «→», «Δ» падает с `UnicodeEncodeError` (комментарий `example_runner.py:14–28`). Поток перенастраивает только `example_runner` (при импорте); `plot_profiles_50k.py`, `check_slopes.py`, `spatial_convergence.py`, `compare_with_corey.py`, `closed_form_convergence.py`, автономные `energy_balance.py` и `energy_balance_convergence.py` его не импортируют | ⚠️ | в сообщениях `figure_io` только кириллица, латиница, цифры и ASCII-знаки; без «→», «Δ», «≈». Хвост stderr Inkscape — чужой текст: аудит воспроизвёл падение (`PYTHONIOENCODING=cp1251`, битый SVG → иероглифы в сообщении парсера → `UnicodeEncodeError`, код 1); хвост перекодируется в кодировку консоли с заменой, как в `run_all._print_safe` — после правки код 0 |
| 4 | `check_slopes.py` глушит `warnings` (`warnings.filterwarnings("ignore")`, стр. 42) | ⚠️ | предупреждения `figure_io` — через `print`, не `warnings.warn` |
| 5 | Тесты запускали бы Inkscape (3 вызова `run_example`, 3 — `plot_pvt`) | ⚠️ | `tests/conftest.py` ставит `GPN_EXAMPLES_EMF=0` на сессию: `save_figure` пишет только PNG, `export_emf` не находит SVG |
| 6 | Устаревший EMF при неудачной конвертации (PNG и SVG новые, EMF старый) | ⚠️ | `save_figure` удаляет `emf/<имя>.emf` в момент сохранения нового SVG |
| 7 | Скрипт упал между `save_figure` и `export_emf` — в `emf/` SVG без EMF | ✅ | следующий `run_example` удаляет `output/` целиком; следующий `export_emf` в той же папке доконвертирует их (SVG без пары = ожидающий). Вреда нет |
| 7а | Повторная конвертация уже готовых рисунков (SVG остаются, решение 5) | ✅ | `export_emf` берёт только SVG без EMF рядом |
| 8 | `run_example` после автономных скриптов удаляет их PNG и EMF | ✅ | так уже ведут себя PNG (`example_runner.py:129–136`); поведение не меняется |
| 9 | Пробелы в пути `C:\Program Files\...` | ✅ | `subprocess.run` со списком аргументов, без `shell=True` |
| 10 | Длина командной строки | ✅ | ≤ 10 путей по ~100 символов против предела Windows 32767 |
| 11 | Зависший Inkscape | ⚠️ | `timeout=300` с; по таймауту — предупреждение; SVG остаются, EMF нет |
| 12 | Циклические импорты | ✅ | `figure_io` импортирует только stdlib и `matplotlib` (не `pyplot`, бэкенд не выбирает) |
| 13 | Импорт `figure_io` из скриптов, которые не добавляют `examples/` в `sys.path` | ⚠️ | `plot_profiles_50k.py` и `check_slopes.py` — добавить путь (шаг 4); остальные уже добавляют |
| 14 | Производительность | ✅ | ≈ +5 с на пример (68 → ~73 с у примера 14); 01/02/05 — ещё ≈ +3 с |
| 15 | Связь с другими задачами | ⚠️ | FEAT-025 (примеры 19–21) будет использовать `run_example` — EMF получит автоматически; собственных `savefig` в плане FEAT-025 нет. Общий файл — `examples/README.md`: FEAT-025 правит таблицу времени (≈171–184) и строку `run_all.py` (≈554), этот план — абзац после стр. 209 и строку `figure_io.py` в таблице модулей (≈553). Кто вливается вторым — искать место по цитате, а не по номеру строки. С BUG-017/018 общих файлов нет. Не влитых веток задач нет (`git branch --no-merged` пуст на 2026-10-02) |
| 16 | Оценки времени в `examples/README.md` (стр. 173 «около 9 мин», таблица по примерам, стр. 554 «~9 мин») устаревают: +≈5 с на пример, у 01/02/05 ещё ≈+2.5 с | ⚠️ | числа не перемеряем (шаг 5 п. 3), но добавляем одну фразу о добавке EMF (шаг 5 п. 1) |

## Новые проблемы

- `convergence.plot_convergence` (`examples/convergence.py:128`) не вызывается ни одним скриптом — мёртвый код. Не блокирует; после реализации предложить пользователю запись DEBT (удаление или подключение).
- (аудит) На `05401a0` были красные 4 теста примера 14; пользователь починил их (`5a8ef08`, `290fbfe`) до реализации — вопрос закрыт.

---

## Как начать работу по этому плану

1. Прочитай этот файл целиком.
2. После аудита (2026-10-02) `numerical_solver/` чист на `290fbfe`; не закоммичены только файлы vault, в том числе этот план (untracked). Перед созданием ветки — `git status`: если в `numerical_solver/` есть незакоммиченные изменения, остановиться и спросить пользователя.
3. Базовая ветка — `numerical_scheme/implementation` (не `master`: в нём нет `numerical_solver/`):
   ```powershell
   cd d:\Lessons\Grants\2026\GPN\Oil_Gas
   git checkout numerical_scheme/implementation
   git checkout -b feat/feat-026/emf-figure-export
   ```
4. Baseline:
   ```powershell
   cd numerical_solver
   .venv\Scripts\python -m pytest tests/ -q
   ```
   Ожидание: **1035 тестов, все зелёные**, около 9 мин (полный прогон аудита — 537 с).

   История: на `05401a0` падали 4 теста примера 14 (`test_example14_fine_grid_first_step[100]`, `[150]`, `test_sg_step_limited_in_third_stage`, `test_matrix_matches_reference[14_high_gor_cooling]`). Пользователь починил их коммитами `5a8ef08` (замороженный сценарий BUG-016, порог сверки матрицы $10^{-12}$) и `290fbfe`; на `290fbfe` все 4 проходят (проверено после аудита: 6 passed в `TestFirstStepConverges` + `test_matrix_matches_reference[14]`), собирается 1035 тестов. Полный набор на `290fbfe` не прогонялся — замерить при старте. Если что-то красное до шага 1 — остановиться и сообщить пользователю: регрессии блокируют работу (CLAUDE.md).
5. Проверить Inkscape: `& 'C:\Program Files\Inkscape\bin\inkscape.com' --version` → `Inkscape 1.4.3 ...`.
6. Шаги 1–6 по порядку; после шагов 1–4 — pytest (регрессия). Новых тестов план не создаёт (решение 6).

---

## Шаг 1: модуль `figure_io.py`

**Цель:** одна функция сохранения рисунка (PNG + SVG) и одна функция пакетной конвертации SVG → EMF.
**Файлы:** `numerical_solver/examples/figure_io.py` (новый).

**Контекст:** matplotlib EMF не пишет (см. «Факты»). Inkscape переводит SVG в EMF; запуск дорогой (2.4 с), пакет из 8 рисунков — 4.5 с, поэтому сохранение и конвертация разнесены. SVG остаются в `emf/` рядом с EMF (решение 5).

**Что сделать:** создать файл целиком:

```python
"""Сохранение рисунков примеров: PNG + SVG и EMF в output/emf/ (FEAT-026).

matplotlib не пишет EMF (бэкенд удалён), поэтому EMF получается из SVG
внешней программой Inkscape. Схема двухфазная:

  1. save_figure — PNG, как раньше, плюс SVG в <папка PNG>/emf/;
  2. export_emf  — один запуск Inkscape на все SVG папки, у которых ещё
     нет EMF. SVG остаются: в emf/ лежат обе векторные версии рисунка.

Один запуск на пакет, а не на рисунок: запуск Inkscape стоит около 2.4 с,
пакет из 8 рисунков — 4.5 с (проба vault/issues/feat-026/probes/).

Переменные окружения:
  GPN_EXAMPLES_EMF = "0" — EMF не делать. tests/conftest.py ставит её на
                           всю сессию pytest: в тестах EMF не нужен.
  INKSCAPE               — явный путь к inkscape.com; если задана,
                           другие места не проверяются.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

ENV_SWITCH = "GPN_EXAMPLES_EMF"
ENV_INKSCAPE = "INKSCAPE"
EMF_SUBDIR = "emf"

# Стандартная установка Inkscape 1.x под Windows. inkscape.com — консольная
# версия: процесс завершается после конвертации и отдаёт вывод в консоль;
# inkscape.exe — оконная, запасной вариант.
_STANDARD_PATHS = (
    Path(r"C:\Program Files\Inkscape\bin\inkscape.com"),
    Path(r"C:\Program Files\Inkscape\bin\inkscape.exe"),
)

# Предел на один запуск Inkscape, с. Пакет примера — около 5 с; предел
# нужен только затем, чтобы зависший процесс не держал пример бесконечно.
_TIMEOUT_S = 300


def emf_enabled() -> bool:
    """EMF включён, если GPN_EXAMPLES_EMF не равна "0". FEAT-026."""
    # Читается при каждом вызове, а не при импорте: переменную можно
    # задать или снять в любой момент до сохранения рисунка.
    return os.environ.get(ENV_SWITCH, "1") != "0"


def find_inkscape() -> Path | None:
    """Путь к Inkscape: переменная INKSCAPE, PATH, стандартная установка. FEAT-026."""
    explicit = os.environ.get(ENV_INKSCAPE)
    if explicit:
        # Явно заданный путь — единственный кандидат: так можно и указать
        # нестандартную установку, и проверить поведение без Inkscape.
        p = Path(explicit)
        return p if p.is_file() else None
    found = shutil.which("inkscape")
    if found:
        return Path(found)
    for p in _STANDARD_PATHS:
        if p.is_file():
            return p
    return None


def save_figure(fig, path, dpi: int) -> Path:
    """PNG в path; при включённом EMF ещё SVG в path.parent/emf/. FEAT-026."""
    path = Path(path)
    fig.savefig(path, dpi=dpi)
    if emf_enabled():
        emf_dir = path.parent / EMF_SUBDIR
        emf_dir.mkdir(parents=True, exist_ok=True)
        # EMF прошлой версии рисунка удаляем сразу. Два следствия:
        # 1) если конвертация не удастся, в emf/ не останется EMF старше
        #    своего PNG и SVG;
        # 2) SVG без EMF рядом — признак «ждёт конвертации» для export_emf.
        (emf_dir / f"{path.stem}.emf").unlink(missing_ok=True)
        # Текст — кривыми: шрифта matplotlib (DejaVu Sans) в Windows нет,
        # Word подставил бы другой, и подписи сдвинулись бы.
        with matplotlib.rc_context({"svg.fonttype": "path"}):
            fig.savefig(emf_dir / f"{path.stem}.svg", format="svg")
    return path


def export_emf(output_dir) -> list[Path]:
    """SVG из output_dir/emf/ без пары — в EMF одним запуском Inkscape. FEAT-026."""
    emf_dir = Path(output_dir) / EMF_SUBDIR
    if not emf_dir.is_dir():
        # EMF выключен (так в тестах) или рисунков не было — молча.
        return []
    # SVG остаются в emf/ навсегда, поэтому «новые» — те, у кого нет пары:
    # save_figure удаляет EMF при каждом сохранении SVG того же имени.
    pending = [s for s in sorted(emf_dir.glob("*.svg"))
               if not s.with_suffix(".emf").is_file()]
    if not pending:
        return []
    inkscape = find_inkscape()
    if inkscape is None:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Inkscape не найден, EMF не созданы "
              f"({len(pending)} рис., SVG сохранены). Путь к inkscape.com "
              f"можно задать переменной {ENV_INKSCAPE}.")
        return []
    t0 = time.perf_counter()
    try:
        # Без output-filename: при нескольких входах Inkscape кладёт
        # a.emf рядом с a.svg. Список аргументов, без shell — пробелы
        # в "Program Files" безопасны.
        proc = subprocess.run(
            [str(inkscape), "--export-type=emf",
             *(str(s.resolve()) for s in pending)],
            capture_output=True, timeout=_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Inkscape не уложился в {_TIMEOUT_S} с, "
              f"EMF не созданы (SVG сохранены).")
        return []
    # Код возврата не проверяем: Inkscape 1.4.3 возвращает 0 и для файла,
    # который не смог открыть (проба FEAT-026). Мерило — EMF на диске.
    made = [s.with_suffix(".emf") for s in pending
            if s.with_suffix(".emf").is_file()]
    missing = [s.stem for s in pending if not s.with_suffix(".emf").is_file()]
    print(f"EMF: {len(made)} рис. в {emf_dir} "
          f"({time.perf_counter() - t0:.1f} с)")
    if missing:
        # stderr Inkscape — байты в неизвестной кодировке; хвоста хватает,
        # чтобы увидеть причину.
        tail = proc.stderr.decode("utf-8", errors="replace")[-500:]
        # Хвост переводим в кодировку консоли с заменой: в нём бывают символы,
        # которых нет в cp1251 (аудит: битый SVG дал иероглифы в сообщении
        # парсера), и print упал бы с UnicodeEncodeError уже после сохранения
        # всех рисунков. Тот же приём, что run_all._print_safe.
        enc = sys.stdout.encoding or "utf-8"
        tail = tail.encode(enc, errors="replace").decode(enc)
        print(f"ПРЕДУПРЕЖДЕНИЕ: EMF не создан для {missing}\n{tail}")
    return made
```

Пояснения для чтения кода:
- `[s for s in ... if ...]` — генератор списка: берёт из перечня SVG только те, для которых условие истинно (EMF рядом нет).
- `matplotlib.rc_context({...})` — временно меняет настройку matplotlib только внутри `with`; после блока прежнее значение возвращается.
- `*(...)` внутри списка — распаковка: пути всех ожидающих SVG становятся отдельными аргументами командной строки.
- `try: ... except subprocess.TimeoutExpired:` — перехват единственной ожидаемой ошибки запуска: процесс не завершился за `_TIMEOUT_S`.

**Проверка после шага:** `.venv\Scripts\python -c "import sys; sys.path.insert(0, 'examples'); import figure_io; print(figure_io.find_inkscape())"` (из `numerical_solver/`) → `C:\Program Files\Inkscape\bin\inkscape.com`.

**Подводные камни:** 1, 2, 3, 4, 6, 7а, 9, 11, 12.
**Зависимости:** блокирует шаги 2–6.
**Оценка:** ~100 строк, 20 мин.

---

## Шаг 2: выключить EMF в pytest

**Цель:** ни один тест не создаёт SVG/EMF и не запускает Inkscape (решение 4). Новых тестов нет (решение 6).
**Файлы:** `numerical_solver/tests/conftest.py`.

**Что сделать:** `tests/conftest.py` — после блока `_PROTO_ROOT` (стр. 9–13):

```python
# FEAT-026: SVG- и EMF-копии рисунков нужны только при запуске примеров,
# не в тестах (решение пользователя 2026-10-02): конвертация Inkscape
# добавила бы секунды к каждому run_example и plot_pvt. С "0" save_figure
# пишет только PNG, а export_emf не находит SVG и ничего не делает.
os.environ["GPN_EXAMPLES_EMF"] = "0"
```

`import os` — в общий блок импортов наверху файла (рядом с `import sys`).

**Проверка после шага:** `.venv\Scripts\python -m pytest tests/ -q` — результат = baseline (1035 passed, «Как начать» п. 4).

**Подводные камни:** 5.
**Зависимости:** требует шаг 1.
**Оценка:** 7 строк, 5 мин.

---

## Шаг 3: общие модули `examples/`

**Цель:** все рисунки `run_example` и автономных общих модулей идут через `save_figure`; `run_example` и автономные запуски вызывают `export_emf`.
**Файлы:** `numerical_solver/examples/example_runner.py`, `pvt_plot.py`, `relperm_plot.py`, `energy_balance.py`, `energy_balance_convergence.py`, `convergence.py`.

**Что сделать** (импорт `from figure_io import save_figure` или `from figure_io import save_figure, export_emf` — рядом с остальными импортами модулей примеров, с `# noqa: E402`, где соседи его имеют). Места импорта:

| Файл | Импорт | После строки |
|---|---|---|
| `example_runner.py` | `save_figure, export_emf` | 75 `from pvt_plot import plot_pvt, report_pvt  # noqa: E402` |
| `pvt_plot.py` | `save_figure` | 80 `from temperature_asymptotics import _pvt_of  # noqa: E402` |
| `relperm_plot.py` | `save_figure` | 36 `import numpy as np  # noqa: E402` |
| `energy_balance.py` | `save_figure, export_emf` | 80 `from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402` |
| `energy_balance_convergence.py` | `save_figure, export_emf` | 97 `from gpn_multiphase_solver.units import S_TO_DAY  # noqa: E402` |
| `convergence.py` | `save_figure, export_emf` | 60 (конец цикла `for _p in ...: sys.path.insert(0, _p)`) |

Замены:

| Файл | Строка | До | После |
|---|---|---|---|
| `example_runner.py` | 185 | `fig.savefig(output_dir / "well_rates.png", dpi=110)` | `save_figure(fig, output_dir / "well_rates.png", dpi=110)` |
| `example_runner.py` | 192 | `fig.savefig(output_dir / "wellbore_dynamics.png", dpi=110)` | `save_figure(fig, output_dir / "wellbore_dynamics.png", dpi=110)` |
| `example_runner.py` | 313 | `fig.savefig(path, dpi=110)` | `save_figure(fig, path, dpi=110)` |
| `pvt_plot.py` | 270 | `fig.savefig(out, dpi=120)` | `save_figure(fig, out, dpi=120)` |
| `relperm_plot.py` | 187 | `fig.savefig(out, dpi=120)` | `save_figure(fig, out, dpi=120)` |
| `energy_balance.py` | 181 | `fig.savefig(out_path, dpi=130)` | `save_figure(fig, out_path, dpi=130)` |
| `energy_balance_convergence.py` | 197 | `fig.savefig(out_path, dpi=130)` | `save_figure(fig, out_path, dpi=130)` |
| `convergence.py` | 170 | `fig.savefig(out_path, dpi=130)` | `save_figure(fig, out_path, dpi=130)` и сразу после `plt.close(fig)`: `export_emf(out_path.parent)` |

Вызовы `export_emf`:

1. `example_runner.py`, после `plot_energy_balance(history, grid, config, output_dir)` (стр. 223):
   ```python
       # ── EMF-копии рисунков (FEAT-026) ──
       # Все рисунки run_example уже сохранены (PNG + SVG в emf/):
       # один запуск Inkscape на пакет, а не на каждый рисунок.
       export_emf(output_dir)
   ```
2. `energy_balance.py`, `__main__`, после `plot_energy_balance(history, sim._grid, config, folder / "output")` (стр. 251): `export_emf(folder / "output")`.
3. `energy_balance_convergence.py`, `__main__`, после `plot_balance_convergence(...)` (стр. 252–253), **до** `raise SystemExit(...)`: `export_emf(folder / "output")`.

Импорт в `relperm_plot.py` и `pvt_plot.py`: эти модули лежат в `examples/` и импортируются только тогда, когда `examples/` уже в `sys.path` (из `example_runner` или тестов), поэтому `from figure_io import save_figure` работает без правки `sys.path`.

**Проверка после шага:**
- `.venv\Scripts\python -m pytest tests/ -q` — регрессия (EMF выключен, PNG прежние).
- Ручной прогон с EMF — на шаге 6.

**Подводные камни:** 8, 12.
**Зависимости:** требует шаг 1.
**Оценка:** ~25 строк, 20 мин.

---

## Шаг 4: скрипты примеров

**Цель:** то же для собственных рисунков примеров 01, 02, 04a, 05.
**Файлы:**
- `numerical_solver/examples/01_single_phase_no_jt/main.py` (стр. 49, 168; `__main__` 185–207)
- `numerical_solver/examples/01_single_phase_no_jt/spatial_convergence.py` (стр. 157; конец модуля)
- `numerical_solver/examples/02_single_phase_jt/main.py` (стр. 77, 268; `__main__` 290–308)
- `numerical_solver/examples/02_single_phase_jt/check_slopes.py` (стр. 218; `main()`)
- `numerical_solver/examples/04a_high_gas_saturation/plot_profiles_50k.py` (стр. 70; `main()`)
- `numerical_solver/examples/05_standing_table_rp/main.py` (стр. 89; `__main__` 93–128)
- `numerical_solver/examples/05_standing_table_rp/compare_with_corey.py` (стр. 233; `main()`)
- `numerical_solver/examples/05_standing_table_rp/closed_form_convergence.py` (стр. 158; `main()`)

**Что сделать:**

1. Каждый `fig.savefig(X, dpi=D)` → `save_figure(fig, X, dpi=D)`.
2. Импорт `from figure_io import save_figure, export_emf` после строк `sys.path.insert(...)`, которые добавляют `examples/`:
   - `01/main.py`, `02/main.py`, `05/main.py` — уже добавляют `parents[1]` (стр. 13 / 38 / 37);
   - `spatial_convergence.py` (стр. 27), `compare_with_corey.py` (стр. 72), `closed_form_convergence.py` (стр. 36) — уже добавляют;
   - **`check_slopes.py`** — добавить `sys.path.insert(0, str(SOLVER_ROOT / "examples"))` после стр. 40;
   - **`plot_profiles_50k.py`** — добавить `import sys` и `sys.path.insert(0, str(HERE.parent))` после `HERE = ...` (стр. 21); `HERE.parent` — это `examples/`.
3. `export_emf(<папка output>)` в конце:
   - `01/main.py`, `02/main.py`, `05/main.py` — последней строкой `__main__`: `export_emf(here / "output")`, с комментарием: `# Перестроенные выше рисунки — вторым пакетом: первый конвертировал run_example (FEAT-026).`
   - `spatial_convergence.py` — после `print(f"\nСохранён: {out_path}")` (стр. 159): `export_emf(out_path.parent)`.
   - `check_slopes.py` — после `print(f"\nСохранён: {out_path}")` (стр. 220): `export_emf(out_dir)`.
   - `plot_profiles_50k.py` — после цикла, перед `print(f"Моменты, с: ...")`: `export_emf(OUT)`.
   - `compare_with_corey.py`, `closed_form_convergence.py` — после `print(f"\nСохранён: {out}")`: `export_emf(out.parent)`.

**Проверка после шага:** `.venv\Scripts\python -m pytest tests/ -q`.

**Подводные камни:** 3, 4, 13.
**Зависимости:** требует шаг 1.
**Оценка:** ~30 строк, 25 мин.

---

## Шаг 5: документация

**Файлы:** `numerical_solver/examples/README.md`; vault.

1. `examples/README.md`, раздел «Что получается на выходе», после строки «Время на всех графиках — в сутках.» (стр. 209):

   > **Векторные копии рисунков (FEAT-026).** Каждый PNG дублируется в `output/emf/` в двух векторных форматах: `<имя>.svg` и `<имя>.emf` (EMF — для вставки в Word). matplotlib EMF не пишет, поэтому рисунок сохраняется в SVG, а в конце скрипта один запуск Inkscape переводит в EMF все SVG папки, у которых ещё нет EMF (около 5 с на пример). Inkscape ищется так: переменная `INKSCAPE` (путь к `inkscape.com`), PATH, `C:\Program Files\Inkscape\bin\`. Без Inkscape печатается предупреждение, PNG и SVG создаются, EMF нет. `GPN_EXAMPLES_EMF=0` отключает обе векторные копии — так делает `tests/conftest.py`. Текст в SVG и EMF — кривыми: в Word выглядит как PNG, но не редактируется. Времена прогона выше в этом README сняты без EMF: конвертация добавляет около 5 с на пример, у 01, 02 и 05 ещё около 2.5 с (второй пакет перестроенных рисунков).

2. Там же, таблица модулей (стр. ~553): строка `| [figure_io.py](figure_io.py) | сохранение рисунков: PNG + SVG и EMF в output/emf/ (FEAT-026) | — |` (формат третьего столбца — как у соседних строк).
3. Время прогона в README примеров **не** трогать: оно меняется на секунды, и замер делает `/run`.

**Зависимости:** требует шаги 3–4.
**Оценка:** ~15 строк, 10 мин.

---

## Шаг 6: ручная верификация с настоящим Inkscape

**Цель:** SVG и EMF появляются у реальных примеров, время в пределах оценки; без Inkscape — предупреждение, недостающие EMF доделываются следующим запуском. Это единственная проверка новой функциональности: новых тестов нет (решение 6).

1. Все рисунки — через `save_figure`:
   ```powershell
   cd numerical_solver
   Select-String -Path examples\*.py, examples\*\*.py -Pattern "\.savefig\(" | Select-Object Path, LineNumber
   ```
   **Ожидание:** только `examples\figure_io.py` (2 строки: PNG и SVG). На 2026-10-02 вызовы были в 15 файлах шагов 3–4 (18 вызовов).
2. Пример 14 (типовой путь `run_example`):
   ```powershell
   Measure-Command { .venv\Scripts\python examples\14_high_gor_cooling\main.py | Out-Default }
   ```
   **Ожидание:** строка `EMF: 9 рис. в ...\output\emf (... с)`, около 5 с; в `output/emf/` 9 `*.svg` и 9 `*.emf` с теми же именами, что 9 `*.png` в `output/` (`pressure_profiles`, `temperature_profiles`, `saturation_profiles`, `rs_profiles`, `well_rates`, `wellbore_dynamics`, `relperm`, `pvt`, `energy_balance`); общее время ≈ прежнее (68 с) + 5 с.
3. Пример 01 (перестройка рисунков после `run_example`): `.venv\Scripts\python examples\01_single_phase_no_jt\main.py`.
   **Ожидание:** две строки `EMF:` — `8 рис.` (у 01 нет `rs_profiles`), затем `2 рис.`; у `output/emf/pressure_profiles.{svg,emf}` и `temperature_profiles.{svg,emf}` `LastWriteTime` позже, чем у остальных файлов `emf/`.
4. Без Inkscape, затем доделка:
   ```powershell
   $env:INKSCAPE = "C:\нет\inkscape.com"; .venv\Scripts\python examples\04a_high_gas_saturation\plot_profiles_50k.py; Remove-Item Env:INKSCAPE
   ```
   (требует `04a/output/profiles.csv` — если нет, сначала `examples\04a_high_gas_saturation\main.py`). **Ожидание:** `ПРЕДУПРЕЖДЕНИЕ: Inkscape не найден, EMF не созданы (4 рис., SVG сохранены)...`; `*_50k.png` и `emf/*_50k.svg` созданы, `emf/*_50k.emf` нет.
   Повторить без переменной: `.venv\Scripts\python examples\04a_high_gas_saturation\plot_profiles_50k.py` → `EMF: 4 рис. ...`; у каждого `*_50k.svg` есть `*_50k.emf`.
5. Проверка EMF средствами Windows:
   ```powershell
   Add-Type -AssemblyName System.Drawing
   $m = [System.Drawing.Imaging.Metafile]::new((Resolve-Path examples\14_high_gor_cooling\output\emf\wellbore_dynamics.emf).Path)
   $m.GetMetafileHeader().Type; $m.Width / $m.HorizontalResolution; $m.Height / $m.VerticalResolution; $m.Dispose()
   ```
   **Ожидание:** `Emf`, 7.0 и 8.0 дюйма (`figsize=(7, 8)`).
6. Пользователю: открыть `wellbore_dynamics.emf` и `pvt.emf` в Word (Вставка → Рисунок). Визуальная приёмка — за пользователем.
7. Полный набор тестов: `.venv\Scripts\python -m pytest tests/ -q` — результат = baseline (те же passed/failed по именам, «Как начать» п. 4); время набора не выросло относительно baseline (537 с на аудите) (с `GPN_EXAMPLES_EMF=0` из `conftest.py` Inkscape в тестах не запускается — рост на секунды при каждом `run_example` указал бы на обратное).

**Зависимости:** требует шаги 1–5.
**Оценка:** 20 мин.

---

## Критерии завершения

- [ ] `examples/figure_io.py` создан; `save_figure`, `export_emf`, `find_inkscape`, `emf_enabled` с однострочными docstring и ссылкой на FEAT-026.
- [ ] 18 вызовов `fig.savefig` заменены; поиск `.savefig(` по `examples/` находит только `figure_io.py` (шаг 6 п. 1).
- [ ] `export_emf` вызывается в `run_example` и в конце каждого из 11 скриптов/функций таблицы «Где вызывается».
- [ ] `tests/conftest.py` выключает SVG/EMF в pytest.
- [ ] Новых тестов нет (решение 6); все 1035 существующих тестов зелёные.
- [ ] Ручная проверка шага 6 (п. 1–5) пройдена; п. 6 — пользователем.
- [ ] `examples/README.md` дополнен.
- [ ] Vault: статус FEAT-026 в реестре; запись DEBT про `plot_convergence` — предложить пользователю.
- [ ] Комментарий в issue #47 (`vault/issues/feat-026/05-comment-done.md`).

## Связь «требование → код → проверка»

| Требование | Код | Проверка |
|---|---|---|
| SVG и EMF каждого рисунка в `output/emf/` (решение 5) | `save_figure`, `export_emf` | шаг 6 п. 2–3 |
| Все рисунки через одну точку | замена 18 `savefig` | шаг 6 п. 1 |
| Пакетная конвертация (решение 1) | `export_emf` | шаг 6 п. 2 (одна строка `EMF:`, ≈ 5 с), п. 3 (второй пакет — только 2 рис.) |
| Текст кривыми (решение 2) | `rc_context({"svg.fonttype": "path"})` | проба: SVG с `path` — 0 элементов `<text`; глазами — шаг 6 п. 6 |
| Без Inkscape — предупреждение (решение 3) | `find_inkscape() is None` | шаг 6 п. 4 |
| Недостающие EMF доделываются | SVG без пары = ожидающий | шаг 6 п. 4, повтор |
| В тестах SVG/EMF нет (решение 4) | `tests/conftest.py` | шаг 6 п. 7 |
| Код возврата Inkscape не доверять | проверка файлов | проба: `nonexistent.svg` → код 0; в коде — сверка по файлам |
| Явный путь `INKSCAPE` | `find_inkscape` | шаг 6 п. 4 |

## Оценка

Файлов: 1 новый (`figure_io.py`), 15 изменённых (14 скриптов `examples/` + `tests/conftest.py`) + `examples/README.md`. Строк: ~100 кода, ~60 правок. Время: ~1.5 ч.

## Пробы

`vault/issues/feat-026/probes/`: `probe_inkscape_emf.py` (время, размер, пакет), `probe_emf_roundtrip.py` (EMF → PNG), `probe_audit_scenarios.py` (аудит: сценарии A–E кода шага 1; теперь импортирует настоящий `examples/figure_io.py` — после шага 1 можно прогнать как дополнительную проверку к шагу 6, вывод в `probes/audit_out/`, удалить после). Папка `probes/out/` — сгенерированные SVG/EMF/PNG проб (2.8 МБ); в git не нужна.

## Результаты реализации (2026-10-02)

Worktree `.worktrees/feat-026`, ветка `feat/feat-026/emf-figure-export` от `4bd1e8c`. Коммиты: `460e681` (vault, начало), `ea62388` (шаг 1), `a9704fd` (шаг 2), `a229677` (шаг 3), `d94b5da` (шаг 4), `078bc6c` и `9ac03c3` (шаг 5). Пока шла реализация, в базу влит BUG-017 (`9f6151a`, база `8eee600`): общих файлов нет, `git merge-tree` — без конфликтов.

| Проверка | Результат |
|---|---|
| Baseline (`4bd1e8c`) | 1035 passed, 592 с |
| После шагов 2–3 | 1035 passed, 591 с, `emf/` тесты не создают |
| После шагов 4–5 | 1035 passed, 598 с (параллельно шёл ручной прогон 01) |
| Шаг 6 п. 1: `.savefig(` в `examples/` | только `figure_io.py:76, 88` |
| Шаг 6 п. 2: пример 14 | 9 PNG, 9 SVG, 9 EMF, имена совпадают; `EMF: 9 рис. (6.4 с)`; расчёт 68.5 с, всего 85.2 с |
| То же с `GPN_EXAMPLES_EMF=0` | всего 73.1 с (расчёт 66.0 с), `emf/` нет |
| Шаг 6 п. 3: пример 01 | `EMF: 8 рис.`, затем `EMF: 2 рис.`; `pressure_profiles.emf`, `temperature_profiles.emf` — позже остальных |
| Шаг 6 п. 4: 04a `plot_profiles_50k.py` | без Inkscape — `ПРЕДУПРЕЖДЕНИЕ: Inkscape не найден ... (4 рис., SVG сохранены)`, код 0; повтор — `EMF: 4 рис.` |
| Шаг 6 п. 5: GDI+ | 13 EMF примера 04a — тип `Emf`, размер = `figsize` (7×5, 7×8, 7.5×5, PVT 18.4×9 дюйма) |
| Шаг 6 п. 6: Word | за пользователем |

**Расхождение с планом.** Цена векторных копий — **≈10 с на пример**, а не ≈5 с: план учитывал только Inkscape (6.4 с у примера 14), но не сохранение 9 SVG с текстом-кривыми (≈3 с). Замер: постобработка примера 14 — 7.1 с без копий, 16.7 с с ними. В `examples/README.md` записана замеренная цифра (`9ac03c3`).

**Отклонение от кода плана.** Модульный docstring `figure_io.py`: «`GPN_EXAMPLES_EMF = "0"` — ни SVG, ни EMF, только PNG» вместо «EMF не делать» — после решения 5 выключатель отключает обе векторные копии.

Мёртвая `convergence.plot_convergence` (и ещё три функции модуля без вызывающих) — зарегистрирован [[DEBT-031]] (решение пользователя 2026-10-02).
