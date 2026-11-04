# SPDX-License-Identifier: BSD-2-Clause-Patent
# Optional EMPTY PC lab disk. Never targets a physical disk or copies Windows.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [ValidateRange(16, 128)][int]$SizeGiB = 64,
    [switch]$Create
)
$ErrorActionPreference = 'Stop'
$full = [IO.Path]::GetFullPath($Path)
$taskProfileRoot = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
if (-not $full.StartsWith($taskProfileRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetExtension($full) -ne '.vhdx' -or (Test-Path -LiteralPath $full)) {
    throw 'Use a NEW .vhdx file under USERPROFILE. Existing files are never overwritten.'
}
$parent = Get-Item -LiteralPath ([IO.Path]::GetDirectoryName($full)) -Force
while ($parent) {
    if (($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Junction/reparse-point parent directories are not allowed.'
    }
    $parent = $parent.Parent
}
$plan = [ordered]@{
    new_pc_file = $full
    virtual_size_gib = $SizeGiB
    partitions = @('ESP 260 MiB FAT32', 'MSR 16 MiB', 'remaining NTFS')
    windows_files_copied = $false
    phone_access = $false
    status = 'PLAN ONLY; -Create explicitly creates an empty disposable PC disk'
}
$plan | ConvertTo-Json -Depth 4
if (-not $Create) { return }
foreach ($command in @('New-VHD', 'Mount-VHD', 'Get-VHD', 'Dismount-VHD')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Missing Hyper-V PowerShell command: $command. No physical-disk fallback is provided."
    }
}
if (-not $PSCmdlet.ShouldProcess($full, 'Create and format ONLY a new empty virtual lab disk')) { return }
$attached = $false
try {
    New-VHD -Path $full -Dynamic -SizeBytes ([long]$SizeGiB * 1GB) -ErrorAction Stop | Out-Null
    $image = Mount-VHD -Path $full -Passthru -ErrorAction Stop
    $attached = $true
    $check = Get-VHD -Path $full -ErrorAction Stop
    if (-not $check.Attached -or $null -eq $image.DiskNumber -or $image.DiskNumber -ne $check.DiskNumber) {
        throw 'Cannot establish the new VHD-to-disk identity; refusing initialization.'
    }
    $disk = Get-Disk -Number $image.DiskNumber -ErrorAction Stop
    if ($disk.IsBoot -or $disk.IsSystem -or [string]$disk.PartitionStyle -ne 'RAW' -or
        [long]$disk.Size -ne [long]$check.Size) {
        throw 'Disk is not the expected NEW RAW virtual disk.'
    }
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT -ErrorAction Stop | Out-Null
    $esp = New-Partition -DiskNumber $disk.Number -Size 260MB -GptType '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' -ErrorAction Stop
    Get-Volume -Partition $esp | Format-Volume -FileSystem FAT32 -NewFileSystemLabel 'LAB_ESP' -Confirm:$false -ErrorAction Stop | Out-Null
    New-Partition -DiskNumber $disk.Number -Size 16MB -GptType '{e3c9e316-0b5c-4db8-817d-f92df00215ae}' -ErrorAction Stop | Out-Null
    $windows = New-Partition -DiskNumber $disk.Number -UseMaximumSize -GptType '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}' -ErrorAction Stop
    Get-Volume -Partition $windows | Format-Volume -FileSystem NTFS -NewFileSystemLabel 'LAB_WIN' -Confirm:$false -ErrorAction Stop | Out-Null
    Write-Output 'Created EMPTY PC lab disk. Windows is not installed and phone boot is not validated.'
} finally {
    if ($attached) { Dismount-VHD -Path $full -ErrorAction Stop }
}
