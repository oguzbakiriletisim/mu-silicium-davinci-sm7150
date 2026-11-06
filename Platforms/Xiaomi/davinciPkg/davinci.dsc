##
#  Copyright (c) 2011 - 2022, ARM Limited. All rights reserved.
#  Copyright (c) 2014, Linaro Limited. All rights reserved.
#  Copyright (c) 2015 - 2020, Intel Corporation. All rights reserved.
#  Copyright (c) 2018, Bingxing Wang. All rights reserved.
#  Copyright (c) Microsoft Corporation.
#
#  SPDX-License-Identifier: BSD-2-Clause-Patent
##

################################################################################
#
# Defines Section - statements that will be processed to create a Makefile.
#
################################################################################
[Defines]
  PLATFORM_NAME                  = davinci
  PLATFORM_GUID                  = 41CAEC3A-0E60-49BD-B42D-B16BF65D9B1D
  PLATFORM_VERSION               = 0.1
  DSC_SPECIFICATION              = 0x00010005
  OUTPUT_DIRECTORY               = Build/davinciPkg
  SUPPORTED_ARCHITECTURES        = AARCH64
  BUILD_TARGETS                  = RELEASE|DEBUG
  SKUID_IDENTIFIER               = DEFAULT
  FLASH_DEFINITION               = davinciPkg/davinci.fdf
!ifndef WINDOWS_BOOT_TEST
  DEFINE WINDOWS_BOOT_TEST = 0
!endif
!if $(WINDOWS_BOOT_TEST) == 1
  USE_CUSTOM_DISPLAY_DRIVER      = 0
!else
  USE_CUSTOM_DISPLAY_DRIVER      = 1
!endif
  HAS_BUILD_IN_KEYBOARD          = 0

!ifndef DAVINCI_PREFINAL
  DEFINE DAVINCI_PREFINAL = 0
!endif

!ifndef DAVINCI_PHOTO_DIAG
  DEFINE DAVINCI_PHOTO_DIAG = 0
!endif
!ifndef DAVINCI_PHOTO_STOP
  DEFINE DAVINCI_PHOTO_STOP = 0
!endif

!ifndef DAVINCI_PHOTO_DELAY_US
  DEFINE DAVINCI_PHOTO_DELAY_US = 1000000
!endif
!ifndef DAVINCI_PHOTO_PHASE_TEST
  DEFINE DAVINCI_PHOTO_PHASE_TEST = 0
!endif
!ifndef DAVINCI_PHOTO_MAX_NATIVE
  DEFINE DAVINCI_PHOTO_MAX_NATIVE = 255
!endif

!ifndef DAVINCI_FIRST_BOOT_HALT
  DEFINE DAVINCI_FIRST_BOOT_HALT  = 0
!endif

!ifndef DAVINCI_ACPI_STORAGE_DEV
  DEFINE DAVINCI_ACPI_STORAGE_DEV = 0
!endif

!ifndef DAVINCI_CPU_ONLY_ACPI
  DEFINE DAVINCI_CPU_ONLY_ACPI    = 0
!endif

  #
  # 0 = SM7150
  # 1 = SM7150-AB
  # 2 = SM7150-AC
  #
  SOC_TYPE                       = 0

[BuildOptions]
  *_*_*_CC_FLAGS = -DSOC_TYPE=$(SOC_TYPE) -DHAS_BUILD_IN_KEYBOARD=$(HAS_BUILD_IN_KEYBOARD) -DDAVINCI_FIRST_BOOT_HALT=$(DAVINCI_FIRST_BOOT_HALT) -DDAVINCI_PREFINAL=$(DAVINCI_PREFINAL) -DDAVINCI_PHOTO_DIAG=$(DAVINCI_PHOTO_DIAG)

[PcdsFixedAtBuild]
  # DDR Start Address
  gArmTokenSpaceGuid.PcdSystemMemoryBase|0x80000000 

  # Device Maintainer
  gSiliciumPkgTokenSpaceGuid.PcdDeviceMaintainer|"hiratazx"

  # UEFI Stack Addresses
  gEmbeddedTokenSpaceGuid.PcdPrePiStackBase|0x9FF90000
  gEmbeddedTokenSpaceGuid.PcdPrePiStackSize|0x00040000 

  # SmBios
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemManufacturer|"Xiaomi Inc"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemModel|"Redmi K20"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemRetailModel|"M1903F10I"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemRetailSku|"Redmi K20_M1903F10I"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosBoardModel|"Redmi K20"

  # Simple Frame Buffer
  gSiliciumPkgTokenSpaceGuid.PcdPrimaryFrameBufferWidth|1080
  gSiliciumPkgTokenSpaceGuid.PcdPrimaryFrameBufferHeight|2340
  gSiliciumPkgTokenSpaceGuid.PcdPrimaryFrameBufferColorDepth|32

  # Platform Pei
  gQcomPkgTokenSpaceGuid.PcdPlatformType|"WP"

  # Dynamic RAM Start Address
  gQcomPkgTokenSpaceGuid.PcdRamPartitionBase|0xA0000000

  # USB Controller
  gQcomPkgTokenSpaceGuid.PcdStartUsbController|TRUE
  
[PcdsDynamicDefault]
  gEfiMdeModulePkgTokenSpaceGuid.PcdVideoHorizontalResolution|1080
  gEfiMdeModulePkgTokenSpaceGuid.PcdVideoVerticalResolution|2340
  gEfiMdeModulePkgTokenSpaceGuid.PcdSetupVideoHorizontalResolution|1080
  gEfiMdeModulePkgTokenSpaceGuid.PcdSetupVideoVerticalResolution|2340
  gEfiMdeModulePkgTokenSpaceGuid.PcdSetupConOutColumn|135
  gEfiMdeModulePkgTokenSpaceGuid.PcdSetupConOutRow|123
  gEfiMdeModulePkgTokenSpaceGuid.PcdConOutColumn|135
  gEfiMdeModulePkgTokenSpaceGuid.PcdConOutRow|123

[LibraryClasses]
  DeviceMemoryMapLib|davinciPkg/Library/DeviceMemoryMapLib/DeviceMemoryMapLib.inf
  DeviceConfigurationMapLib|davinciPkg/Library/DeviceConfigurationMapLib/DeviceConfigurationMapLib.inf
  DeviceGuidLib|davinciPkg/Library/DeviceGuidLib/DeviceGuidLib.inf
  AcpiDeviceUpdateLib|SiliciumPkg/Library/AcpiDeviceUpdateLibNull/AcpiDeviceUpdateLibNull.inf

!include MooreaPkg/MooreaPkg.dsc.inc

[Components.common]
!if $(DAVINCI_ACPI_STORAGE_DEV) == 1
  davinciPkg/AcpiTables/StorageDev.inf
!endif
!if $(WINDOWS_BOOT_TEST) == 1
  davinciPkg/Drivers/WindowsBootTestDxe/WindowsBootTestDxe.inf {
    <BuildOptions>
      *_*_*_CC_FLAGS = -DWBT_CPU_ONLY_ACPI=$(DAVINCI_CPU_ONLY_ACPI) -DWBT_PREFINAL=$(DAVINCI_PREFINAL)
  }
!endif
!if $(DAVINCI_CPU_ONLY_ACPI) == 1
  davinciPkg/AcpiTables/AcpiTables.inf
  davinciPkg/AcpiTables/Gtdt.inf
  davinciPkg/AcpiTables/Fadt.inf
!endif
!if $(TARGET) == DEBUG
  davinciPkg/Drivers/StorageAuditDxe/StorageAuditDxe.inf
  davinciPkg/Drivers/StorageAuditDxe/StorageAuditAfterUfsDxe.inf
!endif

!if $(DAVINCI_PREFINAL) == 1
  davinciPkg/Drivers/PreFinalDxe/PreFinalDxe.inf {
    <BuildOptions>
      *_*_*_CC_FLAGS = -DDAVINCI_PHOTO_STOP=$(DAVINCI_PHOTO_STOP) -DDAVINCI_PHOTO_DELAY_US=$(DAVINCI_PHOTO_DELAY_US) -DDAVINCI_PHOTO_PHASE_TEST=$(DAVINCI_PHOTO_PHASE_TEST) -DDAVINCI_PHOTO_MAX_NATIVE=$(DAVINCI_PHOTO_MAX_NATIVE)
  }
!endif
