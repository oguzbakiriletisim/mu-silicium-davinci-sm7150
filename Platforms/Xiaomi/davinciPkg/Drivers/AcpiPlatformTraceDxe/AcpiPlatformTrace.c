// SPDX-License-Identifier: BSD-2-Clause-Patent
// Import the pinned upstream implementation unchanged; observe its real return.
#include <Protocol/LoadedImage.h>
#define AcpiPlatformEntryPoint ImportedAcpiPlatformEntryPoint
#include "../../../../../Mu_Basecore/MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatform.c"
#undef AcpiPlatformEntryPoint
EFI_STATUS EFIAPI AcpiPlatformEntryPoint(EFI_HANDLE ImageHandle,EFI_SYSTEM_TABLE *SystemTable) {
 EFI_STATUS S,InfoStatus;EFI_LOADED_IMAGE_PROTOCOL *Loaded;
 InfoStatus=gBS->HandleProtocol(ImageHandle,&gEfiLoadedImageProtocolGuid,(VOID **)&Loaded);
 if(!EFI_ERROR(InfoStatus)) {DEBUG((DEBUG_ERROR,"WBT ACPI PLATFORM ENTER handle=%p base=%p size=%lx\n",ImageHandle,Loaded->ImageBase,Loaded->ImageSize));}
 S=ImportedAcpiPlatformEntryPoint(ImageHandle,SystemTable);
 DEBUG((DEBUG_ERROR,"WBT ACPI PLATFORM RETURN raw=%016lx request-unload=%u\n",(UINT64)S,(UINT32)(S==EFI_REQUEST_UNLOAD_IMAGE)));
 return S;
}
