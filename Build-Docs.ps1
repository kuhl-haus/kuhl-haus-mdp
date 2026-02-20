<#
.SYNOPSIS
    Builds the Sphinx documentation locally and opens it in the default browser.

.DESCRIPTION
    Runs sphinx-build to generate HTML documentation from the docs/ source
    directory into docs/_build/html, then opens the resulting index.html.

.PARAMETER Clean
    Remove the existing build output before building.

.EXAMPLE
    .\Build-Docs.ps1
    .\Build-Docs.ps1 -Clean
#>
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$sourceDir   = Join-Path $projectRoot 'docs'
$buildDir    = Join-Path (Join-Path $sourceDir '_build') 'html'

if ($Clean -and (Test-Path $buildDir)) {
    Write-Host 'Cleaning previous build...' -ForegroundColor Yellow
    Remove-Item -Recurse -Force (Join-Path $sourceDir '_build')
}

Write-Host 'Building Sphinx documentation...' -ForegroundColor Cyan
python -m sphinx -b html $sourceDir $buildDir
if ($LASTEXITCODE -ne 0) {
    Write-Error 'sphinx-build failed. Make sure Sphinx is installed: pip install sphinx'
    exit 1
}

$indexFile = Join-Path $buildDir 'index.html'
Write-Host "Opening $indexFile" -ForegroundColor Green
Start-Process $indexFile
