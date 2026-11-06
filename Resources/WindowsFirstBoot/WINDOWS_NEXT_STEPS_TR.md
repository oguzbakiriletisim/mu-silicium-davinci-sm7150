# Windows ilk açılışına geçiş kapıları — otomatik dağıtım yok

Başlangıç kaynak commit'i771d94424f8802931f1bf8846435301681df09b8.
Bu değişiklikte çalışan UFS Block I/O elde edilmedi. Yeni boot denemesi önerilmez.
Mevcut UFSDxe'nin entry'sinde koşullu FFU/private reset yolu bulunduğundan
salt-okunur PREFINAL profili entry'yi EFI_WRITE_PROTECTED ile reddeder.
Bu bir depolama çalıştırma düzeltmesi değildir. Derleme ve host testleri fiziksel
çalışma veya Windows desteği olarak gösterilmez.

## Windows gereksinimleri: mevcut profilin açık eksikleri

`Platforms/Xiaomi/davinciPkg/davinci.fdf` DAVINCI_PREFINAL=1 kolu yalnız
Include/PREFINAL.inc içerir. Normal DXE/ACPI/RAW/SMBIOS kolları atlanır.
Dolayısıyla D010/DXE başarısı, Windows'a hazır firmware değildir:

- UFSDxe/provider Block I/O ve DevicePath henüz çalışır durumda doğrulanmadı.
- PartitionDxe/DiskIoDxe/FAT yok; GPT tipi ESP bulunması FAT32 ve SimpleFileSystem
  erişiminin kanıtı olmayacaktır. ESP'den bootmgfw.efi okuması ayrıca ölçülmeli.
- AcpiTableDxe/AcpiPlatformDxe ve ACPI tabloları bu profilde paketlenmiyor.
  Normal CPU-only DSDT'de UFS0/SM7150 power/PHY kaynak sözleşmesi yoktur.
  CPU/APIC/FADT/GTDT/PPTT ve IORT varlığını tek başına yeterli sayamayız.
- RuntimeDxe/variable/reset/RTC/console/GOP/SMBIOS hizmetleri Windows için ayrıca
  denetlenmeli. Fotoğraf paneli framebuffer'a doğrudan yazar; GOP kanıtı değildir.
- Native UFS DMA allocation/map ve cache-coherency, GetMemoryMap descriptor türleri,
  runtime bölgelerinin korunması, GetMemoryMap→ExitBootServices MapKey akışı ve
  SetVirtualAddressMap/runtime davranışı doğrulanmalı. FD/display/secure/SMEM,
  DMA buffer/firmware alanları normal kullanılabilir RAM olarak ilan edilmemeli.
- LoadedImage/DevicePath/LoadImage/StartImage temel loader desteği vardır;
  bootmgfw.efi ve winload.efi ile gerçek uyumluluk henüz denenmedi.
- Secure Boot/TPM/CPU politikaları ve tam Windows11 build davranışı ayrıca açık
  konulardır; BCD seçenekleri bunların tümünü veya disk sürücüsünü çözmez.

Gerekli modülleri topluca açmak yerine önce güvenilir UFS provider gerekir;
normal DXE profili daha çok native donanım yazması içerdiği için hazır çözüm değildir.

## Microsoft storufs.sys: sürücü varlığı artık olumlu bir veri

Güncelleme: tam build/INF metni sonradan kullanıcı tarafından paylaşıldı.
Aşağıdaki ilk değerlendirmeyi tamamlayan sonuç STORUFS_SM7150_TR.md içindedir.
Gerçek SYS/INF/CAT dosyaları hâlâ bu ortama verilmedi.


Kullanıcı bildirimi: ARM64/0xAA64,125944 bayt; INF genel UFS ve QCOM24A5 içeriyor.
Bu oturumda gerçek SYS/INF/CAT dosyaları ve tam Windows build'i verilmedi;
Microsoft imzası, dosya sürümü, seçilen ARM64 kurulum bölümleri ve registry servis
kurulumu bağımsız doğrulanmadı. "Windows UFS sürücüsü yok" denmiyor;
"bu sürücü SM7150 üzerinde doğrulandı" da denmiyor.

```powershell
python Resources\WindowsFirstBoot\inspect_storufs.py --sys C:\STAGING\Windows\System32\drivers\storufs.sys --inf C:\STAGING\Windows\INF\storufs.inf
Get-AuthenticodeSignature C:\STAGING\Windows\System32\drivers\storufs.sys | Format-List Status,StatusMessage,SignerCertificate
(Get-Item C:\STAGING\Windows\System32\drivers\storufs.sys).VersionInfo | Format-List FileVersion,ProductVersion
```

Bunlar sadece bilgisayardaki dosyaları okur. SYS katalogla imzalanmışsa tek
Get-AuthenticodeSignature sonucu bütün katalog zincirini çözmeyebilir; eşleşen
CAT/INF paketi ayrıca incelenir. INF satırları seçili Install/Services/AddReg/
Include/Needs zinciriyle değerlendirilmelidir. StartType/Start=0 ve Storport
bağımlılıkları kontrol edilmeden boot-start desteği ilan edilmez.
QCOM24A5 eklemek donanım desteği oluşturmaz. Generic UFSHCI register standardı
Qualcomm PHY/clock/reset/rail, ICE, vendor quirks, IORT/DMA veya PEP sözleşmesinin
yerine geçmez. UEFI SMMU identity snapshot'ı Windows IOMMU handoff kanıtı değildir.

## Bölümleri koruyan koşullu ESP ve dağıtım prosedürü

1. Önce salt-okunur UFS provider ile fiziksel LUN kimliği/kapasitesi, blok boyutu,
   primary+backup GPT CRC'si, disk GUID'si ve tüm bölüm GUID/extent/type/name
   alanları kaydedilir. `sda32` adı veya yaklaşık55,37GB tek başına kimlik değildir.
2. Bilgisayardaki eski GPT yedeğiyle kıyaslanır. Arada GPT değişmiş olabileceği
   için eski1MiB dosyalar güncel yedek yerine sayılmaz. Bölüm ve win içeriği için
   doğrulanabilir bağımsız yedek gerekir; yalnız GPT dosyaları veri yedeği değildir.
3. **Gerçek tahsis edilmemiş alan varsa** tüm mevcut extent'lerin dışında,
   hizalı512MiB ESP planlanır. GPT türü C12A7328-F81F-11D2-BA4B-00A0C93EC93B,
   benzersiz yeni partition GUID, FAT32. Mevcut bölümler taşınmaz/silinmez.
   Yeni ESP eklemek primary/backup GPT'ye yazmayı gerektirir; GPT baytlarını
   değiştirmeden ESP eklenebileceği iddia edilmez. Korunan mevcut entry/extent'lerdir.
   Yazma, kullanıcı kesin LUN/disk/bölüm planını ayrıca onayladıktan sonra ve
   güncel GPT eşleşmesi tekrar doğrulanarak yapılabilir; bu dosya komut çalıştırmaz.
4. Tahsis edilmemiş alan yoksa süreç durur. Telefonun başka bölümünü ödünç almak,
   ESP VHD'yi telefonun ESP'si kabul etmek veya ext4 win'e NTFS dosyaları yazmak yok.
   win'i küçültmek/yeniden oluşturmak mevcut extent'i değiştirir; koruma şartıyla
   otomatik uyumlu değildir. Ayrı yedek ve ayrı onay gerektiren tasarım kararıdır.
5. ext4→NTFS için doğrulanmış veri-koruyan yerinde dönüşüm varsayılmaz. Mevcut
   win GUID/extent korunarak NTFS biçimlendirmek de o bölümün ext4 verilerini yok
   eder; otomatik yapılmaz. Bu izin olmadan yalnız offline hazırlık yapılabilir.
6. Windows staging'i `Resources/Windows/davinci/prepare_windows.py inspect`
   yardımındaki gerçek seçeneklerle denetleyin. Mevcut Windows install-kit araçları
   kullanılabilir; bu görevde yeniden üretilmedi. Dosya kopyasının ACL/hardlink/
   reparse metadata'sını koruduğu varsayılmaz; doğrulanmış WIM/DISM veya metadata'yı
   koruyan uygulama yolu gerekir. Telefon bilgisayara disk olarak erişilemiyorsa
   DISM /ApplyDir hedefi hazır değildir; UEFI Block I/O, Windows host disk erişimi
   veya TWRP'nin NTFS dağıtım desteği anlamına gelmez.
7. Önce yalnız bilgisayarda yeni dizinde offline EFI/BCD hazırlanır. Disk GUID,
   gerçek ESP GUID ve gerçek NTFS Windows GUID'i zorunlu girdi olmalıdır. Mevcut
   prepare_windows.py prepare-efi bu amaç için incelenebilir. Host sistem BCD'si
   veya var olan ESP değiştirilmez. Bootmgfw.efi/BCD ve bootaa64.efi yerleşimi
   gerçek FAT32 hedefe ancak açık dağıtım onayından sonra aktarılır.
8. Boot-start sürücü, kaynak/ACPI ve kernel disk erişimi koşulları sağlanmadan
   deployment-ready verilmez. Bu aşamada EFI/BCD klasörlerinin hazır olması yeterli
   değildir. Geri dönüş, geçici UEFI'den önceden çalışan Fastboot/TWRP yoludur;
   henüz yapılmamış GPT/NTFS işlemleri için varsayımsal "tek komut kurtarma" yoktur.

## Birbirine karıştırılmayacak fiziksel başarılar

| Seviye | Somut kabul kanıtı | Bugün |
|---|---|---|
| UEFI | SEC/PrePi ve DXE paneli | Kullanıcı fiziksel testinde doğrulandı. |
| Dahili disk/ESP | Gerçek ReadBlocks+GPT CRC+GUID; FAT32 üzerinden bilinen dosyanın okuması/hash'i | Yok. |
| Windows Boot Manager | bootmgfw.efi gerçekten çalışır; okunabilir BCD ekranı/hatası bile entry kanıtı olabilir | Yok. |
| Windows yükleyici | winload.efi'nin çalışması ve yükleme aşamasını belirleyen çıktı | Yok; sadece logo/spinner kernel kanıtı değildir. |
| Windows kernel | WinDbg/kernel log/BSOD gibi kernel yürütmesini ayırt eden çıktı | Yok; INACCESSIBLE_BOOT_DEVICE başarıyla disk açılması değildir. |
| Masaüstü | Gerçek Windows oturumu ve sistem bilgisi | Yok. |

Bir sonraki fiziksel deneme yalnız FFU/private reset içermediği denetlenmiş bir
UFS provider ve mevcut DMA/ownership/readback kapılarıyla yapılmalı. Tek soru:
"bu provider gerçek ReadBlocks ile primary/backup GPT'yi okuyabiliyor mu?"
Mevcut auto imajını tekrar başlatmak veya bir stop imajını kaldırmak bu düzeltme değildir.
