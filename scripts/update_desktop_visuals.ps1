[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$DesktopRoot = "",
  [switch]$UpdateShortcut,
  [switch]$Launch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ShortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'ULTRON 2.7.lnk'
if ([string]::IsNullOrWhiteSpace($DesktopRoot)) {
  $Candidates = @()
  if (Test-Path -LiteralPath $ShortcutPath) {
    $Shell = New-Object -ComObject WScript.Shell
    $Target = $Shell.CreateShortcut($ShortcutPath).TargetPath
    if ($Target) { $Candidates += Split-Path -Parent $Target }
  }
  $Candidates += Join-Path $env:LOCALAPPDATA 'ULTRON 2.7\desktop-build\dist\ULTRON 2.7'
  $Candidates += Join-Path $Root 'dist\ULTRON 2.7'
  $DesktopRoot = $Candidates | Where-Object {
    (Test-Path -LiteralPath (Join-Path $_ 'ULTRON 2.7.exe')) -and (Test-Path -LiteralPath (Join-Path $_ '_internal\web\app.js'))
  } | Select-Object -First 1
  if (-not $DesktopRoot) { throw 'Pass -DesktopRoot with the folder containing ULTRON 2.7.exe.' }
}
$DesktopRoot = [IO.Path]::GetFullPath($DesktopRoot)
$Executable = Join-Path $DesktopRoot 'ULTRON 2.7.exe'
$Web = Join-Path $DesktopRoot '_internal\web'
$App = Join-Path $Web 'app.js'
if (-not (Test-Path -LiteralPath $Executable) -or -not (Test-Path -LiteralPath $App)) {
  throw "Not a supported ULTRON desktop package: $DesktopRoot"
}
$Text = [IO.File]::ReadAllText($App).Replace("`r`n", "`n")
$Factory = 'const armillaryCore = createArmillaryCore({ scene, camera, renderer });'
$OldRequest = @'
async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}
'@
$NewRequest = @'
async function postJson(url, payload) {
  return coreActivity.run(url, async () => {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "ULTRON request failed.");
    return result;
  }, payload);
}
'@
$OldRequest = $OldRequest.Replace("`r`n", "`n")
$NewRequest = $NewRequest.Replace("`r`n", "`n")
if (-not $Text.Contains('const coreActivity = createCoreActivityController(armillaryCore);')) {
  if ($Text.Split(@($Factory), [StringSplitOptions]::None).Count -ne 2 -or -not $Text.Contains($OldRequest)) {
    throw 'Desktop frontend differs from the supported version. Nothing changed; rebuild the desktop app instead.'
  }
  $Text = 'import { createCoreActivityController } from "./core-activity.js";' + "`n" + $Text
  $Text = $Text.Replace($Factory, $Factory + "`nconst coreActivity = createCoreActivityController(armillaryCore);")
  $Text = $Text.Replace($OldRequest, $NewRequest)
} elseif (-not $Text.Contains('return coreActivity.run(url, async () => {')) {
  throw 'Desktop activity hooks are inconsistent. Nothing changed; rebuild the desktop app instead.'
}
foreach ($Name in @('ultron-core.js', 'core-activity.js')) {
  if (-not (Test-Path -LiteralPath (Join-Path $Root "web\$Name"))) { throw "Missing source asset: $Name" }
}
if ($PSCmdlet.ShouldProcess($DesktopRoot, 'Back up and update the core visuals and activity hooks')) {
  $Backup = Join-Path $DesktopRoot ('visual-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
  New-Item -ItemType Directory -Path $Backup -Force | Out-Null
  foreach ($Name in @('app.js', 'ultron-core.js', 'core-activity.js')) {
    $Original = Join-Path $Web $Name
    if (Test-Path -LiteralPath $Original) { Copy-Item -LiteralPath $Original -Destination (Join-Path $Backup $Name) }
  }
  Copy-Item -LiteralPath (Join-Path $Root 'web\ultron-core.js') -Destination (Join-Path $Web 'ultron-core.js')
  Copy-Item -LiteralPath (Join-Path $Root 'web\core-activity.js') -Destination (Join-Path $Web 'core-activity.js')
  [IO.File]::WriteAllText($App, $Text, [Text.UTF8Encoding]::new($false))
  if ($UpdateShortcut) {
    if (Test-Path -LiteralPath $ShortcutPath) { Copy-Item -LiteralPath $ShortcutPath -Destination (Join-Path $Backup 'ULTRON 2.7.lnk') }
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $Executable
    $Shortcut.WorkingDirectory = $DesktopRoot
    $Shortcut.IconLocation = $Executable
    $Shortcut.Save()
    Write-Host "Desktop shortcut updated: $ShortcutPath"
  }
  Write-Host "Updated desktop visuals: $DesktopRoot"
  Write-Host "Backup: $Backup"
  Write-Host 'Close and reopen ULTRON to load the updated assets. Settings, keys, and Python backend were not changed.'
  if ($Launch) { Start-Process -FilePath $Executable -WorkingDirectory $DesktopRoot -WindowStyle Normal }
}
