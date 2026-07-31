<#
.SYNOPSIS
    Drops the AI Harness context files into a target project.

.DESCRIPTION
    Copies CLAUDE.md and the .ai/ context files from this harness's template/
    folder into the target project root.

    Install mode (default): existing files are NOT overwritten unless -Force
    is passed.

    Update mode (-Update): refreshes protocol files (CLAUDE.md, schema, hook
    scripts) to the latest template version while never touching project state:
      - .ai/context.json (the project's live working memory) is always left alone
      - CLAUDE.md is replaced above its project-specific marker comment;
        anything the project added below the marker is preserved
      - .claude/settings.json is left alone if it differs from the template
        (a warning tells you to merge the hooks block by hand)

.PARAMETER Path
    The target project directory. Defaults to the current directory.

.PARAMETER Force
    Install mode only: overwrite existing harness files in the target.
    WARNING: this includes .ai/context.json, the project's live working
    memory. To refresh protocol files safely, use -Update instead.

.PARAMETER Update
    Update an existing install to the latest protocol files without touching
    project state.

.EXAMPLE
    .\install.ps1 -Path C:\Projects\MyApp

.EXAMPLE
    .\install.ps1 -Path C:\Projects\MyApp -Update

.EXAMPLE
    cd C:\Projects\MyApp; C:\Tools\Project-Tracker-Tool\harness\install.ps1

.NOTES
    Bundled with Project Tracker Tool. scan-all.py calls this automatically for
    any discovered project that is missing CLAUDE.md or .ai/context.json.
#>
[CmdletBinding()]
param(
    [string]$Path = (Get-Location).Path,
    [switch]$Force,
    [switch]$Update
)

$ErrorActionPreference = 'Stop'

if ($Force -and $Update) {
    throw "-Force and -Update are mutually exclusive. -Update already refreshes protocol files, and never touches project state."
}

$templateRoot = Join-Path $PSScriptRoot 'template'

if (-not (Test-Path $templateRoot)) {
    throw "Template folder not found at $templateRoot"
}
if (-not (Test-Path $Path)) {
    throw "Target path does not exist: $Path"
}

$target = (Resolve-Path $Path).Path
$mode = if ($Update) { 'Updating' } else { 'Installing' }
Write-Host "$mode AI Harness in: $target" -ForegroundColor Cyan

# Project state -- never overwritten in update mode.
$stateFiles = @('.ai\context.json')
# Project-owned config -- updated only if identical to template or missing;
# otherwise the project may have merged its own settings in.
$userOwnedFiles = @('.claude\settings.json')

$files = Get-ChildItem -Path $templateRoot -Recurse -File -Force
foreach ($file in $files) {
    $relative = $file.FullName.Substring($templateRoot.Length).TrimStart('\', '/')
    $dest = Join-Path $target $relative
    $destDir = Split-Path $dest -Parent

    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    $exists = Test-Path $dest

    if (-not $Update) {
        # ----- install mode -----
        if ($exists -and -not $Force) {
            Write-Host "  skip (exists): $relative" -ForegroundColor Yellow
            continue
        }
        if ($exists -and ($stateFiles -contains $relative)) {
            Write-Host "  WARNING: overwriting project state: $relative" -ForegroundColor Red
        }
        Copy-Item -Path $file.FullName -Destination $dest -Force
        Write-Host "  copied: $relative" -ForegroundColor Green
        continue
    }

    # ----- update mode -----
    if (-not $exists) {
        Copy-Item -Path $file.FullName -Destination $dest -Force
        Write-Host "  added: $relative" -ForegroundColor Green
        continue
    }

    if ($stateFiles -contains $relative) {
        Write-Host "  skip (project state): $relative" -ForegroundColor DarkGray
        continue
    }

    $templateText = [IO.File]::ReadAllText($file.FullName)
    $targetText = [IO.File]::ReadAllText($dest)

    if ($userOwnedFiles -contains $relative) {
        if ($templateText -eq $targetText) {
            Write-Host "  up to date: $relative" -ForegroundColor DarkGray
        } else {
            Write-Host "  skip (project-owned): $relative differs from template; merge the hooks block by hand if needed" -ForegroundColor Yellow
        }
        continue
    }

    if ($relative -eq 'CLAUDE.md') {
        # Replace the protocol section (everything through the marker comment),
        # preserving whatever the project added below the marker.
        $markerPattern = '(?s)<!--\s*Everything below this line.*?-->'
        $match = [regex]::Match($targetText, $markerPattern)
        if (-not $match.Success) {
            Write-Host "  skip: $relative has no project-section marker comment; merge manually" -ForegroundColor Yellow
            continue
        }
        $tail = $targetText.Substring($match.Index + $match.Length).Trim()
        $composed = $templateText.TrimEnd() + "`r`n"
        if ($tail) {
            $composed += "`r`n" + $tail + "`r`n"
        }
        if ($composed -eq $targetText) {
            Write-Host "  up to date: $relative" -ForegroundColor DarkGray
        } else {
            [IO.File]::WriteAllText($dest, $composed)
            Write-Host "  updated: $relative (project section below marker preserved)" -ForegroundColor Green
        }
        continue
    }

    # Remaining protocol files (schema, hook scripts, .gitignore): straight refresh.
    if ($templateText -eq $targetText) {
        Write-Host "  up to date: $relative" -ForegroundColor DarkGray
    } else {
        Copy-Item -Path $file.FullName -Destination $dest -Force
        Write-Host "  updated: $relative" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Cyan
if ($Update) {
    Write-Host "  1. Validate the state file still fits the schema:"
    Write-Host "       npx ajv-cli validate -s .ai/context.schema.json -d .ai/context.json"
    Write-Host "  2. In your next Claude Code session, ask it to reconcile .ai/context.json"
    Write-Host "     with the updated protocol in CLAUDE.md."
} else {
    Write-Host "  1. Open the project and fill in .ai/context.json (project.name, goal, stack)."
    Write-Host "  2. Start a Claude Code session - CLAUDE.md loads automatically and points it at the JSON."
}
