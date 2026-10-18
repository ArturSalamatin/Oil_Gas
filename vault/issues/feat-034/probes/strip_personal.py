"""FEAT-034: убрать личные сведения из книг-фикстур Excel (tests/data/feat034_excel/).

Книги уйдут заказчику вместе с тестами (FEAT-031). Excel пишет в них имя автора
(docProps/core.xml: dc:creator, cp:lastModifiedBy) и абсолютный путь каталога
книги (xl/workbook.xml: x15ac:absPath). Имя — пустой текст, путь — элемент
удаляется; содержимое прочих частей не меняется (тот же порядок, метод сжатия и
время; сжатый поток — zlib, а не Excel, поэтому файл меньше). Вывод — strip_personal.out.txt.

Запуск из корня worktree задачи:
    D:\\Lessons\\Grants\\2026\\GPN\\Oil_Gas\\numerical_solver\\.venv\\Scripts\\python.exe ^
        vault/issues/feat-034/probes/strip_personal.py
"""

import re
import zipfile
from pathlib import Path

BOOKS = sorted((Path.cwd() / "numerical_solver" / "tests" / "data" / "feat034_excel").glob("*.xlsx"))
EDITS = {
    "docProps/core.xml": [(r"<dc:creator>[^<]*</dc:creator>", "<dc:creator></dc:creator>"),
                          (r"<cp:lastModifiedBy>[^<]*</cp:lastModifiedBy>",
                           "<cp:lastModifiedBy></cp:lastModifiedBy>")],
    "xl/workbook.xml": [(r'<mc:AlternateContent[^>]*><mc:Choice Requires="x15">'
                         r"<x15ac:absPath [^>]*/></mc:Choice></mc:AlternateContent>", "")],
}
LEAKS = re.compile(r"(?i)artur|absPath|<dc:creator>[^<]+|<cp:lastModifiedBy>[^<]+")

for book in BOOKS:
    with zipfile.ZipFile(book) as z:
        members = [(i, z.read(i.filename)) for i in z.infolist()]
    out = book.with_suffix(".tmp")
    with zipfile.ZipFile(out, "w") as z:
        for info, data in members:
            for pattern, new in EDITS.get(info.filename, ()):
                text, n = re.subn(pattern, new, data.decode("utf-8"))
                print(f"{book.name} {info.filename}: замен {n}")
                data = text.encode("utf-8")
            z.writestr(info, data)              # ZipInfo: то же сжатие, время, атрибуты
    out.replace(book)
    with zipfile.ZipFile(book) as z:
        left = [(n, m.group(0)) for n in z.namelist()
                for m in LEAKS.finditer(z.read(n).decode("utf-8", errors="replace"))]
    print(f"{book.name}: осталось {left or 'ничего'}")
