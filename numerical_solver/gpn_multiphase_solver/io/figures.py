"""Сохранение рисунков: PNG + SVG и EMF в <каталог>/emf/ (FEAT-026; в пакете с FEAT-030).

Перенесён из examples/figure_io.py: штатный набор рисунков пишет команда
расчёта пакета (report/pipeline.py), а не только примеры.

matplotlib не пишет EMF (бэкенд удалён), поэтому EMF получается из SVG
внешней программой Inkscape. Схема двухфазная:

  1. save_figure — PNG, как раньше, плюс SVG в <папка PNG>/emf/;
  2. export_emf  — один запуск Inkscape на все SVG папки, у которых ещё
     нет EMF. SVG остаются: в emf/ лежат обе векторные версии рисунка.

Один запуск на пакет, а не на рисунок: запуск Inkscape стоит около 2.4 с,
пакет из 8 рисунков — 4.5 с (проба vault/issues/feat-026/probes/).

Переменные окружения:
  GPN_EXAMPLES_EMF = "0" — ни SVG, ни EMF, только PNG. tests/conftest.py
                           ставит её на всю сессию pytest: в тестах они
                           не нужны.
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


# FEAT-026
def save_figure(fig, path, dpi: int) -> Path:
    """Сохранить рисунок в PNG и, если вывод векторных рисунков не выключен, в SVG в подкаталоге ``emf/``.

    SVG — с текстом кривыми (подписи не сдвигаются при вставке в Word); EMF
    из него делает :func:`export_emf`. Переменная окружения
    ``GPN_EXAMPLES_EMF=0`` выключает SVG и EMF.

    Параметры
    ---------
    fig : matplotlib.figure.Figure
        Рисунок.
    path : str or pathlib.Path
        Файл PNG; SVG — ``<каталог path>/emf/<имя>.svg``.
    dpi : int
        Разрешение PNG, точек на дюйм.

    Возвращает
    ----------
    pathlib.Path
        Путь PNG.
    """
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


# FEAT-026
def export_emf(output_dir) -> list[Path]:
    """Перевести в EMF все SVG каталога ``output_dir/emf/``, у которых ещё нет EMF, одним запуском Inkscape.

    Inkscape — необязательная внешняя программа: путь задаёт переменная
    окружения ``INKSCAPE``, иначе ищется в PATH и в стандартной установке
    Windows. Без Inkscape печатается одно предупреждение, SVG остаются.

    Параметры
    ---------
    output_dir : str or pathlib.Path
        Каталог результатов (PNG); SVG и EMF — в его подкаталоге ``emf/``.

    Возвращает
    ----------
    list of pathlib.Path
        Созданные файлы EMF; пустой список — переводить нечего, Inkscape не
        найден или не уложился в 300 с.
    """
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
