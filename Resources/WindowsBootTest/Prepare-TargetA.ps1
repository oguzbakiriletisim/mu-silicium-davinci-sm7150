# PC files only: no disk cmdlets, mounting, formatting, registry or phone access.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Staging,
 [Parameter(Mandatory=$true)][string]$OutputDirectory,
 [string]$Bcd,
 [string]$Python='python'
)
$ErrorActionPreference='Stop'
$stagePath=(Resolve-Path -LiteralPath $Staging).Path
$bootPath=Join-Path $stagePath 'Windows\Boot\EFI\bootmgfw.efi'
if (!(Test-Path -LiteralPath $bootPath -PathType Leaf)) { throw 'bootmgfw.efi missing from supplied staging' }
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Output directory must be new' }
$outPath=[IO.Path]::GetFullPath($OutputDirectory)
$profilePath=[IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')+'\'
if (!$outPath.StartsWith($profilePath,[StringComparison]::OrdinalIgnoreCase)) { throw 'Use a new output directory under USERPROFILE' }
$signature=Get-AuthenticodeSignature -LiteralPath $bootPath
if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
 throw 'A valid Microsoft Authenticode signature on the actual bootmgfw.efi is required'
}
$beforeHash=(Get-FileHash -LiteralPath $bootPath -Algorithm SHA256).Hash.ToLowerInvariant()
New-Item -ItemType Directory -Path $outPath | Out-Null
$fatPath=Join-Path $outPath 'efi-fat32.img'
$manifestPath=Join-Path $outPath 'FAT_MANIFEST.json'
$pythonArgs=@((Join-Path $PSScriptRoot 'fat32.py'),'--staging',$stagePath,'--output',$fatPath)
if ($Bcd) { $pythonArgs+=@('--bcd',(Resolve-Path -LiteralPath $Bcd).Path) }
$result=& $Python @pythonArgs
if ($LASTEXITCODE -ne 0) { throw 'FAT preparation failed; output retained for inspection' }
$manifest=($result -join "`n") | ConvertFrom-Json
if ($manifest.files.'EFI/Microsoft/Boot/bootmgfw.efi' -ne $beforeHash) { throw 'Boot Manager changed between signature check and FAT capture' }
$manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
[ordered]@{
 bootmgfw_sha256=$beforeHash
 signature_status=[string]$signature.Status
 signer_subject=$signature.SignerCertificate.Subject
 signer_thumbprint=$signature.SignerCertificate.Thumbprint
 file_version=(Get-Item -LiteralPath $bootPath).VersionInfo.FileVersion
 manifest='FAT_MANIFEST.json'
 firmware_physically_ready=$false
 windows_bootmanager_executed=$false
 note='PC preparation only. This image is a RAM FAT input, not an Android boot.img or phone ESP.'
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outPath 'AUTHENTICODE.json') -Encoding UTF8
$zipPath=Join-Path $outPath 'davinci-target-a-input.zip'
Compress-Archive -LiteralPath @($fatPath,$manifestPath,(Join-Path $outPath 'AUTHENTICODE.json')) -DestinationPath $zipPath
Get-FileHash -LiteralPath $zipPath -Algorithm SHA256 | Format-List
Write-Output "PC package created: $zipPath"
Write-Output 'No phone partition changed. No firmware image or physical readiness claim.'
