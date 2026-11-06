// SPDX-License-Identifier: BSD-2-Clause-Patent
// QEMU/host UEFI only. Reuses the actual phone RAM BlockIo/provider functions.
// Does not call the phone's WindowsBootTestEntry or install its arch protocols.
#include "../../Drivers/WindowsBootTestDxe/WindowsBootTestDxe.c"
#include <Library/PrintLib.h>
#include <Protocol/SerialIo.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/Rng.h>
STATIC EFI_SERIAL_IO_PROTOCOL *mSerial;
STATIC VOID Log(CHAR16 *Name,UINT64 Value) {
 CHAR16 W[256];CHAR8 A[256];UINTN N;
 UnicodeSPrint(W,sizeof W,L"HOST_SMOKE %s=%016lx\r\n",Name,Value);Print(L"%s",W);
 if(mSerial) {UnicodeStrToAsciiStrS(W,A,sizeof A);N=AsciiStrLen(A);mSerial->Write(mSerial,&N,A);}
}
STATIC VOID Stop(CHAR16 *Name,EFI_STATUS S) {Log(Name,S);Park();}
STATIC VOID EFIAPI SmokeReset(EFI_RESET_TYPE T,EFI_STATUS S,UINTN N,VOID *D) {
 (VOID)N;(VOID)D;Log(L"RESET_TYPE",T);Log(L"RESET_STATUS",S);Log(L"RESET_TRAPPED_NO_RESET",1);Park();
}
STATIC EFI_STATUS LoadFile(EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs,CHAR16 *Name,VOID **Data,UINTN *Size) {
 EFI_FILE_PROTOCOL *Root,*F;EFI_FILE_INFO *Info;UINTN N=0,Bytes;EFI_STATUS S;
 S=Fs->OpenVolume(Fs,&Root);if(EFI_ERROR(S)) {return S;}
 S=Root->Open(Root,&F,Name,EFI_FILE_MODE_READ,0);Root->Close(Root);if(EFI_ERROR(S)) {return S;}
 S=F->GetInfo(F,&gEfiFileInfoGuid,&N,NULL);if(S!=EFI_BUFFER_TOO_SMALL || N>4096) {F->Close(F);return EFI_COMPROMISED_DATA;}
 Info=AllocatePool(N);if(!Info) {F->Close(F);return EFI_OUT_OF_RESOURCES;}
 S=F->GetInfo(F,&gEfiFileInfoGuid,&N,Info);if(EFI_ERROR(S) || Info->FileSize>40U*1024U*1024U) {FreePool(Info);F->Close(F);return EFI_COMPROMISED_DATA;}
 Bytes=(UINTN)Info->FileSize;FreePool(Info);*Data=AllocatePool(Bytes);if(!*Data) {F->Close(F);return EFI_OUT_OF_RESOURCES;}
 *Size=Bytes;S=F->Read(F,Size,*Data);F->Close(F);return EFI_ERROR(S)?S:(*Size==Bytes?EFI_SUCCESS:EFI_COMPROMISED_DATA);
}
EFI_STATUS EFIAPI UefiMain(EFI_HANDLE Image,EFI_SYSTEM_TABLE *SystemTable) {
 EFI_LOADED_IMAGE_PROTOCOL *Self,*Loaded;EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs;EFI_GRAPHICS_OUTPUT_PROTOCOL *G;VOID *Rng=NULL,*Data;UINTN Bytes;EFI_HANDLE Child,*Handles;UINTN Count,I;EFI_DEVICE_PATH_PROTOCOL *Path;EFI_STATUS S;UINT32 Pe,Entry;
 (VOID)SystemTable;
 gBS->LocateProtocol(&gEfiSerialIoProtocolGuid,NULL,(VOID **)&mSerial);
 Log(L"BEGIN_HOST_NOT_PHONE",1);
 S=Console();Log(L"PHONE_CONSOLE_FUNCTION",S);
 S=gBS->LocateProtocol(&gEfiGraphicsOutputProtocolGuid,NULL,(VOID **)&G);Log(L"GOP",S);
 if(!EFI_ERROR(S) && G && G->Mode && G->Mode->Info) {Log(L"GOP_WIDTH",G->Mode->Info->HorizontalResolution);Log(L"GOP_HEIGHT",G->Mode->Info->VerticalResolution);}
 S=gBS->LocateProtocol(&gEfiRngProtocolGuid,NULL,&Rng);Log(L"RNG",S);
 S=gBS->HandleProtocol(Image,&gEfiLoadedImageProtocolGuid,(VOID **)&Self);if(EFI_ERROR(S)) {Stop(L"SELF",S);}
 S=gBS->HandleProtocol(Self->DeviceHandle,&gEfiSimpleFileSystemProtocolGuid,(VOID **)&Fs);if(EFI_ERROR(S)) {Stop(L"OUTER_SFS",S);}
 // Optional PC-only reference: real GPT child supplied by AAVMF PartitionDxe.
 S=LoadFile(Fs,L"\\TEST\\use-outer-fs.flag",&Data,&Bytes);
 if(!EFI_ERROR(S)) {
  FreePool(Data);mDiskHandle=Self->DeviceHandle;Log(L"OUTER_GPT_REFERENCE_NOT_PHONE",1);
 } else {
  S=LoadFile(Fs,L"\\TEST\\verified-ram-disk.img",&Data,&Bytes);Log(L"INPUT_READ",S);if(EFI_ERROR(S)) {Park();}
  mDisk=Data;mBytes=Bytes;S=PublishDisk();Log(L"SHARED_RAM_PROVIDER_CONNECT",S);if(EFI_ERROR(S)) {Park();}
  S=gBS->LocateHandleBuffer(ByProtocol,&gEfiSimpleFileSystemProtocolGuid,NULL,&Count,&Handles);if(EFI_ERROR(S)) {Stop(L"LOCATE_SFS",S);}
  S=EFI_NOT_FOUND;
  for(I=0;I<Count;++I) {if(IsOurEsp(Handles[I])) {mDiskHandle=Handles[I];S=gBS->HandleProtocol(mDiskHandle,&gEfiSimpleFileSystemProtocolGuid,(VOID **)&Fs);break;}}
  FreePool(Handles);Log(L"SHARED_RAM_SFS",S);if(EFI_ERROR(S)) {Park();}
 }
 S=LoadFile(Fs,L"\\EFI\\Microsoft\\Boot\\bootmgfw.efi",&Data,&Bytes);Log(L"BOOTMGFW_READ",S);if(EFI_ERROR(S) || !WbtArmPe(Data,Bytes)) {Park();}
 Log(L"RAM_READ_CALLS",mReads);
 Path=FileDevicePath(mDiskHandle,L"\\EFI\\Microsoft\\Boot\\bootmgfw.efi");if(!Path) {Stop(L"DEVICE_PATH",EFI_OUT_OF_RESOURCES);}
 S=SetBootContext(Path);Log(L"BOOT_CONTEXT",S);if(EFI_ERROR(S)) {Park();}
 S=gBS->LoadImage(FALSE,Image,Path,Data,Bytes,&Child);Log(L"LOAD_RETURN",S);FreePool(Data);FreePool(Path);if(EFI_ERROR(S)) {Park();}
 S=gBS->HandleProtocol(Child,&gEfiLoadedImageProtocolGuid,(VOID **)&Loaded);if(EFI_ERROR(S)) {Stop(L"LOADED_IMAGE",S);}
 Pe=WbtLe32((CONST UINT8 *)Loaded->ImageBase+60);Entry=WbtLe32((CONST UINT8 *)Loaded->ImageBase+Pe+40);
 Log(L"IMAGE_BASE",(UINTN)Loaded->ImageBase);Log(L"IMAGE_SIZE",Loaded->ImageSize);Log(L"ENTRY_ADDRESS",(UINTN)Loaded->ImageBase+Entry);
 // Match phone test RTC behavior without claiming a functioning RTC. No fake date.
 gST->RuntimeServices->GetTime=NoTime;gST->RuntimeServices->SetTime=NoSetTime;
 gST->RuntimeServices->ResetSystem=SmokeReset;gST->RuntimeServices->Hdr.CRC32=0;
 gBS->CalculateCrc32(gST->RuntimeServices,gST->RuntimeServices->Hdr.HeaderSize,&gST->RuntimeServices->Hdr.CRC32);
 Log(L"PHONE_RTC_UNSUPPORTED_MODE",1);Log(L"START_CALL_NOT_SUCCESS",EFI_NOT_STARTED);
 gBS->Stall(5000000); // Host debugger can set an entry hardware breakpoint.
 S=gBS->StartImage(Child,NULL,NULL);Log(L"START_RETURN",S);Park();return S;
}
