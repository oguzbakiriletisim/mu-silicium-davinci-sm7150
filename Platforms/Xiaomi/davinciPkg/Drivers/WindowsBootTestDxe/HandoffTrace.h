// SPDX-License-Identifier: BSD-2-Clause-Patent
// Boot Services observation only: always forward the original arguments/status.
#ifndef WBT_HANDOFF_TRACE_H
#define WBT_HANDOFF_TRACE_H
#ifndef WBT_TRACE
#define WBT_TRACE(Args) DEBUG(Args)
#endif
STATIC EFI_ALLOCATE_PAGES mRealAllocatePages;
STATIC EFI_FREE_PAGES mRealFreePages;
STATIC EFI_EVENT mExitEvent;
STATIC BOOLEAN mTraceBusy;
STATIC UINTN mTracePhase,mPageCalls,mFreeCalls,mChildApiCalls;
STATIC UINT64 mTraceChildBase,mTraceChildSize;
STATIC BOOLEAN CallerIsChild(UINTN Caller) {
 return mTraceChildBase!=0 && Caller>=mTraceChildBase && Caller-mTraceChildBase<mTraceChildSize;
}
STATIC EFI_STATUS EFIAPI TraceAllocatePages(EFI_ALLOCATE_TYPE Type,EFI_MEMORY_TYPE Kind,UINTN Pages,EFI_PHYSICAL_ADDRESS *Memory) {
 EFI_STATUS S;EFI_PHYSICAL_ADDRESS Requested=Memory?*Memory:0,Actual;UINTN Caller=(UINTN)RETURN_ADDRESS(0);BOOLEAN Child=CallerIsChild(Caller);BOOLEAN Interesting=Type==AllocateAddress && (Requested==0x102000 || Requested==0x10000000);
 if(mTraceBusy) {return mRealAllocatePages(Type,Kind,Pages,Memory);}
 ++mPageCalls;if(Child) {++mChildApiCalls;}
 mTraceBusy=TRUE;
 if(Interesting) {WBT_TRACE((DEBUG_ERROR,"WBT API ALLOC CALL phase=%u type=%u kind=%u pages=%lu req=%016lx caller=%016lx child=%u\n",(UINT32)mTracePhase,Type,Kind,(UINT64)Pages,Requested,(UINT64)Caller,Child));}
 S=mRealAllocatePages(Type,Kind,Pages,Memory);Actual=Memory?*Memory:0;
 if(Interesting || EFI_ERROR(S) || Pages>=256) {
  WBT_TRACE((DEBUG_ERROR,"WBT API ALLOC RETURN phase=%u req=%016lx actual=%016lx pages=%lu status=%016lx caller=%016lx child=%u\n",(UINT32)mTracePhase,Requested,Actual,(UINT64)Pages,(UINT64)S,(UINT64)Caller,Child));
 }
 mTraceBusy=FALSE;return S;
}
STATIC EFI_STATUS EFIAPI TraceFreePages(EFI_PHYSICAL_ADDRESS Memory,UINTN Pages) {
 EFI_STATUS S;UINTN Caller=(UINTN)RETURN_ADDRESS(0);BOOLEAN Child=CallerIsChild(Caller);
 if(mTraceBusy) {return mRealFreePages(Memory,Pages);}
 ++mFreeCalls;if(Child) {++mChildApiCalls;}mTraceBusy=TRUE;
 S=mRealFreePages(Memory,Pages);
 if(EFI_ERROR(S) || Pages>=256) {WBT_TRACE((DEBUG_ERROR,"WBT API FREE phase=%u base=%016lx pages=%lu status=%016lx caller=%016lx child=%u\n",(UINT32)mTracePhase,Memory,(UINT64)Pages,(UINT64)S,(UINT64)Caller,Child));}
 mTraceBusy=FALSE;return S;
}
STATIC VOID EFIAPI ObserveExitBoot(EFI_EVENT Event,VOID *Context) {
 (VOID)Event;(VOID)Context;mBootServicesEnded=TRUE;
 WBT_TRACE((DEBUG_ERROR,"WBT EXIT_BOOT_SERVICES EVENT OBSERVED phase=%u child-api-calls=%lu\n",(UINT32)mTracePhase,(UINT64)mChildApiCalls));
}
STATIC EFI_STATUS InstallHandoffTrace(VOID) {
 EFI_STATUS S;
 if(mRealAllocatePages || mRealFreePages) {return EFI_ALREADY_STARTED;}
 S=gBS->CreateEventEx(EVT_NOTIFY_SIGNAL,TPL_NOTIFY,ObserveExitBoot,NULL,&gEfiEventExitBootServicesGuid,&mExitEvent);
 if(EFI_ERROR(S)) {return S;}
 mRealAllocatePages=gBS->AllocatePages;mRealFreePages=gBS->FreePages;
 gBS->AllocatePages=TraceAllocatePages;gBS->FreePages=TraceFreePages;gBS->Hdr.CRC32=0;
 S=gBS->CalculateCrc32(gBS,gBS->Hdr.HeaderSize,&gBS->Hdr.CRC32);
 if(EFI_ERROR(S)) {
  gBS->AllocatePages=mRealAllocatePages;gBS->FreePages=mRealFreePages;
  gBS->CloseEvent(mExitEvent);mRealAllocatePages=NULL;mRealFreePages=NULL;
  gBS->Hdr.CRC32=0;gBS->CalculateCrc32(gBS,gBS->Hdr.HeaderSize,&gBS->Hdr.CRC32);
 }
 return S;
}
STATIC EFI_STATUS RestoreHandoffTrace(VOID) {
 EFI_STATUS S;
 if(mBootServicesEnded) {return EFI_UNSUPPORTED;}
 gBS->AllocatePages=mRealAllocatePages;gBS->FreePages=mRealFreePages;
 gBS->CloseEvent(mExitEvent);mRealAllocatePages=NULL;mRealFreePages=NULL;
 gBS->Hdr.CRC32=0;S=gBS->CalculateCrc32(gBS,gBS->Hdr.HeaderSize,&gBS->Hdr.CRC32);return S;
}
#endif
