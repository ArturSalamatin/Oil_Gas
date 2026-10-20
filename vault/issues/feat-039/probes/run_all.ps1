# FEAT-039 (планирование): серия замеров start_series.py на одной базе.
# Запуск из numerical_solver/:  powershell -File ..\vault\issues\feat-039\probes\run_all.ps1
$P = "..\vault\issues\feat-039\probes\start_series.py"
$O = "..\vault\issues\feat-039\probes"
$py = ".venv\Scripts\python"
git log --oneline -1 | Out-File -Encoding utf8 "$O\base.txt"

# 1. Все примеры: пуск полным шагом, нарастание от 7.04 и 0.11 с (только первый интервал)
$examples = Get-ChildItem ..\numerical_solver\examples -Directory | Where-Object { $_.Name -match '^\d' } | ForEach-Object { $_.Name }
Remove-Item "$O\start_all.out.txt" -ErrorAction SilentlyContinue
foreach ($e in $examples) { & $py $P start $e none 7.04 0.11 *>> "$O\start_all.out.txt" }

# 2. Ряд по h0 (соседние вдвое) на ключевых примерах
Remove-Item "$O\start_h0.out.txt" -ErrorAction SilentlyContinue
foreach ($e in "03_standing_corey","04a_high_gas_saturation","10_deep_degassing","20_rs300_cooling","19_rs150_cooling","21_rs100_cooling") {
    & $py $P start $e none 1.76 0.88 0.44 0.22 0.11 0.055 0.0275 *>> "$O\start_h0.out.txt"
}

# 3. Предел равномерного сгущения первой записи: первый шаг ~0.1 с, 2**j шагов на октаву
Remove-Item "$O\octave.out.txt" -ErrorAction SilentlyContinue
& $py $P octave 03_standing_corey 15 0 1 2 3 4 5 *>> "$O\octave.out.txt"
& $py $P octave 10_deep_degassing 15 0 1 2 3 4 5 *>> "$O\octave.out.txt"
& $py $P octave 20_rs300_cooling 15 0 1 2 3 4 5 *>> "$O\octave.out.txt"
& $py $P octave 04a_high_gas_saturation 12 0 1 2 3 4 5 *>> "$O\octave.out.txt"
& $py $P octave 19_rs150_cooling 20 0 1 2 3 4 5 *>> "$O\octave.out.txt"
& $py $P octave 21_rs100_cooling 20 0 1 2 3 4 5 *>> "$O\octave.out.txt"

# 4. Поле на всех сменах (поведение после FEAT-039 при h0 = 0.11 с) у примеров со сменами управления
Remove-Item "$O\all_changes.out.txt" -ErrorAction SilentlyContinue
foreach ($e in "13a_pwf_ramp_down","13b_pwf_alternating","15_oil_rate_ramp_up","16_well_shut_in","17_shut_in_strong_cooling","18_prototype_input","20_rs300_cooling","22_workbook_input") {
    & $py $P all $e none 0.11 *>> "$O\all_changes.out.txt"
}
"готово" | Out-File -Encoding utf8 -Append "$O\base.txt"
