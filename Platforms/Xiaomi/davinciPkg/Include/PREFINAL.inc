# Opt-in computer-built read-only diagnostics profile. No BDS, PartitionDxe,
# FAT, variable runtime, USB mass storage, SCM/RPMB/GPT listener consumers,
# auto-dispatched HALIOMMU/UFS driver. HAL is loaded explicitly after dependencies.
APRIORI DXE {
  INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
  INF Binaries/davinci/QcomPkg/Drivers/EnvDxe/EnvDxe.inf
  INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
  INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
  INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
  INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf
  INF davinciPkg/Drivers/PreFinalDxe/PreFinalDxe.inf
}
INF MdeModulePkg/Core/Dxe/DxeMain.inf
INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
INF Binaries/davinci/QcomPkg/Drivers/EnvDxe/EnvDxe.inf
INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf
INF davinciPkg/Drivers/PreFinalDxe/PreFinalDxe.inf

FILE FREEFORM = F541D663-4A48-40AA-AABF-FF158CCAE34C {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/SmemDxe/SmemDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/SmemDxe/SmemDxe.efi
}

FILE FREEFORM = 8E9BD160-B184-11DF-94E2-0800200C9A66 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.efi
}

FILE FREEFORM = AF9763A2-033B-4109-8E17-56A98D380C92 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/HWIODxe/HWIODxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/HWIODxe/HWIODxe.efi
}

FILE FREEFORM = 10E193DF-9966-44E7-B17C-59DD831E20FC {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/ChipInfoDxe/ChipInfoDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/ChipInfoDxe/ChipInfoDxe.efi
}

FILE FREEFORM = B105211B-BBBD-4ADD-A3B0-D1CF4A52154C {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/PlatformInfoDxe/PlatformInfoDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/PlatformInfoDxe/PlatformInfoDxe.efi
}

FILE FREEFORM = E43128A8-8692-42B6-8AFA-676158578D18 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/ULogDxe/ULogDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/ULogDxe/ULogDxe.efi
}

FILE FREEFORM = ABA01FF8-2CCB-4E12-8B2E-CD3F4A742993 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/CmdDbDxe/CmdDbDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/CmdDbDxe/CmdDbDxe.efi
}

FILE FREEFORM = CB29F4D1-7F37-4692-A416-93E82E219711 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/NpaDxe/NpaDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/NpaDxe/NpaDxe.efi
}

FILE FREEFORM = CB29F4D1-7F37-4692-A416-93E82E219766 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/RpmhDxe/RpmhDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/RpmhDxe/RpmhDxe.efi
}

FILE FREEFORM = B43C22DB-6333-490C-872D-0A73439059FD {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/PdcDxe/PdcDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/PdcDxe/PdcDxe.efi
}

FILE FREEFORM = 4DB5DEA6-5302-4D1A-8A82-677A683B0D29 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/ClockDxe/ClockDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/ClockDxe/ClockDxe.efi
}

FILE FREEFORM = 0D35CD8E-97EA-4F9A-96AF-0F0D89F76567 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.efi
}

FILE FREEFORM = 9A00771F-36D4-4DD5-8916-C48ED9B16B86 {
  SECTION DXE_DEPEX = Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.depex
  SECTION PE32 = Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi
}
