// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef DAVINCI_PHOTO_DIAG_H
#define DAVINCI_PHOTO_DIAG_H
#if defined(DAVINCI_PHOTO_DIAG) && DAVINCI_PHOTO_DIAG
#include <Protocol/Cpu.h>
#include <Library/ArmLib.h>
#include <Library/PrintLib.h>
#include <Library/TimerLib.h>
#define font5x12 mPhotoFont
#include <Resources/font5x12.h>
#undef font5x12
#include "PhotoRaster.h"
#ifndef DAVINCI_PHOTO_STOP
#define DAVINCI_PHOTO_STOP 0
#endif
#define PHOTO_STRING_1(X) #X
#define PHOTO_STRING(X) PHOTO_STRING_1(X)
STATIC CONST CHAR8 mPhotoProfile[]="DUU2_STOP=" PHOTO_STRING(DAVINCI_PHOTO_STOP);
STATIC UINT32 *mPhotoPixels;
STATIC EFI_RUNTIME_SERVICES *mPhotoRt;
STATIC EFI_STATUS mPhotoSync=EFI_NOT_STARTED,mPhotoSError=EFI_NOT_STARTED,mPhotoResetHook=EFI_NOT_STARTED;
STATIC EFI_STATUS mPhotoWatchdog=EFI_NOT_STARTED,mPhotoLastStatus=EFI_NOT_STARTED;
STATIC UINT32 mPhotoCode,mPhotoWdt=0xffffffffU,mPhotoWdtInitial=0xffffffffU;
STATIC volatile UINT64 mPhotoMmio;
STATIC UINT32 mPhotoRegMask;
STATIC UINT8 mPhotoBankValid[128];
STATIC UINT64 mPhotoStartCounter,mPhotoElapsed;
STATIC EFI_GUID mPhotoWinGuid,mPhotoEspGuid,mPhotoDiskGuid,mPhotoMissingProtocol;
STATIC BOOLEAN mPhotoMissingSeen;
STATIC BOOLEAN mPhotoWinSeen,mPhotoEspSeen,mPhotoDiskSeen;
STATIC BOOLEAN mPhotoPending,mPhotoFatal,mPhotoStopped;
STATIC CHAR8 mPhotoLabel[64]="INIT",mPhotoResult[64]="NONE";
STATIC UINT64 mPhotoElr,mPhotoEsr,mPhotoFar,mPhotoLr,mPhotoResetType;
STATIC EFI_STATUS mPhotoResetStatus=EFI_NOT_STARTED;
STATIC struct {UINT64 Base,Size;} mPhotoImages[ARRAY_SIZE(mNative)];
STATIC VOID PhotoRender (VOID);
STATIC VOID PhotoPark (VOID) { for (;;) { ArmCallWFI(); } }
STATIC VOID PhotoLine (UINTN Row, CONST CHAR8 *Text, UINT32 Color) {
  UINTN X=12,I=0;
  if (!mPhotoPixels || Row>=54) { return; }
  while (Text[I] && I<58) { PhotoGlyph(mPhotoPixels,1080,2340,X,12+Row*42,(UINT8)Text[I],mPhotoFont,Color);X+=18;++I; }
}
STATIC VOID PhotoStatus (UINTN Row, CHAR8 *Name, EFI_STATUS Status) {
  CHAR8 B[96];AsciiSPrint(B,sizeof B,"%a %016Lx",Name,(UINT64)Status);PhotoLine(Row,B,EFI_ERROR(Status)?0xffff8080U:0xff80ff80U);
}
STATIC VOID PhotoRender (VOID) {
  CHAR8 B[128];UINTN I;UINT32 Bank=0xffffffffU;
  if (!mPhotoPixels) { return; }
  ZeroMem(mPhotoPixels,1080U*2340U*4U);
  AsciiSPrint(B,sizeof B,"DUU2 PHOTO  STOP=%04x  %a",(UINT32)DAVINCI_PHOTO_STOP,mPhotoStopped?"HALTED":"AUTO");PhotoLine(0,B,0xff80ffffU);
  AsciiSPrint(B,sizeof B,"CP=%04x %a",mPhotoCode,mPhotoLabel);PhotoLine(1,B,0xffffff00U);
  PhotoLine(2,mPhotoPending?"CALL PENDING: return/success NOT observed":"CHECKPOINT RETURN / CONTROLLED STOP",0xffffffffU);
  PhotoStatus(3,"LAST EFI",mPhotoLastStatus);PhotoLine(4,mPhotoResult,0xffffffffU);
  PhotoStatus(5,"SYNC HOOK",mPhotoSync);PhotoStatus(6,"SERROR HOOK",mPhotoSError);PhotoStatus(7,"RESET HOOK",mPhotoResetHook);
  PhotoStatus(8,"EFI WATCHDOG CANCEL",mPhotoWatchdog);
  AsciiSPrint(B,sizeof B,"APSS WDT EN init=%08x now=%08x",mPhotoWdtInitial,mPhotoWdt);PhotoLine(9,B,0xffffffffU);
  PhotoStatus(10,"HAL LoadImage",mLoadStatus[NATIVE_HAL_INDEX]);PhotoStatus(11,"HAL StartImage",mHalEntry);
  PhotoStatus(12,"HAL ABI",mHalInit);PhotoStatus(13,"HAL UFS CHAIN",mHalDomain);
  AsciiSPrint(B,sizeof B,"DOMAIN n=%u C=%08x CFG=%08x A=%08x",mDomain.Completed,mDomain.Create,mDomain.Configure,mDomain.Attach);PhotoLine(14,B,0xffffffffU);
  PhotoStatus(15,"IOMMU PATH",mGate);PhotoStatus(16,"IDENTITY READBACK",mReadback);
  if(mPhotoRegMask&1U) {
    AsciiSPrint(B,sizeof B,"IDR0=%08x IDR1=%08x",mLive.Idr0,mLive.Idr1);PhotoLine(17,B,0xffffffffU);
    AsciiSPrint(B,sizeof B,"CR0=%08x NS=%08x",mLive.Cr0,mLive.Cr0Ns);PhotoLine(18,B,0xffffffffU);
  } else {PhotoLine(17,"IDR / CR0: UNREAD",0xffffffffU);}

  for(I=0;(mPhotoRegMask&2U) && I<mLive.N && I<128;++I) {
    UINT32 Sm=mLive.Smr[I];
    if(!(Sm&0x80000000U) || (((0x300U^(Sm&0x7fffU))&~((Sm>>16)&0x7fffU))!=0)) { continue; }
    Bank=mLive.S2cr[I]&255U;
    AsciiSPrint(B,sizeof B,"SMR=%08x S2CR=%08x TYPE=%u CB=%u",Sm,mLive.S2cr[I],(mLive.S2cr[I]>>16)&3U,Bank);PhotoLine(19,B,0xffffffffU);break;
  }
  if(Bank<mLive.Banks && Bank<128) {
    if((mPhotoBankValid[Bank]&3U)==3U) {AsciiSPrint(B,sizeof B,"CBAR=%08x CBA2R=%08x",mLive.Cbar[Bank],mLive.Cba2r[Bank]);PhotoLine(20,B,0xffffffffU);}
    else {PhotoLine(20,"CBAR/CBA2R: UNREAD/PARTIAL",0xffffffffU);}
    if(mPhotoBankValid[Bank]&4U) {AsciiSPrint(B,sizeof B,"SCTLR=%08x M=%u IOC=%u",mLive.Sctlr[Bank],mLive.Sctlr[Bank]&1U,mIoc);PhotoLine(21,B,0xffffffffU);}
    else {PhotoLine(21,"SCTLR: UNREAD",0xffffffffU);}

  }
  PhotoStatus(22,"UFS LoadImage",mLoadStatus[ARRAY_SIZE(mNative)-1]);PhotoStatus(23,"UFS StartImage",mStartStatus[ARRAY_SIZE(mNative)-1]);
  AsciiSPrint(B,sizeof B,"READS=%u BLOCKS=%u GPT-LUN=%u",(UINT32)mReads,(UINT32)mCount,(UINT32)mDisks);PhotoLine(24,B,0xffffffffU);
  PhotoStatus(25,"BLOCK IO",mBlock);PhotoStatus(26,"GPT",mGpt);
  AsciiSPrint(B,sizeof B,"WIN CANDIDATES=%u ESP TYPES=%u",(UINT32)mWin,(UINT32)mEsps);PhotoLine(27,B,0xffffffffU);
  PhotoLine(28,mPath,0xffffffffU);
  AsciiSPrint(B,sizeof B,"ELR=%016Lx",mPhotoElr);PhotoLine(29,B,0xffff8080U);
  AsciiSPrint(B,sizeof B,"ESR=%016Lx FAR=%016Lx",mPhotoEsr,mPhotoFar);PhotoLine(30,B,0xffff8080U);
  AsciiSPrint(B,sizeof B,"LR=%016Lx",mPhotoLr);PhotoLine(31,B,0xffff8080U);
  for(I=0;I<ARRAY_SIZE(mNative);++I) {
    if(mPhotoElr>=mPhotoImages[I].Base && mPhotoImages[I].Size && mPhotoElr-mPhotoImages[I].Base<mPhotoImages[I].Size) {
      AsciiSPrint(B,sizeof B,"FAULT IMAGE %a RVA=%Lx",mNative[I].Name,mPhotoElr-mPhotoImages[I].Base);PhotoLine(32,B,0xffff8080U);break;
    }
  }
  AsciiSPrint(B,sizeof B,"RESET type=%Lu status=%016Lx",mPhotoResetType,(UINT64)mPhotoResetStatus);PhotoLine(33,B,0xffff8080U);
  AsciiSPrint(B,sizeof B,"ELAPSED=%Lu s MMIO(our last)=%Lx",mPhotoElapsed,mPhotoMmio);PhotoLine(34,B,0xffffffffU);
  PhotoLine(35,"NO WINDOWS / NO GPT WRITES / NO FLASH",0xff80ffffU);
  PhotoLine(36,"CP pending identifies the call being attempted",0xffffffffU);
  PhotoLine(37,"Hardware/TZ reset cannot be intercepted here",0xffffffffU);
  PhotoLine(38,"HOLD POWER TO RESTART; photograph this screen",0xffffffffU);
  if(mPhotoWinSeen) {AsciiSPrint(B,sizeof B,"WIN %g",&mPhotoWinGuid);PhotoLine(40,B,0xffffffffU);}
  if(mPhotoEspSeen) {AsciiSPrint(B,sizeof B,"ESP %g",&mPhotoEspGuid);PhotoLine(41,B,0xffffffffU);}
  if(mPhotoDiskSeen) {AsciiSPrint(B,sizeof B,"DISK %g",&mPhotoDiskGuid);PhotoLine(42,B,0xffffffffU);}
  if(mPhotoMissingSeen) {AsciiSPrint(B,sizeof B,"DEPEX MISSING %g",&mPhotoMissingProtocol);PhotoLine(43,B,0xffff8080U);}
  PhotoLine(44,mPhotoProfile,0xff80ffffU);
  WriteBackInvalidateDataCacheRange(mPhotoPixels,1080U*2340U*4U);
}
STATIC VOID EFIAPI PhotoException (EFI_EXCEPTION_TYPE Type, EFI_SYSTEM_CONTEXT Context) {
  if (mPhotoFatal) { PhotoPark(); }
  mPhotoFatal=TRUE;mPhotoStopped=TRUE;
  if(Context.SystemContextAArch64) { mPhotoElr=Context.SystemContextAArch64->ELR;mPhotoEsr=Context.SystemContextAArch64->ESR;mPhotoFar=Context.SystemContextAArch64->FAR;mPhotoLr=Context.SystemContextAArch64->LR; }
  // Keep the pending checkpoint: it identifies the faulting phase.
  mPhotoLastStatus=EFI_ABORTED;
  AsciiSPrint(mPhotoResult,sizeof mPhotoResult,"EXCEPTION type=%d; no stack walk/no reset",(INT32)Type);
  PhotoRender();PhotoPark();
}
STATIC VOID EFIAPI PhotoReset (EFI_RESET_TYPE Type, EFI_STATUS Status, UINTN DataSize, VOID *Data) {
  (VOID)DataSize;(VOID)Data;
  if(mPhotoFatal) { PhotoPark(); }
  mPhotoFatal=TRUE;mPhotoStopped=TRUE;mPhotoResetType=Type;mPhotoResetStatus=Status;
  AsciiSPrint(mPhotoResult,sizeof mPhotoResult,"RESET_SYSTEM REQUEST CAPTURED; not executed");
  PhotoRender();PhotoPark();
}
STATIC VOID PhotoArmResetHook (VOID) {
  if(!mPhotoRt || mPhotoRt->Hdr.HeaderSize<sizeof(EFI_TABLE_HEADER) || mPhotoRt->Hdr.HeaderSize>sizeof(*mPhotoRt)) {mPhotoResetHook=EFI_UNSUPPORTED;return;}
  if(mPhotoRt->ResetSystem!=PhotoReset) {
    mPhotoRt->ResetSystem=PhotoReset;mPhotoRt->Hdr.CRC32=0;
    mPhotoRt->Hdr.CRC32=Crc((UINT8 *)mPhotoRt,mPhotoRt->Hdr.HeaderSize);
  }
  mPhotoResetHook=EFI_SUCCESS;
}
STATIC VOID PhotoCheckpoint (UINT32 Code, CHAR8 *Label, EFI_STATUS Status, BOOLEAN Pending) {
  ARM_MEMORY_REGION_DESCRIPTOR_EX R;
  mPhotoCode=Code;mPhotoPending=Pending;mPhotoLastStatus=Status;
  mPhotoElapsed=GetTimeInNanoSecond(GetPerformanceCounter()-mPhotoStartCounter)/1000000000ULL;
  AsciiSPrint(mPhotoLabel,sizeof mPhotoLabel,"%a",Label);
  if(!EFI_ERROR(LocateMemoryMapAreaByName("APSS_WDT_TMR1",&R)) && R.Address==0x17c10000 && R.Length>=12) {
    mPhotoWdt=MmioRead32((UINTN)R.Address+8);
    if(mPhotoWdtInitial==0xffffffffU) {mPhotoWdtInitial=mPhotoWdt;} // Same ENABLE register disabled by PrePi; never written here.
  }
  PhotoArmResetHook();PhotoRender();
  if(Code==DAVINCI_PHOTO_STOP && DAVINCI_PHOTO_STOP!=0) {mPhotoStopped=TRUE;PhotoRender();PhotoPark();}
  // One-second bounded pre-call window for video/photo. No watchdog feeding.
  if(Pending) {MicroSecondDelay(1000000);}
}
STATIC VOID PhotoNewCapture (VOID) {mPhotoRegMask=0;ZeroMem(mPhotoBankValid,sizeof mPhotoBankValid);}
STATIC VOID PhotoRegsDone (UINT32 Bits) {mPhotoRegMask|=Bits;}
STATIC VOID PhotoBankDone (UINTN Bank, UINT8 Bits) {if(Bank<128) {mPhotoBankValid[Bank]|=Bits;}}
STATIC VOID PhotoDepexMissing (VOID *Protocol, VOID *Image) {(VOID)Image;CopyMem(&mPhotoMissingProtocol,Protocol,16);mPhotoMissingSeen=TRUE;}
STATIC VOID PhotoMarkMmio (UINTN Address) {mPhotoMmio=Address;}
STATIC VOID PhotoDiskGuid (VOID *Guid) {CopyMem(&mPhotoDiskGuid,Guid,16);mPhotoDiskSeen=TRUE;}
STATIC VOID PhotoPartitionGuid (BOOLEAN Win, BOOLEAN Esp, VOID *Guid) {
  if(Win) {CopyMem(&mPhotoWinGuid,Guid,16);mPhotoWinSeen=TRUE;}
  if(Esp) {CopyMem(&mPhotoEspGuid,Guid,16);mPhotoEspSeen=TRUE;}
}
STATIC VOID PhotoModule (UINTN Index, UINT32 Stage, EFI_STATUS Status, BOOLEAN Pending) {
  STATIC CHAR8 *Stages[]={"DEPEX CALL","DEPEX RET","FV READ","FV RET","LOAD CALL","LOAD RET","START CALL","START RET"};
  CHAR8 B[64];
  if(Index>=ARRAY_SIZE(mNative) || Stage>=8) {return;}
  AsciiSPrint(B,sizeof B,"%a %a",mNative[Index].Name,Stages[Stage]);
  PhotoCheckpoint(0xB000U+((UINT32)Index<<4)+Stage,B,Status,Pending);
}
STATIC VOID PhotoResult (CHAR8 *Name, EFI_STATUS Status) {
  AsciiSPrint(mPhotoResult,sizeof mPhotoResult,"%a",Name);mPhotoLastStatus=Status;PhotoRender();
}
STATIC VOID PhotoImage (UINTN Index, EFI_HANDLE Handle) {
  EFI_LOADED_IMAGE_PROTOCOL *L=NULL;
  if(!EFI_ERROR(gBS->HandleProtocol(Handle,&gEfiLoadedImageProtocolGuid,(VOID **)&L)) && L) { mPhotoImages[Index].Base=(UINTN)L->ImageBase;mPhotoImages[Index].Size=L->ImageSize; }
}
STATIC VOID PhotoInit (EFI_SYSTEM_TABLE *SystemTable) {
  ARM_MEMORY_REGION_DESCRIPTOR_EX R;EFI_CPU_ARCH_PROTOCOL *Cpu=NULL;EFI_STATUS S;
  if(EFI_ERROR(LocateMemoryMapAreaByName("Display Reserved",&R)) || !PhotoRasterValid(1080,2340,(UINTN)R.Length) || R.Length<1080U*2340U*4U+0x108) {return;}
  mPhotoPixels=(UINT32 *)(UINTN)R.Address;
  *(volatile UINT64 *)(UINTN)(R.Address+1080U*2340U*4U+0x100)=0x445550324d555445ULL;
  WriteBackInvalidateDataCacheRange((VOID *)(UINTN)(R.Address+1080U*2340U*4U+0x100),8);
  mPhotoRt=SystemTable->RuntimeServices;
  S=gBS->LocateProtocol(&gEfiCpuArchProtocolGuid,NULL,(VOID **)&Cpu);
  if(!EFI_ERROR(S) && Cpu) {
    mPhotoSync=Cpu->RegisterInterruptHandler(Cpu,EXCEPT_AARCH64_SYNCHRONOUS_EXCEPTIONS,PhotoException);
    mPhotoSError=Cpu->RegisterInterruptHandler(Cpu,EXCEPT_AARCH64_SERROR,PhotoException);
  } else {mPhotoSync=mPhotoSError=S;}
  mPhotoStartCounter=GetPerformanceCounter();
  // IRQ/FIQ handlers and existing registered handlers are never unregistered.
  mPhotoWatchdog=gBS->SetWatchdogTimer(0,0,0,NULL);
  PhotoCheckpoint(0xD010,"PHOTO/EXCEPTION/RESET HOOKS",EFI_SUCCESS,FALSE);
}
STATIC VOID PhotoFinish (VOID) {mPhotoStopped=TRUE;PhotoCheckpoint(0xDFFF,"FINAL RESULTS / HALTED",mPhotoLastStatus,FALSE);PhotoPark();}
// Suppress only this coordinator's scrolling DEBUG output. Source serial ports
// also honor the framebuffer cookie; proprietary private loggers may not.
#undef DEBUG
#define DEBUG(Arguments) do {} while (0)
#else
#define PhotoInit(S) do {} while (0)
#define PhotoCheckpoint(C,L,S,P) do {} while (0)
#define PhotoNewCapture() do {} while (0)
#define PhotoRegsDone(B) do {} while (0)
#define PhotoBankDone(I,B) do {} while (0)
#define PhotoDepexMissing(P,I) do {} while (0)
#define PhotoMarkMmio(A) do {} while (0)
#define PhotoDiskGuid(G) do {} while (0)
#define PhotoPartitionGuid(W,E,G) do {} while (0)
#define PhotoModule(I,C,S,P) do {} while (0)
#define PhotoResult(N,S) do {} while (0)
#define PhotoImage(I,H) do {} while (0)
#define PhotoFinish() do {} while (0)
#endif
#endif
