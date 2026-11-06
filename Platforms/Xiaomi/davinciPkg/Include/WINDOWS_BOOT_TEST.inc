# TARGET A development profile. No UFS/USB/PMIC/TZ/storage provider.
# RAM FAT32 comes from build input, not a phone ESP. NOT PHYSICAL-READY.
APRIORI DXE {
  INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
  INF Binaries/davinci/QcomPkg/Drivers/EnvDxe/EnvDxe.inf
  INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
  INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
  INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
  INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf
  INF MdeModulePkg/Core/RuntimeDxe/RuntimeDxe.inf
  INF MdeModulePkg/Universal/SecurityStubDxe/SecurityStubDxe.inf
  INF MdeModulePkg/Universal/Variable/RuntimeDxe/VariableRuntimeDxe.inf
  INF MdeModulePkg/Universal/WatchdogTimerDxe/WatchdogTimer.inf
  INF EmbeddedPkg/EmbeddedMonotonicCounter/EmbeddedMonotonicCounter.inf
  INF MdeModulePkg/Universal/DevicePathDxe/DevicePathDxe.inf
  INF MdeModulePkg/Universal/HiiDatabaseDxe/HiiDatabaseDxe.inf
  INF SiliciumPkg/Drivers/SimpleFbDxe/SimpleFbDxe.inf
  INF MdeModulePkg/Universal/Console/ConSplitterDxe/ConSplitterDxe.inf
  INF MdeModulePkg/Universal/Console/GraphicsConsoleDxe/GraphicsConsoleDxe.inf
  INF MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf
  INF MdeModulePkg/Universal/Disk/PartitionDxe/PartitionDxe.inf
  INF MdeModulePkg/Universal/Disk/UnicodeCollation/EnglishDxe/EnglishDxe.inf
  INF FatPkg/EnhancedFatDxe/Fat.inf
  INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf
  INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf
  INF davinciPkg/Drivers/WindowsBootTestDxe/WindowsBootTestDxe.inf
}
INF MdeModulePkg/Core/Dxe/DxeMain.inf
INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
INF Binaries/davinci/QcomPkg/Drivers/EnvDxe/EnvDxe.inf
INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf
INF MdeModulePkg/Core/RuntimeDxe/RuntimeDxe.inf
INF MdeModulePkg/Universal/SecurityStubDxe/SecurityStubDxe.inf
INF MdeModulePkg/Universal/Variable/RuntimeDxe/VariableRuntimeDxe.inf
INF MdeModulePkg/Universal/WatchdogTimerDxe/WatchdogTimer.inf
INF EmbeddedPkg/EmbeddedMonotonicCounter/EmbeddedMonotonicCounter.inf
INF MdeModulePkg/Universal/DevicePathDxe/DevicePathDxe.inf
INF MdeModulePkg/Universal/HiiDatabaseDxe/HiiDatabaseDxe.inf
INF SiliciumPkg/Drivers/SimpleFbDxe/SimpleFbDxe.inf
INF MdeModulePkg/Universal/Console/ConSplitterDxe/ConSplitterDxe.inf
INF MdeModulePkg/Universal/Console/GraphicsConsoleDxe/GraphicsConsoleDxe.inf
INF MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf
INF MdeModulePkg/Universal/Disk/PartitionDxe/PartitionDxe.inf
INF MdeModulePkg/Universal/Disk/UnicodeCollation/EnglishDxe/EnglishDxe.inf
INF FatPkg/EnhancedFatDxe/Fat.inf
INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf
INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf
INF davinciPkg/Drivers/WindowsBootTestDxe/WindowsBootTestDxe.inf

!include Include/ACPI.inc
FILE FREEFORM = 0713CB3B-EA2E-4AA0-98CE-2E69902794D3 {
 SECTION RAW = $(WINDOWS_FAT_IMAGE)
}
