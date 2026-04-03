param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir
)

$root = [System.IO.Path]::GetFullPath($ProjectDir)
$gitDir = Join-Path $root ".git"
if (-not (Test-Path -LiteralPath $gitDir)) {
    throw "Git directory not found: $gitDir"
}

$excludePath = Join-Path $gitDir "info\\exclude"
$startMarker = "# CodeWorker managed exclude begin"
$endMarker = "# CodeWorker managed exclude end"

$defaultRules = @(
    "node_modules/",
    ".svn/",
    ".hg/",
    ".idea/",
    ".vscode/",
    ".next/",
    ".nuxt/",
    "dist/",
    "build/",
    "target/",
    "out/",
    "coverage/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "*.zip",
    "*.7z",
    "*.rar",
    "*.tar",
    "*.gz",
    "*.bz2",
    "*.xz",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.bin",
    "*.iso",
    "*.mp3",
    "*.mp4",
    "*.mov",
    "*.avi",
    "*.jpg",
    "*.jpeg",
    "*.png",
    "*.gif",
    "*.webp",
    "*.pdf"
)

$largeFiles = Get-ChildItem -LiteralPath $root -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch [regex]::Escape("$gitDir\") -and
        $_.Length -gt 8MB
    } |
    ForEach-Object {
        $_.FullName.Substring($root.Length + 1).Replace('\', '/')
    }

$managedBlock = @($startMarker) + $defaultRules + ($largeFiles | Sort-Object -Unique) + @($endMarker)
$existing = ""
if (Test-Path -LiteralPath $excludePath) {
    $existing = Get-Content -LiteralPath $excludePath -Raw -Encoding UTF8
}

$pattern = [regex]::Escape($startMarker) + ".*?" + [regex]::Escape($endMarker)
if ($existing -match $pattern) {
    $existing = [regex]::Replace($existing, $pattern, "", [System.Text.RegularExpressions.RegexOptions]::Singleline)
}

$existing = $existing.TrimEnd()
$merged = @()
if ($existing) {
    $merged += $existing
}
$merged += ($managedBlock -join [Environment]::NewLine)

$content = ($merged -join ([Environment]::NewLine + [Environment]::NewLine)).Trim() + [Environment]::NewLine
$directory = Split-Path -Parent $excludePath
if (-not (Test-Path -LiteralPath $directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
Set-Content -LiteralPath $excludePath -Value $content -Encoding UTF8
