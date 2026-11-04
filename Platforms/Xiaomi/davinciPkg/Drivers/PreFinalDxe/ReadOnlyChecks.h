// SPDX-License-Identifier: BSD-2-Clause-Patent
// Pure checks shared by the firmware and host tests. No hardware access.
#ifndef DAVINCI_READ_ONLY_CHECKS_H
#define DAVINCI_READ_ONLY_CHECKS_H
STATIC UINT32 Le32 (CONST UINT8 *P) {
  return (UINT32)P[0] | ((UINT32)P[1] << 8) | ((UINT32)P[2] << 16) | ((UINT32)P[3] << 24);
}
STATIC UINT64 Le64 (CONST UINT8 *P) {
  return (UINT64)Le32 (P) | ((UINT64)Le32 (P + 4) << 32);
}
STATIC UINT32 Crc (CONST UINT8 *P, UINTN N) {
  UINT32 C = 0xffffffffU;
  UINTN I, J;
  for (I = 0; I < N; ++I) {
    C ^= P[I];
    for (J = 0; J < 8; ++J) { C = (C >> 1) ^ ((0U - (C & 1)) & 0xedb88320U); }
  }
  return ~C;
}
// Strict SMMUv2 stream-matching gate. Translation contexts, EXIDS,
// unmatched/multiple matches and disabled global client are NOT trusted.
// TYPE=bypass is sufficient here; no guessed context-bank allocation is used.
STATIC BOOLEAN StreamsBypass (UINT32 Idr0, UINT32 Cr0, CONST UINT32 *Smr,
                              CONST UINT32 *S2cr, UINTN Count) {
  UINTN I, Sid, Matches;
  if (!(Idr0 & (1U << 27)) || (Idr0 & (1U << 8)) || (Cr0 & 1U) ||
      Count == 0 || Count > 128 || Count != (Idr0 & 255U)) { return FALSE; }
  for (Sid = 0x300; Sid < 0x310; ++Sid) {
    Matches = 0;
    for (I = 0; I < Count; ++I) {
      if (!(Smr[I] & 0x80000000U)) { continue; }
      if (((Sid ^ (Smr[I] & 0x7fffU)) & ~((Smr[I] >> 16) & 0x7fffU)) == 0) {
        if (((S2cr[I] >> 16) & 3U) != 1U) { return FALSE; }
        ++Matches;
      }
    }
    if (Matches != 1) { return FALSE; }
  }
  return TRUE;
}
STATIC BOOLEAN ValidGptHeader (UINT8 *B, UINTN Block, UINT64 Lba, UINT64 Last) {
  UINT32 Saved, Size, Count, Entry;
  UINT64 First, End, Array, Sectors;
  BOOLEAN Good;
  if (Block < 512 || Le64 (B) != 0x5452415020494645ULL || Le32 (B + 8) != 0x10000 ||
      (Size = Le32 (B + 12)) < 92 || Size > Block || Le32 (B + 20) != 0 ||
      Le64 (B + 24) != Lba || Le64 (B + 32) != (Lba == 1 ? Last : 1)) { return FALSE; }
  First = Le64 (B + 40); End = Le64 (B + 48); Array = Le64 (B + 72);
  Count = Le32 (B + 80); Entry = Le32 (B + 84);
  if (!Count || Count > 1024 || Entry < 128 || Entry > 1024 || (Entry & (Entry - 1)) ||
      First <= 1 || End < First || End >= Last || !Array || (!Le64 (B + 56) && !Le64 (B + 64))) { return FALSE; }
  Sectors = ((UINT64)Count * Entry + Block - 1) / Block;
  if (Array > Last || Sectors > Last - Array ||
      (Lba == 1 ? (Array < 2 || Array + Sectors > First) : (Array <= End || Array + Sectors > Last))) { return FALSE; }
  Saved = Le32 (B + 16);
  B[16] = B[17] = B[18] = B[19] = 0;
  Good = Crc (B, Size) == Saved;
  B[16] = (UINT8)Saved; B[17] = (UINT8)(Saved >> 8);
  B[18] = (UINT8)(Saved >> 16); B[19] = (UINT8)(Saved >> 24);
  return Good;
}
STATIC BOOLEAN UsedEntry (CONST UINT8 *P) {
  return Le64 (P) != 0 || Le64 (P + 8) != 0;
}
STATIC BOOLEAN WinName (CONST UINT8 *P) {
  return P[56] == 'w' && P[57] == 0 && P[58] == 'i' && P[59] == 0 &&
         P[60] == 'n' && P[61] == 0 && P[62] == 0 && P[63] == 0;
}
STATIC BOOLEAN ValidEntries (CONST UINT8 *P, UINT32 Count, UINT32 Size, UINT64 First, UINT64 Last) {
  UINTN I, J, K;
  UINT64 Start, End, OtherStart, OtherEnd;
  BOOLEAN Equal;
  for (I = 0; I < Count; ++I) {
    CONST UINT8 *A = P + I * Size;
    if (!UsedEntry (A)) { continue; }
    Start = Le64 (A + 32); End = Le64 (A + 40);
    if (Start < First || End < Start || End > Last || (!Le64 (A + 16) && !Le64 (A + 24))) { return FALSE; }
    for (J = 0; J < I; ++J) {
      CONST UINT8 *B = P + J * Size;
      if (!UsedEntry (B)) { continue; }
      OtherStart = Le64 (B + 32); OtherEnd = Le64 (B + 40);
      if (Start <= OtherEnd && OtherStart <= End) { return FALSE; }
      Equal = TRUE;
      for (K = 16; K < 32; ++K) { if (A[K] != B[K]) { Equal = FALSE; } }
      if (Equal) { return FALSE; }
    }
  }
  return TRUE;
}
#endif
