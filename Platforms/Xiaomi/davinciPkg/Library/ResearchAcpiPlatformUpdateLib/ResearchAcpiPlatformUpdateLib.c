// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <Library/DebugLib.h>

VOID
PlatformUpdateAcpiTables (VOID)
{
  // The research namespace has no peripheral/SoC Name objects to patch.
  DEBUG ((DEBUG_WARN, "DAVINCI-ACPI: CPU-only research namespace; no peripheral fixups\n"));
}
