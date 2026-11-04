# SPDX-License-Identifier: BSD-2-Clause-Patent
# Read-only Windows Storage inventory. No mounts, partition changes or formatting.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$disks = @(Get-Disk | ForEach-Object {
    $disk = $_
    $partitionError = $null
    $parts = @()
    try {
    $parts = @(Get-Partition -DiskNumber $disk.Number | ForEach-Object {
        $part = $_
        $volume = $null
        try { $volume = Get-Volume -Partition $part -ErrorAction Stop } catch { }
        [ordered]@{
            guid = [string]$part.Guid
            number = [int]$part.PartitionNumber
            gpt_type = [string]$part.GptType
            offset = [long]$part.Offset
            size = [long]$part.Size
            file_system = if ($volume) { [string]$volume.FileSystem } else { $null }
            drive_letter = if ([int][char]$part.DriveLetter -ne 0) { [string]$part.DriveLetter } else { $null }
            is_boot = [bool]$part.IsBoot
            is_system = [bool]$part.IsSystem
        }
    })
    } catch { $partitionError = $_.Exception.Message }
    [ordered]@{
        partition_error = $partitionError
        guid = [string]$disk.Guid
        number = [int]$disk.Number
        partition_style = [string]$disk.PartitionStyle
        size = [long]$disk.Size
        logical_sector_size = [int]$disk.LogicalSectorSize
        is_boot = [bool]$disk.IsBoot
        is_system = [bool]$disk.IsSystem
        partitions = $parts
    }
})
[ordered]@{
    schema_version = 1
    source = 'Windows Storage cmdlets (read-only)'
    captured_at = [DateTime]::UtcNow.ToString('o')
    disks = $disks
} | ConvertTo-Json -Depth 8
