# SPDX-License-Identifier: BSD-2-Clause-Patent
param([string]$ToolsRoot, [ValidateSet('Parse','Inventory','LabGuard')][string]$Action)
$ErrorActionPreference = 'Stop'
if ($Action -eq 'Parse') {
    foreach ($name in @('Collect-DiskInventory.ps1','New-LabDisk.ps1')) {
        $tokenSet = $null; $astErrors = $null
        [Management.Automation.Language.Parser]::ParseFile((Join-Path $ToolsRoot $name), [ref]$tokenSet, [ref]$astErrors) | Out-Null
        if ($astErrors.Count -ne 0) { throw ($astErrors | Out-String) }
    }
} elseif ($Action -eq 'Inventory') {
    # Mock all Windows storage commands; this test never queries host disks.
    function Get-Disk {
        foreach ($number in @(7,9)) {
            [pscustomobject]@{ Number=$number; Guid='11111111-2222-3333-4444-555555555555';
                PartitionStyle='GPT'; Size=68719476736; LogicalSectorSize=4096; IsBoot=$false; IsSystem=$false }
        }
    }
    function Get-Partition([int]$DiskNumber) {
        if ($DiskNumber -eq 9) { throw 'fixture inaccessible disk' }
        foreach ($number in @(1,3)) {
            [pscustomobject]@{ Guid='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'; PartitionNumber=$number;
                GptType='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'; Offset=1048576;
                Size=272629760; DriveLetter=[char]'S'; IsBoot=$false; IsSystem=$false }
        }
    }
    function Get-Volume([object]$Partition) {
        [pscustomobject]@{ FileSystem= $(if ($Partition.PartitionNumber -eq 1) { 'FAT32' } else { 'NTFS' }) }
    }
    $result = (& (Join-Path $ToolsRoot 'Collect-DiskInventory.ps1')) | ConvertFrom-Json
    if ($result.schema_version -ne 1 -or $result.disks.Count -ne 2 -or
        $result.disks[0].partitions.Count -ne 2 -or $result.disks[0].partitions[0].file_system -ne 'FAT32' -or
        $result.disks[1].partition_error -ne 'fixture inaccessible disk') {
        throw 'Unexpected mocked inventory result'
    }
} else {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        $rejected = $false
        try { & (Join-Path $ToolsRoot 'New-LabDisk.ps1') -Path '/tmp/never-created.vhdx' }
        catch { $rejected = $_.Exception.Message -like 'Windows is required*' }
        if (-not $rejected) { throw 'Non-Windows lab execution was not rejected' }
    } else {
        $path = Join-Path $env:USERPROFILE ('davinci-plan-only-test-' + [guid]::NewGuid().ToString() + '.vhdx')
        $plan = (& (Join-Path $ToolsRoot 'New-LabDisk.ps1') -Path $path) | ConvertFrom-Json
        if ($plan.phone_access -ne $false -or (Test-Path -LiteralPath $path)) { throw 'Plan-only operation wrote a disk image' }
    }
}
Write-Output ('PASS: ' + $Action)
