param(
    [string]$PythonExe,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "eisenhower_widget.py"
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
    throw "Could not find the widget script: $scriptPath"
}

$shortcutName = "Eisenhower Matrix.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) $shortcutName
$startupFolder = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupShortcut = Join-Path $startupFolder $shortcutName

if ($Remove) {
    foreach ($shortcutPath in @($desktopShortcut, $startupShortcut)) {
        if (Test-Path -LiteralPath $shortcutPath) {
            Remove-Item -LiteralPath $shortcutPath
            Write-Output "Removed $shortcutPath"
        }
    }
    exit 0
}

if (-not $PythonExe) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found on PATH. Pass -PythonExe with the full path to python.exe."
    }
    $PythonExe = $pythonCommand.Source
}

$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$pythonwPath = Join-Path (Split-Path -Parent $PythonExe) "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonwPath -PathType Leaf)) {
    throw "Could not find pythonw.exe beside '$PythonExe'. Install standard Windows Python or use an interpreter that includes pythonw.exe."
}

New-Item -ItemType Directory -Path $startupFolder -Force | Out-Null
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @($desktopShortcut, $startupShortcut)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonwPath
    $shortcut.Arguments = '"' + $scriptPath + '"'
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = "Open the local Eisenhower Matrix task widget"
    $shortcut.IconLocation = "$pythonwPath,0"
    $shortcut.Save()
    Write-Output "Created $shortcutPath"
}
