# Microsoft StorUFS — kullanıcı INF aktarımıyla güncellenen değerlendirme

Kaynak başlangıcı a7230b5b1b300515414f77f2db877c7ede2ee7d5.
SYS/INF/CAT dosyaları bu ortama verilmedi; aşağıdaki sürüm/INF bilgileri kullanıcı
metin aktarımıdır. Dosyalar değiştirilmedi; imza/PE içe aktarımları bağımsız
incelenmedi. Native UEFI UFS entry engeli ve mevcut HAL/SMMU kapıları korunur.

## Artık hangi noktalar biliniyor?

- Kullanıcının DISM çıktısı Windows11 Pro ARM64,10.0.26300.9457, WIM index3;
  uygulama host'u DISM10.0.19041.3636. Windows48GB dinamik VHD'ye uygulanmış.
- INF DriverVer06/21/2006,10.0.26100.9278; Microsoft/SCSIAdapter,
  storufs.sys125944 bayt/AA64. INF DriverVer, SYS dosya sürümüyle ayrıca eşlenmeli.
  Image/driver build sayılarının farklı olması tek başına uyumsuzluk/bozulma kanıtı
  değildir;2006 tarihinden de sürücünün gerçek geliştirme yaşı çıkarılamaz.
- ARM64 QCOM24A5 modeli→UfsQualcomm8996Install; AddService storufs,2,
  UfsServiceInstall. Genel model PCI/ACPI CC_010901→UfsInstall.
- UfsServiceInstall ServiceType1,StartType0,ErrorControl1, %12%\\storufs.sys.
  Dolayısıyla **INF'de ARM64 boot-start UFS servisi tanımı vardır**. Offline SYSTEM
  hive'da gerçek Services\\storufs, StartOverride, yükleme bağımlılıkları ve
  ilgili PnP device-instance kurulumu ayrıca doğrulanmalıdır. Henüz bağımsız test yok.
- Include/Needs bulunmadığı bildirildi. Bu, Storport ikili import'larının,
  controller power/clock/PHY veya ACPI bağımlılıklarının bulunmadığını göstermez.

## Genel UFS yolu SM7150'ya bağlanabilir mi?

PnP düzeyinde, gerçek ACPI enumerator genel modelle eşleşen ID sunarsa teknik
olarak mümkün bir adaydır. Bu, denetleyicinin UFSHCI register/interrupt/descriptor
biçimi, Qualcomm quirks, PHY/power init ve DMA sözleşmesinin generic miniport'la
uyumlu olduğunu göstermez. PCI CC eşleşmesi de bu platform denetleyicisini PCI
cihazı yapmaz; sahte PCI köprüsü veya sahte kimlik önerilmez.

Firmware ACPI _HID/_CID/_CLS alanları ile Windows'un oluşturacağı HardwareIDs/
CompatibleIDs birebir aynı sözdizimi değildir. INF'deki `ACPI\\CC_010901` metnini
_HID'ye yapıştırmak doğru bir ACPI tasarımı değildir. Gerçek Windows ACPI
numaralandırmasının ürettiği ID'ler doğrulanmalıdır. Kimlik eşleşmesi yalnız
binding kanıtıdır; donanımın çalıştığının kanıtı değildir.

QCOM24A5 yolunun kurulum bölümündeki8996 adı, tek başına sürücünün sadece8996
üzerinde çalışacağını da bütün Qualcomm SoC'lerinde çalışacağını da kanıtlamaz.
Yerel `Silicium-ACPI/Platforms/Xiaomi/cepheus/DSDT.dsl:40–76` aynı QCOM24A5
adını taşır (altmodül992be737c217ba86b2efbded0ecc60142f108917). Bu sadece farklı
bir cihazın referans AML sözleşmesidir; SM7150'ya kopyalanmadı, cepheus üzerinde
bu Microsoft sürücüsünün çalıştığına ilişkin kanıt diye sunulmadı.

## FeatureFlags ve HSSeries

| Ayar | Kanıtlanabilen | Henüz kanıtlanamayan |
|---|---|---|
| FeatureFlags40000000 | Qualcomm install HW.AddReg yolunda driver'a verilen bit30 | Hangi quirk/register/clock/power/DMA yolunu seçtiği. Gerçek26100.9278 SYS kodu veya güvenilir sembol/kaynak gerekir. |
| HSSeries2 | Qualcomm install HW.AddReg yolunda2 değeri | Registry değerinin bu SYS sürümünde hangi dala çevrildiği ve SM7150'ya uygunluğu. |

UniPro standart frekans serisinde A=1, B=2'dır: Linux include/ufs/unipro.h,
blob9c168703b104801c87f24aae6d5c7cf42fb8263f, enum ufs_hs_gear_rate.
Bu yüzden HSSeries2 **HS Rate B adayıdır**; gear2 veya2 lane anlamına geldiği
söylenemez. Ancak Linux enum'u, Microsoft registry okuyucusunun davranış kanıtı
değildir. HS-B clock/PHY desteği ve device negotiation ayrıca gerekir.
FeatureFlags'a bir isim uydurulmadı ve bu iki değer SM7150'ya uygulanmadı.

## ACPI için sabit kaynaklar ve karar verilmemesi gereken alanlar

`Resources/DTBs/davinci.dts:4680–4738` ve cihaz DeviceMemoryMapLib kaynağı:

- HCI1D84000/3000, PHY1D87000/DDC, ICE1D90000/8000. CPU MMIO haritasında
  kapsanmaları erişimin/controller'ın çalıştığı anlamına gelmez.
- Interrupt specifier `<0 0x109 0>`:265 **SPI indeksidir**; GIC INTID/GSI
  karşılığı standart SPI tabanı32 eklenince **297/0x129** olur. ACPI Interrupt
  alanına265'i doğrudan yazmak hatalı olur. Trigger/polarity/ownership, yalnız
  üçüncü hücre0'dan tahmin edilmez; doğru GIC ve driver sözleşmesiyle doğrulanır.
- Generic miniport için HCI resource'u, vendor miniport için PHY/ICE/ek vendor
  pencereleri ve resource sıralaması farklı olabilir. Cepheus referansı14000
  uzunluklu birleşik pencere kullanıyor; bu uzunluk davinci'ye otomatik taşınmaz.
- _HID gerçek cihaz kimliği; _CID yalnız doğrulanmış uyumluluk; _STA gerçek
  kullanılabilirlik. QCOM24A5 adıyla PnP'yi zorlamak uygulanmadı.
- _CCA gerçek DMA coherency sözleşmesine göre seçilmeli. Referansın_CCA=1'i
  kopyalanamaz. UEFI IOC0/SCTLR E0 gözlemi tek başına Windows coherency değerini
  belirlemez. Get/Map DMA ve cache-maintenance davranışı gerekir.
- IORT: DAL'dan UFS0/ARID0→SID300, mask kapsamı300–30F ve SMMU15000000 bilgisi
  var. Named Component yolu, ID kapsamı, SMMUv2 kaynak/interrupt'ları ve mapping
  semantiği gerçek donanımla tamamlanmalı; eksik IRQ/bank/TTBR uydurulmaz.
- _DEP/_PR0/_PR3/_PS0/_PS3 ancak gerçek clock/regulator/reset/PEP sağlayıcısıyla
  anlamlıdır. Başarı döndüren boş AML yöntemleri veya olmayan PEP node'u eklenmez.
  Mevcut CPU-only DSDT henüz böyle bir storage/power sözleşmesi sunmuyor.

## UEFI→Windows devir koşulları

1. FFU/private-reset/provisioning içermeyen, kaynak veya çağrı grafiği denetlenmiş
   provider gerçek Block I/O ve GPT CRC/GUID erişimini sağlamalı.
2. PHY lane/refclk, host core/bus/iface/unipro/ICE clock'ları, güç rayları ve reset
   durumu tanımlı kalmalı; Windows'un kendi init/power geçişleriyle çelişmemeli.
3. UEFI pending transfer/interrupt ve ring/list/DMA sahipliği düzgün bırakılmalı.
   OS başlamadan SMMU kapısını körlemesine kaldırmak veya DMA'nın eski firmware
   buffer'larına devam etmesi kabul edilemez. ExitBootServices bir UFS driver
   reset/destructor garantisi değildir.
4. OS DMA buffer'ları, IORT/SMMU mapping'i ve cache coherency desteklenmeli.
   UEFI'nin geçici identity readback'i Windows'un yeni map/attach davranışının
   veya boot-start disk erişiminin kanıtı değildir.
5. Windows miniport gerekli init/quirk/resource/power yolunu kullanabilmeli;
   UEFI'nin clock'u açık bırakması tek başına sürücünün platform init ihtiyacını
   ortadan kaldırmaz. ACPI/Storport/PEP ve irq ownership bu sınırda doğrulanır.

48GB dinamik VHD, telefondaki mevcut ext4 bölümü veya ESP değildir. VHD dosyasını
win bölümüne kopyalamak, ext4'ü NTFS yapmaz; VHD native boot da fiziksel UFS
boot-start erişimi ihtiyacını kendiliğinden çözmez. Önceki ESP/GUID/NTFS planı
WINDOWS_NEXT_STEPS_TR.md içinde geçerlidir; bölüm yazması otomatik başlamaz.

Bir sonraki güvenli bilgisayar işi, aynı SYS/INF/CAT'ın hash/imza/version/import
ve registry okuma dallarını incelemektir. Gerçek driver dosyası verilmeden
FeatureFlags0x40000000 için kesin bit anlamı veya destekli bir SM7150 ACPI
şablonu üretildiği iddia edilemez. Bu yüzden SYS/INF değiştirilmedi ve henüz
telefon için yeni Windows boot komutu verilmedi.
