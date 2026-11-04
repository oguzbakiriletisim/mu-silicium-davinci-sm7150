# Xiaomi Mi 9T UEFI geliştirme raporu

> Bu belge ilk 11 commit aşamasının tarihsel kaydıdır. Devam eden geliştirme ve güncel test sonuçları için [ikinci aşama raporuna](FAZ2_RAPOR.md) bakın.

Tarih: 4 Kasım 2026. Hedef: `davinci`, Snapdragon 730 / SM7150-AA.
Dal: `davinci-win11-uefi-research`.
Taban: `89cae67c6544cd100d3080fe02b3f3190c9be3ba`.

**Bu çalışma fiziksel cihazda doğrulanmamıştır. Üretilen FD telefon üzerinde test veya kurulum için hazır kabul edilmemelidir. Windows Boot Manager veya Windows 11 masaüstü başarısı elde edildiği iddia edilmiyor.**

## Sonuç

Kaynak değişiklikleri, AARCH64 derlemesi, ACPI derlemesi, host birim testleri ve FD içerik incelemesi yapıldı. İsteğe bağlı CPU-only ACPI profili ile ve profil kapalı varsayılan DEBUG yapılandırmasıyla tam firmware volume derlemeleri tamamlandı. Aynı hazırlanmış ortamda taban kaynak tekrar derlendiğinde `RealTimeClockLibNull` başlık bağımlılığı hatası yeniden üretildi; bu dalda düzeltildi.

UFSDxe ikilisi değiştirilmedi. `4112f787d3d85426871c505088c4ebf298bdc76f` ile gelen IOMMU atlatması korunuyor. Dahili UFS'nin algılanması veya DMA'nın doğru çalışması çözülmüş değildir. Yeni DEBUG tanılama sürücüsü bunun ileride hangi aşamada kaldığını gözlemlemeyi amaçlar.

## Kaynak ve araç sabitleme

Ana kaynak ve karşılaştırmalar:

| Kaynak | Commit / artefakt |
|---|---|
| mu-silicium-davinci-sm7150 | `89cae67c6544cd100d3080fe02b3f3190c9be3ba` |
| edk2-msm-sm7150-davinci | `5c81c678e5f8e115e5490ed42778b4b1bf57ad37` |
| Cl1nkkk/edk2-davinci | `60ab49153d86efbd647d73dc2a4c7d5be47538c0` / 0.2; yalnız çevrimdışı karşılaştırma |
| edk2-porting/edk2-sm7150 | `b8c0f5665c678ca695ccc11f53c4891d585d8e1c` |

`source-lock.json`, 27 alt modülün üst Git ağacındaki gitlink kimliği ile gerçek checkout kimliğini kaydeder. Kayıt sırasında eksik checkout veya kimlik uyuşmazlığı yoktu. Alt modül kodları değiştirilmedi. İndirme alanını sınırlamak için bazı alt modüllerin geçmişi sığlaştırıldı; kaynak commit kimlikleri değiştirilmedi. OpenSSL'in derlemede kullanılmayan test depoları için yerel recursion ayarları kullanıldı; bunların checkout kimlikleri de kilit dosyasında kayıtlıdır.

Araçlar: Python 3.12.14; Clang/LLVM/LLD 19.1.7; IASL 20250404; host GCC 14.2.0; sistem NASM 2.16.03. Python paketlerinin kesin sürümleri `python-requirements.lock` dosyasında. Mu BaseTools `v2025020003.0.5`, crypto binary paketi `1.1.3`; kaynak descriptor SHA-256 kontrolleri korunmuştur. Bu kayıt bit düzeyinde yeniden üretim garantisi değildir; tüm host paketleri ve zaman damgaları sabitlenmiş değildir.

## Küçük commit'ler ve gerekçeleri

| Commit | Dosya / değişiklik | Gerekçe |
|---|---|---|
| `4b1f6c401fcefaca21c8badcf94ce6d72a8bf052` | `pip-requirements.txt` | Eski pytools `pkg_resources` kullanıyor. Setuptools 80.9.0 sabitlendi. |
| `810ea5a3df2324b6f7f56e4c5ca800db5124473e` | `Platforms/Xiaomi/davinciPkg/davinci.dsc` | `SOC_TYPE=2` (732G) yerine `0` (730/SM7150-AA). Bu bir donanım başlatma düzeltmesi olarak sunulmuyor. |
| `44c013dce384fcb40957c663c3bf44792db304d2` | `Drivers/StorageAuditDxe/*`, cihaz DSC/DXE/APRIORI, C testi | DEBUG preflight ve Block I/O metadata gözlemi. UFS ikilisine veya başlatma kararına müdahale yok. |
| `73e95f108a61d805162a4038caa4b033b2bfe1d7` | `AcpiTables/Dsdt.asl`, INF, cihaz ACPI/DSC ve research update library | Davinci CPU topolojisi için sıfırdan yazılmış, isteğe bağlı CPU-only namespace. |
| `e448322da0ac9f443dd9287e5482fd43742436c1` | `DeviceBuild.py`, `SystemTools/system_nasm_path_env.json` | `DAVINCI_SYSTEM_NASM=1` ile açık yerel araç seçimi; alt modül descriptor'ını değiştirmeden NASM NuGet bağımlılığını devreden çıkarır. Varsayılan davranış korunur. |
| `5933c833998c57886da3c1ed162459198f77f8df` | `Silicon/Silicium/SiliciumPkg/Library/RealTimeClockLibNull/RealTimeClockLibNull.inf` | Başlığın sahibi olan `MdeModulePkg` paketini ekler. Taban derleme hatası bu eksiklikle yeniden üretildi. |
| `b2e08962c0dee12cadac4edf707a7887d88da961` | cihaz FDF ve ACPI.inc | Yalnız AML üreten DSDT için ayrı paketleme kuralı. Ortak ACPITABLE kuralı ayrıca `.acpi` bekliyordu. |
| `5814518fd1b3505d7a86be8b4011caae68d834e6` | `AcpiTables/Gtdt.aslc`, `Gtdt.inf`, cihaz DSC/FDF/ACPI | Araştırma GTDT'sinin PPI numarası ve kutuplamasını davinci DTS'den üretir. |
| `dc6dd9cae19bad5e0eb2f6bc584298c2da991b40` | `Resources/Scripts/davinci_audit.py`, Python testleri, kaynak/araç kilitleri | MMIO, CPU/timer, EFI mimarisi, değişmez UFS ve gerçek FD içeriği kontrolleri. |
| `865278e8` | `Resources/Scripts/davinci_audit.py` | Derlenen APRIORI GUID sırasını ve UFSDxe'nin gerçek DEPEX bölümünü ayrıca doğrular. |

`Drivers`, `AcpiTables`, `DeviceBuild.py`, `SystemTools` ve research library yolları aksi belirtilmedikçe `Platforms/Xiaomi/davinciPkg/` altındadır. Moorea DSC değişikliği yalnız davinci'nin açıkça seçilen CPU-only profiline yöneliktir; başka cihaz derlemeleri bu oturumda test edilmedi.

## UFS/IOMMU: yapılanlar ve açık engeller

`Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.efi` SHA-256 değeri kaynakta ve FD içinde aynıdır:

`0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1`

RVA `0x24F8`'deki `mov w0,#0; ret` korunuyor. Bu, gerçek IOMMU domain oluşturma/yapılandırma/bağlama değildir. Sürücünün kaynak kodu veya doğrulanmış DMA/SMMU yapılandırması elde edilmedi. Dolayısıyla IOMMU için çalışan bir çözüm geliştirildiği iddia edilemez.

İkilinin Shared IMEM başlığı ve boot-device sorgusu UFS'yi tanımazsa disk taramasına girmeden başarı dönebildiği önceki disassembly ile belirlenmişti. Yeni sürücü, yalnız bilinen ve yeterli uzunluktaki eşleme varsa IMEM magic/version/raw boot-type alanlarını okur. Boot tipini zorlamaz; IOMMU yöntemlerini çağırmaz; DMA veya depolama içeriğine yazmaz. C testi geçersiz başlık, bilinmeyen aygıt, kısa eşleme ve adres taşmasını kapsar. Bu sınırlı host testi MMIO'nun fiziksel güvenilirliğini kanıtlamaz.

DEBUG preflight, APRIORI'de mevcut UFSDxe'den hemen önce eklenmiştir. SMEM, Clock ve IOMMU protokolünün mevcut olup olmadığını raporlar. EndOfDxe/ReadyToBoot olaylarında Block I/O handle ve media metadata'sını raporlar. Sektör okuma, yazma, reset veya ConnectController çağrısı yoktur. UFSDxe takılırsa sonraki olaylar gerçekleşmeyebilir; preflight mesajı tek başına UFSDxe giriş noktasının kesin konumunu göstermez.

Ham UFS DEPEX yalnız SMEM protokolünü içerir. APRIORI, DEPEX değerlendirmesini atlar. Mevcut sıra SMEM/HALIOMMU/Clock/SCM'yi UFS'den önce, TZ/PMIC/SPMI/TLMM'nin bazılarını sonra çalıştırır. Sağlayıcının listede önce olması protokolün başarıyla kurulduğunu kanıtlamaz. Donanım bağımlılıkları bilinmediğinden bu sıra körlemesine değiştirilmedi; yeni bir ready-protocol veya zorlanmış UFS probe eklenmedi.

## Bellek haritası ve ekran

65 statik bölge incelendi. UFS eşlemesi `[0x01D80000, 0x01DA0000)`; DTS'deki HCI `0x01D84000/0x3000`, PHY `0x01D87000/0xDDC`, ICE `0x01D90000/0x8000` alanlarını kapsıyor. UFS MMIO eksikliği doğrulanmadığı için adresler değiştirilmedi. CPU MMU kapsamı ile DMA/SMMU kapsamı ayrı konulardır.

Dört mevcut iç içe eşleme açıkça kaydedildi: IMEM/IMEM Cookie, GPU_CC/GPU_CPR, MDSS/DISP_CC, QTIMER/APSS_WDT. Denetim yalnız bu mevcut kapsanan alias çiftlerini kabul eder; yeni veya kısmi çakışmaları reddeder. Bu kabul donanım doğrulaması değildir.

Ana taban zaten 1080x2340 kullanıyor. 1080x2350 uyumsuzluğu karşılaştırma EDK2 deposundadır; bu dala aktarılmadı. Framebuffer rezervasyonu `0x9C000000`, 24 MiB; 1080x2340x4 için yeterli. Aktif DisplayDxe'nin fiziksel panel/GOP davranışı doğrulanmadı ve sürücü seçimi değiştirilmedi.

## ACPI

Varsayılan profil korunur: DSDT eksikliği ve doğrulanmamış ortak çevre birimi tabloları hâlâ Windows için engeldir. Yeni profil `BLD_DEBUG_DAVINCI_CPU_ONLY_ACPI=1` ile açıkça seçilir; varsayılan değildir.

Bu profilde:

- DSDT sıfırdan yazıldı; OEM `DVNCI`, sekiz `ACPI0007` CPU aygıtı ve UID 0..7 içerir. UFS/USB/PEP cihaz kimlikleri uydurulmadı.
- `davinci.dts` MPIDR 0x000..0x700 ile ortak MADT UID/MPIDR değerleri eşleşir. GIC distributor 0x17A00000 ve GICR 0x17A60000..0x17B40000 değerleri DTS kaynak aralığıyla tutarlıdır.
- DTS architected timer PPIs 1,2,3,0, GIC PPI tabanı 16 ile INTID 17,18,19,16 olur. DTS `0xf08` değerinin alt bayrağı level-low'dur; araştırma GTDT'sinde polarity BIT1 kullanılır. Ortak GTDT'nin flags=0 değeriyle uyuşmazlık bu profilde giderildi.
- GTDT yalnız architected timer'ları tanımlar; doğrulanmamış always-on iddiası ve memory-mapped timer frame'leri eklenmedi.
- Ortak IORT, CSRT ve MCFG bu CPU-only profiline dahil edilmez. Bu, çalışan bir IOMMU veya PCI platformu oluşturmaz.
- Genel SoC DSDT fixup kitaplığı yerine CPU-only namespace için açık no-op kitaplık kullanılır. Başka cihazın adlarını yamalamaya çalışmaz.

DSDT IASL ile 0 hata/uyarı/remark ile derlendi. FD'de DSDT 329, GTDT 96 bayt ve checksum toplamları sıfırdır. Ortak FACP RAW tablosunun checksum toplamı 200 olarak korunuyor; UEFI InstallAcpiTable bunu yeniden hesaplayabilir. Çalışma anındaki kurulum burada test edilmedi; tüm tabloların runtime doğruluğu iddia edilmiyor.

**CPU-only ACPI, Windows on ARM platform sözleşmesi değildir. Özellikle Windows UFS/USB/PEP sürücülerini bağlayacak çevre birimi namespace'i eksiktir.**

## Derleme ve test kanıtları

İzole ortamda Docker araç imajı hazırlandı, ancak VFS katman kopyaları 8 GB disk sınırını aştı. Bu yol bırakıldı; derleme araçları kullanıcıya ait çalışma dizinine Debian paketlerinden açıldı. Sistem paketleri veya telefon değiştirilmedi. Kaynak commit'leri korunarak gereksiz Git geçmişi küçültüldü.

| Deneme / test | Sonuç |
|---|---|
| İlk taban wrapper denemesi | BootShim başarılı, `pkg_resources` eksikliği |
| Uyumlu setuptools ile bootstrap | Disk kapasitesi / sonra NASM NuGet HTTP 403 engeli |
| Hazırlanmış aynı ortamda orijinal taban kaynak derlemesi | `RealTimeClockLib.h` bulunamıyor; kaynak eksikliği yeniden üretildi |
| Düzeltmeler sonrası CPU-only DEBUG tam FD | Başarılı; Mu imaj doğrulaması geçti |
| Varsayılan DEBUG tam FD, CPU-only profil kapalı | Başarılı; içerik ayrıca incelendi |
| IASL DSDT | 0 hata, 0 uyarı, 0 remark |
| Python unittest | 10 test başarılı |
| C host sınır kontrolleri | Başarılı; `-Wall -Wextra -Werror` |
| Gerçek FD incelemesi | ARM64 tanılama sürücüsü, değişmemiş UFSDxe, araştırma DSDT/GTDT, APRIORI sırası ve SMEM DEPEX doğrulandı |
| Git whitespace kontrolü | Başarılı |

Taban tekrar denemesinde yalnız build-environment NASM descriptor override'ı kullanıldı; platformun derlenen kaynakları taban commit'e geri alınmıştı. Denemeden sonra dalın tüm kaynakları geri yüklendi ve araştırma derlemesi tekrar çalıştırıldı. NASM'ın engellenen Azure adresine erişim kuralı aşılmadı; açık sistem aracı seçeneği kullanıldı.

Günlükler ve JSON sonuçları inceleme paketindedir. `baseline-source-compile.log`, `final-research-build.log`, `default-debug-build.log`, `final-unit-tests.log`, `final-c-tests.log`, `acpi-source-compile.log`, `final-firmware-audit.json` ve `default-firmware-audit.json` temel kanıtlardır. İmaj doğrulama sayıları ve FD hash'leri gerçek günlük/JSON'dan okunmalıdır; kaynak değişikliği, timestamp veya profil değişince hash değişebilir.

## Çözülen / kısmen çözülen / açık kalan

Çözülen: Python araç uyumsuzluğu için sürüm sabitleme; RTC başlık paketi bağımlılığı; 730/732G kimlik karışıklığı; isteğe bağlı DSDT paketlemesi ve DTS kaynaklı araştırma timer tanımı; çevrimdışı denetim altyapısı.

Kısmi: UFS başlatma gözlemlenebilirliği; CPU/timer ACPI altyapısı; görüntü yapılandırmasının statik tutarlılığı. Yeni tanılama kodu dahil bu bileşenler fiziksel olarak doğrulanmadı.

Açık: UFSDxe kaynakları/ABI, gerçek IOMMU domain ve DMA, çalışma anındaki boot-device algılama, PHY/clock/reset/güç, LUN ve Block I/O/GPT erişimi, Windows boot-start sürücü zinciri, doğru UFS/USB/PEP ACPI namespace'i, touch/USB/şarj/güç yönetimi. Mevcut ext4 `win` bölümü standart Windows sistem hacmi değildir; burada değiştirilmedi.

## Fiziksel hazırlık ve sonraki adımlar

**Fiziksel test için hazır değil.** Ne varsayılan ne araştırma FD'si çalıştığı doğrulanmış kurulum imajı olarak sunuluyor. ADB/Fastboot, telefon bağlantısı, GPT işlemi veya firmware yükleme yapılmadı.

Öncelikli geliştirme: UFSDxe'nin kaynak veya sembollerini edinmek; IOMMU protokol ABI'sini ve DMA gereksinimlerini belgelemek; protokol sağlayıcı/DEPEX grafiğini tamamlamak; Windows driver INF kimlikleriyle davinci kaynaklarını karşılaştırmak. Fiziksel kabul ölçütleri ayrı: preflight ve UFSDxe giriş/çıkış kaydı; LUN/Block I/O; sektör okuma; bölüm handle'ları; ESP dosya okuma; sonra Windows Boot Manager/kernel devralması. Bunlar gelecekte sağlanması gereken kanıtlardır, kullanıcıya şimdi uygulanacak adımlar değildir.

## Bilgisayarda tekrar üretim

Alt modülleri kilit gitlink'lerinde kullanın; `--remote` ile güncellemeyin. Python ortamında bu klasördeki lock dosyasını kullanın. Clang/LLD, IASL ve sistem NASM PATH üzerinde olmalıdır. Host araçları firmware başarısı değildir.

```sh
export DAVINCI_SYSTEM_NASM=1
python Platforms/Xiaomi/davinciPkg/DeviceBuild.py --update -t DEBUG
python Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG \
  FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300 \
  BLD_DEBUG_DAVINCI_CPU_ONLY_ACPI=1
python -m unittest discover -s Resources/Tests -p 'test_davinci*.py' -v
cc -std=c11 -Wall -Wextra -Werror Resources/Tests/davinci_storage_audit_test.c -o /tmp/davinci-audit-test
/tmp/davinci-audit-test
python Resources/Scripts/davinci_audit.py \
  --fd Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd --cpu-only
```

Bu komutlar yalnız bilgisayar derlemesi/incelemesi içindir. Herhangi bir cihaz bağlantısı veya firmware çalıştırma komutu içermez. İlk klonda alt modüllerin ayrıca hazırlanması gerekir. Ortama özgü araç yolları ve erişim sorunları günlüklerde kayıtlıdır.
