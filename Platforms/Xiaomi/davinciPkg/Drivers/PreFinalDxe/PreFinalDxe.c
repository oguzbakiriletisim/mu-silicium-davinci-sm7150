// SPDX-License-Identifier: BSD-2-Clause-Patent
// No partition/filesystem/BDS driver is dispatched by this profile. No storage
// WriteBlocks, Reset, FlushBlocks, GPT repair, SCM listeners or Windows launch.
#include <Uefi.h>
#include <Pi/PiFirmwareFile.h>
#include <Protocol/BlockIo.h>
#include <Protocol/LoadedImage.h>
#include <Library/ConfigurationMapHelperLib.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/CacheMaintenanceLib.h>
#include <Library/DebugLib.h>
#include <Library/DxeServicesLib.h>
#include <Library/IoLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/MemoryMapHelperLib.h>
#include <Library/SerialPortLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include "ReadOnlyChecks.h"
#include "NativeImages.h"
#include "HalUfsBridge.h"

STATIC EFI_GUID mHal = {0x54b6d3b4,0x5d33,0x4f91,{0x86,0,0x6c,0x41,0xd5,0xde,0xb1,0x9a}};
STATIC EFI_GUID mEsp = {0xc12a7328,0xf81f,0x11d2,{0xba,0x4b,0,0xa0,0xc9,0x3e,0xc9,0x3b}};
STATIC EFI_STATUS mGate = EFI_NOT_STARTED, mHalStatus = EFI_NOT_STARTED, mUfs = EFI_NOT_STARTED, mBlock = EFI_NOT_FOUND;
STATIC EFI_STATUS mGpt = EFI_NOT_FOUND;
STATIC UINTN mCount, mDisks, mWin, mEsps, mGptFailures, mReads;
STATIC UINT32 mIdr0, mIdr1, mCr0, mMatching;
STATIC EFI_HANDLE mThisImage;

// All writes in the native path belong to the unchanged Qualcomm HAL image.
// This coordinator only reads registers and invokes published ABI methods.
#define NATIVE_HAL_INDEX (ARRAY_SIZE (mNative) - 2)
STATIC EFI_HANDLE mNativeHandle[ARRAY_SIZE (mNative)];
STATIC EFI_STATUS mLoadStatus[ARRAY_SIZE (mNative)], mStartStatus[ARRAY_SIZE (mNative)];
STATIC EFI_STATUS mHalEntry = EFI_NOT_STARTED, mHalInit = EFI_NOT_STARTED;
STATIC EFI_STATUS mHalDomain = EFI_NOT_STARTED, mReadback = EFI_NOT_STARTED;
STATIC DAVINCI_UFS_DOMAIN mDomain = { NULL, 0xffffffffU, 0xffffffffU, 0xffffffffU, 0 };
STATIC UINT32 mIoc;
STATIC CHAR8 *mPath = "NOT SELECTED";
STATIC struct {
  UINT32 Idr0, Idr1, Cr0, Cr0Ns, N, Banks;
  UINT64 CtxOffset;
  UINT32 Smr[128], S2cr[128], Cbar[128], Cba2r[128], Sctlr[128];
} mLive;

#include "PhotoDiag.h"

STATIC BOOLEAN MatchSid (UINT32 Smr, UINT32 Sid) {
  return (Smr & 0x80000000U) && (((Sid ^ (Smr & 0x7fffU)) & ~((Smr >> 16) & 0x7fffU)) == 0);
}
STATIC EFI_STATUS CaptureNative (CHAR8 *Label) {
  ARM_MEMORY_REGION_DESCRIPTOR_EX R; UINTN I;
  EFI_STATUS S = LocateMemoryMapAreaByName ("SMMU", &R);
  if (EFI_ERROR (S) || R.Address != 0x15000000 || R.Length < 0x2000) { return EFI_UNSUPPORTED; }
  PhotoNewCapture();
  PhotoMarkMmio((UINTN)R.Address+0x20);
  PhotoCheckpoint(0xA100,"SMMU IDR READ CALL",EFI_NOT_STARTED,TRUE);
  mLive.Idr0 = MmioRead32 ((UINTN)R.Address + 0x20);
  PhotoMarkMmio((UINTN)R.Address+0x24);
  mLive.Idr1 = MmioRead32 ((UINTN)R.Address + 0x24);
  PhotoMarkMmio((UINTN)R.Address);
  mLive.Cr0 = MmioRead32 ((UINTN)R.Address);
  PhotoMarkMmio((UINTN)R.Address+0x400);
  mLive.Cr0Ns = MmioRead32 ((UINTN)R.Address + 0x400);
  PhotoRegsDone(1U);
  DEBUG ((DEBUG_ERROR, "%a IDR0=%08x IDR1=%08x CR0=%08x CR0NS=%08x\n", Label, mLive.Idr0,mLive.Idr1,mLive.Cr0,mLive.Cr0Ns));
  mLive.N = mLive.Idr0 & 255U;
  // The observed QSMMU ID pair has SMS=0 although live SMRs exist. Support
  // only that exact reported pair or ordinary SMS layouts, never infer a
  // different register schema just from a nonzero word at an MMIO address.
  if (!NativeLayoutSupported(mLive.Idr0,mLive.Idr1) ||
      !ContextWindow (mLive.Idr1, R.Length, &mLive.CtxOffset, &mLive.Banks)) { return EFI_UNSUPPORTED; }
  DEBUG ((DEBUG_ERROR, "NATIVE LAYOUT SMR=%u BANKS=%u CTX_OFFSET=0x%Lx\n", mLive.N,mLive.Banks,mLive.CtxOffset));
  PhotoCheckpoint(0xA101,"SMMU SMR/S2CR READ CALL",EFI_NOT_STARTED,TRUE);
  for (I = 0; I < mLive.N; ++I) {
    PhotoMarkMmio((UINTN)R.Address+0x800+4*I);
    mLive.Smr[I] = MmioRead32 ((UINTN)R.Address + 0x800 + 4*I);
    PhotoMarkMmio((UINTN)R.Address+0xc00+4*I);
    mLive.S2cr[I] = MmioRead32 ((UINTN)R.Address + 0xc00 + 4*I);
    if (MatchSid (mLive.Smr[I], 0x300)) {
      DEBUG ((DEBUG_ERROR, "UFS GROUP=%u SMR=%08x S2CR=%08x TYPE[17:16]=%u CB[7:0]=%u\n",
              (UINT32)I,mLive.Smr[I],mLive.S2cr[I],(mLive.S2cr[I]>>16)&3U,mLive.S2cr[I]&255U));
    }
  }
  PhotoRegsDone(2U);
  PhotoMarkMmio((UINTN)R.Address+0x1000);
  PhotoCheckpoint(0xA102,"SMMU CBAR READ CALL",EFI_NOT_STARTED,TRUE);
  for (I = 0; I < mLive.Banks; ++I) {
    PhotoMarkMmio((UINTN)R.Address + 0x1000 + 4*I);
    mLive.Cbar[I] = MmioRead32 ((UINTN)R.Address + 0x1000 + 4*I); PhotoBankDone(I,1U);
  }
  PhotoMarkMmio((UINTN)R.Address+0x1800);
  PhotoCheckpoint(0xA103,"SMMU CBA2R READ CALL",EFI_NOT_STARTED,TRUE);
  for (I = 0; I < mLive.Banks; ++I) {
    PhotoMarkMmio((UINTN)R.Address + 0x1800 + 4*I);
    mLive.Cba2r[I] = MmioRead32 ((UINTN)R.Address + 0x1800 + 4*I); PhotoBankDone(I,2U);
  }
  PhotoMarkMmio((UINTN)R.Address+(UINTN)mLive.CtxOffset);
  PhotoCheckpoint(0xA104,"SMMU SCTLR READ CALL",EFI_NOT_STARTED,TRUE);
  for (I = 0; I < mLive.Banks; ++I) {
    PhotoMarkMmio((UINTN)R.Address + (UINTN)mLive.CtxOffset + (I<<12));
    mLive.Sctlr[I] = MmioRead32 ((UINTN)R.Address + (UINTN)mLive.CtxOffset + (I<<12)); PhotoBankDone(I,4U);
  }
  for (I = 0; I < mLive.N; ++I) {
    UINT32 Bank = mLive.S2cr[I] & 255U;
    if (MatchSid (mLive.Smr[I],0x300) && Bank < mLive.Banks) {
      DEBUG ((DEBUG_ERROR, "LIVE CB=%u CBAR=%08x CBA2R=%08x SCTLR=%08x M=%u\n",
              Bank,mLive.Cbar[Bank],mLive.Cba2r[Bank],mLive.Sctlr[Bank],mLive.Sctlr[Bank]&1U));
    }
  }
  if (mLive.Idr0 != MmioRead32 ((UINTN)R.Address+0x20) ||
      mLive.Idr1 != MmioRead32 ((UINTN)R.Address+0x24) ||
      mLive.Cr0 != MmioRead32 ((UINTN)R.Address) ||
      mLive.Cr0Ns != MmioRead32 ((UINTN)R.Address+0x400)) { return EFI_NOT_READY; }
  if ((mLive.Cr0 | mLive.Cr0Ns) & 1U) { PhotoCheckpoint(0xA1EF,"SMMU GLOBAL DISABLED",EFI_SECURITY_VIOLATION,FALSE); return EFI_SECURITY_VIOLATION; }
  PhotoCheckpoint(0xA105,"SMMU CAPTURE RETURN",EFI_SUCCESS,FALSE);
  return EFI_SUCCESS;
}
STATIC EFI_STATUS ReadbackUfs (VOID) {
  UINTN I, Sid, Matches;
  for (Sid=0x300; Sid<0x310; ++Sid) {
    Matches=0;
    for (I=0; I<mLive.N; ++I) {
      UINT32 B = mLive.S2cr[I] & 255U, T = (mLive.S2cr[I]>>16)&3U;
      if (!MatchSid (mLive.Smr[I],(UINT32)Sid)) { continue; }
      ++Matches;
      if (T == 1) { continue; } // Explicit stream bypass, no CB access needed.
      if (B >= mLive.Banks || !NativeBankBypass (mLive.S2cr[I],mLive.Cbar[B],mLive.Cba2r[B],mLive.Sctlr[B],mIoc,mLive.Banks)) {
        return EFI_SECURITY_VIOLATION;
      }
    }
    if (Matches != 1) { return EFI_SECURITY_VIOLATION; }
  }
  return EFI_SUCCESS;
}
STATIC BOOLEAN HasUfsRoute (VOID) {
  UINTN I, Sid;
  for (I=0; I<mLive.N; ++I) {
    for (Sid=0x300; Sid<0x310; ++Sid) { if (MatchSid (mLive.Smr[I],(UINT32)Sid)) { return TRUE; } }
  }
  return FALSE;
}
// The native provider runs SDC1/2/4 and USB3-0 dummy clients. Do not create
// duplicate stream matches or let its free-bank heuristic clobber live banks.
STATIC EFI_STATUS SafePool (UINTN NeedSmr, UINTN NeedCb) {
  UINTN I, B, FreeSmr=0, FreeCb=0;
  for (I=0; I+1<mLive.N; ++I) { if (!(mLive.Smr[I]&0x80000000U)) { ++FreeSmr; } }
  for (B=0; B<mLive.Banks; ++B) {
    UINT32 T=(mLive.Cbar[B]>>16)&3U;
    if (T!=0 && T!=2 && !(T==1 && (mLive.Cbar[B]&255U)==255U)) { continue; }
    if (mLive.Sctlr[B]&1U) { return EFI_SECURITY_VIOLATION; }
    for (I=0; I<mLive.N; ++I) {
      if ((mLive.Smr[I]&0x80000000U) && ((mLive.S2cr[I]>>16)&3U)==0 && (mLive.S2cr[I]&255U)==B) { return EFI_SECURITY_VIOLATION; }
    }
    ++FreeCb;
  }
  DEBUG ((DEBUG_ERROR,"HAL AVAILABLE free-SMR=%u free-CB=%u NEED=%u/%u\n",(UINT32)FreeSmr,(UINT32)FreeCb,(UINT32)NeedSmr,(UINT32)NeedCb));
  return FreeSmr>=NeedSmr && FreeCb>=NeedCb ? EFI_SUCCESS : EFI_OUT_OF_RESOURCES;
}
STATIC EFI_STATUS NativeProviderSafe (VOID) {
  UINTN I, Sid;
  for (I=0; I<mLive.N; ++I) {
    if (!(mLive.Smr[I]&0x80000000U)) { continue; }
    for (Sid=0x2a0; Sid<0x2b0; ++Sid) { if (MatchSid(mLive.Smr[I],(UINT32)Sid)) { return EFI_ALREADY_STARTED; } }
    for (Sid=0x2c0; Sid<0x2d0; ++Sid) { if (MatchSid(mLive.Smr[I],(UINT32)Sid)) { return EFI_ALREADY_STARTED; } }
    for (Sid=0x340; Sid<0x350; ++Sid) { if (MatchSid(mLive.Smr[I],(UINT32)Sid)) { return EFI_ALREADY_STARTED; } }
    if (MatchSid(mLive.Smr[I],0x540)) { return EFI_ALREADY_STARTED; }
  }
  return SafePool(5,3);
}
STATIC BOOLEAN InImage (VOID *P, UINTN Bytes, EFI_LOADED_IMAGE_PROTOCOL *L) {
  UINTN Base=(UINTN)L->ImageBase, A=(UINTN)P;
  return A>=Base && Bytes<=L->ImageSize && A-Base<=L->ImageSize-Bytes;
}
STATIC EFI_STATUS InitHalTable (DAVINCI_HAL_TABLE **T) {
  EFI_LOADED_IMAGE_PROTOCOL *L=NULL; DAVINCI_HAL_PROTOCOL *P=NULL;
  EFI_STATUS S;
  // An entry error may have caused image unload despite protocol publication.
  // Never dereference a potentially dangling protocol after StartImage failed.
  if (mHalEntry != EFI_SUCCESS || mStartStatus[NATIVE_HAL_INDEX] != EFI_SUCCESS) { return EFI_NOT_STARTED; }
  S=gBS->HandleProtocol(mNativeHandle[NATIVE_HAL_INDEX],&gEfiLoadedImageProtocolGuid,(VOID **)&L);
  if (EFI_ERROR(S) || L==NULL || L->ImageBase==NULL) { return EFI_COMPROMISED_DATA; }
  mHalStatus=gBS->LocateProtocol(&mHal,NULL,(VOID **)&P);
  if (EFI_ERROR(mHalStatus)) { return mHalStatus; }
  if (!InImage(P,sizeof(*P),L) || P->Revision!=1 ||
      !InImage((VOID *)(UINTN)P->Init,4,L) || (UINTN)P->Init-(UINTN)L->ImageBase!=0x13bc) { return EFI_COMPROMISED_DATA; }
  PhotoCheckpoint(0xC100,"HAL PROTOCOL INIT CALL",EFI_NOT_STARTED,TRUE);
  P->Init(T); // void ABI: validate its output, never invent a return status.
  PhotoCheckpoint(0xC101,"HAL INIT VOID RETURN",EFI_SUCCESS,FALSE);
  if (!InImage(*T,sizeof(**T),L) ||
      (UINTN)(*T)->Create-(UINTN)L->ImageBase!=0x1904 ||
      (UINTN)(*T)->Attach-(UINTN)L->ImageBase!=0x1b70 ||
      (UINTN)(*T)->ConfigureBypass-(UINTN)L->ImageBase!=0x3160) { return EFI_COMPROMISED_DATA; }
  return EFI_SUCCESS;
}
STATIC VOID HalTrace (CHAR8 *Step, BOOLEAN Returned, UINT32 Raw) {
  UINT32 Base=Step[0]=='C' ? (Step[1]=='R' ? 0xC200 : 0xC210) : 0xC220;
  (VOID)Base;
  PhotoCheckpoint(Base+(Returned?1U:0U),Step,Returned?(Raw==0?EFI_SUCCESS:EFI_DEVICE_ERROR):EFI_NOT_STARTED,!Returned);
  if (Returned) { DEBUG ((DEBUG_ERROR,"HAL %a RETURN RAW=0x%x\n",Step,Raw)); }
  else { DEBUG ((DEBUG_ERROR,"HAL %a CALL (pending)\n",Step)); }
}

STATIC VOID Screen (VOID) {
  ARM_MEMORY_REGION_DESCRIPTOR_EX R;
  UINTN Bytes = 1080 * 2340 * 4;
  if (!EFI_ERROR (LocateMemoryMapAreaByName ("Display Reserved", &R)) &&
      R.Length >= Bytes + 2 * sizeof (INTN)) {
    ZeroMem ((VOID *)(UINTN)R.Address, Bytes + 2 * sizeof (INTN));
    WriteBackInvalidateDataCacheRange ((VOID *)(UINTN)R.Address, Bytes + 2 * sizeof (INTN));
    SerialPortInitialize ();
  }
}
STATIC VOID Result (CHAR8 *Name, EFI_STATUS S) {
  PhotoResult(Name,S);
  DEBUG ((DEBUG_ERROR, "%a: %a STATUS=0x%Lx (%r)\n", Name,
          EFI_ERROR (S) ? "FAIL" : "PASS", (UINT64)S, S));
}

// Arm SMMUv2 GR0 IDR0/1, NS alias CR0, SMRn and S2CRn. Reads only.
// No interpretation of reset/zero state as identity; only explicit, unique
// live S2CR TYPE=bypass mappings for every conservative UFS SID are allowed.
STATIC EFI_STATUS Snapshot (BOOLEAN Verbose) {
  ARM_MEMORY_REGION_DESCRIPTOR_EX R;
  UINT32 Smr[128], S2cr[128], Again;
  UINTN I, N;
  EFI_STATUS S = LocateMemoryMapAreaByName ("SMMU", &R);
  if (EFI_ERROR (S) || R.Address != 0x15000000 || R.Length < 0x1000) { return EFI_UNSUPPORTED; }
  mIdr0 = MmioRead32 ((UINTN)R.Address + 0x20);
  mIdr1 = MmioRead32 ((UINTN)R.Address + 0x24);
  mCr0 = MmioRead32 ((UINTN)R.Address + 0x400);
  N = mIdr0 & 255U;
  mMatching = 0;
  if (Verbose) {
    DEBUG ((DEBUG_ERROR, "SMMU RO base=0x15000000 IDR0=%08x IDR1=%08x CR0NS=%08x\n", mIdr0, mIdr1, mCr0));
  }
  if (!N || N > 128 || !(mIdr0 & (1U << 27)) || (mIdr0 & (1U << 8))) { return EFI_UNSUPPORTED; }
  for (I = 0; I < N; ++I) {
    Smr[I] = MmioRead32 ((UINTN)R.Address + 0x800 + 4 * I);
    S2cr[I] = MmioRead32 ((UINTN)R.Address + 0xc00 + 4 * I);
    if ((Smr[I] & 0x80000000U) &&
        (((0x300U ^ (Smr[I] & 0x7fffU)) & ~((Smr[I] >> 16) & 0x7fffU)) == 0)) {
      ++mMatching;
      if (Verbose) { DEBUG ((DEBUG_ERROR, "SID300 group=%u SMR=%08x S2CR=%08x type=%u cb=%u\n",
                       (UINT32)I, Smr[I], S2cr[I], (S2cr[I] >> 16) & 3U, S2cr[I] & 255U)); }
    }
  }
  Again = MmioRead32 ((UINTN)R.Address + 0x400);
  if (Again != mCr0) { return EFI_NOT_READY; }
  return StreamsBypass (mIdr0, mCr0, Smr, S2cr, N) ? EFI_SUCCESS : EFI_SECURITY_VIOLATION;
}

// Original binary DEPEX is honored even though these images are stored as
// FREEFORM PE32 sections. Unknown opcodes, SOR and ordering expressions fail.
STATIC EFI_STATUS Depex (EFI_GUID *Guid) {
  UINT8 *B = NULL; UINTN N = 0, I = 0, Top = 0;
  BOOLEAN Stack[64]; EFI_GUID G; VOID *P;
  EFI_STATUS S = GetSectionFromAnyFv (Guid, EFI_SECTION_DXE_DEPEX, 0, (VOID **)&B, &N);
  if (EFI_ERROR (S)) { return S; }
  S = EFI_COMPROMISED_DATA;
  while (I < N) {
    UINT8 Op = B[I++];
    if (Op == 2) {
      if (I + sizeof G > N || Top == 64) { break; }
      CopyMem (&G, B + I, sizeof G); I += sizeof G;
      Stack[Top++] = !EFI_ERROR (gBS->LocateProtocol (&G, NULL, &P));
      if (!Stack[Top-1]) { PhotoDepexMissing(&G,Guid); DEBUG ((DEBUG_ERROR,"DEPEX MISSING %g for image %g\n",&G,Guid)); }
    } else if (Op == 6 || Op == 7) {
      if (Top == 64) { break; } Stack[Top++] = (Op == 6);
    } else if (Op == 3 || Op == 4) {
      if (Top < 2) { break; } --Top;
      Stack[Top-1] = Op == 3 ? (Stack[Top-1] && Stack[Top]) : (Stack[Top-1] || Stack[Top]);
    } else if (Op == 5) {
      if (!Top) { break; } Stack[Top-1] = !Stack[Top-1];
    } else if (Op == 8) {
      if (I == N && Top == 1) { S = Stack[0] ? EFI_SUCCESS : EFI_NOT_READY; } break;
    } else { break; }
  }
  FreePool (B); return S;
}
STATIC EFI_STATUS StartNative (UINTN Index) {
  VOID *B = NULL; UINTN N = 0; EFI_HANDLE H = NULL;
  EFI_STATUS S;
  if (Index >= ARRAY_SIZE (mNative)) { return EFI_INVALID_PARAMETER; }
  if (Index == ARRAY_SIZE (mNative)-1) {
    // This profile promises read-only storage access, including driver entry.
    // Pinned UFSDxe SHA0576f04f...: entry RVA2ABC -> conditional BL at2E70
    // to FFU routine2694; its matching-device path calls D44C (update) and
    // 13E78 (private reset). Calling only ReadBlocks AFTER entry is not enough.
    // Do not patch the image or spoof chip/vendor/revision to evade this path.
    // A reviewed read-only UFS provider is required before enabling its entry.
    S = EFI_WRITE_PROTECTED;
    Result ("UFS ENTRY REFUSED: NATIVE FFU/RESET", S);
    PhotoCheckpoint(0xC0F0,"UFS ENTRY POLICY / FFU-RESET BLOCKED",S,FALSE);
    return S;
  }
  PhotoModule(Index,0,EFI_NOT_STARTED,FALSE);
  S = Depex (&mNative[Index].Guid);
  PhotoModule(Index,1,S,FALSE);
  if (EFI_ERROR (S)) { DEBUG ((DEBUG_ERROR,"DEPEX %a STATUS=%r\n",mNative[Index].Name,S)); return S; }
  PhotoModule(Index,2,EFI_NOT_STARTED,FALSE);
  S = GetSectionFromAnyFv (&mNative[Index].Guid, EFI_SECTION_PE32, 0, &B, &N);
  PhotoModule(Index,3,S,FALSE);
  if (!EFI_ERROR (S)) {
    PhotoModule(Index,4,EFI_NOT_STARTED,TRUE);
    S = gBS->LoadImage (FALSE, mThisImage, NULL, B, N, &H); mLoadStatus[Index]=S; FreePool (B);
    PhotoModule(Index,5,S,FALSE);
  }
  if (!EFI_ERROR (S)) {
    DEBUG ((DEBUG_ERROR, "START %a (if hangs, this entry did not return)\n", mNative[Index].Name));
    mNativeHandle[Index] = H;
    PhotoImage(Index,H);
    PhotoModule(Index,6,EFI_NOT_STARTED,TRUE);
    S = gBS->StartImage (H, NULL, NULL); mStartStatus[Index]=S;
    PhotoModule(Index,7,S,FALSE);
  }
  Result (mNative[Index].Name, S);
  return S;
}

STATIC EFI_STATUS Read (EFI_BLOCK_IO_PROTOCOL *Io, UINT64 Lba, UINTN Bytes, VOID *B) {
  if (!Io || !Io->Media || !Io->ReadBlocks || !Io->Media->MediaPresent ||
      !Bytes || Bytes % Io->Media->BlockSize || Lba > Io->Media->LastBlock ||
      Bytes / Io->Media->BlockSize - 1 > Io->Media->LastBlock - Lba) { return EFI_INVALID_PARAMETER; }
  {
    EFI_STATUS Status;
    PhotoCheckpoint(0xE100,"BLOCK IO ReadBlocks CALL",EFI_NOT_STARTED,TRUE);
    Status = Io->ReadBlocks (Io, Io->Media->MediaId, Lba, Bytes, B);
    PhotoCheckpoint(0xE101,"BLOCK IO ReadBlocks RETURN",Status,FALSE);
    if (!EFI_ERROR (Status)) { ++mReads; }
    return Status;
  }
}
STATIC EFI_STATUS Gpt (EFI_BLOCK_IO_PROTOCOL *Io, UINTN Disk) {
  UINTN Block = Io->Media->BlockSize, Align = Io->Media->IoAlign, Pages, Bytes, Total, I;
  UINT8 *H = NULL, *Backup = NULL, *Entries = NULL, *Other = NULL;
  EFI_STATUS S = EFI_OUT_OF_RESOURCES;
  UINT32 Count, Size; UINT64 First, Last;
  if (Block != 512 && Block != 4096) { return EFI_UNSUPPORTED; }
  if (Align < EFI_PAGE_SIZE) { Align = EFI_PAGE_SIZE; }
  if (Align > 0x10000 || (Align & (Align - 1))) { return EFI_UNSUPPORTED; }
  H = AllocateAlignedPages (1, Align); Backup = AllocateAlignedPages (1, Align);
  if (!H || !Backup) { goto Exit; }
  S = Read (Io, 1, Block, H); if (EFI_ERROR (S)) { goto Exit; }
  S = Read (Io, Io->Media->LastBlock, Block, Backup); if (EFI_ERROR (S)) { goto Exit; }
  S = EFI_COMPROMISED_DATA;
  if (!ValidGptHeader (H, Block, 1, Io->Media->LastBlock) ||
      !ValidGptHeader (Backup, Block, Io->Media->LastBlock, Io->Media->LastBlock) ||
      CompareMem (H + 40, Backup + 40, 32) || CompareMem (H + 80, Backup + 80, 12)) { goto Exit; }
  Count = Le32 (H + 80); Size = Le32 (H + 84); First = Le64 (H + 40); Last = Le64 (H + 48);
  Total = (UINTN)Count * Size; Bytes = ALIGN_VALUE (Total, Block); Pages = EFI_SIZE_TO_PAGES (Bytes);
  Entries = AllocateAlignedPages (Pages, Align); Other = AllocateAlignedPages (Pages, Align);
  S = EFI_OUT_OF_RESOURCES; if (!Entries || !Other) { goto Exit; }
  S = Read (Io, Le64 (H + 72), Bytes, Entries); if (EFI_ERROR (S)) { goto Exit; }
  S = Read (Io, Le64 (Backup + 72), Bytes, Other); if (EFI_ERROR (S)) { goto Exit; }
  S = EFI_COMPROMISED_DATA;
  if (Crc (Entries, Total) != Le32 (H + 88) || CompareMem (Entries, Other, Total) ||
      !ValidEntries (Entries, Count, Size, First, Last)) { goto Exit; }
  ++mDisks; PhotoDiskGuid(H+56);
  DEBUG ((DEBUG_ERROR, "GPT DISK %u GUID=%g BLOCK=%u LAST=0x%Lx\n", (UINT32)Disk, H + 56, (UINT32)Block, Io->Media->LastBlock));
  for (I = 0; I < Count; ++I) {
    UINT8 *P = Entries + I * Size;
    BOOLEAN Win, Esp;
    if (!UsedEntry (P)) { continue; }
    Win = WinName (P); Esp = CompareMem (P, &mEsp, 16) == 0;
    if (!Win && !Esp) { continue; }
    mWin += Win; mEsps += Esp; PhotoPartitionGuid(Win,Esp,P+16);
    DEBUG ((DEBUG_ERROR, "%a DISK=%u ENTRY=%u GUID=%g\n", Win ? "WIN CANDIDATE" : "ESP TYPE", (UINT32)Disk, (UINT32)I+1, P + 16));
    DEBUG ((DEBUG_ERROR, "TYPE=%g LBA=0x%Lx..0x%Lx BYTES=0x%Lx\n", P, Le64 (P+32), Le64 (P+40), (Le64(P+40)-Le64(P+32)+1)*Block));
    // Read only a partition's first block. Label/type do not prove filesystem.
    S = Read (Io, Le64 (P + 32), Block, H);
    if (!EFI_ERROR (S)) {
      DEBUG ((DEBUG_ERROR, "FS FIRST BLOCK: %a (no mount)\n",
        CompareMem (H+3, "NTFS    ", 8) == 0 ? "NTFS SIGNATURE" :
        (Block >= 4096 && H[1080] == 0x53 && H[1081] == 0xef) ? "EXT MAGIC" :
        CompareMem (H+82, "FAT32   ", 8) == 0 ? "FAT32 SIGNATURE" : "UNVERIFIED"));
    } else { Result ("PARTITION READ", S); }
  }
  S = EFI_SUCCESS;
Exit:
  if (H) { FreeAlignedPages (H, 1); } if (Backup) { FreeAlignedPages (Backup, 1); }
  if (Entries) { FreeAlignedPages (Entries, Pages); } if (Other) { FreeAlignedPages (Other, Pages); }
  return S;
}

EFI_STATUS EFIAPI PreFinalEntry (EFI_HANDLE Image, EFI_SYSTEM_TABLE *SystemTable) {
  EFI_STATUS S, ProviderGuard; VOID *Hal = NULL; EFI_HANDLE *Handles = NULL;
  EFI_BLOCK_IO_PROTOCOL *Io; UINTN I, Stage, Pass, RawCount = 0;
  BOOLEAN Done[ARRAY_SIZE (mNative)] = {FALSE};
  DAVINCI_HAL_TABLE *Table = NULL;
  mThisImage = Image;
  for (I=0; I<ARRAY_SIZE(mNative); ++I) { mLoadStatus[I]=mStartStatus[I]=EFI_NOT_STARTED; }
  gBS->SetWatchdogTimer (0, 0, 0, NULL);
  Screen (); PhotoInit(SystemTable); DEBUG ((DEBUG_ERROR,"DAVINCI UFS UNBLOCK V1 / DUU1\n")); Result ("DXE", EFI_SUCCESS);
  DEBUG ((DEBUG_ERROR,"PREPI: PASS (previous physical success preserved)\n"));
  PhotoCheckpoint(0xA000,"LEGACY SMMU READ CALL",EFI_NOT_STARTED,TRUE);
  S=Snapshot(TRUE); Result("LEGACY TYPE1 CHECK (NOT THE NEW GATE)",S);
  PhotoCheckpoint(0xA001,"LEGACY SMMU READ RETURN",S,FALSE);
  mGate=CaptureNative("BEFORE HAL");
  if (EFI_ERROR(mGate)) { goto Summary; }
  S=LocateConfigurationMapUINT32ByName("EnableUfsIOC",&mIoc);
  if (S==EFI_NOT_FOUND) { mIoc=0; }
  else if (EFI_ERROR(S)) { mGate=S; goto Summary; }
  if (mIoc>1) { mGate=EFI_UNSUPPORTED; goto Summary; }
  DEBUG ((DEBUG_ERROR,"EnableUfsIOC=%u STATUS=%r\n",mIoc,S));
  mHalStatus=gBS->LocateProtocol(&mHal,NULL,&Hal);
  Result("HALIOMMU BEFORE LOAD PRESENCE",mHalStatus);
  // Dependencies are no longer hidden behind the failed inherited-TYPE1 gate.
  for (Pass=0; Pass<ARRAY_SIZE(mNative); ++Pass) {
    BOOLEAN Progress=FALSE;
    for (Stage=0; Stage<NATIVE_HAL_INDEX; ++Stage) {
      if (Done[Stage]) { continue; }
      S=Depex(&mNative[Stage].Guid);
      if (S==EFI_NOT_READY) { continue; }
      S=StartNative(Stage); Done[Stage]=TRUE; Progress=TRUE;
      if (EFI_ERROR(S)) { mUfs=S; goto Summary; }
    }
    if (!Progress) { break; }
  }
  for (Stage=0; Stage<NATIVE_HAL_INDEX; ++Stage) {
    if (!Done[Stage]) { S=Depex(&mNative[Stage].Guid); Result("DEPENDENCY STILL BLOCKED",S); mUfs=EFI_NOT_READY; goto Summary; }
  }
  mGate=CaptureNative("AFTER DEPENDENCIES");
  if (EFI_ERROR(mGate)) { goto Summary; }
  if (HasUfsRoute()) {
    mReadback=ReadbackUfs();
    if (EFI_ERROR(mReadback)) {
      mGate=mReadback;
      DEBUG ((DEBUG_ERROR,"EXISTING UFS BANK NOT VERIFIED IDENTITY; HAL/DMA NOT STARTED\n"));
      goto Summary;
    }
  }
  ProviderGuard=NativeProviderSafe(); Result("HAL PROVIDER OWNERSHIP GUARD",ProviderGuard);
  if (EFI_ERROR(ProviderGuard)) {
    // Never load a dummy provider that would duplicate a live SDC/USB mapping
    // or reclaim a bank used by a live stream. Reuse is permitted ONLY after
    // actual, complete identity readback; no configure/attach success is claimed.
    mGate=ReadbackUfs(); mReadback=mGate;
    if (EFI_ERROR(mGate)) { goto Summary; }
    mPath="EXISTING VERIFIED IDENTITY; HAL PROVIDER SKIPPED";
  } else {
    S=StartNative(NATIVE_HAL_INDEX); mHalEntry=mStartStatus[NATIVE_HAL_INDEX];
    Result("HALIOMMU LOAD/START PATH",S); Result("HALIOMMU ENTRY",mHalEntry);
    if (S!=EFI_SUCCESS || mHalEntry!=EFI_SUCCESS) { goto Summary; }
    mHalInit=InitHalTable(&Table); Result("HALIOMMU INIT ABI",mHalInit);
    if (EFI_ERROR(mHalInit)) { goto Summary; }
    mGate=CaptureNative("AFTER HAL ENTRY");
    if (EFI_ERROR(mGate)) { goto Summary; }
    if (HasUfsRoute()) {
      mGate=ReadbackUfs(); mReadback=mGate;
      if (EFI_ERROR(mGate)) {
        DEBUG ((DEBUG_ERROR,"EXISTING UFS ROUTE IS NOT VERIFIED IDENTITY; NO OVERWRITE/DETACH\n"));
        goto Summary;
      }
      mPath="EXISTING VERIFIED IDENTITY; ATTACH NOT NEEDED";
    } else {
      // A second matching SMR would cause a multi-hit. Only attach an unmapped
      // UFS range; native HAL selects a free bank from live CBAR state.
      ProviderGuard=SafePool(1,1); Result("UFS ALLOCATION OWNERSHIP GUARD",ProviderGuard);
      if (EFI_ERROR(ProviderGuard)) { mGate=ProviderGuard; goto Summary; }
      mHalDomain=RunUfsDomainChain(Table,mIoc,&mDomain,HalTrace);
      Result("HAL UFS DOMAIN CHAIN",mHalDomain);
      if (EFI_ERROR(mHalDomain)) { goto Summary; }
      mGate=CaptureNative("AFTER UFS ATTACH");
      if (!EFI_ERROR(mGate)) { mGate=ReadbackUfs(); mReadback=mGate; }
      if (EFI_ERROR(mGate)) { goto Summary; }
      mPath="NATIVE CREATE/CONFIGURE_BYPASS/ATTACH + READBACK";
    }
  }
  Result("UFS IOMMU READBACK",mGate);
  if (!EFI_ERROR(mGate)) {
    mUfs = StartNative (ARRAY_SIZE(mNative)-1);
    if (EFI_ERROR (mUfs)) { goto Summary; }
    S = CaptureNative ("AFTER UFS ENTRY");
    if (!EFI_ERROR (S)) { S=ReadbackUfs(); }
    mReadback=S;
    if (EFI_ERROR (S)) { mGate = S; goto Summary; }
    Screen ();
    PhotoCheckpoint(0xE000,"BLOCK IO ENUM CALL",EFI_NOT_STARTED,TRUE);
    mBlock = gBS->LocateHandleBuffer (ByProtocol, &gEfiBlockIoProtocolGuid, NULL, &RawCount, &Handles);
    PhotoCheckpoint(0xE001,"BLOCK IO ENUM RETURN",mBlock,FALSE);
    if (!EFI_ERROR (mBlock)) {
      for (I = 0; I < RawCount; ++I) {
        S = gBS->HandleProtocol (Handles[I], &gEfiBlockIoProtocolGuid, (VOID **)&Io);
        if (EFI_ERROR (S) || !Io || !Io->Media || !Io->Media->MediaPresent ||
            Io->Media->LogicalPartition || Io->Media->RemovableMedia) { continue; }
        ++mCount;
        DEBUG ((DEBUG_ERROR, "LUN HANDLE %u block=%u last=0x%Lx\n", (UINT32)I, Io->Media->BlockSize, Io->Media->LastBlock));
        PhotoCheckpoint(0xE200,"GPT VALIDATION CALL",EFI_NOT_STARTED,TRUE);
        S = Gpt (Io, I);
        PhotoCheckpoint(0xE201,"GPT VALIDATION RETURN",S,FALSE);
        // UFS has boot/RPMB-related LUNs without GPT. Count/report each failure.
        Result ("LUN GPT READ", S);
        if (EFI_ERROR (S)) { ++mGptFailures; }
      }
      FreePool (Handles);
    }
    if (!mCount && !EFI_ERROR (mBlock)) { mBlock = EFI_NOT_FOUND; }
    mGpt = mDisks ? EFI_SUCCESS : EFI_NOT_FOUND;
  } else { mUfs = EFI_SECURITY_VIOLATION; }
Summary:
  DEBUG ((DEBUG_ERROR, "\n=== DAVINCI PREFINAL RESULTS ===\nPREPI: PASS\n"));
  Result ("DXE", EFI_SUCCESS); Result ("HALIOMMU PRESENCE", mHalStatus);
  Result("HALIOMMU LOADIMAGE",mLoadStatus[NATIVE_HAL_INDEX]);
  Result("HALIOMMU ENTRY",mHalEntry); Result("HALIOMMU INIT ABI",mHalInit);
  Result("HAL UFS DOMAIN CHAIN",mHalDomain);
  DEBUG ((DEBUG_ERROR,"UFS DOMAIN completed=%u create=%08x cfg=%08x attach=%08x\n",mDomain.Completed,mDomain.Create,mDomain.Configure,mDomain.Attach));
  DEBUG ((DEBUG_ERROR,"IOMMU PATH: %a\n",mPath));
  Result ("IOMMU PATH STATUS", mGate);
  Result ("IOMMU NATIVE/IDENTITY READBACK", mReadback);
  DEBUG ((DEBUG_ERROR,"RAW IDR0=%08x IDR1=%08x CR0=%08x CR0NS=%08x\n",mLive.Idr0,mLive.Idr1,mLive.Cr0,mLive.Cr0Ns));
  for (I=0; I<mLive.N && I<128; ++I) {
    UINT32 B=mLive.S2cr[I]&255U;
    if (!MatchSid(mLive.Smr[I],0x300)) { continue; }
    DEBUG ((DEBUG_ERROR,"LAST UFS SMR=%08x S2CR=%08x TYPE=%u CB=%u\n",mLive.Smr[I],mLive.S2cr[I],(mLive.S2cr[I]>>16)&3U,B));
    if (B<mLive.Banks && B<128) { DEBUG ((DEBUG_ERROR,"LAST CBAR=%08x CBA2R=%08x SCTLR=%08x M=%u IOC=%u\n",mLive.Cbar[B],mLive.Cba2r[B],mLive.Sctlr[B],mLive.Sctlr[B]&1U,mIoc)); }
  }

  DEBUG ((DEBUG_ERROR, "UFS LOAD/START PATH STATUS=0x%Lx (%r) (entry alone is not PASS)\n", (UINT64)mUfs, mUfs));
  Result ("UFS READ ACCESS", mReads ? EFI_SUCCESS : (EFI_ERROR(mUfs) ? mUfs : EFI_NOT_FOUND));
  DEBUG ((DEBUG_ERROR, "UFS SUCCESSFUL READ CALLS=%u\n", (UINT32)mReads));
  Result ("BLOCK IO", mBlock); DEBUG ((DEBUG_ERROR, "BLOCK IO COUNT=%u\n", (UINT32)mCount));
  Result ("GPT", mGpt); DEBUG ((DEBUG_ERROR, "GPT DISKS=%u GPT REJECTED LUNS=%u\n", (UINT32)mDisks,(UINT32)mGptFailures));
  DEBUG ((DEBUG_ERROR, "WINDOWS PARTITION: %a CANDIDATES=%u (label only)\n", mWin ? "FOUND" : "NOT FOUND", (UINT32)mWin));
  DEBUG ((DEBUG_ERROR, "ESP: %a COUNT=%u (GPT type only)\n", mEsps ? "FOUND" : "NOT FOUND", (UINT32)mEsps));
  DEBUG ((DEBUG_ERROR, "NO INSTALL / NO BOOT MANAGER / HALTED\nHOLD POWER TO RESTART\n"));
  PhotoFinish();
  for (;;) { CpuDeadLoop (); }
}
