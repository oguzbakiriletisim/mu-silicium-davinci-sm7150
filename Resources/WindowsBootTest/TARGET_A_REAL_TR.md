# Davinci — Gerçek Microsoft Boot Manager entegrasyonu

**Sonuç:** Gerçek Microsoft ARM64 Boot Manager, ARM64 QEMU'da, telefon
profilinin aynı RAM Block I/O / GPT / SFS yardımcıları üzerinden yürütüldü.
Microsoft Recovery ekranı görüldü: `\EFI\Microsoft\Boot\BCD`, `0xc000000f`.
**Telefon üzerinde bu profil denenmedi; Hedef A telefonda tamamlanmış değildir.**
Windows çekirdeği veya masaüstü açılmadı. Deneysel geçici boot imajı hazırlandı;
fiziksel güvenlik veya başarı garantisi verilmez.

## Kaynak ve değişiklikler

Başlangıç: `c2a061ccb421108829c8a868f722370e1bf7263e`,
dal: `davinci-windows-boot-test`.

- `a1f8e41a9512041b2565b86bfe48c2ebad331117`: `verify_target_a.py`, güvenilmeyen
  ZIP/FAT girdisini denetler; altı bozuk girdi testi. Yardımcı ZIP kaynakları
  önce okundu; sağlanan shell betiği körlemesine çalıştırılmadı.
- `7b3002645a0078370fdfe6de745c8fc53900a21b`: aşağıdaki gerçek entegrasyon.

| Dosya | Değişiklik ve gerekçe |
|---|---|
| `Drivers/WindowsBootTestDxe/WindowsBootTestDxe.c` | RAM provider ortak `PublishDisk()`; GPT ESP çocuğu gerçek DevicePath/bölüm GUID/başlangıç/boyut ile seçilir. Başka medyaya geçilmez. BCD gerçek Open sonucu gösterilir. Microsoft dosyasına ait gerçek `Boot5742`/`BootCurrent` oluşturulur; BootOrder değiştirilmez. |
| `Drivers/WindowsBootTestDxe/RamGpt.h` | Tampon boyutu, protective MBR, iki GPT header/CRC, iki entry dizisi/CRC, tek ESP sınırı ve içerideki FAT denetlenir. |
| `Include/WINDOWS_BOOT_TEST.inc` | PartitionDxe hem APRIORI hem FV listesine eklenir. DiskIo → Partition → FAT → SFS zinciri. |
| `Applications/WindowsBootSmoke/*` ve `davinci.dsc` | Varsayılan kapalı, FDF'ye eklenmeyen ARM64 host uygulaması. Telefon driver'ının aynı RAM/console/context kodunu kullanır; telefonun architecture protokollerini kurmaz. |
| `Resources/WindowsBootTest/ram_gpt.py` | Gerçek FAT bytes'larını değiştirmeden 40 MiB sanal GPT diskinin içine alır. Bu, telefon GPT planı değildir. |
| `build_verified_target_a.sh`, `build_windows.sh` | Doğrulanmış özel girdiyi firmware'e bağlar; ikinci büyük RAM kopyası oluşturmaz. Microsoft verileri Git ağacı dışında tutulur. |
| `audit.py` | FD'nin içindeki LZMA FV açılarak denetlenen FV ile birebir eşleştirilir. Gerçek RAW → sanal GPT → özgün FAT C yolu da doğrulanır. |
| `run_arm64_smoke.py` | Ağsız, salt okunur QEMU taşıyıcısı; gerçek PE girişinde breakpoint, gerçek dönüş/reset kayıtları ve ekran görüntüsü. |
| `Resources/BootTests/davinci_boot_image.py` | Yeni WBT paketleme profili, eşleşen özel build klasörünü yeniden denetlemeden imaj üretmez. Önceki profillerin marker koşulları korunur. |

Driver yolları `Platforms/Xiaomi/davinciPkg/` altındadır. Kesin satırlar ilgili
commit'in diff'inde görülebilir. `PREFINAL.inc`, DeviceMemoryMapLib ve PrePi
kaynaklarında değişiklik yok. Native UFS/FFU/HAL/SMMU kapıları kaldırılmadı.

## Girdi doğrulaması

Her iki ZIP güvenli ad, boyut, tekrar ve symlink kontrollerinden sonra ayrı
özel klasörlere çıkarıldı. Yeniden gönderilen ZIP'ler önceki kopyalarla aynı.

| Girdi | SHA-256 |
|---|---|
| Yardımcı ZIP | `d2212c76dc0ead3a702f9563beb33c01d21be7514b2cd24536efea64d3d7287b` |
| Microsoft girdi ZIP | `0571383771c0575ca7508cddb416d07d5132533498a4de682c99aec5a99a4af0` |
| Özgün 36 MiB FAT | `c077c62fdb2a6619680f243cdb16de67b01f6e9e66a7c19d6d5d96e553e63ded` |
| Gerçek bootmgfw.efi / bootaa64.efi | `fae47d78487e781aa06466775cb461adeb7ff7f887fe2c15295bb2eb4f4954e1` |

Dokuz FAT dosyasının hash'i manifestle eşleşti; mtools ile bağımsız okumalar da
aynı dosyaları verdi. BCD **yok**. PE: 3.120.648 bayt, Machine AA64, PE32+,
EFI application, entry RVA `0x3e130`, SizeOfImage `0x341000`.

Gerçek PE resource FileVersion **10.0.28000.367**. Kullanıcının Authenticode
raporundaki version 28000.342; MUI dosyaları da 28000.342. bootres.dll
26100.8655. Bu fark bozulma kanıtı değildir; servis edilmiş kaynak sürümleri
farklı olabilir, bunun nedeni doğrulanmadı. Dosyalar değiştirilmedi.

Gönderilen Windows imza raporu Valid/Microsoft diyor. Yerel osslsigncode
Authenticode içerik digest'ini eşleştirdi; yerel CA deposuyla Microsoft issuer
zinciri kurulamadı. Tam bağımsız güven zinciri doğrulaması geçti denmiyor.
`evidence/target-a-real/OSSLSIGNCODE.log` ve PE metadata kayıtları korunmuştur.

## Gerçek yürütme deneyleri ve düzeltmenin sınırı

1. İlk, GPT'siz RAM FAT yolu: SFS ve LoadImage başarılı, gerçek PE girişinde
   breakpoint; StartImage `0x8000000000000002` (EFI_INVALID_PARAMETER).
2. QEMU'nun virtio/GPT bölümündeki aynı PE: gerçek Recovery arayüzü ve eksik BCD.
3. RAM GPT eklendiğinde fakat doğru BootCurrent olmadan: PE girişine ulaşıldı,
   reset isteği gözlendi; fotoğrafta Microsoft hata arayüzü yoktu.
4. **Aynı RAM GPT yolu + gerçek yükleme seçeneği bağlamı:** Boot context/SFS/
   LoadImage başarı; debugger `PC=entry=0x7b273130`; **Microsoft Recovery**
   ekranı, BCD `0xc000000f`. ResetSystem type 0 / status 0 çağrısı host hook'ta
   tutuldu. StartImage dönüşü gözlenmedi; bu alana sahte EFI_SUCCESS yazılmadı.

Bu karşılaştırmalar kullanılan ortamda yükleme bağlamının önemini gösterir;
kapalı Microsoft kodundaki kesin iç karar dalı çözümlenmiş değildir. BCD'nin
olmaması Recovery ekranından doğrulanır, ilk Invalid Parameter'ın tek nedeni
olduğu iddia edilmez. Son ekranın altındaki `HOST_SMOKE` satırları bizim gerçek
reset kayıtlarımızdır; üstteki Recovery ekranı Microsoft ikilisinin çıktısıdır.

Host: QEMU 10.0.13, ARM64 virt/GICv3/TCG, 1 GiB RAM, AAVMF
2025.02-8+deb13u1, GOP 800×600. Telefon firmware'i QEMU'da bütünüyle
başlatılmadı; host uygulaması aynı C provider/console/context işlevlerini
kullanır. AAVMF'nin DXE/ACPI/RNG/variable ortamı davinci firmware'i değildir.
GOP, RNG protokol varlığı host'ta başarıyla ölçüldü; RNG kalitesi test edilmedi.
Telefondaki GOP/protokol kurulumları ve gerçek Microsoft davranışı açık kalır.

## Derleme, bellek ve regresyon

- Gerçek DEBUG derlemeleri başarılı. Güncel FD 3.145.728 bayt; sınır 3 MiB.
- Açılmış FV **43.057.152 bayt**. Sanal disk 40 MiB, özgün FAT 36 MiB.
  FAT değişmedi; GPT/boşluk ilavesi firmware'in içinde, salt okunur RAM'dedir.
- Sanal diskin RAW alanı açılmış FV içinde doğrudan kullanılır; ikinci 40 MiB
  AllocatePool yok. Standart RAM-disk DevicePath gerçek başlangıç/bitiş RAM
  adreslerini taşır, GPT çocuğu gerçek HD DevicePath alır.
- DXE Heap 69 MiB; FV bunun yaklaşık %59,5'idir. Kalan alanın tüm Microsoft
  allocations için yeterli olduğu fiziksel olarak doğrulanmadı; heap büyütülmedi.
- Gerçek FD açılımı FV ile, RAW içindeki FAT özgün dosyayla eşleşti.
  Paketlenen ARM64 EFI mimarileri, FFS/DEPEX envanteri ve ACPI checksum'ları geçti.
- Native lock listesindeki UFS/HAL/bağımlılıklar FV'de **yok**. EnvDxe önceki
  ikiliyle aynı hash. RAM disk WriteBlocks daima EFI_WRITE_PROTECTED.
- **115 test, sıfır failure/error/skip.** CRC bozulmaları, sınırlar, eski BootShim
  emülasyonu, eski korumalar ve PowerShell kontrolleri dahil. Bir önceki denemede
  eksik Python yolu; diğerinde eşzamanlı derleme sırasında geçici disk doluluğu
  test hatası verdi. Ortam düzeltildikten sonra tüm suite sıralı olarak geçti.
- Bu turda yeni PREFINAL firmware derlemesi yapılmadı; o profilin kaynakları
  değiştirilmedi. Önceki bağımsız derleme kanıtı eski evidence klasöründedir.

## Deneysel Android imajı

`davinci-target-a-experimental.img`, **4.145.152 bayt**.

SHA-256:
`9633ff286df1d288a0fe02210f9adc444a7ed9a27c8e341e7edec3e7640e7ce6`

FD SHA-256:
`5092905551b96e96d5336da37ffdff9a5c33e339790c48175b1899fc5ba87e59`

Özgün 128 MiB backup hash'i
`a25d36cb56d8ee3cc110dece98fee39e4ce9729c8eeeb0d007e8faf1723f2cda`.
Orijinal değiştirilmedi. Girdi header **v1**, page **4096**, header size **1648**.
Korunan alan değerleri: kernel_addr `0x8000`, ramdisk_addr `0x1000000`,
second_addr `0xf00000`, tags_addr `0x100`. Bunlar header'ın ham değerleridir;
ABL'nin bunlardan fiziksel adres hesaplama davranışı yeniden varsayılmadı.
Ramdisk, second ve recovery_dtbo boş. BootShim 144 bayt; hedef FD
`0x9fc00000..0x9ff00000`, PrePi stack `0x9ff90000..0x9ffd0000`, display
`0x9c000000..0x9d800000`: mevcut tanımlarda bu aralıklar çakışmaz.

Gzip içinde aynı BootShim + FD var; özgün appended DTB'ler birebir korundu.
DTB hash: `80343237651179447d50c2d0cefa08a398c3b50e3428a12415ce87f1638d5ec2`.
Header'da yalnız kernel_size/image_id güncellendi. Özgün AVB footer yeni
imaja taşınmadı; yeni imaj AVB imzalı değildir. Tekrar paketleme birebir aynı
hash'i verdi. Bu kontroller ABL kabulünü veya cihazda bellek yeterliliğini
kanıtlamaz. Önceki geçici fastboot yolu kullanıcının eski imaj testlerinde
çalışmıştı; **yeni imajda çalışma garantisi yoktur**.

## Kullanıcının isteğe bağlı fiziksel denemesi

Paket açıldıktan sonra Windows PowerShell:

```powershell
Get-FileHash .\davinci-target-a-experimental.img -Algorithm SHA256
fastboot boot .\davinci-target-a-experimental.img
```

Hash yukarıdakiyle aynı değilse çalıştırmayın. Komutları bu çalışma sırasında
telefonda biz çalıştırmadık. Kalıcı flash, format veya bölüm değişikliği yok.
Telefonun önceki açık bootloader/Fastboot durumunun korunduğu varsayılır.

UEFI tanılama yazısı, FAT okuması veya LoadImage başarı satırı Hedef A değildir.
**Telefonda gerçek Microsoft Recovery/Boot Manager arayüzü görülmesi** ve ekran
fotoğrafı/video ile ilişkilendirilmesi Hedef A'nın cihaz kanıtıdır. Mevcut girdiyle
BCD 0xc000000f beklenebilir; kernel/masaüstü başarısı değildir. Tuş/USB/touch
sürücüsü sağlanmadığı için Recovery'nin Esc seçeneği çalışıyor kabul edilmez.

Takılırsa güç tuşunu basılı tutarak yeniden başlatın; Güç + Ses Kısma ile
Fastboot'a dönün. Önceden kurulu TWRP'ye dönüş mevcut kurulumdaki Güç + Ses Açma
kombinasyonuna bağlıdır. Paket kurtarma için bölüme yazma komutu gerektirmez.
Dış watchdog/güç yönetimi kaynaklı reset ihtimali bu profilde giderilmiş değildir.

## Yeniden üretim

Mevcut toolchain ortamını etkinleştirdikten sonra Git dışındaki yeni klasörde:

```bash
bash Resources/WindowsBootTest/build_verified_target_a.sh \
  /private/davinci-target-a-input.zip /private/target-a-build
python3 Resources/WindowsBootTest/run_arm64_smoke.py \
  --qemu /tools/qemu-system-aarch64 --firmware /tools/QEMU_EFI.fd \
  --rom-dir /tools/seabios --efi /private/target-a-build/DavinciWindowsBootSmoke.efi \
  --fat /private/target-a-build/efi-fat32.img --output /private/qemu-target-a
python3 Resources/BootTests/davinci_boot_image.py --profile windows-boot-test \
  --backup /private/boot_clean.zip --shim /private/BootShim.bin \
  --fd /private/target-a-build/WINDOWS_BOOT_TEST.fd \
  --windows-folder /private/target-a-build --output /private/target-a.img
```

Toolchain ve submodule listeleri evidence altında. Kaynakdaki tarih/saat
makroları nedeniyle yeniden **derleme** FD hash'ini değiştirebilir; aynı FD,
shim ve backup ile **paketleme** deterministiktir. Derlemede taban/boyut veya
header parametresi tahmin edilmez; boyut taşması build/audit'i durdurmalıdır.

## Kalan engeller ve sonraki işlem

En yakın işlem bu tek deneysel imajın kullanıcı tarafından geçici açılışını
belgelemek. QEMU sonucu telefon başarısı yerine geçmez. Microsoft ekranı
telefonda görülürse BCD içeren doğrulanmış girdiyle bir sonraki aşama planlanır.
Mevcut `Prepare-TargetA.ps1` `-Bcd` ile bilgisayardaki **offline** BCD'yi alabilir;
VHD'ye bağlı disk kimlikleri otomatik telefona çevrilmez. BCD eklemek RAM
önyüklemenin bütün koşullarını veya kernel erişimini tek başına çözmez.

Telefon için hâlâ GOP/console görünümü, MemoryMap/allocations, emüle variables,
RTC'siz çalışma, runtime protokolleri ve platform firmware farkı test bekliyor.
CPU-only ACPI depolama/power/IORT sözleşmesi değildir; UFS ACPI cihazı devre dışı.
Native UFS Block I/O, gerçek ESP/NTFS erişimi, SM7150 PHY/clock/DMA/Windows
storufs devri, gerekli ACPI ve Windows kernel handoff çözülmedi. Kimlik taklidi,
tahmini IRQ/DMA veya yeni donanım register yazması yapılmadı.

GitHub'a yalnız kaynak, günlük ve ekran kanıtı gönderilir. Gerçek Microsoft
PE/FAT, onları içeren FD, boot.img ve deneysel ZIP **GitHub'a commit edilmez**.
