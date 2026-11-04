// SPDX-License-Identifier: BSD-2-Clause-Patent
// No partition/filesystem/BDS driver is dispatched by this profile. No storage
// WriteBlocks, Reset, FlushBlocks, GPT repair, SCM listeners or Windows launch.
#include <Uefi.h>
#include <Pi/PiFirmwareFile.h>
#include <Protocol/BlockIo.h>
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

STATIC EFI_GUID mHal = {0x54b6d3b4,0x5d33,0x4f91,{0x86,0,0x6c,0x41,0xd5,0xde,0xb1,0x9a}};
STATIC EFI_GUID mEsp = {0xc12a7328,0xf81f,0x11d2,{0xba,0x4b,0,0xa0,0xc9,0x3e,0xc9,0x3b}};
STATIC EFI_STATUS mGate, mHalStatus, mUfs = EFI_NOT_STARTED, mBlock = EFI_NOT_FOUND;
STATIC EFI_STATUS mGpt = EFI_NOT_FOUND;
STATIC UINTN mCount, mDisks, mWin, mEsps, mGptFailures, mReads;
STATIC UINT32 mIdr0, mIdr1, mCr0, mMatching;
STATIC EFI_HANDLE mThisImage;

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
  EFI_STATUS S = Depex (&mNative[Index].Guid);
  if (EFI_ERROR (S)) { Result (mNative[Index].Name, S); return S; }
  S = GetSectionFromAnyFv (&mNative[Index].Guid, EFI_SECTION_PE32, 0, &B, &N);
  if (!EFI_ERROR (S)) { S = gBS->LoadImage (FALSE, mThisImage, NULL, B, N, &H); FreePool (B); }
  if (!EFI_ERROR (S)) {
    DEBUG ((DEBUG_ERROR, "START %a (if hangs, this entry did not return)\n", mNative[Index].Name));
    S = gBS->StartImage (H, NULL, NULL);
  }
  Result (mNative[Index].Name, S);
  return S;
}

STATIC EFI_STATUS Read (EFI_BLOCK_IO_PROTOCOL *Io, UINT64 Lba, UINTN Bytes, VOID *B) {
  if (!Io || !Io->Media || !Io->ReadBlocks || !Io->Media->MediaPresent ||
      !Bytes || Bytes % Io->Media->BlockSize || Lba > Io->Media->LastBlock ||
      Bytes / Io->Media->BlockSize - 1 > Io->Media->LastBlock - Lba) { return EFI_INVALID_PARAMETER; }
  {
    EFI_STATUS Status = Io->ReadBlocks (Io, Io->Media->MediaId, Lba, Bytes, B);
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
  ++mDisks;
  DEBUG ((DEBUG_ERROR, "GPT DISK %u GUID=%g BLOCK=%u LAST=0x%Lx\n", (UINT32)Disk, H + 56, (UINT32)Block, Io->Media->LastBlock));
  for (I = 0; I < Count; ++I) {
    UINT8 *P = Entries + I * Size;
    BOOLEAN Win, Esp;
    if (!UsedEntry (P)) { continue; }
    Win = WinName (P); Esp = CompareMem (P, &mEsp, 16) == 0;
    if (!Win && !Esp) { continue; }
    mWin += Win; mEsps += Esp;
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
  EFI_STATUS S; VOID *Hal = NULL; EFI_HANDLE *Handles = NULL;
  EFI_BLOCK_IO_PROTOCOL *Io; UINTN I, Stage, Pass, RawCount = 0;
  BOOLEAN Done[ARRAY_SIZE (mNative)] = {FALSE};
  mThisImage = Image;
  gBS->SetWatchdogTimer (0, 0, 0, NULL); // UEFI software watchdog only.
  Screen (); Result ("DXE", EFI_SUCCESS);
  DEBUG ((DEBUG_ERROR, "PREPI: PASS (execution reached DXE)\nSMMU: READ-ONLY SNAPSHOT NEXT\n"));
  mGate = Snapshot (TRUE); Result ("IOMMU INHERITED BYPASS", mGate);
  mHalStatus = gBS->LocateProtocol (&mHal, NULL, &Hal);
  Result ("HALIOMMU PROTOCOL PRESENCE ONLY", mHalStatus);
  DEBUG ((DEBUG_ERROR, "HALIOMMU: NOT STARTED; dummy-client writes are excluded\n"));
  if (!EFI_ERROR (mGate)) {
    // No HAL calls: preserve inherited identity state. This is NOT a native
    // domain/attach fix and cannot handle translated or unmatched streams.
    // Load only original davinci dependencies; never ignore their DEPEX.
    for (Pass = 0; Pass < ARRAY_SIZE(mNative); ++Pass) {
      BOOLEAN Progress = FALSE;
      for (Stage = 0; Stage + 1 < ARRAY_SIZE(mNative); ++Stage) {
        if (Done[Stage]) { continue; }
        S = Depex (&mNative[Stage].Guid);
        if (S == EFI_NOT_READY) { continue; }
        S = StartNative (Stage); Done[Stage] = TRUE; Progress = TRUE;
        if (EFI_ERROR (S)) { DEBUG ((DEBUG_ERROR, "DEPENDENCY FAILURE; UFS WILL NOT START\n")); mUfs = S; goto Summary; }
      }
      if (!Progress) { break; }
    }
    for (Stage = 0; Stage + 1 < ARRAY_SIZE(mNative); ++Stage) {
      if (!Done[Stage]) { mUfs = EFI_NOT_READY; goto Summary; }
    }
    S = Snapshot (FALSE);
    if (EFI_ERROR (S)) { mGate = S; mUfs = S; goto Summary; }
    mUfs = StartNative (ARRAY_SIZE(mNative)-1);
    if (EFI_ERROR (mUfs)) { goto Summary; }
    S = Snapshot (FALSE);
    if (EFI_ERROR (S)) { mGate = S; goto Summary; }
    Screen ();
    mBlock = gBS->LocateHandleBuffer (ByProtocol, &gEfiBlockIoProtocolGuid, NULL, &RawCount, &Handles);
    if (!EFI_ERROR (mBlock)) {
      for (I = 0; I < RawCount; ++I) {
        S = gBS->HandleProtocol (Handles[I], &gEfiBlockIoProtocolGuid, (VOID **)&Io);
        if (EFI_ERROR (S) || !Io || !Io->Media || !Io->Media->MediaPresent ||
            Io->Media->LogicalPartition || Io->Media->RemovableMedia) { continue; }
        ++mCount;
        DEBUG ((DEBUG_ERROR, "LUN HANDLE %u block=%u last=0x%Lx\n", (UINT32)I, Io->Media->BlockSize, Io->Media->LastBlock));
        S = Gpt (Io, I);
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
  Result ("DXE", EFI_SUCCESS); Result ("HALIOMMU PRESENCE ONLY", mHalStatus);
  DEBUG ((DEBUG_ERROR, "HALIOMMU INIT: NOT RUN (no native attach writes)\n"));
  Result ("IOMMU INHERITED BYPASS", mGate);
  DEBUG ((DEBUG_ERROR, "SID300 MATCHES=%u IDR0=%08x IDR1=%08x CR0NS=%08x\n", mMatching,mIdr0,mIdr1,mCr0));
  DEBUG ((DEBUG_ERROR, "UFS LOAD/START PATH STATUS=0x%Lx (%r) (entry alone is not PASS)\n", (UINT64)mUfs, mUfs));
  Result ("UFS READ ACCESS", mReads ? EFI_SUCCESS : (EFI_ERROR(mUfs) ? mUfs : EFI_NOT_FOUND));
  DEBUG ((DEBUG_ERROR, "UFS SUCCESSFUL READ CALLS=%u\n", (UINT32)mReads));
  Result ("BLOCK IO", mBlock); DEBUG ((DEBUG_ERROR, "BLOCK IO COUNT=%u\n", (UINT32)mCount));
  Result ("GPT", mGpt); DEBUG ((DEBUG_ERROR, "GPT DISKS=%u GPT REJECTED LUNS=%u\n", (UINT32)mDisks,(UINT32)mGptFailures));
  DEBUG ((DEBUG_ERROR, "WINDOWS PARTITION: %a CANDIDATES=%u (label only)\n", mWin ? "FOUND" : "NOT FOUND", (UINT32)mWin));
  DEBUG ((DEBUG_ERROR, "ESP: %a COUNT=%u (GPT type only)\n", mEsps ? "FOUND" : "NOT FOUND", (UINT32)mEsps));
  DEBUG ((DEBUG_ERROR, "NO INSTALL / NO BOOT MANAGER / HALTED\nHOLD POWER TO RESTART\n"));
  for (;;) { CpuDeadLoop (); }
}
