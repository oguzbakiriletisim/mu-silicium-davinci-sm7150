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
!if $(DAVINCI_CPU_ONLY_ACPI) != 1
  SECTION RAW = Moorea/FACP.aml
!endif
  SECTION RAW = Moorea/FACS.aml
# SECTION RAW = Moorea/FPDT.aml
!if $(DAVINCI_CPU_ONLY_ACPI) != 1
  SECTION RAW = Moorea/GTDT.aml
!endif
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
  INF RuleOverride = DAVINCI_ASL davinciPkg/AcpiTables/AcpiTables.inf
  INF RuleOverride = DAVINCI_ACPI davinciPkg/AcpiTables/Gtdt.inf
  INF RuleOverride = DAVINCI_ACPI davinciPkg/AcpiTables/Fadt.inf
!endif

!if $(DAVINCI_ACPI_STORAGE_DEV) == 1
  INF RuleOverride = DAVINCI_ASL davinciPkg/AcpiTables/StorageDev.inf
!endif
