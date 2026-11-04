// SPDX-License-Identifier: BSD-2-Clause-Patent
// Actual coordinator source; all services/register reads are RAM-only fakes.
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#define STATIC static
#define VOID void
#define CONST const
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define DEBUG_ERROR 1
#define DEBUG(args) Log args
#define EFI_SUCCESS 0ULL
#define ERR(x) (0x8000000000000000ULL | (x))
#define EFI_INVALID_PARAMETER ERR(2)
#define EFI_UNSUPPORTED ERR(3)
#define EFI_DEVICE_ERROR ERR(7)
#define EFI_OUT_OF_RESOURCES ERR(9)
#define EFI_NOT_FOUND ERR(14)
#define EFI_NOT_STARTED ERR(19)
#define EFI_ALREADY_STARTED ERR(20)
#define EFI_NOT_READY ERR(6)
#define EFI_SECURITY_VIOLATION ERR(26)
#define EFI_COMPROMISED_DATA ERR(33)
#define EFI_ERROR(x) (((x)>>63)!=0)
#define EFI_SECTION_DXE_DEPEX 19
#define EFI_SECTION_PE32 16
#define EFI_PAGE_SIZE 4096
#define EFI_SIZE_TO_PAGES(x) (((x)+4095)/4096)
#define ALIGN_VALUE(x,a) (((x)+(a)-1)&~((a)-1))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define ByProtocol 2
typedef char CHAR8; typedef int BOOLEAN;
typedef uint8_t UINT8; typedef uint32_t UINT32; typedef uint64_t UINT64;
typedef intptr_t INTN; typedef uintptr_t UINTN; typedef uint64_t EFI_STATUS;
typedef void *EFI_HANDLE; typedef void EFI_SYSTEM_TABLE;
typedef struct {UINT32 A;uint16_t B,C;uint8_t D[8];} EFI_GUID;
typedef struct {UINT64 Address,Length;} ARM_MEMORY_REGION_DESCRIPTOR_EX;
typedef struct {VOID *ImageBase;UINT64 ImageSize;} EFI_LOADED_IMAGE_PROTOCOL;
typedef struct {UINT32 MediaId,BlockSize,IoAlign;UINT64 LastBlock;BOOLEAN MediaPresent,LogicalPartition,RemovableMedia;} EFI_BLOCK_IO_MEDIA;
struct Block;
typedef struct Block {EFI_BLOCK_IO_MEDIA *Media;EFI_STATUS (*ReadBlocks)(struct Block *,UINT32,UINT64,UINTN,VOID *);} EFI_BLOCK_IO_PROTOCOL;
typedef struct {
 EFI_STATUS (*LocateProtocol)(EFI_GUID *,VOID *,VOID **);
 EFI_STATUS (*HandleProtocol)(EFI_HANDLE,EFI_GUID *,VOID **);
 EFI_STATUS (*LoadImage)(BOOLEAN,EFI_HANDLE,VOID *,VOID *,UINTN,EFI_HANDLE *);
 EFI_STATUS (*StartImage)(EFI_HANDLE,VOID *,VOID *);
 EFI_STATUS (*SetWatchdogTimer)(UINTN,UINT64,UINTN,VOID *);
 EFI_STATUS (*LocateHandleBuffer)(UINTN,EFI_GUID *,VOID *,UINTN *,EFI_HANDLE **);
} EFI_BOOT_SERVICES;
static EFI_BOOT_SERVICES Services;
static EFI_BOOT_SERVICES *gBS=&Services;
static EFI_GUID gEfiLoadedImageProtocolGuid,gEfiBlockIoProtocolGuid;
static UINT32 Regs[0xd0000/4];
static unsigned Reads, LoadCalls, StartCalls;
static int SectionMode;
static EFI_STATUS FakeLoadStatus, FakeStartStatus;
static VOID Log(int L,const char *F,...) {(void)L;(void)F;}
static UINT32 MmioRead32(UINTN A) {assert(A>=0x15000000 && A+4<=0x150d0000 && A%4==0);Reads++;return Regs[(A-0x15000000)/4];}
static EFI_STATUS LocateMemoryMapAreaByName(CHAR8 *N,ARM_MEMORY_REGION_DESCRIPTOR_EX *R) {
 if(strcmp(N,"SMMU"))return EFI_NOT_FOUND;R->Address=0x15000000;R->Length=0xd0000;return 0;
}
static EFI_STATUS LocateConfigurationMapUINT32ByName(CHAR8 *N,UINT32 *V) {(void)N;(void)V;return EFI_NOT_FOUND;}
static VOID *AllocateAlignedPages(UINTN N,UINTN A) {(void)A;return malloc(N*4096);}
static VOID FreeAlignedPages(VOID *P,UINTN N) {(void)N;free(P);}
static VOID FreePool(VOID *P) {free(P);}
static EFI_STATUS GetSectionFromAnyFv(EFI_GUID *G,UINTN T,UINTN I,VOID **B,UINTN *N) {
 (void)G;(void)I;
 if(!SectionMode)return EFI_NOT_FOUND;
 *N=T==EFI_SECTION_DXE_DEPEX?2:64;*B=calloc(1,*N);
 if(T==EFI_SECTION_DXE_DEPEX){((UINT8 *)*B)[0]=6;((UINT8 *)*B)[1]=8;}
 return 0;
}
static EFI_STATUS FakeLoad(BOOLEAN P,EFI_HANDLE Parent,VOID *Path,VOID *B,UINTN N,EFI_HANDLE *H) {
 (void)P;(void)Parent;(void)Path;(void)B;(void)N;LoadCalls++;*H=(VOID *)0x1111;return FakeLoadStatus;
}
static EFI_STATUS FakeStart(EFI_HANDLE H,VOID *A,VOID *B) {(void)A;(void)B;assert(H==(VOID *)0x1111);StartCalls++;return FakeStartStatus;}
static VOID ZeroMem(VOID *P,UINTN N) {memset(P,0,N);}
static VOID CopyMem(VOID *D,CONST VOID *S,UINTN N) {memcpy(D,S,N);}
static int CompareMem(CONST VOID *A,CONST VOID *B,UINTN N) {return memcmp(A,B,N);}
static VOID WriteBackInvalidateDataCacheRange(VOID *P,UINTN N) {(void)P;(void)N;}
static EFI_STATUS SerialPortInitialize(VOID) {return 0;}
static VOID CpuDeadLoop(VOID) {abort();}
#include "../../Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/PreFinalDxe.c"

static VOID ReportedFixture(VOID) {
 memset(Regs,0,sizeof Regs);Reads=0;
 Regs[0x20/4]=0x40017e4f;Regs[0x24/4]=0x6000003d;
 Regs[0x800/4]=0x800f0300;Regs[0xc00/4]=2;
 // CB2 values are a fixture, NOT claimed physical observations.
 Regs[(0x1000+2*4)/4]=0x1f000;Regs[(0x1800+2*4)/4]=1;
 Regs[(0x80000+2*0x1000)/4]=0xe0;mIoc=0;
 assert(CaptureNative("fixture")==EFI_SUCCESS);
}
int main(void) {
 Services.LoadImage=FakeLoad;Services.StartImage=FakeStart;
 mLoadStatus[0]=mStartStatus[0]=EFI_NOT_STARTED;
 assert(StartNative(0)==EFI_NOT_FOUND && LoadCalls==0 && StartCalls==0);
 SectionMode=1;FakeLoadStatus=EFI_DEVICE_ERROR;
 assert(StartNative(0)==EFI_DEVICE_ERROR && LoadCalls==1 && StartCalls==0);
 assert(mLoadStatus[0]==EFI_DEVICE_ERROR && mStartStatus[0]==EFI_NOT_STARTED);
 FakeLoadStatus=0;FakeStartStatus=EFI_NOT_READY;
 assert(StartNative(0)==EFI_NOT_READY && LoadCalls==2 && StartCalls==1);
 assert(mLoadStatus[0]==0 && mStartStatus[0]==EFI_NOT_READY);
 FakeStartStatus=0;assert(StartNative(0)==0 && LoadCalls==3 && StartCalls==2);
 assert(mLoadStatus[0]==0 && mStartStatus[0]==0);
 mHalEntry=EFI_NOT_READY;
 {DAVINCI_HAL_TABLE *T=NULL;assert(InitHalTable(&T)==EFI_NOT_STARTED);}
 mHalEntry=EFI_NOT_STARTED;
 assert(mReadback==EFI_NOT_STARTED && mHalStatus==EFI_NOT_STARTED && mDomain.Create==0xffffffffU);
 ReportedFixture();assert(Reads>0);assert(ReadbackUfs()==EFI_SUCCESS);
 assert(Snapshot(FALSE)==EFI_UNSUPPORTED); // old-source/status inconsistency
 assert(NativeProviderSafe()==EFI_SUCCESS);
 mLive.Sctlr[2]=0xe1;assert(ReadbackUfs()==EFI_SECURITY_VIOLATION);mLive.Sctlr[2]=0xe0;
 mLive.S2cr[0]=0x20002;assert(ReadbackUfs()==EFI_SECURITY_VIOLATION);mLive.S2cr[0]=2;
 mLive.Smr[1]=0x800f0300;mLive.S2cr[1]=2;assert(ReadbackUfs()==EFI_SECURITY_VIOLATION);mLive.Smr[1]=0;
 mLive.Smr[0]=0;assert(!HasUfsRoute());assert(ReadbackUfs()==EFI_SECURITY_VIOLATION);
 ReportedFixture();mLive.Smr[1]=0x80000540;mLive.S2cr[1]=3;
 assert(NativeProviderSafe()==EFI_ALREADY_STARTED);assert(ReadbackUfs()==EFI_SUCCESS);
 ReportedFixture();mLive.Smr[1]=0x80000800;mLive.S2cr[1]=0;
 assert(NativeProviderSafe()==EFI_SECURITY_VIOLATION); // HAL would reclaim live CB0
 ReportedFixture();mLive.Sctlr[0]=1;assert(SafePool(1,1)==EFI_SECURITY_VIOLATION);
 ReportedFixture();Regs[0]=1;assert(CaptureNative("disabled")==EFI_SECURITY_VIOLATION);
 ReportedFixture();Regs[0x24/4]=0x6000003e;assert(CaptureNative("unknown signature")==EFI_UNSUPPORTED);
 return 0;
}
