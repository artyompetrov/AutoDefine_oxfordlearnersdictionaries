<#
This script is used by developers of the Anki add-on to simplify local development.

It creates a symbolic link from Anki’s addons folder
(AppData\Anki2\addons21\570730390) to the local project directory, so Anki
loads the add-on directly from the source code during development.

Creating symlinks on Windows requires administrator privileges,
so the script asks for elevation.

We use SymbolicLink instead of Junction because the add-on source directory
may be located on a different drive. Junctions require both paths to be on the
same NTFS volume, while symbolic links work across different drives.
#>

function Is-Symlink([string]$path) {
  $file = Get-Item $path -Force -ea SilentlyContinue
  return [bool]($file.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Run-Elevated ([string]$command)
{
  $sh = New-Object -ComObject 'Shell.Application'
  $sh.ShellExecute('powershell', "-NoExit -Command $command", '', 'runas')
}

# путь к .ps1, независимо от текущего каталога
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$addonPath = Join-Path $env:APPDATA 'Anki2\addons21\570730390'
$pathToProject = Join-Path $scriptDir "AutoDefineAddon"

if (Is-Symlink($addonPath)) {
    return
}

if (Test-Path $addonPath) {
    Remove-Item $addonPath -Recurse -Force
}

Write-Output $addonPath
Write-Output $pathToProject

# передаём абсолютные пути
$cmd = "New-Item -ItemType SymbolicLink -Path `"$addonPath`" -Target `"$pathToProject`""
Run-Elevated $cmd
