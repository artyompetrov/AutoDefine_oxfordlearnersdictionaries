cd ./AutoDefineAddon
$currentfolder = Get-Location
Get-ChildItem -Path $currentfolder -Directory -Include __pycache__ -Recurse | Remove-Item -Force -Recurse -Verbose
if (Test-Path ./meta.json) {
  Remove-Item ./meta.json
}
Compress-Archive -Path .\* -DestinationPath ..\to_publish.zip -Update