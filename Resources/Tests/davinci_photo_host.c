// SPDX-License-Identifier: BSD-2-Clause-Patent
// Execute the actual photo exception/reset/checkpoint code in host RAM.
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#define STATIC static
#define CONST const
#define VOID void
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define EFI_SUCCESS 0ULL
#define EFI_NOT_STARTED 0x8000000000000013ULL
#define EFI_UNSUPPORTED 0x8000000000000003ULL
#define EFI_NOT_FOUND 0x800000000000000eULL
#define EFI_ALREADY_STARTED 0x8000000000000014ULL
#define EFI_ABORTED 0x8000000000000015ULL
#define EFI_ERROR(x) (((x)>>63)!=0)
#define EXCEPT_AARCH64_SYNCHRONOUS_EXCEPTIONS 0
#define EXCEPT_AARCH64_SERROR 3
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define DAVINCI_PHOTO_DIAG 1
#define DAVINCI_PHOTO_STOP 0xd010
#define NATIVE_HAL_INDEX 0
typedef uint8_t UINT8; typedef uint32_t UINT32; typedef uint64_t UINT64;
typedef size_t UINTN; typedef intptr_t INTN; typedef int32_t INT32;
typedef int BOOLEAN; typedef char CHAR8; typedef uint64_t EFI_STATUS;
typedef void *EFI_HANDLE; typedef unsigned EFI_RESET_TYPE,EFI_EXCEPTION_TYPE;
typedef struct {uint32_t A;uint16_t B,C;uint8_t D[8];} EFI_GUID;
typedef struct {UINT64 Address,Length;} ARM_MEMORY_REGION_DESCRIPTOR_EX;
typedef struct {UINT64 Signature;UINT32 Revision,HeaderSize,CRC32,Reserved;} EFI_TABLE_HEADER;
typedef void (*EFI_RESET_SYSTEM)(EFI_RESET_TYPE,EFI_STATUS,UINTN,VOID *);
typedef struct {EFI_TABLE_HEADER Hdr;EFI_RESET_SYSTEM ResetSystem;} EFI_RUNTIME_SERVICES;
typedef struct {EFI_RUNTIME_SERVICES *RuntimeServices;} EFI_SYSTEM_TABLE;
typedef struct {UINT64 ELR,ESR,FAR,LR;} EFI_SYSTEM_CONTEXT_AARCH64;
typedef struct {EFI_SYSTEM_CONTEXT_AARCH64 *SystemContextAArch64;} EFI_SYSTEM_CONTEXT;
typedef void (*HANDLER)(EFI_EXCEPTION_TYPE,EFI_SYSTEM_CONTEXT);
struct Cpu;
typedef struct Cpu {EFI_STATUS (*RegisterInterruptHandler)(struct Cpu *,EFI_EXCEPTION_TYPE,HANDLER);} EFI_CPU_ARCH_PROTOCOL;
typedef struct {VOID *ImageBase;UINT64 ImageSize;} EFI_LOADED_IMAGE_PROTOCOL;
typedef struct {
 EFI_STATUS (*LocateProtocol)(EFI_GUID *,VOID *,VOID **);
 EFI_STATUS (*HandleProtocol)(EFI_HANDLE,EFI_GUID *,VOID **);
 EFI_STATUS (*SetWatchdogTimer)(UINTN,UINT64,UINTN,VOID *);
} EFI_BOOT_SERVICES;
static struct {CHAR8 *Name;} mNative[2]={{"HAL"},{"UFS"}};
static EFI_STATUS mLoadStatus[2]={EFI_NOT_STARTED,EFI_NOT_STARTED},mStartStatus[2]={EFI_NOT_STARTED,EFI_NOT_STARTED};
static EFI_STATUS mHalEntry=EFI_NOT_STARTED,mHalInit=EFI_NOT_STARTED,mHalDomain=EFI_NOT_STARTED,mGate=EFI_NOT_STARTED,mReadback=EFI_NOT_STARTED,mBlock=EFI_NOT_STARTED,mGpt=EFI_NOT_STARTED;
static UINTN mReads,mCount,mDisks,mWin,mEsps;
static UINT32 mIoc;
static CHAR8 *mPath="NONE";
static struct {UINT32 Completed,Create,Configure,Attach;} mDomain;
static struct {UINT32 Idr0,Idr1,Cr0,Cr0Ns,N,Banks,Smr[128],S2cr[128],Cbar[128],Cba2r[128],Sctlr[128];}mLive;
static EFI_GUID gEfiCpuArchProtocolGuid,gEfiLoadedImageProtocolGuid;
static jmp_buf Park;
static unsigned RegisterCount,CallsWfi,Delays,CacheCalls;
static UINT32 FakeWdt;
static UINT8 *Frame;
static EFI_STATUS RegStatus,WatchdogStatus;
static HANDLER Handlers[4];
static EFI_STATUS Register(EFI_CPU_ARCH_PROTOCOL *P,EFI_EXCEPTION_TYPE T,HANDLER H) {
 (void)P;assert(T==0 || T==3);assert(H!=NULL);RegisterCount++;if(RegStatus==0)Handlers[T]=H;return RegStatus;
}
static EFI_CPU_ARCH_PROTOCOL Cpu={Register};
static EFI_STATUS Locate(EFI_GUID *G,VOID *R,VOID **P) {(void)G;(void)R;*P=&Cpu;return 0;}
static EFI_STATUS Handle(EFI_HANDLE H,EFI_GUID *G,VOID **P) {(void)H;(void)G;(void)P;return EFI_NOT_FOUND;}
static EFI_STATUS Watchdog(UINTN N,UINT64 C,UINTN S,VOID *P) {assert(N==0&&C==0&&S==0&&P==NULL);return WatchdogStatus;}
static EFI_BOOT_SERVICES Bs={Locate,Handle,Watchdog};static EFI_BOOT_SERVICES *gBS=&Bs;
static VOID ArmCallWFI(VOID) {CallsWfi++;longjmp(Park,1);}
static VOID MicroSecondDelay(UINTN N) {assert(N==1000000);Delays++;}
static UINT64 GetPerformanceCounter(VOID) {return 1000000000ULL;}
static UINT64 GetTimeInNanoSecond(UINT64 N) {return N;}
static EFI_STATUS LocateMemoryMapAreaByName(CHAR8 *N,ARM_MEMORY_REGION_DESCRIPTOR_EX *R) {
 if(!strcmp(N,"Display Reserved")){R->Address=(UINTN)Frame;R->Length=1080U*2340U*4U+0x108;return 0;}
 if(!strcmp(N,"APSS_WDT_TMR1")){R->Address=0x17c10000;R->Length=4096;return 0;}
 return EFI_NOT_FOUND;
}
static UINT32 MmioRead32(UINTN A) {assert(A==0x17c10008);return FakeWdt;}
static VOID WriteBackInvalidateDataCacheRange(VOID *P,UINTN N) {
 assert((UINTN)P>=(UINTN)Frame && (UINTN)P+N<=(UINTN)Frame+1080U*2340U*4U+0x108);CacheCalls++;
}
static VOID ZeroMem(VOID *P,UINTN N){memset(P,0,N);}
static VOID CopyMem(VOID *D,VOID *S,UINTN N){memcpy(D,S,N);}
// Format-independent mock: screen bounds/control-flow, not PrintLib testing.
static UINTN AsciiSPrint(CHAR8 *B,UINTN N,CONST CHAR8 *F,...) {UINTN L=strlen(F);if(L>=N)L=N-1;memcpy(B,F,L);B[L]=0;return L;}
#include "../../Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/ReadOnlyChecks.h"
#include "../../Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/PhotoDiag.h"
int main(void) {
 UINTN Bytes=1080U*2340U*4U+0x108;Frame=calloc(1,Bytes+32);assert(Frame);
 EFI_RUNTIME_SERVICES Rt={0};Rt.Hdr.HeaderSize=sizeof Rt;
 EFI_SYSTEM_TABLE St={&Rt};WatchdogStatus=EFI_NOT_FOUND;
 if(setjmp(Park)==0){PhotoInit(&St);assert(0);}
 assert(mPhotoCode==0xd010 && mPhotoStopped && CallsWfi==1);
 assert(RegisterCount==2 && Handlers[0] && Handlers[3] && !Handlers[1] && !Handlers[2]);
 assert(mPhotoWatchdog==EFI_NOT_FOUND && mPhotoWdt==0 && mPhotoWdtInitial==0);
 assert(Rt.ResetSystem==PhotoReset);UINT32 Saved=Rt.Hdr.CRC32;Rt.Hdr.CRC32=0;assert(Crc((UINT8 *)&Rt,sizeof Rt)==Saved);Rt.Hdr.CRC32=Saved;
 assert(*(UINT64 *)(Frame+1080U*2340U*4U+0x100)==0x445550324d555445ULL);
 assert(CacheCalls>0 && Frame[Bytes]==0 && Frame[Bytes+31]==0);
 mPhotoStopped=FALSE;PhotoCheckpoint(0xb0b6,"HAL START",EFI_NOT_STARTED,TRUE);assert(Delays==1 && mPhotoCode==0xb0b6);
 EFI_SYSTEM_CONTEXT_AARCH64 A={0x1234,0x96000000,0x15000000,0x5678};EFI_SYSTEM_CONTEXT C={&A};
 if(setjmp(Park)==0){PhotoException(0,C);assert(0);}
 assert(mPhotoFatal && mPhotoStopped && mPhotoCode==0xb0b6 && mPhotoPending);
 assert(mPhotoElr==0x1234 && mPhotoEsr==0x96000000 && mPhotoFar==0x15000000 && mPhotoLr==0x5678);
 assert(mPhotoResetStatus==EFI_NOT_STARTED);mPhotoFatal=FALSE;
 if(setjmp(Park)==0){PhotoReset(1,EFI_ABORTED,0,NULL);assert(0);}
 assert(mPhotoResetType==1 && mPhotoResetStatus==EFI_ABORTED && mPhotoStopped);
 Rt.Hdr.HeaderSize=sizeof Rt+1;EFI_RESET_SYSTEM Prev=Rt.ResetSystem;PhotoArmResetHook();assert(mPhotoResetHook==EFI_UNSUPPORTED && Rt.ResetSystem==Prev);
 mPhotoFatal=FALSE;RegStatus=EFI_ALREADY_STARTED;mPhotoStopped=FALSE;Rt.Hdr.HeaderSize=sizeof Rt;
 if(setjmp(Park)==0){PhotoInit(&St);assert(0);}
 assert(mPhotoSync==EFI_ALREADY_STARTED && mPhotoSError==EFI_ALREADY_STARTED && RegisterCount==4);
 free(Frame);return 0;
}
