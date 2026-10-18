"""Проба Sphinx для плана FEAT-031: подразделы в докстринге модуля (обзор пакета в __init__.py).

Техническое описание по решению 13 — в докстрингах пакета и подпакетов.
docutils не допускает заголовков разделов внутри содержимого директивы
(automodule), поэтому проверяется: (а) подраздел, объявленный в
napoleon_custom_sections простой строкой (выходит рубрикой); (б) подраздел,
не объявленный; (в) рубрика `.. rubric::` прямо в докстринге.

Запуск — после sphinx_probe.py, тем же интерпретатором и с тем же срезом:

    dist\\probe-feat031\\venv\\Scripts\\python vault\\issues\\feat-031\\probes\\sphinx_module_sections.py dist\\probe-feat031\\slice
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

SLICE = Path(sys.argv[1]).resolve()
SRC = SLICE / "doc" / "source_modsec"
OUT = SLICE / "doc" / "build" / "modsec"

MODULE = '''"""Обзор пакета — проба.

Первый абзац обзора.

Устройство пакета
-----------------
Объявленный подраздел: список модулей.

- ``simulator`` — цикл по времени;
- ``factory`` — сборка по конфигу.

Незаявленный подраздел
----------------------
Этот подраздел в napoleon_custom_sections не объявлен.

.. rubric:: Рубрика напрямую

Текст под рубрикой.
"""
'''

CONF = '''
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
language = "ru"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon"]
napoleon_google_docstring = False
napoleon_custom_sections = ["Устройство пакета"]
'''


def main() -> None:
    if SRC.exists():
        shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    (SRC / "conf.py").write_text(CONF, encoding="utf-8")
    (SRC / "probe_mod.py").write_text(MODULE, encoding="utf-8")
    (SRC / "index.rst").write_text("Проба\n=====\n\n.. automodule:: probe_mod\n", encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    r = subprocess.run([sys.executable, "-m", "sphinx", "-b", "html", "-E", "-q", str(SRC), str(OUT)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"sphinx-build: код {r.returncode}")
    print("stderr:\n  " + "\n  ".join(r.stderr.strip().splitlines()[:10]))
    html = (OUT / "index.html").read_text(encoding="utf-8")
    print(f"рубрики: {re.findall(r'<p class=\"rubric\">([^<]+)</p>', html)}")
    for probe in ("Устройство пакета", "Незаявленный подраздел", "Рубрика напрямую", "<h2"):
        print(f"  {probe!r} в HTML: {probe in html}")


if __name__ == "__main__":
    main()
