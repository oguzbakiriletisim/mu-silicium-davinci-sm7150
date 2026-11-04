// SPDX-License-Identifier: BSD-2-Clause-Patent
// Minimal ABI of the pinned *davinci* HAL. No foreign SoC register policy.
// Protocol revision 1; init is void. Function slots 0/2/8 are independently
// recovered from HAL and from the original unpatched davinci UFS routine.
#ifndef DAVINCI_HAL_UFS_BRIDGE_H
#define DAVINCI_HAL_UFS_BRIDGE_H

typedef UINT32 (EFIAPI *HAL_CREATE)(VOID **Domain);
typedef UINT32 (EFIAPI *HAL_ATTACH)(VOID *Domain, VOID *Client, UINT32 Arid, UINT32 Mask);
typedef UINT32 (EFIAPI *HAL_BYPASS)(VOID *Domain, UINT32 Type);
typedef struct {
  HAL_CREATE Create;
  VOID *Delete;
  HAL_ATTACH Attach;
  VOID *Detach;
  VOID *Configure;
  VOID *Flush;
  VOID *FlushList;
  VOID *RegisterFault;
  HAL_BYPASS ConfigureBypass;
  VOID *IdiomDetach;
} DAVINCI_HAL_TABLE;
typedef struct {
  UINT64 Revision;
  VOID (EFIAPI *Init)(DAVINCI_HAL_TABLE **Table);
  VOID *Deinit;
} DAVINCI_HAL_PROTOCOL;
typedef struct {
  VOID *Domain;
  UINT32 Create, Configure, Attach;
  UINT32 Completed;
} DAVINCI_UFS_DOMAIN;
typedef VOID (*HAL_TRACE)(CHAR8 *Step, BOOLEAN Returned, UINT32 Raw);

// Stop at the first failure; never manufacture a domain/attach success.
// No cleanup/detach on partial failure: ownership may be uncertain. Caller
// halts and the user resets the phone. The domain stays allocated until reset.
STATIC EFI_STATUS RunUfsDomainChain (DAVINCI_HAL_TABLE *T, UINT32 Ioc,
                                     DAVINCI_UFS_DOMAIN *D, HAL_TRACE Trace) {
  if (T == NULL || D == NULL || Trace == NULL || Ioc > 1 ||
      T->Create == NULL || T->ConfigureBypass == NULL || T->Attach == NULL) {
    return EFI_INVALID_PARAMETER;
  }
  D->Domain = NULL; D->Completed = 0;
  D->Create = D->Configure = D->Attach = 0xffffffffU;
  Trace ("CREATE", FALSE, 0);
  D->Create = T->Create (&D->Domain);
  Trace ("CREATE", TRUE, D->Create);
  if (D->Create != 0 || D->Domain == NULL) { return EFI_NOT_STARTED; }
  D->Completed = 1;
  Trace ("CONFIGURE_BYPASS", FALSE, 0);
  D->Configure = T->ConfigureBypass (D->Domain, Ioc);
  Trace ("CONFIGURE_BYPASS", TRUE, D->Configure);
  if (D->Configure != 0) { return EFI_UNSUPPORTED; }
  D->Completed = 2;
  Trace ("ATTACH UFS0 ARID0 MASK0", FALSE, 0);
  D->Attach = T->Attach (D->Domain, (VOID *)"\\_SB_.UFS0", 0, 0);
  Trace ("ATTACH UFS0 ARID0 MASK0", TRUE, D->Attach);
  if (D->Attach != 0) { return EFI_DEVICE_ERROR; }
  D->Completed = 3;
  return EFI_SUCCESS;
}

STATIC BOOLEAN NativeLayoutSupported (UINT32 Idr0, UINT32 Idr1) {
  return ((Idr0 & (1U<<27)) || (Idr0==0x40017e4fU && Idr1==0x6000003dU)) &&
         (Idr0 & (1U<<30)) && !(Idr0 & (1U<<8)) &&
         (Idr0 & 255U)>=2 && (Idr0 & 255U)<=128;
}
// Decode the same context-array base formula used by the pinned HAL RVA
// 0x3690. 64K-page banks are deliberately unsupported: this HAL uses a 4K
// bank stride. Validate every possible bank access against the CPU map.
STATIC BOOLEAN ContextWindow (UINT32 Idr1, UINT64 Length, UINT64 *Offset, UINT32 *Banks) {
  UINT64 O, End; UINT32 N = Idr1 & 255U;
  if (!N || N > 128 || (Idr1 & 0x80000000U)) { return FALSE; }
  O = 0x1000ULL << (((Idr1 >> 28) & 7U) + 1);
  End = O + ((UINT64)(N - 1) << 12) + 0x40;
  if (O < 0x2000 || End > Length || 0x1800ULL + (UINT64)N * 4 > Length) { return FALSE; }
  *Offset = O; *Banks = N; return TRUE;
}
// Native HAL programs TYPE=translation-context, CBAR=S1/S2-bypass and
// SCTLR.M=0. This is a real identity/bypass domain, unlike "TYPE must be 1".
STATIC BOOLEAN NativeBankBypass (UINT32 S2cr, UINT32 Cbar, UINT32 Cba2r,
                                UINT32 Sctlr, UINT32 Ioc, UINT32 Banks) {
  return Ioc <= 1 && (S2cr & 255U) < Banks && ((S2cr >> 16) & 3U) == 0 &&
         ((Cbar >> 16) & 3U) == 1 && (Cbar & 255U) == 0 &&
         (Cba2r & 1U) == 1 && Sctlr == (Ioc ? 0x009f00e0U : 0x000000e0U);
}
#endif
