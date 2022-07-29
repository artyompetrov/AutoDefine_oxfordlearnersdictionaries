function Is-Symlink([string]$path) {
  $file = Get-Item $path -Force -ea SilentlyContinue
  return [bool]($file.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Run-Elevated ([string]$scriptblock)
{
  $sh = new-object -com 'Shell.Application'
  $sh.ShellExecute('powershell', "-NoExit -Command $scriptblock", '', 'runas')
}

$addonPath = $env:APPDATA + '\Anki2\addons21\21570730390'

if (Is-Symlink($addonPath))
{
    return
}

if (Test-Path $addonPath)
{
    Remove-Item $addonPath -Force -Recurse 
}

$pathToProject = "C:\Users\APETROV\PycharmProjects\AutoDefine_oxfordlearnersdictionaries\AutoDefineAddon\"

Write-Output $addonPath
Write-Output $pathToProject

Run-Elevated("New-Item -ItemType SymbolicLink -Path '${addonPath}' -Target '${pathToProject}'")