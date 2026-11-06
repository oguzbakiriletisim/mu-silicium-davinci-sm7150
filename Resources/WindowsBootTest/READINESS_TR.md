# Windows First Boot Readiness — TARGET A

Sonuç: **Gerçek Microsoft Boot Manager henüz çalıştırılmadı.** Kaynakta ayrı,
RAM FAT32 tabanlı yükleme yolu geliştirildi ve host'ta derlenip denetlendi.
Bu çalışma UFS/ESP oluşturmayı gerektirmeyen Hedef A alternatifidir; UFS sorunu
çözülmüş değildir. Kullanıcının güvenlik şartı gereği güvenilir UFS provider
olmadan bu profil fiziksel teste hazır ilan edilmez. Yeni Android boot.img yok.

## Durum ve kanıt sınıfı

| Konu | Durum | Kanıt |
|---|---|---|
| Eski SEC/PrePi/DXE | Fiziksel doğrulanmış | Kullanıcının önceki cihaz testleri; yeni profil için geçerli başarı değil. |
| Native UFS FFU/private-reset engeli | Korundu | PreFinalDxe.c bu dalda değiştirilmedi; aynı guard host testleri geçer. |
| Windows test profili | Kısmen çözüldü | WINDOWS_BOOT_TEST.inc/DSC/FDF, gerçek DEBUG build/FV audit. |
| BDS üzerinden kontrollü giriş | Kaynak/host derleme | DXE mimari protokolleri tamamlanınca WBT BDS entry; runtime çalışması açık. |
| Salt-okunur RAM BlockIo | Host doğrulandı | Gerçek callback C testi: MediaId, alignment/bounds, write rejection, canary. |
| Geçici FAT32 | Host doğrulandı |36MiB standart FAT32, LFN/çok cluster mtools okuması; FV RAW ile birebir hash. |
| GOP hataları | Kaynak/host düzeltildi | Gerçek Query/Set fonksiyonları; fiziksel GOP/BLT açık. |
| ACPI geliştirme profili | Kısmen çözüldü | CPU-only tablolar + _STA=0 storage SSDT derlendi; UFS kimliği/IORT yok. |
| Gerçek Windows EFI payload | Açık | Bu ortama gerçek bootmgfw/boot font/BCD verilmedi; fixture yalnız README içerir. |
| Microsoft EFI/BCD/VHD dosyaları | Kullanıcı bildirimi | Win11 Pro ARM64/26300.9457, VHD'ler mevcut; dosyalar burada bağımsız incelenmedi. |
| UEFI host smoke | Kısmi | C contracts/mtools/build yapıldı; QEMU/gerçek UEFI içinde loader yürütmesi yapılmadı. |
| Runtime / RTC / reset | Açık/kısıtlı | RAM variables, RTC unsupported, reset WFI trap; gerçek Windows uyumluluğu yok. |
| Fiziksel UFS BlockIo/GPT/ESP | Açık | Çalışır provider yok; telefona erişilmedi. |
| Windows Boot Manager ekranı | Açık | LoadImage/StartImage çağrısını görmek tek başına Microsoft çıktı kanıtı olmaz. |
| winload/kernel | Açık / Target B | UFS driver, IORT/power/coherency, gerçek NTFS/BCD ve memory handoff eksik. |

## UFS sağlayıcı incelemesi

Mu_Basecore3609e51f683e4d9eed13df8dccbb05b0a64ebab2 içinde BSD lisanslı
MdeModulePkg/Bus/Ufs/UfsPassThruDxe kaynakları var. Host-controller protokolü
(gEdkiiUfsHostControllerProtocolGuid) gerektiriyor; mevcut UfsPciHcDxe,
PciIo tabanlı. SM7150'nın platform MMIO/PHY/clock/reset ve DMA sağlayıcısı
bu protokolün hazır uygulaması olarak depoda bulunamadı. ScsiBus/ScsiDisk ile
BlockIo zinciri kurulabilir ama yalnız INF eklemek yeterli değil; yazma ve
DeviceConfig/PassThru arayüzleri de salt-okunur politika gerektirir.

Rivko/android-firmware-qti-sdm670 commit20bb8ae36c93fc16bbadda0e0a83f930c0c8a271
altındaki boot_images/QcomPkg/Library/UfsCommonLib incelendi. UfsLib yolu yok;
gerçek kaynak UfsCommonLib. ufs_open/UTP/cache/transfer kodları mevcut, ancak
UfsTargetUefiLib ve BSP clock/reset/PHY tablo/allocate/cache/bariyer işlevlerine
bağımlı. UfsCommonLib.inf başlığı proprietary/confidential: public GitHub dosyası
olması doğrulanmış açık kaynak lisansı değildir. SDM670 board kodu SM7150'ya
kopyalanmadı ve sürücüye dahil edilmedi. Kesin kaynak/blob/line bilgileri
evidence/UFS_SOURCE_REFERENCES.json içinde. SM7150 BSP ve salt-okunur init
sözleşmesi tamamlanmadan telefon için yeni UFS denemesi önerilmez.

Donanım referansı Resources/DTBs/davinci.dts4680–4738: HCI1D84000/3000,
PHY1D87000/DDC, ICE1D90000/8000; SPI265→standart GSI297 yalnız sayısal dönüşüm.
IRQ flags, power, coherency ve SMMU ownership tahmin edilmedi. Native SID300
identity gözlemi Windows DMA handoff kanıtı değildir.

## Neden RAM FAT32?

Hedef A için bütün Windows'u telefona kurmak veya gerçek ESP oluşturmak zorunlu
olmayabilir: source loader yalnız kendi RAM FAT32 handle'ından Microsoft EFI
okur. Hiçbir fiziksel disk taranmaz. Root bu RAM superfloppy'dir; GPT/ESP değildir.
Standart RAM-disk DevicePath ve FileDevicePath kullanılır. NTFS/ext4/VHD'ye
bölüm yazması yok. Host VHD'ye bağlı mevcut BCD otomatik düzeltilmez.

RAM FAT RAW dosyası firmware'in genişletilmiş FV'sindedir; ikinci36MiB kopya
ayırmadan, PI büyük FFS/SECTION2 başlıkları denetlenerek bulunur. Kaynak FV'nin
ömrü Boot Services ile sınırlıdır; bunu kernel RAM-disk handoff'u diye sunmuyoruz.
Genişletilmiş FV yaklaşık37MiB, mevcut DXE Heap69MiB. Kalan RAM Boot Manager
allocations için yeterli kabul edilmez; gerçek dosyalarla ölçülecek. FD sınırı3MiB
korunur; payload sığmazsa build başarısız olmalı, FD/memory adresleri büyütülmez.

## EFI dosya seti ve doğrulama

Prepare-TargetA.ps1, bilgisayarda mevcut staging'den şunları alır:

- EFI/Microsoft/Boot/bootmgfw.efi; EFI/Boot/bootaa64.efi aynı dosyanın kopyası.
- Varsa Windows/Boot/Fonts, EFI/en-US MUI ve Boot/Resources dosyaları uygun
  EFI/Microsoft/Boot alt dizinlerine kopyalanır. Dosyalar değiştirilmez.
- BCD isteğe bağlıdır; verilirse sadece header doğrulanıp kopyalanır. İlk
  Target A denemesinde BCD yokluğu Microsoft'un gerçek hata ekranı adayıdır;
  hata oluşacağı veya görüntü vereceği garanti değildir.

Bunların evrensel minimum dosya seti olduğu kanıtlanmadı. Gerçek build26300.9457
Boot Manager'ın import/resource/font/locale ve RTC/policy beklentisiyle host EFI
smoke test gerekir. Microsoft imzası PowerShell'de ve ARM64 PE mimarisi Python'da
kontrol edilir. SYS storufs imza doğrulaması Boot Manager imzası yerine geçmez.
Prepare betiği Authenticode ile alınan SHA'yı FAT'a gerçekten konan SHA ile eşler.
Bilgisayarın sistem ESP'sine, BCD'sine veya registry'sine yazılmaz.

## Telefon GPT / ESP / Windows dağıtımı

Bu oturumda canlı GPT veya güncel primary/backup dosyaları elde edilmedi. Gerçek
unallocated alan ve partition extent/GUID'leri bilinmiyor; yaklaşık win boyutu
ve /dev/block/sda32 adı kimlik kanıtı değil. Eski1MiB yedekler tüm dosya sistemi
verisini korumaz. Varsayımsal ESP veya NTFS komutu verilmedi. Önceki
Resources/WindowsFirstBoot/WINDOWS_NEXT_STEPS_TR.md içindeki, güncel GPT+CRC+
GUID ve ayrı açık onay koşullu plan geçerlidir. VHD'ler telefon bölümü sayılmaz.

## İlk fiziksel test kapısı

Bugün yeni fastboot komutu yok: firmware fixture Microsoft payload içermez;
phone üzerinde GOP/SFS/runtime doğrulanmadı ve UFS provider hâlâ eksik.
İleride fiziksel paket hazırlanırsa Android header/DTB paketlemesi yalnız
orijinal boot_clean.zip ve önceki doğrulanmış BootShim temeliyle yeniden
kontrol edilmeli. FD doğrudan fastboot boot dosyası değildir.

Önce gerçek Microsoft dosyalarıyla FAT hazırlanmalı, dosya hash/imza ve ARM64
UEFI loader smoke testi tamamlanmalı; kalan donanım/runtime riskleri incelenmeli.
Fiziksel paket o zaman ayrı IMG+SHA ile teslim edilebilir. Denemede WBT RAM
okuma/LoadImage dönüşü/StartImage sınırı ile **Microsoft'un kendi ekranı** ayrı
kaydedilmeli; bizim WBT satırları veya bir logo Target A başarısı değildir.
Windows hata kodu/BCD ekranı ve doğrulanmış PE kimliği daha güçlü kanıttır;
StartImage çağrısı/EFI dönüşü yalnız sınır kanıtıdır. Kernel başarısı için
winload/kernel çıktısı ayrıca gerekir.

Kurtarma: mevcut geçici boot yolu ileride kullanılırsa güç tuşuyla çıkış ve
önceden çalışan Fastboot/TWRP tuş yolu korunur; yeni flash/format/GPT onarımı
önerilmez. ResetSystem test trap'i otomatik restart yapmaz; harici watchdog/TZ
resetlerini engellediğini iddia etmez.

**Tek sonraki işlem:** Mevcut Windows VHD/staging'inden Prepare-TargetA.ps1 ile
Microsoft imzası/hash'i kaydedilmiş RAM FAT32 girdisini üretip ARM64 UEFI
entegrasyon denemesine almak. Bu, bilinen D010/B0C6 testlerinin tekrarı değildir.
