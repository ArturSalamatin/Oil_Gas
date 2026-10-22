

# ── Перевод книги в конфиг (FEAT-035) ────────────────────────
# Блок дописывается в конец tests/test_cli.py; SOLVER, _run, cli — оттуда

TEMPLATE_BOOK = SOLVER / "configs" / "INPUT_TEMPLATE_v1.xlsx"


def test_convert_via_module(tmp_path):
    """python -m gpn_multiphase_solver convert книга каталог: код 0, 4 файла, путь конфига в выводе."""
    r = _run(["-m", "gpn_multiphase_solver", "convert", str(TEMPLATE_BOOK), "case"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    case = (tmp_path / "case").resolve()
    assert sorted(p.name for p in case.iterdir()) == [
        "config.json", "gas_pvt.csv", "oil_pvt.csv", "relperm.csv"]
    assert f"Конфиг записан: {case / 'config.json'}" in r.stdout
    assert "gpn-solver run" in r.stdout


def test_convert_help(capsys):
    """convert --help: код 0, коды возврата и правило каталога в справке."""
    with pytest.raises(SystemExit) as e:
        cli.main(["convert", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "Коды возврата" in out and "пустой" in out


def test_convert_book_error_returns_2(tmp_path, capsys):
    """Ошибка книги → код 2, «Ошибка книги» и причина; каталог не создан."""
    import xlsxwriter
    book = tmp_path / "model_only.xlsx"
    wb = xlsxwriter.Workbook(book)
    wb.add_worksheet("MODEL")
    wb.close()
    assert cli.main(["convert", str(book), str(tmp_path / "c")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("Ошибка книги:") and "нет листа THERMAL" in err
    assert not (tmp_path / "c").exists()


def test_convert_not_xlsx_returns_2(tmp_path, capsys):
    fake = tmp_path / "fake.xlsx"
    fake.write_text("a,b\n", encoding="utf-8")
    assert cli.main(["convert", str(fake), str(tmp_path / "c")]) == 2
    assert "не zip" in capsys.readouterr().err


def test_convert_missing_book_returns_2(tmp_path, capsys):
    assert cli.main(["convert", str(tmp_path / "нет.xlsx"), str(tmp_path / "c")]) == 2
    assert "не найдена" in capsys.readouterr().err


def test_convert_non_empty_dir_returns_2(tmp_path, capsys):
    """Непустой каталог → код 2, файл в нём не тронут (решение 10)."""
    out = tmp_path / "c"
    out.mkdir()
    (out / "old.json").write_text("{}", encoding="utf-8")
    assert cli.main(["convert", str(TEMPLATE_BOOK), str(out)]) == 2
    assert "не пустой каталог" in capsys.readouterr().err
    assert [p.name for p in out.iterdir()] == ["old.json"]


def test_convert_does_not_import_solver(tmp_path):
    """Переводу не нужны решатель, scipy и прототип: их нет в sys.modules после команды."""
    code = ("import sys; from gpn_multiphase_solver import cli; "
            f"rc = cli.main(['convert', {str(TEMPLATE_BOOK)!r}, 'c']); "
            "print(rc, 'scipy' in sys.modules, 'radial_blackoil' in sys.modules)")
    r = _run(["-c", code], cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split()[-3:] == ["0", "False", "False"]
