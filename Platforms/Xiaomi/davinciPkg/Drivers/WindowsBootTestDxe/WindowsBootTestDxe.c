// SPDX-License-Identifier: BSD-2-Clause-Patent
// TARGET A only: firmware-contained FAT32, no native UFS/USB/PMIC/TZ/SMMU.
#include <PiDxe.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/BaseLib.h>
#include <Library/ArmLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/DevicePathLib.h>
#include <Library/HobLib.h>
#include <Library/DebugLib.h>
#include <Protocol/BlockIo.h>
#include <Protocol/Bds.h>
#include <Protocol/Capsule.h>
#include <Protocol/DevicePath.h>
#include <Protocol/SimpleFileSystem.h>
#include <Protocol/GraphicsOutput.h>
#include <Protocol/SimpleTextOut.h>
#include <Protocol/Reset.h>
#include <Protocol/RealTimeClock.h>
#include <Guid/Acpi.h>
#include <Guid/FileInfo.h>
#include <Guid/EventGroup.h>
#include "RamChecks.h"
#if !defined(WBT_CPU_ONLY_ACPI) || WBT_CPU_ONLY_ACPI != 1 || WBT_PREFINAL != 0
#error WINDOWS_BOOT_TEST requires its separate CPU-only-ACPI profile and PREFINAL=0
#endif
STATIC EFI_GUID mFatGuid={0x0713cb3b,0xea2e,0x4aa0,{0x98,0xce,0x2e,0x69,0x90,0x27,0x94,0xd3}};
STATIC CONST UINT8 *mDisk;STATIC UINTN mBytes;
STATIC UINTN mReads;
STATIC EFI_HANDLE mParentImage;
STATIC EFI_BLOCK_IO_MEDIA mMedia={.MediaId=0x57425431,.RemovableMedia=FALSE,.MediaPresent=TRUE,.LogicalPartition=TRUE,.ReadOnly=TRUE,.WriteCaching=FALSE,.BlockSize=512,.IoAlign=1};
STATIC EFI_STATUS EFIAPI ResetDisk(EFI_BLOCK_IO_PROTOCOL *This,BOOLEAN Extended) {(VOID)This;(VOID)Extended;return EFI_SUCCESS;}
STATIC EFI_STATUS EFIAPI ReadDisk(EFI_BLOCK_IO_PROTOCOL *This,UINT32 Id,EFI_LBA Lba,UINTN Bytes,VOID *Buffer) {
 if(This==NULL || (Bytes && Buffer==NULL)) {return EFI_INVALID_PARAMETER;}
 if(Id!=mMedia.MediaId) {return EFI_MEDIA_CHANGED;}
 if(!mMedia.MediaPresent) {return EFI_NO_MEDIA;}
 if(Bytes==0) {return EFI_SUCCESS;}
 if(Bytes%512) {return EFI_BAD_BUFFER_SIZE;}
 if(!WbtReadRange(Lba,Bytes,mBytes)) {return EFI_INVALID_PARAMETER;}
 CopyMem(Buffer,mDisk+(UINTN)Lba*512,Bytes);++mReads;return EFI_SUCCESS;
}
STATIC EFI_STATUS EFIAPI WriteDisk(EFI_BLOCK_IO_PROTOCOL *This,UINT32 Id,EFI_LBA Lba,UINTN Bytes,VOID *Buffer) {
 (VOID)This;(VOID)Id;(VOID)Lba;(VOID)Bytes;(VOID)Buffer;return EFI_WRITE_PROTECTED;
}
STATIC EFI_STATUS EFIAPI FlushDisk(EFI_BLOCK_IO_PROTOCOL *This) {(VOID)This;return EFI_SUCCESS;}
STATIC EFI_BLOCK_IO_PROTOCOL mBlock={EFI_BLOCK_IO_PROTOCOL_REVISION,&mMedia,ResetDisk,ReadDisk,WriteDisk,FlushDisk};
STATIC struct {MEDIA_RAM_DISK_DEVICE_PATH Ram;EFI_DEVICE_PATH_PROTOCOL End;} mPath;
STATIC VOID Park(VOID) {for(;;) {ArmCallWFI();}}
STATIC VOID Stage(CHAR16 *Name,EFI_STATUS Status) {Print(L"WBT %s: %r\r\n",Name,Status);DEBUG((DEBUG_ERROR,"WBT %s: %r\n",Name,Status));}
STATIC VOID Fail(CHAR16 *Name,EFI_STATUS S) {Stage(Name,S);Print(L"TARGET A NOT REACHED. HOLD POWER TO RESTART.\r\n");Park();}
// Runtime code, no BS/console/global-state calls after ExitBootServices.
STATIC VOID EFIAPI TrapReset(EFI_RESET_TYPE Type,EFI_STATUS S,UINTN Bytes,VOID *Data) {
 (VOID)Type;(VOID)S;(VOID)Bytes;(VOID)Data;for(;;) {ArmCallWFI();}
}
STATIC EFI_STATUS EFIAPI NoTime(EFI_TIME *T,EFI_TIME_CAPABILITIES *C) {(VOID)C;return T?EFI_UNSUPPORTED:EFI_INVALID_PARAMETER;}
STATIC EFI_STATUS EFIAPI NoSetTime(EFI_TIME *T) {return T?EFI_UNSUPPORTED:EFI_INVALID_PARAMETER;}
STATIC EFI_STATUS EFIAPI NoWake(BOOLEAN *E,BOOLEAN *P,EFI_TIME *T) {(VOID)E;(VOID)P;(VOID)T;return EFI_UNSUPPORTED;}
STATIC EFI_STATUS EFIAPI NoSetWake(BOOLEAN E,EFI_TIME *T) {(VOID)E;(VOID)T;return EFI_UNSUPPORTED;}
STATIC EFI_STATUS EFIAPI NoCapsule(EFI_CAPSULE_HEADER **C,UINTN N,EFI_PHYSICAL_ADDRESS G) {(VOID)C;(VOID)N;(VOID)G;return EFI_UNSUPPORTED;}
STATIC EFI_STATUS EFIAPI NoCapsuleQuery(EFI_CAPSULE_HEADER **C,UINTN N,UINT64 *M,EFI_RESET_TYPE *R) {(VOID)C;(VOID)N;(VOID)M;(VOID)R;return EFI_UNSUPPORTED;}
STATIC EFI_STATUS RuntimeStubs(VOID) {
 EFI_HANDLE H=NULL;EFI_STATUS S;
 gST->RuntimeServices->ResetSystem=TrapReset;
 gST->RuntimeServices->GetTime=NoTime;gST->RuntimeServices->SetTime=NoSetTime;
 gST->RuntimeServices->GetWakeupTime=NoWake;gST->RuntimeServices->SetWakeupTime=NoSetWake;
 gST->RuntimeServices->UpdateCapsule=NoCapsule;gST->RuntimeServices->QueryCapsuleCapabilities=NoCapsuleQuery;
 gST->RuntimeServices->Hdr.CRC32=0;
 S=gBS->CalculateCrc32(gST->RuntimeServices,gST->RuntimeServices->Hdr.HeaderSize,&gST->RuntimeServices->Hdr.CRC32);
 if(EFI_ERROR(S)) {return S;}
 return gBS->InstallMultipleProtocolInterfaces(&H,&gEfiResetArchProtocolGuid,NULL,&gEfiRealTimeClockArchProtocolGuid,NULL,&gEfiCapsuleArchProtocolGuid,NULL,NULL);
}
STATIC EFI_STATUS Console(VOID) {
 EFI_HANDLE *Handles;UINTN N,I;EFI_STATUS S;EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *Out=NULL;
 S=gBS->LocateHandleBuffer(ByProtocol,&gEfiGraphicsOutputProtocolGuid,NULL,&N,&Handles);
 if(EFI_ERROR(S)) {return S;}
 for(I=0;I<N;++I) {
  gBS->ConnectController(Handles[I],NULL,NULL,TRUE);
  S=gBS->HandleProtocol(Handles[I],&gEfiSimpleTextOutProtocolGuid,(VOID **)&Out);
  if(!EFI_ERROR(S) && Out) {
   // Do not rely on unconfigured ConOut variables or an empty splitter.
   gST->ConOut=Out;gST->StdErr=Out;
   gST->ConsoleOutHandle=Handles[I];gST->StandardErrorHandle=Handles[I];break;
  }
  Out=NULL;
 }
 FreePool(Handles);
 if(!Out || !gST->ConIn) {return EFI_NOT_READY;}
 gST->Hdr.CRC32=0;return gBS->CalculateCrc32(gST,gST->Hdr.HeaderSize,&gST->Hdr.CRC32);
}
STATIC EFI_STATUS Disk(VOID) {
 VOID *Hob;EFI_PEI_HOB_POINTERS P;EFI_HANDLE H=NULL;EFI_STATUS S;UINT64 Start,End;
 Hob=GetFirstHob(EFI_HOB_TYPE_FV);
 while(Hob) {
  P.Raw=Hob;
  if(P.FirmwareVolume->Length<=64U*1024U*1024U &&
     WbtRawFromFv((CONST UINT8 *)(UINTN)P.FirmwareVolume->BaseAddress,(UINTN)P.FirmwareVolume->Length,(CONST UINT8 *)&mFatGuid,&mDisk,&mBytes)) {break;}
  Hob=GetNextHob(EFI_HOB_TYPE_FV,GET_NEXT_HOB(Hob));
 }
 if(!Hob || !WbtFatValid(mDisk,mBytes)) {return EFI_COMPROMISED_DATA;}
 mMedia.LastBlock=mBytes/512-1;
 ZeroMem(&mPath,sizeof mPath);mPath.Ram.Header.Type=MEDIA_DEVICE_PATH;mPath.Ram.Header.SubType=MEDIA_RAM_DISK_DP;
 SetDevicePathNodeLength(&mPath.Ram.Header,sizeof mPath.Ram);CopyGuid(&mPath.Ram.TypeGuid,&gEfiVirtualDiskGuid);
 Start=(UINTN)mDisk;End=Start+mBytes-1;CopyMem(mPath.Ram.StartingAddr,&Start,8);CopyMem(mPath.Ram.EndingAddr,&End,8);SetDevicePathEndNode(&mPath.End);
 S=gBS->InstallMultipleProtocolInterfaces(&H,&gEfiBlockIoProtocolGuid,&mBlock,&gEfiDevicePathProtocolGuid,&mPath,NULL);
 if(EFI_ERROR(S)) {return S;}
 return gBS->ConnectController(H,NULL,NULL,TRUE);
}
STATIC EFI_STATUS MemoryMapCheck(VOID) {
 UINTN Size=0,Key,Stride=0;UINT32 Version;EFI_MEMORY_DESCRIPTOR *Map;EFI_STATUS S;
 S=gBS->GetMemoryMap(&Size,NULL,&Key,&Stride,&Version);
 if(S!=EFI_BUFFER_TOO_SMALL || Stride<40 || Stride>256 || Size>1024*1024) {return EFI_COMPROMISED_DATA;}
 Size+=8*Stride;Map=AllocatePool(Size);if(!Map) {return EFI_OUT_OF_RESOURCES;}
 S=gBS->GetMemoryMap(&Size,Map,&Key,&Stride,&Version);
 if(!EFI_ERROR(S) && !WbtMapValid((CONST UINT8 *)Map,Size,Stride)) {S=EFI_COMPROMISED_DATA;}
 FreePool(Map);return S; // This snapshot/Key is NOT reused for ExitBootServices.
}
STATIC VOID EFIAPI WindowsBdsEntry(EFI_BDS_ARCH_PROTOCOL *This) {
 EFI_STATUS S;EFI_HANDLE *Handles,Child;UINTN N,I,InfoSize,Size,ReadSize;EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs;EFI_FILE_PROTOCOL *Root,*File;
 EFI_FILE_INFO *Info;VOID *Buffer,*Acpi;EFI_DEVICE_PATH_PROTOCOL *Path;EFI_GRAPHICS_OUTPUT_PROTOCOL *Gop;
 (VOID)This;
 EfiEventGroupSignal(&gEfiEndOfDxeEventGroupGuid);
 S=Console();if(EFI_ERROR(S)) {Fail(L"CONSOLE/GOP",S);}
 Stage(L"NO UFS / NO PHONE DISK / RAM FAT32 ONLY",EFI_SUCCESS);
 S=gBS->LocateProtocol(&gEfiGraphicsOutputProtocolGuid,NULL,(VOID **)&Gop);
 if(EFI_ERROR(S) || !Gop || !Gop->Mode || !Gop->Mode->Info || Gop->Mode->Info->HorizontalResolution!=1080 || Gop->Mode->Info->VerticalResolution!=2340) {Fail(L"GOP MODE",EFI_UNSUPPORTED);}
 S=EfiGetSystemConfigurationTable(&gEfiAcpi20TableGuid,&Acpi);Stage(L"CPU-ONLY ACPI (NOT UFS ACPI)",S);
 if(EFI_ERROR(S)) {Fail(L"ACPI TABLE",S);}
 S=gBS->SetWatchdogTimer(0,0,0,NULL);Stage(L"EFI WATCHDOG CANCEL",S);
 S=Disk();if(EFI_ERROR(S)) {Fail(L"RAM FAT32 DRIVER CONNECT",S);}
 S=gBS->LocateHandleBuffer(ByProtocol,&gEfiSimpleFileSystemProtocolGuid,NULL,&N,&Handles);
 if(EFI_ERROR(S)) {Fail(L"SIMPLE FILE SYSTEM",S);}
 // Accept only the handle that owns OUR RAM BlockIo; never scan physical media.
 for(I=0;I<N;++I) {
  EFI_BLOCK_IO_PROTOCOL *Io=NULL;
  S=gBS->HandleProtocol(Handles[I],&gEfiBlockIoProtocolGuid,(VOID **)&Io);
  if(EFI_ERROR(S) || Io!=&mBlock) {continue;}
  S=gBS->HandleProtocol(Handles[I],&gEfiSimpleFileSystemProtocolGuid,(VOID **)&Fs);if(EFI_ERROR(S)) {continue;}
  S=Fs->OpenVolume(Fs,&Root);if(EFI_ERROR(S)) {Fail(L"FAT32 OPEN VOLUME",S);}
  S=Root->Open(Root,&File,L"\\EFI\\Microsoft\\Boot\\bootmgfw.efi",EFI_FILE_MODE_READ,0);
  Root->Close(Root);if(EFI_ERROR(S)) {Fail(L"BOOTMGFW FILE ABSENT / NOT READABLE",S);}
  InfoSize=0;S=File->GetInfo(File,&gEfiFileInfoGuid,&InfoSize,NULL);
  if(S!=EFI_BUFFER_TOO_SMALL || InfoSize>4096) {Fail(L"PE FILE INFO",EFI_COMPROMISED_DATA);}
  Info=AllocatePool(InfoSize);if(!Info) {Fail(L"FILE INFO ALLOCATION",EFI_OUT_OF_RESOURCES);}
  S=File->GetInfo(File,&gEfiFileInfoGuid,&InfoSize,Info);
  if(EFI_ERROR(S) || Info->FileSize<64 || Info->FileSize>16U*1024U*1024U) {Fail(L"PE FILE SIZE",EFI_COMPROMISED_DATA);}
  Size=(UINTN)Info->FileSize;FreePool(Info);Buffer=AllocatePool(Size);if(!Buffer) {Fail(L"PE BUFFER",EFI_OUT_OF_RESOURCES);}
  ReadSize=Size;S=File->Read(File,&ReadSize,Buffer);File->Close(File);
  if(EFI_ERROR(S) || ReadSize!=Size || !WbtArmPe(Buffer,Size)) {Fail(L"ARM64 PE VALIDATION",EFI_COMPROMISED_DATA);}
  Stage(L"FAT32 FILE READ / ARM64 PE VALID",EFI_SUCCESS);
  S=MemoryMapCheck();Stage(L"MEMORY MAP STRUCTURAL CHECK ONLY",S);if(EFI_ERROR(S)) {Fail(L"MEMORY MAP",S);}
  Path=FileDevicePath(Handles[I],L"\\EFI\\Microsoft\\Boot\\bootmgfw.efi");if(!Path) {Fail(L"FILE DEVICE PATH",EFI_OUT_OF_RESOURCES);}
  Stage(L"BOOTMGFW LoadImage CALL",EFI_NOT_STARTED);
  EfiSignalEventReadyToBoot();
  S=gBS->LoadImage(FALSE,mParentImage,Path,Buffer,Size,&Child);FreePool(Buffer);FreePool(Path);FreePool(Handles);
  Stage(L"BOOTMGFW LoadImage RETURN",S);if(EFI_ERROR(S)) {Fail(L"BOOTMGFW LOAD FAILED",S);}
  Print(L"Boot-time RAM reads=%u. RTC unavailable. Variables are RAM-only.\r\n",(UINT32)mReads);
  Stage(L"BOOTMGFW StartImage CALL / NOT A SUCCESS CLAIM",EFI_NOT_STARTED);
  S=gBS->StartImage(Child,NULL,NULL);Stage(L"BOOTMGFW StartImage RETURN",S);Park();
 }
 FreePool(Handles);Fail(L"OUR RAM FAT32 SFS HANDLE NOT FOUND",EFI_NOT_FOUND);
}
STATIC EFI_BDS_ARCH_PROTOCOL mBds={WindowsBdsEntry};
EFI_STATUS EFIAPI WindowsBootTestEntry(EFI_HANDLE Image,EFI_SYSTEM_TABLE *SystemTable) {
 EFI_STATUS S;EFI_HANDLE H=NULL;(VOID)SystemTable;mParentImage=Image;
 S=RuntimeStubs();if(EFI_ERROR(S)) {return S;}
 // Return to DXE dispatch. DxeCore validates all architectural protocols first,
 // then invokes this BDS entry. Never launch Windows from a DXE constructor.
 return gBS->InstallMultipleProtocolInterfaces(&H,&gEfiBdsArchProtocolGuid,&mBds,NULL);
}
