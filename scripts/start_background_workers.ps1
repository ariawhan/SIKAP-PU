param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,

    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
$resolvedProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$resolvedPythonPath = (Resolve-Path -LiteralPath (Join-Path $resolvedProjectRoot $PythonPath)).Path
$workerLogDirectory = Join-Path $resolvedProjectRoot "logs\workers"
New-Item -ItemType Directory -Path $workerLogDirectory -Force | Out-Null

$workers = @(
    @{
        Name = "Telegram Bot"
        Match = "manage.py run_telegram_bot"
        Arguments = @("-u", "manage.py", "run_telegram_bot")
        LogName = "telegram-bot"
    },
    @{
        Name = "Monitor Session WhatsApp"
        Match = "manage.py monitor_whatsapp_session"
        Arguments = @("-u", "manage.py", "monitor_whatsapp_session", "--interval", "300", "--reminder", "3600")
        LogName = "whatsapp-monitor"
    },
    @{
        Name = "Antrean dan Reminder Otomatis"
        Match = "manage.py run_automatic_notifications"
        Arguments = @("-u", "manage.py", "run_automatic_notifications", "--interval", "30")
        LogName = "automatic-notifications"
    }
)

$pythonProcesses = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine
        }
)

foreach ($worker in $workers) {
    $alreadyRunning = $pythonProcesses | Where-Object {
        $_.CommandLine -like "*$($worker.Match)*"
    } | Select-Object -First 1

    if ($alreadyRunning) {
        Write-Output "[OK] $($worker.Name) sudah berjalan."
        continue
    }

    $stdoutPath = Join-Path $workerLogDirectory "$($worker.LogName).log"
    $stderrPath = Join-Path $workerLogDirectory "$($worker.LogName)-error.log"
    $process = Start-Process `
        -FilePath $resolvedPythonPath `
        -ArgumentList $worker.Arguments `
        -WorkingDirectory $resolvedProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    Start-Sleep -Milliseconds 350
    if ($process.HasExited) {
        Write-Error "$($worker.Name) gagal dijalankan. Periksa $stderrPath"
    }
    Write-Output "[OK] $($worker.Name) berjalan di background (PID $($process.Id))."
}
