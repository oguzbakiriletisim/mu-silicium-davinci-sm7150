// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Uefi.h>
#include <Guid/EventGroup.h>
#include <Protocol/BlockIo.h>
#include <Protocol/EFIClock.h>
#include <Protocol/EFISmem.h>
#include <Protocol/EFIScm.h>
#include <Library/ConfigurationMapHelperLib.h>
#include <Library/DebugLib.h>
#include <Library/IoLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/MemoryMapHelperLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include "StorageAudit.h"

// Identified by UFSDxe's LocateProtocol argument. No IOMMU methods are called.
STATIC EFI_GUID mIommuGuid =
  { 0x54B6D3B4, 0x5D33, 0x4F91, { 0x86, 0x00, 0x6C, 0x41, 0xD5, 0xDE, 0xB1, 0x9A } };

STATIC VOID
AuditProtocol (CHAR8 *Name, EFI_GUID *Guid)
{
  VOID       *Interface = NULL;
  EFI_STATUS  Status = gBS->LocateProtocol (Guid, NULL, &Interface);
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: %a protocol %r (presence only; initialization status unknown)\n", Name, Status));
}

STATIC VOID
AuditImem (VOID)
{
  UINT32                          Base = 0;
  UINT32                          Magic;
  UINT32                          Version;
  UINT32                          Type;
  ARM_MEMORY_REGION_DESCRIPTOR_EX Region = {0};
  EFI_STATUS                      Status;

  Status = LocateConfigurationMapUINT32ByName ("SharedIMEMBaseAddr", &Base);
  if (EFI_ERROR (Status)) {
    DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: no SharedIMEMBaseAddr (%r)\n", Status));
    return;
  }
  Status = LocateMemoryMapAreaByAddress (Base, &Region);
  if (EFI_ERROR (Status) || !DavinciImemRangeValid (Base, Region.Address, Region.Length)) {
    DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: IMEM range is not mapped; skipping reads\n"));
    return;
  }
  Magic   = MmioRead32 ((UINTN)Base);
  Version = MmioRead32 ((UINTN)Base + 4);
  if (Magic != DAVINCI_IMEM_MAGIC || Version < DAVINCI_IMEM_MIN_VERSION) {
    DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: unrecognized IMEM header magic=0x%x version=%u\n", Magic, Version));
    return;
  }
  Type = MmioRead32 ((UINTN)Base + DAVINCI_IMEM_BOOT_OFFSET);
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: IMEM raw type=%u reports-UFS=%u (no override)\n",
          Type, DavinciImemReportsUfs (Magic, Version, Type)));
}

STATIC VOID EFIAPI
AuditBlockIo (EFI_EVENT Event, VOID *Context)
{
  EFI_HANDLE             *Handles = NULL;
  EFI_BLOCK_IO_PROTOCOL  *BlockIo;
  EFI_STATUS              Status;
  UINTN                   Count = 0;
  UINTN                   Index;

  Status = gBS->LocateHandleBuffer (ByProtocol, &gEfiBlockIoProtocolGuid, NULL, &Count, &Handles);
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: %a BlockIo discovery %r handles=%u\n", (CHAR8 *)Context, Status, (UINT32)Count));
  if (EFI_ERROR (Status)) {
    return;
  }
  for (Index = 0; Index < Count; Index++) {
    Status = gBS->HandleProtocol (Handles[Index], &gEfiBlockIoProtocolGuid, (VOID **)&BlockIo);
    if (!EFI_ERROR (Status) && BlockIo != NULL && BlockIo->Media != NULL) {
      DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: handle=%p present=%u partition=%u block=%u last=0x%Lx\n",
              Handles[Index], BlockIo->Media->MediaPresent, BlockIo->Media->LogicalPartition,
              BlockIo->Media->BlockSize, (UINT64)BlockIo->Media->LastBlock));
    } else {
      DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: handle=%p unavailable media metadata (%r)\n",
              Handles[Index], Status));
    }
  }
  FreePool (Handles);
  // Metadata only: never ConnectController, ReadBlocks, WriteBlocks or Reset.
}

EFI_STATUS EFIAPI
StorageAuditEntry (EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable)
{
  EFI_EVENT   Event;
  EFI_STATUS  Status;
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: pre-UFSDxe audit; bundled IOMMU bypass is unchanged\n"));
  AuditProtocol ("SMEM", &gEfiSMEMProtocolGuid);
  AuditProtocol ("Clock", &gEfiClockProtocolGuid);
  AuditProtocol ("HALIOMMU", &mIommuGuid);
  AuditProtocol ("SCM", &gQcomScmProtocolGuid);
  AuditImem ();
  {
    UINT32 Ioc = 0;
    Status = LocateConfigurationMapUINT32ByName ("EnableUfsIOC", &Ioc);
    DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: EnableUfsIOC lookup %r value=%u; bypassed routine does not consume it\n", Status, Ioc));
  }
  Status = gBS->CreateEventEx (EVT_NOTIFY_SIGNAL, TPL_CALLBACK, AuditBlockIo,
                             "EndOfDxe", &gEfiEndOfDxeEventGroupGuid, &Event);
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: EndOfDxe audit registration %r\n", Status));
  Status = gBS->CreateEventEx (EVT_NOTIFY_SIGNAL, TPL_CALLBACK, AuditBlockIo,
                             "ReadyToBoot", &gEfiEventReadyToBootGuid, &Event);
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: ReadyToBoot audit registration %r\n", Status));
  return EFI_SUCCESS; // Diagnostics do not gate or change the existing UFS path.
}

// Separate image placed immediately after UFSDxe in DEBUG APRIORI. Reaching
// this point proves dispatcher progress only: UFS may have failed to load,
// returned an error, or deliberately skipped probing. Never report it as a
// successful UFS entry/initialization marker.
EFI_STATUS EFIAPI
StorageAuditAfterUfsEntry (EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable)
{
  DEBUG ((DEBUG_WARN, "DAVINCI-STORAGE: post-UFSDxe APRIORI position reached; UFS status unknown\n"));
  AuditProtocol ("SMEM", &gEfiSMEMProtocolGuid);
  AuditProtocol ("Clock", &gEfiClockProtocolGuid);
  AuditProtocol ("HALIOMMU", &mIommuGuid);
  AuditProtocol ("SCM", &gQcomScmProtocolGuid);
  AuditBlockIo (NULL, "post-UFSDxe");
  return EFI_SUCCESS;
}
