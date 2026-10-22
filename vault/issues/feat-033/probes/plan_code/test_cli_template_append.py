

# ── Шаблон книги ввода (FEAT-033) ────────────────────────────

def test_template_via_module(tmp_path):
    """python -m gpn_multiphase_solver template book.xlsx: код 0, файл, путь в выводе."""
    r = _run(["-m", "gpn_multiphase_solver", "template", "book.xlsx"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "book.xlsx").is_file()
    assert f"Шаблон книги записан: {(tmp_path / 'book.xlsx').resolve()}" in r.stdout


def test_template_help(capsys):
    """template --help: код 0, в справке — отказ перезаписи и коды возврата."""
    with pytest.raises(SystemExit) as e:
        cli.main(["template", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "не перезаписывается" in out and "Коды возврата" in out


def test_template_existing_file_returns_2(tmp_path, capsys):
    """Существующий файл → код 2, путь в сообщении, байты не тронуты (решение 58)."""
    path = tmp_path / "filled.xlsx"
    path.write_bytes(b"filled")
    assert cli.main(["template", str(path)]) == 2
    err = capsys.readouterr().err
    assert "уже существует" in err and str(path.resolve()) in err
    assert path.read_bytes() == b"filled"


def test_template_not_xlsx_returns_2(tmp_path, capsys):
    assert cli.main(["template", str(tmp_path / "book.txt")]) == 2
    assert ".xlsx" in capsys.readouterr().err
    assert not (tmp_path / "book.txt").exists()


def test_template_missing_directory_returns_2(tmp_path, capsys):
    path = tmp_path / "нет" / "book.xlsx"
    assert cli.main(["template", str(path)]) == 2
    assert str(path.resolve()) in capsys.readouterr().err


def test_template_does_not_import_solver(tmp_path):
    """Шаблону не нужны решатель, scipy и прототип: их нет в sys.modules после команды."""
    code = ("import sys; from gpn_multiphase_solver import cli; "
            "rc = cli.main(['template', 'b.xlsx']); "
            "print(rc, 'scipy' in sys.modules, 'radial_blackoil' in sys.modules)")
    r = _run(["-c", code], cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split()[-3:] == ["0", "False", "False"]
