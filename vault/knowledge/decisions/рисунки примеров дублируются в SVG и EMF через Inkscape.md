---
tags: [решение, примеры, визуализация]
date: 2026-10-02
source: FEAT-026
---

# Рисунки примеров дублируются в SVG и EMF через Inkscape

Каждый рисунок примеров `numerical_solver/examples/` сохраняется как PNG в `output/` и дополнительно — как `<имя>.svg` и `<имя>.emf` в `output/emf/` ([[feat-026 emf-figure-export]], FEAT-026).

**Почему так.** matplotlib EMF не пишет: бэкенд удалён, поддерживаются avif, eps, gif, jpeg, pdf, pgf, png, ps, raw, rgba, svg, svgz, tif, webp (matplotlib 3.11.1). EMF получается из SVG внешней программой Inkscape 1.4.3 (`C:\Program Files\Inkscape\bin\inkscape.com`, вне PATH). LibreOffice и ImageMagick на машине нет.

**Как устроено** (`gpn_multiphase_solver/io/figures.py`; до FEAT-030 — `examples/figure_io.py`):
- `save_figure(fig, path, dpi)` — единственное место с `fig.savefig`: PNG + SVG (текст кривыми, `svg.fonttype = "path"`: шрифта DejaVu Sans в Windows нет); удаляет EMF прошлой версии рисунка.
- `export_emf(output_dir)` — SVG без EMF рядом переводятся в EMF **одним** запуском Inkscape в конце скрипта (запуск ≈2.4 с, пакет 8 рисунков ≈4.5 с). Вызывается в `run_case` (штатный набор команды расчёта, FEAT-030) и в конце каждого автономного скрипта, сохраняющего рисунки.
- `GPN_EXAMPLES_EMF=0` — только PNG; так `tests/conftest.py` выключает копии в pytest (решение пользователя: в тестах не нужны). Имя переменной историческое: с FEAT-030 она управляет и командой пакета (решение пользователя 2026-10-13 — EMF как прежде).
- `INKSCAPE` — явный путь к Inkscape; иначе PATH, затем стандартная установка. Без Inkscape — предупреждение, PNG и SVG есть, EMF нет; следующий `export_emf` доделает. Поведение без Inkscape проверяют `tests/test_figures.py::test_export_emf_without_inkscape_keeps_svg` и приёмка FEAT-030 в чистом окружении (`vault/issues/feat-030/probes/clean_env_command.py`: одно предупреждение, код 0).

**Факты, которые легко забыть:**
- Inkscape 1.4.3 возвращает код 0, даже если файл не открылся — успех проверяется по наличию EMF.
- Хвост stderr Inkscape бывает с символами вне cp1251 — печатается с перекодировкой в кодировку консоли, иначе `UnicodeEncodeError` в скриптах, которые не зовут `cli.configure_batch_run`.
- Цена — ≈10 с на пример (пример 14: Inkscape 6.4 с + сохранение 9 SVG ≈3 с).

**Новый рисунок в примерах** — только через `save_figure`, и в конце скрипта — `export_emf(<папка output>)`; иначе у рисунка не будет SVG/EMF.
