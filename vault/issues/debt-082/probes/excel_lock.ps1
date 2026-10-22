# DEBT-082, аудит 1: настоящий Excel держит открытый CSV так же, как open() Python?
# Невидимый экземпляр Excel через COM открывает well_history.csv в свежем каталоге;
# пока файл открыт — os.rename каталога (проверка плана) и, во втором каталоге,
# shutil.rmtree (прежняя очистка). Каталоги рядом со скриптом, удаляются в конце.
# Запуск (из корня проекта): powershell -File vault/issues/debt-082/probes/excel_lock.ps1

$ErrorActionPreference = "Stop"
$py = "numerical_solver\.venv\Scripts\python.exe"
$base = Join-Path $PSScriptRoot "excel_work"

function Fresh($name) {
    $d = Join-Path $base $name
    New-Item -ItemType Directory -Force $d | Out-Null
    Set-Content -Path (Join-Path $d "a.png") -Value "1"
    Set-Content -Path (Join-Path $d "well_history.csv") -Value "t,p`n0,1"
    Set-Content -Path (Join-Path $d "z.csv") -Value "1"
    return $d
}

# Без двойных кавычек: PowerShell 5.1 срезает их в аргументах внешней программы
$code = @'
import os, shutil, sys
from pathlib import Path
d, action = Path(sys.argv[1]), sys.argv[2]
try:
    if action == 'rename':
        t = d.with_name(d.name + '.check')
        os.rename(d, t)
        os.rename(t, d)
    else:
        shutil.rmtree(d)
    print(action + ': прошло')
except OSError as e:
    left = sorted(p.name for p in d.iterdir()) if d.is_dir() else 'каталога нет'
    print(action + ': отказ WinError ' + str(getattr(e, 'winerror', None)) + ', осталось ' + str(left))
'@

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    foreach ($action in "rename", "rmtree") {
        $d = Fresh $action
        $wb = $xl.Workbooks.Open((Join-Path $d "well_history.csv"))
        & $py -c $code $d $action
        $wb.Close($false)
    }
} finally {
    $xl.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
    Start-Sleep -Milliseconds 500
    Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue
}
