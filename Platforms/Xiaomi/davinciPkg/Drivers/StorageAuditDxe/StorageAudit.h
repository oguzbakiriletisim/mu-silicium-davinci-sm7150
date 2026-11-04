// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef DAVINCI_STORAGE_AUDIT_H
#define DAVINCI_STORAGE_AUDIT_H

// Inputs observed in the bundled UFSDxe, not a replacement boot-device policy.
#define DAVINCI_IMEM_MAGIC           0xC1F8DB40U
#define DAVINCI_IMEM_MIN_VERSION     3U
#define DAVINCI_IMEM_BOOT_OFFSET     0x50U
#define DAVINCI_IMEM_UFS_BOOT_TYPE   8U

static int
DavinciImemReportsUfs (unsigned int Magic, unsigned int Version, unsigned int Type)
{
  return Magic == DAVINCI_IMEM_MAGIC &&
         Version >= DAVINCI_IMEM_MIN_VERSION && Type == DAVINCI_IMEM_UFS_BOOT_TYPE;
}

static int
DavinciImemRangeValid (unsigned long long Base, unsigned long long RegionBase,
                      unsigned long long RegionLength)
{
  return Base != 0 && Base == RegionBase &&
         RegionLength >= DAVINCI_IMEM_BOOT_OFFSET + 4 &&
         Base <= (~0ULL) - RegionLength;
}
#endif
