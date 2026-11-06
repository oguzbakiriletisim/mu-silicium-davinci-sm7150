// SPDX-License-Identifier: BSD-2-Clause-Patent
// SM7150 storage resource development ONLY. Always hidden. No driver identity,
// coherency, IRQ polarity, power methods or IORT mapping are fabricated.
DefinitionBlock ("", "SSDT", 2, "DAVNCI", "UFSDEV", 1)
{
    Scope (\_SB)
    {
        Device (UFSD)
        {
            Name (_ADR, Zero)
            Name (_UID, Zero)
            Method (_STA, 0, NotSerialized) { Return (Zero) }
            Name (_CRS, ResourceTemplate ()
            {
                Memory32Fixed (ReadWrite, 0x01D84000, 0x00003000)
                Memory32Fixed (ReadWrite, 0x01D87000, 0x00000DDC)
                Memory32Fixed (ReadWrite, 0x01D90000, 0x00008000)
            })
            // No _HID/_CID: neither QCOM24A5 nor CC_010901 binding is proven.
            // No _CCA: DMA coherency unverified. No interrupt: SPI265->GSI297
            // is a numerical conversion; trigger/polarity remain unverified.
            // No PEP/_PS0/_PS3: provider and physical power contract missing.
        }
    }
}
