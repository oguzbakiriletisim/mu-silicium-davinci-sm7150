// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <assert.h>
#include <limits.h>
#include "../../Platforms/Xiaomi/davinciPkg/Drivers/StorageAuditDxe/StorageAudit.h"

int main (void)
{
  assert (DavinciImemReportsUfs (DAVINCI_IMEM_MAGIC, 3, 8));
  assert (DavinciImemReportsUfs (DAVINCI_IMEM_MAGIC, 4, 8));
  assert (!DavinciImemReportsUfs (0, 3, 8));
  assert (!DavinciImemReportsUfs (DAVINCI_IMEM_MAGIC, 2, 8));
  assert (!DavinciImemReportsUfs (DAVINCI_IMEM_MAGIC, 3, 1));
  assert (!DavinciImemReportsUfs (DAVINCI_IMEM_MAGIC, 3, UINT_MAX));
  assert (DavinciImemRangeValid (0x146AA000, 0x146AA000, 0x1000));
  assert (DavinciImemRangeValid (0x1000, 0x1000, 0x54));
  assert (!DavinciImemRangeValid (0x1000, 0x1000, 0x53));
  assert (!DavinciImemRangeValid (0x1000, 0x2000, 0x1000));
  assert (!DavinciImemRangeValid (0, 0, 0x1000));
  assert (!DavinciImemRangeValid (ULLONG_MAX - 7, ULLONG_MAX - 7, 0x1000));
  return 0;
}
