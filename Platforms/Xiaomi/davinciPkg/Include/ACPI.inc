FILE FREEFORM = 7E374E25-8E01-4FEE-87F2-390C23C606CD {
  SECTION RAW = Moorea/APIC.aml
!if $(DAVINCI_CPU_ONLY_ACPI) != 1
# SECTION RAW = Moorea/BERT.aml
# SECTION RAW = Moorea/BGRT.aml
  SECTION RAW = Moorea/CSRT.aml
!if $(TARGET) == DEBUG
  SECTION RAW = Moorea/DBG2.aml
!endif
!endif
  SECTION RAW = Moorea/FACP.aml
  SECTION RAW = Moorea/FACS.aml
# SECTION RAW = Moorea/FPDT.aml
  SECTION RAW = Moorea/GTDT.aml
!if $(DAVINCI_CPU_ONLY_ACPI) != 1
  SECTION RAW = Moorea/IORT.aml
  SECTION RAW = Moorea/MCFG.aml
!endif
# SECTION RAW = Moorea/MSDM.aml
  SECTION RAW = Moorea/PPTT.aml
# SECTION RAW = Moorea/SPCR.aml
# SECTION RAW = Moorea/TPM2.aml
# SECTION RAW = Moorea/XSDT.aml
  SECTION UI = "AcpiTables"
}

!if $(DAVINCI_CPU_ONLY_ACPI) == 1
  // Deliberately CPU-only: no borrowed UFS/USB/PEP/IOMMU resources.
  INF RuleOverride = ACPITABLE davinciPkg/AcpiTables/AcpiTables.inf
!endif
