

# ── Расчёт по книге (FEAT-036) ───────────────────────────────
# Блок дописывается в конец tests/test_cli.py; cli, pytest — оттуда. Сам расчёт
# по книге и команду в отдельном процессе проверяет tests/test_workbook_run.py

def test_run_help_mentions_workbook(capsys):
    """run --help: вход — конфиг или книга Excel; каталог вывода у книги очищается до расчёта."""
    with pytest.raises(SystemExit) as e:
        cli.main(["run", "--help"])
    assert e.value.code == 0
    # argparse переносит строки по ширине консоли — сравнивается текст без переносов
    out = " ".join(capsys.readouterr().out.split())
    assert "книга ввода Excel (.xlsx)" in out and "по книге — до него" in out


def test_run_book_error_returns_2(tmp_path, capsys):
    """Не книга .xlsx → код 2, «Ошибка книги:» и причина разбора, без трассировки."""
    fake = tmp_path / "fake.xlsx"
    fake.write_text("a,b\n", encoding="utf-8")
    assert cli.main(["run", str(fake)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("Ошибка книги:") and "не zip" in err
    assert "Traceback" not in err


def test_run_missing_book_returns_2(tmp_path, capsys):
    """Нет книги → код 2, «Ошибка книги:», «книга не найдена»; у конфига по-прежнему «Ошибка конфига» (test_missing_config_returns_2)."""
    assert cli.main(["run", str(tmp_path / "нет.xlsx")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("Ошибка книги:") and "книга не найдена" in err
