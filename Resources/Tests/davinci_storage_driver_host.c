// SPDX-License-Identifier: BSD-2-Clause-Patent
// Compile the real DXE source with mocked UEFI services; no device access.
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define STATIC static
#define VOID void
#define EFIAPI
#define DEBUG_WARN 1
#define DEBUG(args) HostDebug args
#define EFI_SUCCESS 0
#define EFI_NOT_FOUND 14
#define EFI_ERROR(s) ((s) != EFI_SUCCESS)
#define EVT_NOTIFY_SIGNAL 1
#define TPL_CALLBACK 8
#define ByProtocol 2
#define TRUE 1
#define FALSE 0
typedef char CHAR8;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
typedef uintptr_t UINTN;
typedef int EFI_STATUS;
typedef void *EFI_HANDLE;
typedef void *EFI_EVENT;
typedef void EFI_SYSTEM_TABLE;
typedef struct { UINT32 A; unsigned short B, C; unsigned char D[8]; } EFI_GUID;
typedef struct { UINT64 Address, Length; } ARM_MEMORY_REGION_DESCRIPTOR_EX;
typedef struct { int MediaPresent, LogicalPartition; UINT32 BlockSize; UINT64 LastBlock; } EFI_BLOCK_IO_MEDIA;
typedef struct { EFI_BLOCK_IO_MEDIA *Media; } EFI_BLOCK_IO_PROTOCOL;
typedef void (*NOTIFY)(EFI_EVENT, VOID *);
typedef struct {
  EFI_STATUS (*LocateProtocol)(EFI_GUID *, VOID *, VOID **);
  EFI_STATUS (*LocateHandleBuffer)(int, EFI_GUID *, VOID *, UINTN *, EFI_HANDLE **);
  EFI_STATUS (*HandleProtocol)(EFI_HANDLE, EFI_GUID *, VOID **);
  EFI_STATUS (*CreateEventEx)(int, int, NOTIFY, VOID *, EFI_GUID *, EFI_EVENT *);
} EFI_BOOT_SERVICES;
static EFI_GUID gQcomScmProtocolGuid;
static EFI_GUID gEfiSMEMProtocolGuid, gEfiClockProtocolGuid, gEfiBlockIoProtocolGuid;
static EFI_GUID gEfiEndOfDxeEventGroupGuid, gEfiEventReadyToBootGuid;
static unsigned ProtocolCalls, ReadCalls, MapCalls, EventCalls, ScanCalls, FreeCalls, LogCalls;
static int FailConfiguration, FailMapping, FailProtocol, FailScan, FailEvents, NullBlockIo, NullMedia;
static NOTIFY Callbacks[2];
static VOID *Contexts[2];
static EFI_BLOCK_IO_MEDIA Media = {1, 0, 4096, 1023};
static EFI_BLOCK_IO_PROTOCOL Block = {&Media};
static void HostDebug(int Level, const char *Format, ...) { (void)Level; (void)Format; LogCalls++; }
static EFI_STATUS LocateConfigurationMapUINT32ByName(CHAR8 *Name, UINT32 *Base) {
  if (strcmp(Name,"EnableUfsIOC")==0) return EFI_NOT_FOUND;
  *Base = 0x146aa000; return FailConfiguration ? EFI_NOT_FOUND : EFI_SUCCESS;
}
static EFI_STATUS LocateMemoryMapAreaByAddress(UINT32 Base, ARM_MEMORY_REGION_DESCRIPTOR_EX *R) {
  MapCalls++; R->Address=Base; R->Length=0x1000; return FailMapping ? EFI_NOT_FOUND : EFI_SUCCESS;
}
static UINT32 MmioRead32(UINTN Address) {
  ReadCalls++;
  if(Address==0x146aa000) return 0xc1f8db40;
  if(Address==0x146aa004) return 3;
  assert(Address==0x146aa050); return 8;
}
static VOID FreePool(VOID *P) { FreeCalls++; free(P); }
static EFI_STATUS Locate(EFI_GUID *G, VOID *R, VOID **I) {
  (void)G; (void)R; ProtocolCalls++; *I=NULL; return EFI_NOT_FOUND;
}
static EFI_STATUS Scan(int Type, EFI_GUID *G, VOID *R, UINTN *N, EFI_HANDLE **H) {
  (void)Type; (void)G; (void)R; ScanCalls++;
  if(FailScan) return EFI_NOT_FOUND;
  *N=1; *H=malloc(sizeof(EFI_HANDLE)); assert(*H); (*H)[0]=(VOID *)1; return EFI_SUCCESS;
}
static EFI_STATUS Handle(EFI_HANDLE H, EFI_GUID *G, VOID **I) {
  (void)H; (void)G;
  Block.Media=NullMedia ? NULL : &Media; *I=NullBlockIo ? NULL : &Block;
  return FailProtocol ? EFI_NOT_FOUND : EFI_SUCCESS;
}
static EFI_STATUS Event(int Type, int Tpl, NOTIFY F, VOID *C, EFI_GUID *G, EFI_EVENT *E) {
  (void)G; assert(Type==EVT_NOTIFY_SIGNAL && Tpl==TPL_CALLBACK); assert(EventCalls<2);
  Callbacks[EventCalls]=F; Contexts[EventCalls]=C; EventCalls++;
  *E=NULL; return FailEvents ? EFI_NOT_FOUND : EFI_SUCCESS;
}
static EFI_BOOT_SERVICES Services={Locate,Scan,Handle,Event};
static EFI_BOOT_SERVICES *gBS=&Services;
#include "../../Platforms/Xiaomi/davinciPkg/Drivers/StorageAuditDxe/StorageAuditDxe.c"
static void Reset(void) {
  ProtocolCalls=ReadCalls=MapCalls=EventCalls=ScanCalls=FreeCalls=LogCalls=0;
  FailConfiguration=FailMapping=FailProtocol=FailScan=FailEvents=NullBlockIo=NullMedia=0;
}
int main(void) {
  Reset(); assert(StorageAuditEntry(NULL,NULL)==EFI_SUCCESS);
  assert(ProtocolCalls==4 && ReadCalls==3 && EventCalls==2 && ScanCalls==0);
  Callbacks[0](NULL,Contexts[0]); Callbacks[1](NULL,Contexts[1]);
  assert(ScanCalls==2 && FreeCalls==2);
  Reset(); FailConfiguration=1; assert(StorageAuditEntry(NULL,NULL)==EFI_SUCCESS);
  assert(ReadCalls==0 && MapCalls==0 && EventCalls==2);
  Reset(); FailMapping=1; FailEvents=1; assert(StorageAuditEntry(NULL,NULL)==EFI_SUCCESS);
  assert(ReadCalls==0 && MapCalls==1 && EventCalls==2);
  Reset(); assert(StorageAuditAfterUfsEntry(NULL,NULL)==EFI_SUCCESS);
  assert(ProtocolCalls==4 && ScanCalls==1 && FreeCalls==1 && ReadCalls==0 && EventCalls==0);
  Reset(); FailScan=1; assert(StorageAuditAfterUfsEntry(NULL,NULL)==EFI_SUCCESS);
  assert(FreeCalls==0);
  Reset(); FailProtocol=1; AuditBlockIo(NULL,"test"); assert(FreeCalls==1);
  Reset(); NullBlockIo=1; AuditBlockIo(NULL,"test"); assert(FreeCalls==1);
  Reset(); NullMedia=1; AuditBlockIo(NULL,"test"); assert(FreeCalls==1);
  return 0;
}
