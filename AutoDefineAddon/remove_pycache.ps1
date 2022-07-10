$currentfolder = Get-Location
Get-ChildItem -Path $currentfolder -Directory -Include __pycache__ -Recurse | Remove-Item -Force -Recurse -Verbose