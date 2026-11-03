# Registra Licha.bot como tarea programada de Windows (el equivalente al servicio
# de systemd): arranca con la PC aunque no inicies sesión y, si el bot se cae,
# lo vuelve a levantar en menos de 5 minutos.
#
# Antes: vinculá el número una vez con `python bot.py` y agregá LOG_FILE al .env.
# Después, en una PowerShell abierta "como administrador", desde la carpeta del bot:
#
#   powershell -ExecutionPolicy Bypass -File deploy\windows\instalar-tarea.ps1
#
# Detener:   Disable-ScheduledTask -TaskName "Licha.bot"; Stop-ScheduledTask -TaskName "Licha.bot"
# Reanudar:  Enable-ScheduledTask -TaskName "Licha.bot"; Start-ScheduledTask -TaskName "Licha.bot"
# Quitar:    Unregister-ScheduledTask -TaskName "Licha.bot" -Confirm:$false

$ErrorActionPreference = "Stop"
$TaskName = "Licha.bot"
$BotDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $BotDir ".venv\Scripts\python.exe"
$EnvFile = Join-Path $BotDir ".env"

if (-not (Test-Path $Python)) {
    throw "No encontré $Python. Creá el entorno virtual primero (ver README)."
}
if (-not (Test-Path $EnvFile)) {
    throw "No encontré $EnvFile. Copiá .env.example como .env y completalo."
}
if (-not (Select-String -Path $EnvFile -Pattern '^\s*LOG_FILE\s*=\s*\S' -Quiet)) {
    Write-Warning "El .env no define LOG_FILE: sin eso no vas a poder ver los logs. Agregá: LOG_FILE=data\bot.log"
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument "bot.py" -WorkingDirectory $BotDir

$AtStartup = New-ScheduledTaskTrigger -AtStartup
# Red de seguridad: cada 5 minutos lo arranca si no está corriendo
# (MultipleInstances IgnoreNew evita que haya dos a la vez).
$Every5Min = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)

# S4U: corre aunque no hayas iniciado sesión, sin guardar tu contraseña.
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($AtStartup, $Every5Min) `
    -Principal $Principal -Settings $Settings -Description "Bot de stickers de WhatsApp (Licha.bot)" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$LogPath = Join-Path $BotDir "data\bot.log"
Write-Host "Listo: la tarea '$TaskName' quedó registrada y corriendo."
Write-Host "Para ver el log:  Get-Content -Wait -Tail 50 `"$LogPath`""
