$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$env:PYTHONPATH = (Join-Path (Get-Location) "lab16.2-hybrid-service")
py -3.11 -m unittest discover -s lab16.2-hybrid-service/tests -p "test_*.py" -v
