[CmdletBinding()]
param(
    [switch]$SkipRuntime,
    [switch]$SkipModels,
    [switch]$Force,
    [switch]$ForceWinPython,
    [string[]]$Models
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[INFO] $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message"
}

function Get-RootDir {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Clear-Directory {
    param([string]$Path)
    Ensure-Directory -Path $Path
    Get-ChildItem -LiteralPath $Path -Force | Remove-Item -Recurse -Force
}

function Get-PortablePythonExe {
    $rootDir = Get-RootDir
    $candidates = @(
        (Join-Path $rootDir "runtime\WinPython\python\python.exe"),
        (Join-Path $rootDir "runtime\WinPython\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Get-GitHubReleaseAsset {
    param(
        [string]$Repo,
        [string]$AssetPattern,
        [string]$ReleaseTag
    )

    $headers = @{
        "User-Agent" = "CodeWorker-Bootstrap"
        "Accept"     = "application/vnd.github+json"
    }
    if ([string]::IsNullOrWhiteSpace($ReleaseTag)) {
        $release = Invoke-JsonApi -Headers $headers -Url "https://api.github.com/repos/$Repo/releases/latest"
    } else {
        $release = Invoke-JsonApi -Headers $headers -Url "https://api.github.com/repos/$Repo/releases/tags/$ReleaseTag"
    }
    $asset = $release.assets | Where-Object { $_.name -match $AssetPattern } | Select-Object -First 1
    if (-not $asset) {
        $releaseLabel = if ([string]::IsNullOrWhiteSpace($ReleaseTag)) { "latest release" } else { "release tag '$ReleaseTag'" }
        throw "No asset matched pattern '$AssetPattern' in $Repo $releaseLabel."
    }

    return [pscustomobject]@{
        Name = $asset.name
        Url  = $asset.browser_download_url
    }
}

function Download-File {
    param(
        [string]$Url,
        [string]$Destination,
        [hashtable]$Headers = @{}
    )

    Ensure-Directory -Path (Split-Path -Parent $Destination)
    try {
        Invoke-WebRequest -Uri $Url -Headers $Headers -OutFile $Destination
        return
    } catch {
        $curlError = $_
        $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
        if ($curl) {
            $arguments = @("-L", "--fail", "--silent", "--show-error", "--ssl-no-revoke", "-o", $Destination)
            foreach ($entry in $Headers.GetEnumerator()) {
                $arguments += @("-H", "$($entry.Key): $($entry.Value)")
            }
            $arguments += $Url

            & $curl.Source @arguments
            if ($LASTEXITCODE -eq 0) {
                return
            }
        }

        $pythonExe = Get-PortablePythonExe
        if (-not $pythonExe) {
            throw $curlError
        }

        $headersJson = ($Headers | ConvertTo-Json -Compress)
        $headersBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($headersJson))
        $pythonCode = @'
import base64
import json
import sys
import urllib.request

url = sys.argv[1]
destination = sys.argv[2]
headers = json.loads(base64.b64decode(sys.argv[3]).decode('utf-8'))
request = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(request, timeout=300) as response, open(destination, 'wb') as handle:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        handle.write(chunk)
'@
        & $pythonExe -c $pythonCode $Url $Destination $headersBase64
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to download file with portable Python: $Url"
        }
    }
}

function Invoke-JsonApi {
    param(
        [string]$Url,
        [hashtable]$Headers = @{}
    )

    try {
        return Invoke-RestMethod -Headers $Headers -Uri $Url
    } catch {
        $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
        if (-not $curl) {
            throw
        }

        $arguments = @("-L", "--fail", "--silent", "--show-error")
        foreach ($entry in $Headers.GetEnumerator()) {
            $arguments += @("-H", "$($entry.Key): $($entry.Value)")
        }
        $arguments += $Url

        $output = & $curl.Source @arguments
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($output)) {
            throw "Failed to fetch JSON from $Url with curl.exe"
        }

        return $output | ConvertFrom-Json
    }
}

function Expand-ZipPayload {
    param(
        [string]$ArchivePath,
        [string]$TargetDir
    )

    $stageDir = Join-Path ([System.IO.Path]::GetTempPath()) ("codeworker-expand-" + [guid]::NewGuid().ToString("N"))
    Ensure-Directory -Path $stageDir
    try {
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $stageDir -Force
        Install-StagedContent -StageDir $stageDir -TargetDir $TargetDir
    } finally {
        if (Test-Path -LiteralPath $stageDir) {
            Remove-Item -LiteralPath $stageDir -Recurse -Force
        }
    }
}

function Install-StagedContent {
    param(
        [string]$StageDir,
        [string]$TargetDir
    )

    Clear-Directory -Path $TargetDir

    $children = Get-ChildItem -LiteralPath $StageDir -Force
    if ($children.Count -eq 1 -and $children[0].PSIsContainer) {
        Get-ChildItem -LiteralPath $children[0].FullName -Force | Move-Item -Destination $TargetDir -Force
        return
    }

    Get-ChildItem -LiteralPath $StageDir -Force | Move-Item -Destination $TargetDir -Force
}

function Expand-7zSfxPayload {
    param(
        [string]$ArchivePath,
        [string]$TargetDir
    )

    Clear-Directory -Path $TargetDir
    $arguments = @("-y", "-o$TargetDir")
    $process = Start-Process -FilePath $ArchivePath -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Failed to extract self-extracting archive: $ArchivePath"
    }
}

function Get-HuggingFaceFiles {
    param(
        [string]$Repo,
        [string]$Pattern,
        [string]$Token
    )

    $headers = @{
        "User-Agent" = "CodeWorker-Bootstrap"
    }
    if ($Token) {
        $headers["Authorization"] = "Bearer $Token"
    }

    if ($Pattern -notmatch '[\*\?\[\]]') {
        return @(
            [pscustomobject]@{
                Name = $Pattern
                Url  = "https://huggingface.co/$Repo/resolve/main/${Pattern}?download=true"
            }
        )
    }

    $model = Invoke-JsonApi -Headers $headers -Url "https://huggingface.co/api/models/$Repo"
    $wildcard = [System.Management.Automation.WildcardPattern]::new($Pattern, [System.Management.Automation.WildcardOptions]::IgnoreCase)
    $matches = $model.siblings | Where-Object { $wildcard.IsMatch($_.rfilename) } | Sort-Object rfilename

    if (-not $matches) {
        throw "No Hugging Face files matched pattern '$Pattern' in $Repo."
    }

    $nonSplit = $matches | Where-Object { $_.rfilename -notmatch '-\d{5}-of-\d{5}\.gguf$' }
    if ($nonSplit) {
        $matches = $nonSplit
    }

    return $matches | ForEach-Object {
        [pscustomobject]@{
            Name = $_.rfilename
            Url  = "https://huggingface.co/$Repo/resolve/main/$($_.rfilename)?download=true"
        }
    }
}

function Download-HuggingFaceModel {
    param(
        [pscustomobject]$Config,
        [string]$RootDir,
        [string]$Token
    )

    $targetDir = Join-Path $RootDir $Config.targetDir
    Ensure-Directory -Path $targetDir

    $existing = Get-ChildItem -LiteralPath $targetDir -Filter *.gguf -ErrorAction SilentlyContinue
    $healthyExisting = $existing | Where-Object { $_.Length -gt 0 }
    if ($healthyExisting -and $healthyExisting.Count -eq $existing.Count -and -not $Force) {
        Write-Step "Skipping model '$($Config.repo)' because GGUF already exists in '$targetDir'."
        return
    }

    if ($Force) {
        Get-ChildItem -LiteralPath $targetDir -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        Ensure-Directory -Path $targetDir
    }

    Write-Step "Resolving Hugging Face files for $($Config.repo)"
    $headers = @{ "User-Agent" = "CodeWorker-Bootstrap" }
    if ($Token) {
        $headers["Authorization"] = "Bearer $Token"
    }

    foreach ($file in (Get-HuggingFaceFiles -Repo $Config.repo -Pattern $Config.filePattern -Token $Token)) {
        $destination = Join-Path $targetDir ([System.IO.Path]::GetFileName($file.Name))
        Write-Step "Downloading $($file.Name)"
        Download-File -Url $file.Url -Destination $destination -Headers $headers
        $downloaded = Get-Item -LiteralPath $destination -ErrorAction Stop
        if ($downloaded.Length -le 0) {
            throw "Downloaded model file is empty: $destination"
        }
    }

    $finalFiles = Get-ChildItem -LiteralPath $targetDir -Filter *.gguf -ErrorAction SilentlyContinue
    if (-not $finalFiles) {
        throw "No GGUF files were downloaded into '$targetDir'."
    }
    foreach ($file in $finalFiles) {
        if ($file.Length -le 0) {
            throw "Model file is invalid because it is empty: $($file.FullName)"
        }
    }

    Write-Ok "Model ready in '$targetDir'"
}

function Install-RuntimePackage {
    param(
        [string]$Name,
        [pscustomobject]$Config,
        [string]$RootDir
    )

    $targetDir = Join-Path $RootDir $Config.targetDir
    $skip = $false

    switch ($Name) {
        "llamaCpp" {
            if ((Test-Path -LiteralPath (Join-Path $targetDir "llama-server.exe")) -and -not $Force) {
                $skip = $true
            }
        }
        "portableGit" {
            if (((Test-Path -LiteralPath (Join-Path $targetDir "cmd\git.exe")) -or (Test-Path -LiteralPath (Join-Path $targetDir "bin\git.exe"))) -and -not $Force) {
                $skip = $true
            }
        }
        "winPython" {
            $pythonExe = Join-Path $targetDir "python.exe"
            if (-not (Test-Path -LiteralPath $pythonExe)) {
                $pythonExe = Join-Path $targetDir "python\python.exe"
            }

            if ((Test-Path -LiteralPath $pythonExe) -and -not $Force -and -not $ForceWinPython) {
                $versionText = ""
                try {
                    $versionText = & $pythonExe -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"
                } catch {
                    $versionText = ""
                }

                if ($versionText -match '^3\.(10|11|12)$') {
                    $skip = $true
                } else {
                    Write-Step "Portable Python at '$pythonExe' is incompatible with aider-chat (detected $versionText). Reinstalling WinPython."
                }
            }
        }
    }

    if ($skip) {
        Write-Step "Skipping runtime '$Name' because it already exists."
        return
    }

    Write-Step "Resolving latest asset for $Name"
    $asset = Get-GitHubReleaseAsset -Repo $Config.repo -AssetPattern $Config.assetPattern -ReleaseTag $Config.releaseTag
    $downloadDir = Join-Path $RootDir "downloads"
    Ensure-Directory -Path $downloadDir
    $archivePath = Join-Path $downloadDir $asset.Name

    Write-Step "Downloading $($asset.Name)"
    Download-File -Url $asset.Url -Destination $archivePath

    Write-Step "Installing $Name into '$targetDir'"
    switch ($Config.extract) {
        "zip" {
            Expand-ZipPayload -ArchivePath $archivePath -TargetDir $targetDir
        }
        "7z-sfx" {
            Expand-7zSfxPayload -ArchivePath $archivePath -TargetDir $targetDir
        }
        default {
            throw "Unsupported extract mode '$($Config.extract)'"
        }
    }

    Write-Ok "Runtime '$Name' is ready."
}

$rootDir = Get-RootDir
$manifestPath = Join-Path $rootDir "config\bootstrap.manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Manifest not found: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$hfToken = $env:HF_TOKEN
$selectedModels = @()

if ($Models) {
    $selectedModels = $Models | ForEach-Object { $_.ToLowerInvariant() }
}

if (-not $SkipRuntime) {
    Install-RuntimePackage -Name "llamaCpp" -Config $manifest.runtime.llamaCpp -RootDir $rootDir
    Install-RuntimePackage -Name "portableGit" -Config $manifest.runtime.portableGit -RootDir $rootDir
    Install-RuntimePackage -Name "winPython" -Config $manifest.runtime.winPython -RootDir $rootDir
}

if (-not $SkipModels) {
    foreach ($property in $manifest.models.PSObject.Properties) {
        $name = $property.Name.ToLowerInvariant()
        $config = $property.Value

        if ($selectedModels.Count -gt 0 -and $selectedModels -notcontains $name) {
            continue
        }

        if (-not $config.enabled) {
            Write-Step "Skipping model '$name' because it is disabled in bootstrap.manifest.json."
            continue
        }

        if ([string]::IsNullOrWhiteSpace($config.repo) -or [string]::IsNullOrWhiteSpace($config.filePattern)) {
            Write-Step "Skipping model '$name' because repo or filePattern is empty in bootstrap.manifest.json."
            continue
        }

        Download-HuggingFaceModel -Config $config -RootDir $rootDir -Token $hfToken
    }
}

Write-Ok "Bootstrap completed."
