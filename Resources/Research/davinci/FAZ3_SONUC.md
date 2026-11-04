# Davinci Windows 11 ARM64: son görev sonucu

4 Kasım 2026. Başlangıç `6ac46d335fb867dec9842a0ffff1ec857211a016`.
Önceki 18 commit korunmuştur. Bu aşama aynı araştırma dalında sürdürülmüştür.

**Nihai hedef gerçekleşmedi: telefonda Windows 11 masaüstü, kernel veya Windows Boot Manager başlatılmadı. Telefona erişilmedi. UFS başlatma / Block I/O / GPT-ESP erişimi de fiziksel olarak doğrulanmadı.**

Bu aşamada gerçek davinci ikililerinden eksik DAL/IORT bağlantısı çıkarıldı; gerçek HAL ikilisinin ABI ve hata davranışı RAM emülasyonunda ayrıştırıldı; mevcut Windows dosyalarından bilgisayarda EFI ve yeni offline BCD hazırlayan kod geliştirildi. Tahmini DMA/register yazması, binary patch veya telefon kurulum komutu üretilmedi. Bu sınır nedeniyle **çalışan bir UFS/IOMMU firmware düzeltmesi teslim edildiği söylenemez**.

## 1. Kod ve kesin commit'ler

| Commit | Uygulama |
|---|---|
| [45a7f2773dc8559968d62854c96d1e1a26700f25](https://github.com/oguzbakiriletisim/mu-silicium-davinci-sm7150/commit/45a7f2773dc8559968d62854c96d1e1a26700f25) | `Resources/Scripts/davinci_dal_iort.py`, `Resources/Tests/test_davinci_dal_iort.py`: PE section/VA sınırları, DAL property-bin/string-device/struct-pointer zinciri, IORT kaynakları ve sınırlı DAL registration emülasyonu. |
| [ae354ef31474f276c2cdbd24d858436dfa7f2bbb](https://github.com/oguzbakiriletisim/mu-silicium-davinci-sm7150/commit/ae354ef31474f276c2cdbd24d858436dfa7f2bbb) | `Resources/Scripts/davinci_hal_offline.py`, `Resources/Tests/test_davinci_hal_offline.py`: gerçek HAL protokol tablosu ve dummy-client akışı; domain servislerinin tamamı sahte. |
| [11aa9ded8426551e6ebd9ac18fdd30f94bac9398](https://github.com/oguzbakiriletisim/mu-silicium-davinci-sm7150/commit/11aa9ded8426551e6ebd9ac18fdd30f94bac9398) | `Resources/Windows/davinci/prepare_windows.py`, `Collect-DiskInventory.ps1`, `New-LabDisk.ps1`, `Resources/Tests/test_davinci_windows_prepare.py`: dosya/kimlik doğrulama, küçük EFI staging, bilgisayarda offline BCD üretimi ve isteğe bağlı boş sanal disk hazırlığı. |

Ek kod commit'leri:

- [181947df57d62a97b98df31f1233c141410bb297](https://github.com/oguzbakiriletisim/mu-silicium-davinci-sm7150/commit/181947df57d62a97b98df31f1233c141410bb297): gerçek HAL context-bank seçme rutinini fixture register servisleriyle emüle eder; üretim firmware'ine register yazma kodu eklemez.
- [7bc1b63fc1ae22f5d5d68326a1744c52dbde3dad](https://github.com/oguzbakiriletisim/mu-silicium-davinci-sm7150/commit/7bc1b63fc1ae22f5d5d68326a1744c52dbde3dad): PowerShell syntax/mock testleri ve Windows dışı lab provisioning koruması.

Test aracı PowerShell 7.4.6 linux-x64 resmi release SHA-256 değeriyle doğrulandı; araç teslimata/Git'e eklenmedi.

Bu kodlar gerçek kaynaktır; telefonda çalıştıkları iddia edilmez. Son belge commit'i rapor, [Windows kullanım kılavuzu](../../Windows/davinci/README_TR.md) ve `phase3-evidence/` kanıtlarını ekler. Ana dal veya orijinal depo değiştirilmez; PR açılmaz.

## 2. P0: davinci DAL/IORT eşlemesi artık hangi kanıta dayanıyor?

İncelenen dosya başlangıç commit'indeki:

`Binaries/davinci/QcomPkg/Drivers/DALSYSDxe/DALSYSDxe.efi`

SHA-256: `0542d91c859baf816f42438cc3472fed84897e7c5dec7cdfc05221e5ede40544`.

Yeni kod yalnız dosyada `IORT` aramakla yetinmez. Aynı PE içinde şu bağlantıyı çözer:

| Konum / değer | Anlamı |
|---|---|
| File/RVA `0x7970` | DALProps kaydı; property bin `0x19A60`, struct table `0x195C0`, 12 string device, device table `0x19EE8`. |
| `0x19FD8` | `SMMU` string-device girdisi; hash `0x7C8BE4C7`, property offset `0x2A8`. |
| `0x19D08` | Compact property DWORD `0x12800136`, ardından struct index 16 ve `0xFF00FF00` terminator. Name pool `0x19AA0` + `0x136` → `IORT`. |
| `0x196C0` | Struct descriptor: 8 ve pointer `0x27688`. |
| `0x27688` | Gömülü IORT tablosu, revision 0, 1657 bayt. |
| `0x1B1E8` / `0x1B1F0` | `7150_xml` hedef kaydı ve DALProps pointer'ı; phase 0. |

Pinlenmiş DAL rutinleri `0x3814`, `0x38BC`, `0x3888` RAM içinde çalıştırıldı; yalnız allocator sahteleştirildi. Phase-zero getter `0x7970` döndürdü. Bu, linked data ve bu kod yolunun **emülasyondaki** seçimini doğrular; gerçek UEFI entry/servislerinin cihazda tamamlandığını doğrulamaz.

Çıkarılan UFS kaydı:

- IORT named component `\\_SB_.UFS0`, node offset `0x443`.
- ARID/input base 0 → SID/output base `0x300`.
- Raw NumberIDs alanı 16. Diğer ARID 0x10/0x20 girdilerinde raw NumberIDs 0; kullanılabilir eşleme gibi kabul edilmedi.
- SMMU node offset `0x30`, base `0x15000000`, span `0x100000`, raw model=3, context interrupt count=80.
- Context-bank numarası tabloda sabit olarak atanmış değil. Eşdeğer HAL algoritması IDR/CBAR durumuna göre serbest bank seçiyor; bu cihazın gerçek register durumu okunmadı.

Bağımsız tutarlılık kontrolü: aynı tabloda USB3-0 SID tabanı `0x540`; `Resources/DTBs/davinci.dts:17275` USB düğümündeki `iommus` değeriyle eşleşiyor. SMMU base/span de DTS `apps-smmu@0x15000000` ile eşleşiyor. UFS düğümünde açık SID bulunmadığından UFS SID'si ikinci bağımsız donanım kaynağıyla doğrulanmış sayılmaz. Bu dosyaların kullanıcının aynı firmware sürümünden çıkarıldığı ayrıca kanıtlanmadı.

**Tablonun sorunları gizlenmedi:** checksum toplamı 27; header 9 node ilan ediyor, bu node'lar sonunda 101 bayt tail var. Tail içinde QGP1 benzeri bir kayıt görünmesi, node sayısını tahmin ederek yamalama gerekçesi değildir. Raw NumberIDs'ın eski HAL tarafından yorumlanması ile OS ACPI IORT standardındaki count-minus-one anlamı da aynı kabul edilemez. Bu nedenle tablo doğrudan Windows ACPI'si olarak paketlenmedi. SMMU CPU memory map'in mevcut 0xD0000 penceresi de bütün 1 MiB span için doğrulanmış erişim anlamına gelmez; gerçek register erişimleri bilinmeden değiştirilmedi.

Şema karşılaştırması için kullanılan SDM670 `DALSysCmn.h`, `DALPropDef.h`, `reverse_propgen.py` kaynakları commit `20bb8ae36c93fc16bbadda0e0a83f930c0c8a271` altında sabittir; yollar/SHA'lar `phase3-reference-lock.json` içindedir. Eski reverse_propgen'in her property kodlaması bu ikiliye aynen uygulanmadı; compact 2-DWORD SMMU kaydı gerçek dosya üzerinden doğrulandı. Yabancı SoC eşlemesi kopyalanmadı.

## 3. P0: gerçek HAL ikilisi SDM670 örneğinden farklı

Dosya: `Binaries/davinci/QcomPkg/Drivers/HALIOMMUDxe/HALIOMMUDxe.efi`.
SHA-256: `72bdfde0fb278a2a5bbaa6eb8a6f72a36d3b3b3e61864f6e6aad6f59c6da52e5`.

Yeni RAM emülasyonu ve disassembly:

- Protokol revision=1, init RVA `0x13BC`; init gerçek fonksiyon tablosu RVA `0x90A8` pointer'ını döndürüyor.
- Slot +0: create `0x1904`; +0x10: attach `0x1B70`; +0x20: genel configure `0x2ED8`; +0x40: configure_bypass `0x3160`.
- Dummy client RVA `0x1490` iki domain oluşturuyor ve SDC1/SDC2/SDC4/USB3-0 için attach çağırıyor. **UFS attach çağrısı yok.** Dolayısıyla bu dummy client'ın UFS stub'ının eksik başlatmasını telafi ettiği varsayılamaz.
- Create/configure hataları EFI hata dönüşüne giderken, attach hataları `0x15C4..0x16BC` yolunda yalnız debug mesajıyla kaydediliyor; akış sonunda başarı dönebiliyor. HAL başarı/protokol varlığı bu cihazda storage-ready kanıtı değildir.

Ek commit `181947df` altında gerçek `0x2278` bank seçme rutini de test edildi: IDR/CBAR/CBA2R callback'leri fixture değerler döndürür; register-write callback'leri yalnız argüman kaydeder. POR bank0 fixture'ında bank0, ilk iki bank kullanımda olduğunda bank2 seçilir; bütün bank'ler kullanımdayken sentinel korunur ve write callback'i çağrılmaz. TYPE=1 / VMID=0xFF durumu da kapsanır. Bu, aynı davinci ikilisinde bank seçiminin donanım state'ine bağlı olduğunu doğrular; **cihazda bank0/1/2 atanmasını önermez**.

Tüm create/configure/attach ve debug servisleri sahteydi; gerçek domain veya MMIO işlemi yürütülmedi. Başarılı ve hata senaryoları unit testleriyle ayrıldı. Faz 2'deki SDM670 örnek davranışı bu gerçek ikiliye genellenmedi.

UFSDxe hash'i değişmedi:
`0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1`.

Orijinal UFS rutininin configure_bypass + UFS0 attach zinciri ve stub davranışı önceki testlerle regresyon olarak korundu. Stub kaldırılmadı; HAL'a yeni DMA çağrısı eklenmedi. **P0'ın veri bulma kısmı ilerledi; gerçek donanım başlatma düzeltmesi tamamlanmadı.**

## 4. P1/P2: firmware ve Windows sürücü sınırı

Bu aşamada UEFI'nin çalıştırdığı firmware kaynakları değiştirilmedi; değişiklikler bilgisayar araçları/testleridir. DXE sırası, PHY/clock/reset, ACPI ve UFS ikilileri tahmine dayanarak değiştirilmedi. Bu nedenle iki regresyon FD'sinin hash'i Faz 2 ile aynıdır:

- Default: `f6d31f3392f50df33fe8ef10907bd2168bddee52a942f268dd57b499ffb636ae`.
- CPU-only: `c7596d0583fa4c3a9d434ed4efd42497455e73a04ff2841b2ace5852a295971d`.

Önceki kaynak pinleri (27 alt modül), MMIO kontrolleri, gerçek FV/APRIORI/DEPEX denetimi ve ACPI denetimleri geçti. CPU-only ACPI hâlâ tam Windows platformu değildir. Default profilde eksik DSDT ve RAW checksum sorunları devam eder.

Uyumlu Windows sürücü paketi elde edilmedi. Açık kalan zincir:

| Alt sistem | Eksik olan |
|---|---|
| UFS boot-start | SM7150-AA için uygun ve kaynağı doğrulanmış sürücü/INF/CAT, doğru ACPI kaynak/power/DMA sözleşmesi ve kernel devralma testi. |
| IOMMU | Firmware'in gerçek SMMU state'i, context-bank/SID ataması ve OS devralması. Firmware DAL tablosu bulmak Windows IORT/sürücü desteği değildir. |
| ACPI / güç | UFS/USB/PEP namespace, clock/regulator/idle/thermal sözleşmeleri. |
| Ekran | Mevcut GOP/framebuffer fiziksel doğrulaması ve Windows görüntü devralması. |
| USB | PHY/role/controller/power ve Windows sürücü eşleşmesi. |
| Dokunmatik | Gerçek Goodix varyantı ve bus/GPIO/touch Windows ARM64 paketi. |
| Şarj / pil / termal | Doğru PMIC/PEP/ACPI cihazları ve Windows sürücüleri. |

Faz 2'de incelenen SM7180/8180 sürücüleri uyumlu kabul edilmedi veya entegre edilmedi. Eksik sürücüleri gizlemek için test-signing/integrity bypass eklenmedi.

## 5. P2/P3: kullanılabilir bilgisayar betikleri

Tam komutlar ve dosya ağacı [Windows kılavuzunda](../../Windows/davinci/README_TR.md).

`prepare_windows.py`:

- `inspect`: mevcut staging dosyalarında ARM64 PE32+ ve registry base-block kontrolleri. Kaynak salt okunur.
- `stage-efi`: yalnız yeni bir PC kullanıcı klasörüne boot manager/EFI yardımcıları/font/resource kopyası; BCD veya boot başarı iddiası yok.
- `plan`: gerçek envanter + disk/ESP/Windows GUID seçimiyle JSON ve bcdedit argüman dizileri üretir; dosya bile yazmaz.
- `prepare-efi`: Windows'ta envanteri tekrar okur; GPT/FAT32/NTFS/extent/harf/host-disk korumalarını kontrol eder; yalnız yeni PC klasöründe **offline BCD** oluşturur. `device` ve `osdevice` hedef harflerden kurulurken gerçek GUID ilişkisini Windows bcdedit kodlar. Host sistem BCD'sine veya hedef bölümlere yazmaz.
- Kullanıcının loader GUID'i `{8af49d28-d85c-11f1-8157-f0038c0eb282}` varsayılandır. Disk/partition GUID'i sabitlenmez. Mevcut ext4 ve eksik ESP reddedilir, format edilmez.
- Var olan BCD/kaynak klasör üzerine yazmaz; başarısız bcdedit işleminin çıktısını saklar.

`Collect-DiskInventory.ps1`: Windows Storage üzerinden salt okunur envanter. `New-LabDisk.ps1`: varsayılan plan-only; açık `-Create` ile yalnız **yeni bir PC VHDX dosyası** üzerinde ESP/MSR/NTFS hazırlamak için yazıldı; mevcut fiziksel disk fallback'i yok. Hyper-V gerektirir. Windows/Hyper-V runtime test edilmedi; telefon için test edilmiş bir kurulum yöntemi değildir.

Kullanıcının 25,4 GB staging klasörü, gerçek BCD'si ve Windows disk düzeni bu çalışma ortamında bulunmuyor. Bunlar üzerinde betik çalıştırılmadı; 25 GB indirme/kopyalama yapılmadı. Tam Windows kurulumunun ACL/hardlink/reparse metadata'sı ve sürüm/provenance doğrulanmış sayılmaz. Yalnız dosya kopyasının yeterli olduğu varsayılmadı. Telefonu NTFS'e biçimlendiren veya Windows dosyalarını telefona dağıtan betik yoktur.

## 6. Test ve derleme kanıtı

`phase3-evidence/` içinde tam son build günlükleri, makine sonuçları ve başarısız ilk HAL testinin günlüğü bulunur.

| Test | Sonuç |
|---|---|
| Mevcut + yeni Python/C host/emülasyon testleri | **59 geçti, 0 hata, 0 skip**. |
| Yeni DAL parser/registration testleri | 9 test; gerçek pinlenmiş binary, bozuk pointer/string/node/interrupt bounds senaryoları. |
| Yeni HAL testleri | 7 test; gerçek ABI tablosu, UFS içermeyen dummy akış, hata davranışı. |
| Yeni Windows hazırlık testleri | 13 test; ARM64/x64 ayrımı, hive, ext4/yanlış GUID/host disk/overlap koruması, gerçek küçük dosya kopyası, offline BCD orchestration ve başarısız işlem günlüğü. |
| Default DEBUG regresyon build | Başarılı. |
| Deneysel ACPI DEBUG regresyon build | Başarılı. |
| Gerçek FD / ARM64 PE / APRIORI / UFS hash / ACPI | Önceki denetimler geçti; FD'ler Faz 2 ile aynı. |
| PowerShell syntax / mock inventory / Linux guard | PowerShell 7.4.6 gerçek parser/runtime ile 3 test geçti; Windows storage komutları mock. |
| Native Windows bcdedit / Storage / Hyper-V | **Çalıştırılmadı.** Windows orchestration testlerinde bunlar mock'tur. |
| Kullanıcının gerçek Windows dosyaları | Erişilebilir değildi; test edilmedi. |
| Fiziksel telefon | Erişilmedi; test edilmedi. |

İlk yeni HAL hata testi attach hatasının durmasını bekliyordu. Debug fonksiyonu modelde eksik olduğu için instruction-budget hatası oluştu. Gerçek disassembly attach hatasının debug ile kaydedilip akışın devam ettiğini gösterdi. Mock ve test beklentisi bu davranışı doğrulayacak şekilde düzeltildi. Bu, telefonda gözlenen bir hang değildir; ilk başarısız test günlüğü saklandı.

Günlüklerin Git kopyalarında yalnız sondaki boşluk/fazla EOF boş satırları temizlendi; ham günlük SHA'ları ve teslim kopyası SHA'ları RESULTS.json içinde ayrıdır. Firmware/VHDX/CAB/SYS/ZIP teslim edilmedi.

## 7. İşlem güvenliği ve bir sonraki test

| Sınıf | İşlem | Bu aşamadaki durum |
|---|---|---|
| A | Binary/staging inceleme, JSON plan, unit test | Bilgisayarda uygulandı veya betiği hazır. |
| B | Yeni PC klasörüne küçük EFI ve offline BCD | Python dosya/kontrol akışı test edildi; native Windows çalıştırması bekliyor. Kaynak/host BCD/hedef bölüm değişmez. |
| B-lab | Yeni boş VHDX oluşturma/format | İsteğe bağlı kod, native test edilmedi; telefona uygulanmaz. |
| C-read | Zaten çalışan TWRP'den kernel logu okuma | Bu oturumda yapılmadı; aşağıda yalnız sonraki kanıt toplama komutu var. |
| C-write | Telefon GPT/format/ESP dağıtımı/firmware yükleme | **Engelli; bu teslimatta komut yok.** Önce gerçek depolama ve yükleme yolu doğrulanmalı. |

Gerçek cihazda henüz güvenilir bir kalıcı-yazmasız UEFI çalıştırma yolu doğrulanmadı. `fastboot boot` desteği varsayılmadı; recovery/boot/TWRP üzerine yazacak komut verilmedi. Derlenen FD fiziksel test için hazır ilan edilmiyor.

**En yakın düşük etkili fiziksel kanıt adımı**, cihaz zaten mevcut TWRP'de çalışıyorsa mevcut kernel logundaki UFS/SMMU/context kayıtlarını bilgisayara almaktır. Aşağıdaki PowerShell komutları log okumak içindir; bu oturumda çalıştırılmadı:

```powershell
adb shell dmesg | Out-File -Encoding utf8 "$env:USERPROFILE\Mi9T-existing-kernel-log.txt"
Select-String -Path "$env:USERPROFILE\Mi9T-existing-kernel-log.txt" `
  -Pattern 'smmu|iommu|context.bank|ufshcd|ufs'
```

Yeni TWRP/UEFI yüklemeyi veya telefonu reboot etmeyi gerektiren adım tarif edilmiyor. Bu kernel logu Linux'un kullandığı koşullara aittir; **ABL/UEFI devralma anındaki context-bank durumunu kanıtlamaz**. Register dump, devmem veya yeni DMA işlemi önerilmedi.

Asıl UEFI açılış testinin komutlarını güvenilir biçimde verebilmek için davinci üzerinde doğrulanmış geçici yükleme yolu ve cihazın o boot zincirindeki SMMU/clock/reset devralma kanıtı gerekir. Mevcut yedekler bu eksikliği veya brick riskini ortadan kaldırmaz.

## 8. Hangi başarı aşamasına ulaşıldı?

| Fiziksel ara başarı | Kanıt |
|---|---|
| UFS sürücüsü başlatıldı | Yok. |
| Dahili disk Block I/O oldu | Yok. |
| GPT/ESP erişildi | Yok. |
| Windows Boot Manager açıldı | Yok. |
| Windows kernel yüklendi | Yok. |
| Kullanılabilir Windows 11 masaüstü | Yok. |

Bilgisayarda çalışan kod bileşenleri ve veri eşlemesi çıkarımı ara geliştirme çıktılarıdır; bu tabloya fiziksel başarı olarak yazılmadı.

**Tek sonraki somut hamle:** mevcut TWRP kernel logunu salt okunur biçimde edinip, yeni çıkarılan UFS SID/SMMU ilişkisi için ek donanım kanıtı aramak. Bu bile UEFI devralma durumunu doğrulamazsa DMA zinciri etkinleştirilmemelidir. Windows dosyalarını telefona yazmak veya ext4'ü biçimlendirmek, bu sıradaki eksikliği çözmez.

**Bugün bu çalışma sonucunda doğrulanmış bir Windows 11 masaüstü yolu üretilmedi.** En kritik kazanım, artık tahmini değil mevcut davinci ikilisine bağlı bir UFS DAL eşlemesi ve gerçek HAL davranışının bulunmasıdır. Tamamlanmamış kısım, bunu gerçek boot zincirinde güvenle çalıştırmak ve uygun Windows boot-start sürücüleriyle devralmaktır.
