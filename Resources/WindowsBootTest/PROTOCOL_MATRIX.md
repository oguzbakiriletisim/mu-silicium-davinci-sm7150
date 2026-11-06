# Hedef A protokol ve donanım denetimi

Kesin kaynak commit'leri SOURCE_COMMIT.txt/Git geçmişinde. Aşağıdaki WBT sütunu
paketlenmiş kaynak/host doğrulamasıdır; runtime protokol kurulumu gösterilmedi.
Eski PrePi/DXE fiziksel başarısı yeni WBT profilinin başarısı değildir.

| Hizmet | PREFINAL | WINDOWS_BOOT_TEST / kaynak | Hedef A ve kalan risk |
|---|---|---|---|
| Boot Services / Allocate / LoadedImage / LoadImage / StartImage | DxeCore var; native LoadImage fiziksel görüldü | Aynı DxeCore; BDS yalnız bizim RAM dosyasını yükler | Microsoft PE yürütmesi henüz yok. |
| BDS / Boot option | Normal BDS yok | WindowsBootTestDxe, EFI_BDS_ARCH_PROTOCOL | DXE tamamlanınca giriş; BootOrder/host BCD yazmaz. |
| Device Path | Core tüketir | DevicePathDxe, standart RAM disk DP + FileDevicePath | ARM64 derlendi; Windows'un RAM yolunu kabulü açık. |
| Block I/O | UFS entry yasak | Yeni RAM BlockIo; callback host testi | Sadece36MiB RAM kapasitesi; telefon kapasitesi değildir. |
| Disk I/O | Yok | DiskIoDxe | CPU/buffer yolu; fiziksel disk scan yok. |
| GPT/Partition discovery | Coordinator salt-okunur CRC kodu, fiziksel okuma yok | PartitionDxe eklenmedi; RAM superfloppy GPT gerektirmez | Telefon ESP/GPT için hâlâ gerçek provider gerekir. |
| FAT32 / SFS | Yok | EnhancedFatDxe + EnglishDxe; gerçek FAT32 fixture | mtools okuması ve firmware RAW eşleşmesi host'ta; SFS runtime açık. |
| FAT yazma | Telefon yazısı amaçlanmıyor ama native entry FFU tehlikeliydi | BlockIo ReadOnly=TRUE; WriteBlocks EFI_WRITE_PROTECTED | RAM provider dışında depolama yok. |
| GOP | Fotoğraf paneli GOP değildir | SimpleFbDxe source düzeltildi | Query/Set host testi; fiziksel GOP ve BLT görünümü açık. |
| Console Out | Doğrudan serial/framebuffer | HiiDatabase, GraphicsConsole, ConSplitter | GOP handle'da gerçek TextOut seçilip ST CRC güncellenir; runtime açık. |
| Console In | Yok/önemsiz tanılama | ConSplitter boş input arayüzü | Gerçek tuş/USB/touch yok; otomatik dosya yolu, çıkış fiziksel güç tuşu. |
| Runtime architecture | Yok | RuntimeDxe | Runtime geçişi/Windows kullanımı test edilmedi. |
| Variable services | Yok | VariableRuntimeDxe, EmuNvMode=TRUE | Nv flag'li çağrılar bile RAM emülasyonu; yeniden başlatmada kaybolur. |
| EFI watchdog | Cancel sonucu örneklenir | Standart WatchdogTimerDxe yazılım eventi + cancel0 | Yeni APSS/PMIC watchdog ayarı yok; dış reset engellenmiş değil. |
| ResetSystem | RAM hook | Runtime image içinde WFI trap + ResetArch | Gerçek reset sağlamaz; Windows Restart tuşu manuel güç çıkışı gerektirir. |
| Time/RTC | Yok | Runtime handler EFI_UNSUPPORTED; RTCArch bildirimi | Sahte tarih/RTC yazması yok; Boot Manager'ın toleransı açık. |
| Capsule services | Yok | Runtime handler EFI_UNSUPPORTED; CapsuleArch bildirimi | FFU/firmware update yapılmaz. |
| Monotonic counter | Yok | EmbeddedMonotonicCounter | RAM variable backend; fiziki sayaç/persistans yok. |
| GetMemoryMap | Core var | Yeni structural overlap/overflow/runtime-attribute kontrolü | Reserved/secure alanların tümü ve Windows RAM yeterliliği ayrıca açık. |
| ExitBootServices / VA map | Core API var, kullanılmadı | DxeCore/RuntimeDxe; yeni snapshot MapKey tekrar kullanılmaz | Target B handoff testi yok; FAT kaynak FV boot-services ömürlüdür. |
| ACPI config table | Yok | AcpiTableDxe/PlatformDxe; CPU-only FADT/GTDT/APIC/PPTT/DSDT | UFS ACPI/IORT/power yok; Kernel için yeterli değildir. |
| SM7150 ACPI geliştirme | Yok | StorageDev SSDT opt-in; _STA=0 | Kimlik/coherency/power/IRQ tahmini yok; cihaz Windows'a sunulmaz. |
| SMBIOS | Yok | Bu minimal profile eklenmedi | Boot Manager ihtiyacı runtime'da açık; kernel readiness yok. |
| Secure Boot / image security | Tam güvenlik profili değil | SecurityStubDxe geliştirme politikası | PK/KEK/db/TPM ve Windows politikası test edilmedi; secure boot doğrulaması iddia edilmez. |
| Gerçek UFS / DMA / cache | Gate var, çalışır provider yok | Hiçbiri paketlenmez | Native FFU/HAL/SMMU engelleri korunur; RAM route bu sorunu çözmez. |

## Yeni modüllerin donanım etkisi

- Runtime/variables/watchdog/DevicePath/HII/DiskIo/FAT/ACPI: kaynakta RAM ve UEFI
  servis işlemleri. VariableNv emülasyonu canlı NV flash/FVB/RPMB kullanmaz.
- GraphicsConsole/SimpleFb: mevcut Display Reserved RAM penceresine çizim ve
  cache maintenance. Yeni panel/PHY/clock/PMIC register yazması yoktur.
- Runtime test stub'ları: reset isteğinde WFI; RTC/capsule unsupported. Bunlar
  tam platform runtime desteği olarak raporlanmaz.
- EnvDxe, CpuDxe, GIC ve timer: baseline'da kullanılan ortak çekirdek korunur;
  Env opaque native bileşendir ve aynı hash ile taşınır. Kaynakları biliniyor gibi
  sunulmaz. PrePi'nin mevcut APSS kapatma yolu değiştirilmedi.
- UFS, SMEM/DAL/HWIO/Clock/RPMh/PDC/HALIOMMU native DXE'leri, USB, charger,
  PMIC/TZ/SCM, FVB ve gerçek disk tüketicileri bu profile eklenmez.

GOP değişikliği ortak driver'ı etkiler.24-bit ve32-bit destek korunur; mode0
artık alanı temizleyip cache flush yapar; geçersiz mode/pointer doğru EFI hatası
verir. BLT cache flush maliyeti artabilir. Diğer cihazlarda fiziksel regression
çalıştırılmadı; normal davinci custom-display varsayılanı değiştirilmedi.
