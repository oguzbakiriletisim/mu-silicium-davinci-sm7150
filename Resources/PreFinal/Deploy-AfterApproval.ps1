# SPDX-License-Identifier: BSD-2-Clause-Patent
# An explicit approval cannot substitute for missing support. This delivery
# contains no formatting, disk-write, DISM apply or firmware deployment command.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PreflightJson,
    [Parameter(Mandatory=$true)][guid]$DiskGuid,
    [Parameter(Mandatory=$true)][guid]$WindowsPartitionGuid,
    [guid]$EspPartitionGuid,
    [switch]$ApproveDeployment
)
$ErrorActionPreference = 'Stop'
$report = Get-Content -LiteralPath $PreflightJson -Raw | ConvertFrom-Json
if ($report.schema_version -ne 1 -or -not $report.layout -or -not $report.selected.windows) {
    throw 'DURDURULDU: Gecerli preflight raporu bulunamadi.'
}
if ([guid]$report.layout.disk_guid -ne $DiskGuid -or
    [guid]$report.selected.windows.guid -ne $WindowsPartitionGuid) {
    throw 'DURDURULDU: Disk veya Windows bolum GUID eslesmiyor.'
}
if ($EspPartitionGuid -eq [guid]::Empty -or -not $report.selected.esp -or
    [guid]$report.selected.esp.guid -ne $EspPartitionGuid) {
    throw 'DURDURULDU: Telefon ESP GUID bilgisi eksik veya eslesmiyor.'
}
if (-not $ApproveDeployment) { throw 'DURDURULDU: Ayri dagitim onayi verilmedi. Hicbir bolume yazilmadi.' }
# Never trust an editable JSON boolean as hardware/driver compatibility proof.
throw 'DAGITIM ENGELLI: Bu surumde dogrulanmis SM7150-AA Windows UFS surucusu, yeterli ACPI ve dogrulanmis telefon aktarim yolu yok. Onay verilse de yazma yapilmaz.'
