# Xiaomi Mi 9T / davinci: UFS ve ACPI geliştirme, ikinci aşama

Tarih: 4 Kasım 2026. Cihaz: Snapdragon 730 / SM7150-AA; raphael veya sweet değildir.
Başlangıç: `6d5d7453389864fa6562069d77a2582480d349c6`; önceki 11 commit korundu.
Dal: `davinci-win11-uefi-research`, yalnız kullanıcının `oguzbakiriletisim/mu-silicium-davinci-sm7150` fork'u.

**Sonuç: kaynak kodu geliştirildi, her iki DEBUG profili derlendi ve 27 test geçti. Dahili UFS, DMA, Windows Boot Manager veya Windows 11 masaüstünün çalışması doğrulanmadı. Firmware fiziksel test/kurulum için hazır değildir.**

## Gerçek kod değişiklikleri

| Commit | Dosyalar ve çözmeyi hedeflediği sorun |
|---|---|
| `59e344c3f909c46e0bba5c583db5bd384d92fc85` | `Platforms/Xiaomi/davinciPkg/Drivers/StorageAuditDxe/StorageAuditDxe.c`, yeni `StorageAuditAfterUfsDxe.inf`, `Include/APRIORI.inc`, `Include/DXE.inc`, `davinci.dsc`: UFS'nin hemen arkasına ayrı bir DEBUG gözlem imajı. Başarılı HandleProtocol sonrasında NULL BlockIo arayüzü de korunur. Gerçek DXE C kaynağına karşı sahte UEFI host testi eklendi. |
| `4bbc7875037f18e6f4107962a3bb036d9c1a3002` | `AcpiTables/Fadt.aslc`, `Fadt.inf`, cihaz DSC ve `Include/ACPI.inc`: yalnız CPU-only profilde kaynak FADT; desteklenmeyen S0 idle/reset/hypervisor iddiaları kaldırılır. Varsayılan profil korunur. |
| `b4cb861579edfa0ac016c94b4384cc8aa64ce9c2` | StorageAudit kaynak/INF ve host testleri: SCM protokolü ve `EnableUfsIOC` sorgusu. Protokol varlığının sağlayıcının başarıyla başlatıldığı anlamına gelmediği günlükte belirtilir. |
| `13fc0485710b087eea29cff3da80f78679a8fa4b` | `Resources/Scripts/davinci_audit.py`, `Resources/Tests/test_davinci_audit.py`, `test_davinci_acpi_bundle.py`: gerçek FV içindeki iki gözlem noktasının komşuluğu, boolean DEPEX çözümü, ACPI paket bütünlüğü, checksum, MADT/PPTT CPU kimlikleri, PPTT parent/resource referansları, FADT/PSCI ve GTDT tutarlılığı. |
| `b404f75cb1b754865d22586481e40ddaffdcfe36` | `Resources/Scripts/davinci_ufs_offline.py`, `Resources/Tests/test_davinci_ufs_offline.py`, `requirements-offline-ufs.txt`: hash ile sabitlenmiş eski ve yamalı UFS rutinlerini sınırlı ARM64 emülasyonunda, tamamen sahte servislerle karşılaştırır. |
| `3f9119ba5590ab7e41acc59a5df46655ac01f809` | `davinci_audit.py`: DBG2 checksum'u da gerçek FD incelemesinde raporlanır; önceki denetimde kapsanmıyordu. |

Tablodaki `AcpiTables`, `Include` ve cihaz dosyaları `Platforms/Xiaomi/davinciPkg/` altındadır. Her commit aşağıdaki biçimde incelenebilir:
`https://github.com/oguzbakiriletisim/mu-silicium-davinci-sm7150/commit/<tam-commit>`.

### DEBUG gözlem noktalarının anlamı

`StorageAuditDxe.inf` → mevcut `UFSDxe.inf` → `StorageAuditAfterUfsDxe.inf` sırası hem kaynakta hem derlenmiş APRIORI GUID listesinde denetlendi. Her iki sürücü AARCH64 PE'dir.

Yeni post-UFS imajı protokol varlığı ve Block I/O media metadata'sı kaydeder; IMEM okumaz, callback kaydetmez. Önceki pre-UFS sürücüsü mevcut IMEM okumasını ve EndOfDxe/ReadyToBoot kayıtlarını korur; SCM ve IOC yapılandırma sorgusu ekler. Sektör okuma/yazma, Reset, ConnectController veya IOMMU yöntemi çağrısı eklenmedi.

Post mesajı **yalnız dispatcher'ın sonraki APRIORI konumuna ulaştığını** gösterir. UFS imajı yüklenememiş, hata dönmüş veya boot-device koşuluyla taramayı atlamış olabilir. Pre mesajının bulunup post mesajının bulunmaması da tek başına UFS'nin belirli bir fonksiyonda takıldığını kanıtlamaz. Fiziksel çalışma veya günlük elde edilmedi.

## UFS/IOMMU için yeni kaynak kanıtı

### Eşdeğer Qualcomm kaynakları

Karşılaştırma deposu `Rivko/android-firmware-qti-sdm670`, kesin commit:
`20bb8ae36c93fc16bbadda0e0a83f930c0c8a271`.
Bunlar SDM670 kaynaklarıdır; davinci'nin hazır ikilisinin birebir kaynakları olarak kabul edilmez. Bu depodan firmware uygulaması kopyalanmadı.

Somut bağlantılar ve önemli konumlar:

- [HALIOMMU GUID](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/QcomPkg.dec#L216): `54b6d3b4-5d33-4f91-8600-6c41d5deb19a`. Bu, mevcut UFS LocateProtocol argümanı ve tanılama GUID'i ile eşleşiyor.
- [Protokol başlığı](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Include/Protocol/EFIHALIOMMUProtocol.h#L25): revision, init ve deinit. Init bir fonksiyon tablosu verir; EFI/EDKII Map-Unmap arayüzü değildir.
- [Fonksiyon tablosu](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Include/api/kernel/HALIOMMU/HALIOMMUTypes.h#L195): enum 0 NON_CCA, 1 CCA; create +0, attach +0x10, genel configure +0x20, **configure_bypass +0x40** (AARCH64 pointer boyuyla).
- [Domain attach](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMU.c#L541): named component, ID mapping, SMMU bilgisi, context-bank ve stream eşlemesi ister; eksik IORT bilgisi hata üretir. [Bypass yapılandırması](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMU.c#L868) TTBR/MAIR alanlarını sıfırlar ve NON_CCA/CCA ayarını seçer.
- [IORT veri kaynağı](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Library/IORTLib/IORT.c#L120): `DALSYS_GetDALPropertyHandleStr("SMMU")` ve `DALSYS_GetPropertyValue(...,"IORT",...)`. Bu, OS'ye yayımlanan ACPI tablosundan ayrı firmware DAL verisidir.
- [HAL sağlayıcı girişi](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.c#L49) önce protokolü kurar, sonra dummy client başlatır. Bu örnekte protokol bulunması bile sonraki donanım başlatmasının başarısını kanıtlamaz. Örneğin UFS ARID 0x10 kullanması davinci'ye taşınamaz.
- [Eşdeğer UFS girişi](https://github.com/Rivko/android-firmware-qti-sdm670/blob/20bb8ae36c93fc16bbadda0e0a83f930c0c8a271/boot_images/QcomPkg/Drivers/UFSDxe/UFS.c#L813): boot_from_ufs yanlışsa başarı döner; sonra SCM bildirimi, `ufs_open` ve LUN keşfi gelir. Bu eski sürümün INF/DEPEX'i de davinci ikilisiyle aynı kabul edilmez.

Sekiz referans kaynak dosyasının SHA-256 değerleri ve kesin yolları `phase2-reference-lock.json` içinde kayıtlıdır.

### Sabitlenmiş ikililer ve emülasyon

Orijinal ikili `4112f787...` öncesindeki `ffa8933a6ae7688fcbe3693b698833efdaa3536f` commit'inden `git show` ile RAM'e alınır. Diskte yeni ikili üretmez.

- Orijinal SHA-256: `7549f618b3e511a5cedca84c6e76870062961add72753b37d0221a87ba5802dc`.
- Mevcut kaynak ve iki FD içindeki UFSDxe SHA-256: `0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1`.
- RVA 0x24F8: mevcut `mov w0,#0; ret` korunur. Yeni binary patch yok.

`davinci_ufs_offline.py` PE bölüm yerleşimini kullanır ve 2000 komutluk sınır uygular. Tüm protokol/config/boot-query çağrıları sahtedir; fiziksel adreslere erişim veya gerçek DMA yoktur.

Orijinal rutinin gözlenen akışı: protokol gerekirse LocateProtocol → protocol init → create → `EnableUfsIOC` sorgusu → configure_bypass → `\\_SB_.UFS0`, ARID=0, mask=0 ile attach. Sorgu bulunmazsa enum 0, değeri 1 verilirse enum 1 geçer. Servis hataları sonraki aşamayı durdurup EFI hata sonucu verir. Mevcut stub hiçbir IOMMU servisini çağırmadan başarı döner. Boot-query tip 8 için doğru, tip 1 ve sorgu hatasında yanlış predicate döner; bu disk keşfi değildir.

**Daraltılan engel:** UFS'nin kaldırılmış işlemi genel configure (+0x20) veya standart EDKII Map değildir; Qualcomm bypass domain yapılandırması (+0x40) ve named-component attach zinciridir. Önceki çalışmadaki genel “configure” adlandırması bu aşamada netleştirildi. Davinci için DAL/IORT named-component → ARID → SID → SMMU/context-bank verisi doğrulanmadan bu zincir güvenle yeniden etkinleştirilemez. Sadece DSDT'ye UFS0 eklemek bu veriyi sağlamaz.

Mu Basecore `3609e51f683e4d9eed13df8dccbb05b0a64ebab2`, `MdeModulePkg/Include/Protocol/IoMmu.h` GUID'i `4e939de9-d948-4b0f-88ed-e6e1ce517c1e`'dir. Qualcomm protokolüyle farklıdır. Aynı commit'teki `Bus/Ufs/UfsPassThruDxe/UfsPassThru.c` (Supported/Start) ve `UfsPassThruHci.c` (DMA Map, UfsControllerInit) açık bir eşdeğer algoritma sunar; ancak UfsHostController platform protokolü ve gerçek Qualcomm PHY/clock/reset/DMA uyarlaması olmadan davinci sürücüsü değildir. Mevcut Arm SmmuDxe de SMMUv3 içindir; sadece eklenerek bu ABI/SMMU ihtiyacı karşılanamaz.

### DEPEX ve sıralama

`phase2-evidence/*-audit-final.json` hazır ikililerin DEPEX ifadelerini çözer. UFSDxe yalnız SMEM ister; SmemDxe TRUE'dur. HALIOMMU çok sayıda mimari protokolü AND ile ister; Clock ve SCM ayrıca kendi bağımlılıklarına sahiptir. Binary INF'nin metin `[Depex] TRUE` alanı gerçek DXE_DEPEX bölümünün yerine geçmez. Gerçek FD içindeki UFS DEPEX de kontrol edildi.

APRIORI normal DEPEX değerlendirmesini atlar; önceki SMEM/HALIOMMU/Clock/SCM sırası korunmuştur. Tanılamada eksik protokol görülürse bunun nedeni incelenebilir; protokol varlığı, sıralama ve başlatma başarısı aynı kanıt değildir. TZ/PMIC/SPMI/TLMM sırası doğrulanmamış donanım tahminiyle değiştirilmedi.

## ACPI ve Windows sürücü eşlemesi

### İsteğe bağlı FADT

`4bbc7875` ile yeni FADT yalnız `BLD_DEBUG_DAVINCI_CPU_ONLY_ACPI=1` profilindedir:

- ACPI 6.0, 276 bayt, OEM DVNCI, HW_REDUCED_ACPI.
- `Resources/DTBs/davinci.dts:21676` PSCI 1.0 ve SMC tanımına göre ArmBootArch=1; kaynak denetimi DTS'nin değişmesini yakalar.
- S0 low-power idle, reset GAS, hypervisor kimliği ve önceden atanmış DSDT/FACS pointer'ları ilan edilmez. Bunların sıfırlanması çalışan güç/reset desteği değildir.
- DSDT/FACS pointer'ları runtime AcpiTableDxe tarafından yerleştirilir. Mu Basecore `3609e51...`, `MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableProtocol.c:206` ve devamında tablo kopyalanıp checksum/bağlantılar güncellenir; burada o runtime işlem test edilmedi.

Yeni denetim eksik/tekrar tabloyu, yanlış checksum'u, MADT/PPTT UID farkını, devre dışı GICC'yi, parent döngüsünü, yanlış private resource referansını, beklenmeyen FADT güç/PSCI alanlarını ve GTDT kutuplama değişimini reddeder. PPTT revision 1 cache ve ID kaynaklarını kabul eder. Cache fiziksel özellikleri veya tüm IORT/CSRT semantiği doğrulanmış değildir. FACS'nin checksum/OEM içeren standart description header'ı yoktur; ayrı ele alınır.

### Android kaynakları ve INF kanıtı

DTS, başlangıç commit'i `6d5d7453` altında `Resources/DTBs/davinci.dts` olarak sabittir:

| Donanım | Android kaynak kanıtı | Windows tarafındaki durum |
|---|---|---|
| UFS | 4697: HCI 0x1d84000/0x3000; ICE 0x1d90000/0x8000; SPI indeks 0x109; PHY, sekiz clock, reset ve regülatör bağımlılıkları. UFS düğümünde açık `iommus` eşlemesi yok. | Davinci için doğrulanmış ARM64 boot-start UFS INF/sürücü ve ACPI kaynak sözleşmesi elde edilmedi. UFS SID'si USB'den türetilemez. |
| USB | 17275: wrapper 0xa600000/0x100000, IOMMU 0x540, S1 bypass; dwc3 alt düğümü 0xa600000/0xcd00, SPI 0x85, OTG. | Davinci için Windows PHY/role/host/device/power zinciri doğrulanmadı. UEFI USB dosyalarının bulunması Windows USB desteği değildir. |
| Dokunmatik | 9229: GENI I2C 0xa84000; goodix@5d, compatible goodix,gt9889; reset GPIO8, IRQ GPIO9. Config adlarında GT9886 de geçiyor. | Windows ARM64 bus/GPIO/touch sürücüleri ve doğru HID/ACPI sözleşmesi yok; isim benzerliğinden model veya uyumluluk çıkarılmadı. |
| Güç | PSCI/SMC, RPMh/PMIC kaynakları mevcut. | PEP, idle states, termal, pil/şarj ve regülatör sözleşmeleri eksik. S0 desteği varsayılmadı. |

Gerçek Windows INF'leri karşılaştırma amacıyla `WOA-Project/Qualcomm-Reference-Drivers` commit `ad6e472836d40d6ba81855e57bbd3c7c0522735f` içindeki CAB'lardan sadece okunarak çıkarıldı. CAB/SYS dosyaları firmware'e veya Git teslimatına eklenmedi. Bunlar SM7180/8180 referanslarıdır; **davinci için uygun sürücüler olarak sunulmuyor**.

| Paket / INF | Etkin ARM64 model veya servis kanıtı |
|---|---|
| `7180_CLS/200.0.11.0/qciommu7180.cab` / `qciommu7180.inf` | Satır 39–40: ACPI\\QCOM089B. Satır 81: StartType=3. Yorumdaki QCOM0200 etkin model değildir. |
| Aynı klasörde `qcpep.wd7180.cab` / `qcpep.wd7180.inf` | Satır 32–33: PEP ACPI\\QCOM0819; çok sayıda TSENS/ADC modeli ayrıca listelenir. Satır 248: StartType=0; qcpep7180.sys. |
| Aynı klasörde `QcXhciFilter7180.cab` / `QcXhciFilter7180.inf` | Satır 39–41: ACPI\\QCOM0826; StartType=3. Bir USB filtresidir; tüm USB platform sürücüsü değildir. |
| `1000_CLS/200.0.5.0/qcusbfn8180.cab` / `qcusbfn8180.inf` | ARM64 model bölümündeki tek ACPI satırı yorumdur; etkin model HID'i yoktur. StartType=0 tek başına PnP eşleşmesi veya UFS boot desteği sağlamaz. |

CAB bağlantısı örneği: [qciommu7180.cab](https://github.com/WOA-Project/Qualcomm-Reference-Drivers/blob/ad6e472836d40d6ba81855e57bbd3c7c0522735f/7180_CLS/200.0.11.0/qciommu7180.cab).
Tüm CAB ve orijinal INF SHA-256 değerleri, etkin model satırları ve yollar `phase2-reference-lock.json` içindedir. Örnek HIDs DSDT'ye eklenmedi. Kaynağı doğrulanmış, doğru modele ait INF/CAT/SYS ve kaynak/power/DMA sözleşmeleri hâlâ gereklidir.

## Derleme ve test sonuçları

Araçlar ve alt modül gitlink'leri önceki aşamayla aynı; 27 checkout kimliği tekrar doğrulandı. Opsiyonel emülasyon bağımlılıkları pefile 2024.8.26 ve Unicorn 2.1.4. Bunlar host araçlarıdır.

| Kontrol | Sonuç |
|---|---|
| Varsayılan DEBUG | Başarılı; `phase2-evidence/default-debug-final.log` |
| CPU-only ACPI DEBUG | Başarılı; `research-debug-final.log` |
| Python unittest + gerçek DXE C host harness + UFS emülasyonu | 27 test, 0 hata, 0 skip; `unit-tests-final.log` |
| Ayrı C IMEM sınır testi | Başarılı; `-Wall -Wextra -Werror` |
| DSDT IASL derlemesi | 0 hata, 0 uyarı, 0 remark |
| FD'den 15 ACPI tablo örneğinin IASL disassembly'si | Her biri exit code 0; bu checksum/donanım doğruluğu anlamına gelmez |
| APRIORI / gerçek UFS DEPEX / ARM64 PE | İki profilde doğrulandı |
| UFS hash ve mevcut stub | Kaynakta ve iki FD'de değişmedi |
| Bellek haritası | Önceki 65 bölge, UFS MMIO kapsamı ve kayıtlı alias kontrolleri geçti; DMA kapsamı değildir |

Deneysel FD: `c7596d0583fa4c3a9d434ed4efd42497455e73a04ff2841b2ace5852a295971d`.
Varsayılan FD: `f6d31f3392f50df33fe8ef10907bd2168bddee52a942f268dd57b499ffb636ae`.
Bunlar yalnız yerel analiz artefaktlarının SHA-256 değerleridir; imajlar Git'e eklenmedi.

Deneysel profilde DSDT/APIC/GTDT/FADT/PPTT checksum toplamları sıfır; FACS için checksum uygulanmaz. Varsayılan RAW tablolarında CSRT=161, DBG2=43, FADT=200 checksum toplamları ve DSDT yokluğu korunuyor. Runtime kurulum checksum'u yeniden hesaplayabilse de gerçek kurulum kanıtı yoktur; varsayılan profil Windows'a hazır sayılmaz.

İlk yeni ACPI denetimi, PPTT revision 1 private resource alanını yalnız cache'e sınırlayan hatalı varsayım yüzünden başarısız oldu. Revision 1'deki ID kaynağına izin verilip regresyon testi eklendi; donanım tablosu bu nedenle değiştirilmedi. Ayrıntı `phase2-evidence/DEVELOPMENT_NOTES.txt`. Bu aşamadaki firmware derlemelerinde başarısızlık yaşanmadı. Önceki baseline başarısızlıkları ilk `RAPOR.md` içinde duruyor.

## Açık engeller ve fiziksel hazırlık

**Çözülen:** host tanılama NULL arayüz koruması; UFS sonrasındaki dispatcher ilerlemesini ayrı kaydetme; deneysel FADT'nin kaynak/PSCI/checksum tutarlılığı; eksik ACPI/DEPEX denetimleri.

**Daraltılan:** kaldırılmış IOMMU rutininin ABI'si ve bypass/attach akışı; `EnableUfsIOC` default davranışı; named-component ve firmware DAL/IORT verisinin önemi; protokol varlığı ile sağlayıcı başarı durumunun ayrımı.

**Çözülmeyen:** davinci HAL/DAL eşleme verisi, SID/context-bank doğruluğu, PHY/clock/reset/güç davranışı, gerçek boot-device sonucu, UFS LUN/Block I/O/GPT/ESP erişimi, OS devralması ve Windows boot-start sürücüleri. Dokunmatik/USB/güç için uygun Windows sürücü ve ACPI eşleşmeleri yok. Boot Manager'ın dosyaya erişmesi ile Windows çekirdeğinin UFS'yi devralması ayrı aşamalardır.

CPU-only profil tam bir Windows platformu değildir. Fiziksel test, firmware kurulumu veya Windows masaüstü başarısı iddia edilmiyor. Telefon bağlantısı, ADB/Fastboot, firmware yükleme, GPT/bölüm işlemi veya kullanıcının Windows/GPT yedeklerinde değişiklik yapılmadı.

Sonraki somut kod hedefleri:

1. Davinci HALIOMMUDxe'nin kullandığı DAL/IORT veri kaynağını çevrimdışı çözümlemek; UFS0/ARID0 için doğrulanmış SID/SMMU eşleme kanıtı çıkarmak. Kaynak sürüm farkları giderilmeden başka SoC verisi kullanmamak.
2. DXE image load/start dönüş statülerini kayıt altına alacak kaynak düzeyinde ve davinci ile sınırlı bir tanılama seçeneğini değerlendirmek. Mevcut post marker'ı giriş/başarı kanıtı gibi yorumlamamak.
3. SM7150-AA için doğru Windows boot-start sürücü paketi ve INF kaynak sözleşmesini edinmek; ancak sonra UFS/USB/PEP namespace geliştirmek.
4. Firmware içi IORT verisi ile OS ACPI IORT'u ayrı doğrulamak; varsayılan RAW checksum ve DSDT eksikliğini platform desteği tamamlanırken ele almak.

Donanım gerektiren kabul kanıtları: UFS giriş/çıkış statüsü, LUN ve Block I/O, tutarlı bölüm/ESP erişimi, ardından Windows loader ve kernel devralması. Bunlar kullanıcıya şimdi uygulanacak işlemler değildir; bu oturumda çalıştırılmadı.

## Bilgisayarda yeniden doğrulama

İlk rapordaki araç ortamını ve `source-lock.json` gitlink'lerini kullanın. Emülasyon için `requirements-offline-ufs.txt` paketleri ve orijinal commit'in Git nesnesi gerekir; eksik paketler unittest içinde açıkça skip olarak görünür. Bu oturumun nihai koşusunda skip yoktu.

```sh
python -m unittest discover -s Resources/Tests -p 'test_davinci*.py' -v
python Resources/Scripts/davinci_ufs_offline.py
export DAVINCI_SYSTEM_NASM=1
python Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG \
  FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300
# Deneysel profil için aynı build komutuna ekleyin:
# BLD_DEBUG_DAVINCI_CPU_ONLY_ACPI=1
python Resources/Scripts/davinci_audit.py \
  --fd Build/davinciPkg/DEBUG_CLANGPDB/FV/DAVINCI_UEFI.fd
# Yalnız deneysel FD denetlenirken --cpu-only ekleyin.
```

Tam son derleme günlükleri, unit test çıktısı, emülasyon JSON'u, ACPI disassembly günlükleri ve checksum sonuçları küçük metin dosyaları olarak `phase2-evidence/` altındadır. Firmware veya harici sürücü ikilileri bu klasörde yoktur.

Git günlük kopyalarında yalnız satır sonu boşlukları ve dosya sonundaki fazla boş satırlar temizlendi; ham günlükler yerel çalışma alanında korundu. Ham ve teslim edilen kopyaların SHA-256 değerleri RESULTS.json içinde ayrı kaydedilir.
