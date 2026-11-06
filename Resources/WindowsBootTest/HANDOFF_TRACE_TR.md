# Target A — üçüncü fiziksel kaydın ayrıştırılması ve handoff gözlemcisi

**Telefon kaydı aynı `davinci-target-a-prepi-fix.img` imajına aittir.**
DXE/FV2 düzeltme imajı veya bu yeni sürüm telefonda test edilmiş sayılmaz.
Microsoft Recovery hâlâ telefonda doğrulanmadı.

Kaynak başlangıcı: `45aa8c7b3ad75b8a276b53c2dd58df1f68519cd2`.
Uygulama commit'i: `3bc34bb650227a440c97bf5cb69d4bc2c7524680`.
Mu_Basecore: `3609e51f683e4d9eed13df8dccbb05b0a64ebab2`.
Dal: `davinci-windows-boot-test`.

## 0x10000000–0x10340fff: PE tercih edilen yükleme adresi

Gerçek Microsoft dosyası SHA
`fae47d78487e781aa06466775cb461adeb7ff7f887fe2c15295bb2eb4f4954e1`:
ImageBase **0x10000000**, SizeOfImage **0x341000**. Inclusive bitiş adresi
`0x10000000 + 0x341000 - 1 = 0x10340fff`.

`MdeModulePkg/Core/Dxe/Image/Image.c:737–757`, varsayılan
`PcdImageLargeAddressLoad=TRUE` ile önce tercih edilen adrese AllocateAddress
ister; relocations mevcutsa başarısızlığın ardından AllocateAnyPages dener.
`MdeModulePkg/MdeModulePkg.dec:1401` varsayılanı, `Mem/Page.c`
CoreInternalAllocatePages/CoreConvertPagesEx gerçek tahsis yolunu tanımlar.

Dolayısıyla bu tam aralık, gerçek PE ile ve source loader'ın ilk adres
denemesiyle eşleşiyor. Telefon LoadImage RETURN Success gördüğüne göre bu
çağrının nihai yüklemesi başarılı; sadece bu erken adres denemesini fatal
image-load hatası diye sunmuyoruz. Tercih edilen PE adresi, gerçek yüklenen
ImageBase değildir. Düşük adresi RAM diye eklemedik; PCD'yi de log gizlemek
amacıyla değiştirmedik.

## 0x102000–0x102fff: gerçek Microsoft API çağrısı yeniden üretildi

Yeni gözlemciyle ARM64 QEMU'da **aynı Microsoft dosyası** çalıştırıldı:

```text
WBT API ALLOC CALL phase=2 type=2 kind=2 pages=1
req=0000000000102000 caller=000000007B27225C child=1
WBT API ALLOC RETURN ... status=800000000000000E ... child=1
```

Type 2 AllocateAddress, kind 2 EfiLoaderData, bir sayfa; status EFI_NOT_FOUND.
QEMU loaded base `0x7b234000`, caller RVA **0x3e25c**. Debugger entry breakpoint
ve gerçek **Microsoft Recovery / BCD 0xc000000f ekranı** aynı koşuda doğrulandı.
Yeni hook'lar API'nin argümanını/adresini/dönüşünü değiştirmedi.

Kapalı Microsoft ikilisinin çevrimdışı sınırlı incelemesinde RVA `0x3e258`
AllocatePages çağrısı, `0x3eb28` literalinde `0x102000`, sonrasındaki return
adresi `0x3e25c` ile eşleşir. Fonksiyon/isteğin Microsoft iç adı bilinmiyor;
isim uydurulmadı. Telefon çağıran PC henüz ölçülmedi; aynı zamanlama ve aralık
güçlü bir eşleşmedir, yeni `caller / child=1` satırı cihazdaki yolu doğrular.

**Önemli:** Aynı başarısız düşük adres denemesinden sonra QEMU'da Recovery
çıktı. Bu başarısızlık tek başına her ortamda fatal değildir. Telefonla
QEMU'nun firmware/ACPI/RAM farkları devam eder; bundan telefon başarısı çıkmaz.
Logdaki `actual` alanı çağrı sonrası `*Memory` değeridir. Hata halinde değişmeden
`0x102000` kalır; **adresin tahsis edildiği anlamına gelmez**.

Davinci memory-map kaynağında DDR `0x80000000`'dan başlar. `0x102000`,
`DeviceMemoryMapLib.c` içindeki GCC CLK CTL (`0x00100000`, length `0x000b0000`)
MMIO penceresine denk gelir; conventional RAM değildir. DXE iç tahsis haritası
ile GetMemoryMap'in GCD/MMIO dahil çıktısı aynı liste değildir. Bir MMIO/GCD
bölgesi görülebilse bile AllocatePages için serbest System RAM sayılmaz.
**Burayı RAM'e dönüştürmek veya hatayı koşulsuz başarı yapmak yapılmadı.**

## AcpiPlatform.efi sonrasındaki 00000001

Standart driver GUID'i `cb933912-df8f-4305-b1f9-7b44fa11395c`;
`Universal/Acpi/AcpiPlatformDxe/AcpiPlatform.c:251`, normal sonunda
**EFI_REQUEST_UNLOAD_IMAGE** döndürür. `Pi/PiMultiPhase.h:46–48` bu durumun
AARCH64 değerini **0xa000000000000001** olarak tanımlar.

`Core/Dxe/Image/Image.c:1927`, CoreExit, bu PI durumunu da error-bit set
olduğu için "start failed" metniyle loglar. `BasePrintLib/PrintLibInternal.c:
1035–1059` `%r` için bilinmeyen PI durumlarında `%08X` fallback'i kullanır;
burada düşük 32 bit **00000001** görünür. Bu, EFI_LOAD_ERROR'nin kesin kaydı
değildir; normal unload isteğiyle tam uyumludur. Görüntüde ImageBase kesin
olmadığından eski frame'in adresli modül eşlemesi bağımsız doğrulanmış sayılmaz.

Yeni `Drivers/AcpiPlatformTraceDxe` pinned upstream driver'ı **değiştirmeden
include eder**, gerçek entry base/size ve tam 64 bit dönüşü loglayıp aynı
status'u döndürür. Normal unload başarıya çevrilmedi veya gizlenmedi:

```text
WBT ACPI PLATFORM ENTER handle=... base=... size=...
WBT ACPI PLATFORM RETURN raw=A000000000000001 request-unload=1
```

Gerçek dönüş farklıysa raw alanı o değeri gösterecek. Bu tanılama sadece WBT
profilinde standart driver yerine paketlenir; diğer profiller değişmez.

## SecurityLock: normal ReadyToBoot politikası

`VariablePolicyLib.c:1025–1040`, `LockVariablePolicy`, mevcut yazılım politikası
arayüzünü kilitler ve `SECURITY_LOCK_REPORT_EVENT("VariablePolicy Lock",
SOFTWARE_LOCK)` çağırır. `VariablePolicyLockingCommon.c:57–79` ReadyToBoot
callback'inde bu API'yi çağırır. WBT, ReadyToBoot olayını LoadImage öncesi
sinyaller. Bu kayıt, tek başına güvenlik hatası veya UFS/IOMMU blokajı değildir.

`SecurityLockAuditDebugMessageLib.c:43` normal audit satırını da DEBUG_ERROR
seviyesinde basar. Fotoğraftaki bulanık Module GUID'i okunmuş gibi sunulmadı.
Bu build'in VariableRuntimeDxe FILE_GUID'i `CBD2E4D5-7068-4FF5-B462-9822B4AD8D60`;
bu source/module bağlamıdır, fotoğraf OCR sonucu değildir. Kilit kaldırılmadı.

## Bulunan gerçek ACPI tüketici/paketleme eksikliği

AcpiPlatform normal dönebilirken tablo seti eksik kalabiliyordu. PCD
`PcdAcpiTableStorageFile`, yalnız `7e374e25-8e01-4fee-87f2-390c23c606cd` dosyasının
RAW instance'larını tüketir. Önceki FV'de bu dosya APIC/FACS/PPTT içeriyordu;
DSDT/FADT/GTDT ayrı FFS'lerde bulunmasına rağmen bu installer onları okumuyordu.
RSDP config-table varlığı ve statik FV'de tablo bulunması, kurulduğunu kanıtlamaz.

`Include/ACPI.inc`, sadece WINDOWS_BOOT_TEST için **zaten mevcut** CPU-only
DSDT/FADT/GTDT derleme çıktılarını aynı tüketici dosyasına ekliyor. Tablo
içerikleri/HID/IRQ/DMA/GIC/PSCI alanları bu değişiklikte değiştirilmedi.
FV audit artık gerçek tüketici dosyasında APIC/DSDT/FACP/GTDT/FACS/PPTT
bulunmasını zorunlu tutuyor; ayrı FFS kopyaları denetim için korunuyor.
Peripheral `_STA=0` SSDT ayrı dosyada kalır; yeni UFS cihazı etkinleştirilmez.

WBT-only ACPI SDT enumeration protokolü açıldı. BDS, **kurulmuş** tabloları
GetAcpiTable üzerinden sayar ve `INSTALLED: FADT=... DSDT=... GTDT=...` gösterir.
Bunlar runtime ölçümüdür; paketlenmiş varlık üzerinden sabit PASS yazılmaz.
Kurulumun gerçek telefonda tamamlandığı veya kernel için yeterli olduğu henüz
iddia edilmiyor. Yeni ACPI donanım kaynakları uydurulmadı.

## API sınırı tanılaması

`HandoffTrace.h`, Boot Services AllocatePages/FreePages çağrılarını kendi
orijinal fonksiyonlarına aynen iletir. Table CRC güncellenir; reentrancy guard
vardır. Native allocation hataları değiştirilmez; sabit-adres yönlendirmesi yok.
Log filtresi bilinen iki adresi, hataları ve büyük istekleri öne çıkarır;
Microsoft ekranını gereksiz başarılı tahsis satırlarıyla doldurmaz.

`phase=1` LoadImage sınırı; `phase=2` StartImage sınırı; `phase=3` dönüş sonrası.
`caller`, gerçek RETURN_ADDRESS; `child=1` yalnız caller yüklenmiş Microsoft
imaj aralığındaysa oluşur. Bu, saf CALL/pending etiketinden daha kuvvetli
execution ölçümüdür. API kullanımı Microsoft arayüzü veya kernel başarısı değildir.

StartImage dönerse hook'lar geri alınır, tam raw durum ve sayımlar sabit sonuç
ekranında gösterilir. ExitBootServices olayı gözlenirse sonrasında Boot Services
ve console çağrısı yapılmaz. Reset trap kasıtlı halt davranışını korur;
Microsoft ekranını silmemek için reset sırasında console çıktısı üretmez.
RTC/capsule unsupported kalır; gerçek runtime/Windows kernel desteği iddia edilmez.

## Doğrulama ve yeni deneysel dosya

- **118 test geçti**, hata/skip yok. Gözlemci testi gerçek wrapper fonksiyonlarını
  derleyip orijinal argüman, pointer, hata/success, tekrar giriş ve caller
  sınıflandırmasını doğrular; fake fiziksel sonuç üretmez.
- DEBUG firmware derlendi; FD 3 MiB. FV açılımı **43.065.344 bayt**.
- Gerçek FD→LZMA→FV→RAW/GPT/FAT ve ACPI checksum denetimleri geçti; ACPI tüketici
  dosyası zorunlu tabloları içeriyor. Native UFS/FFU/HAL bağımlılıkları yok.
- QEMU'da gerçek Microsoft PE entry breakpoint, `0x102000` hata/caller kaydı
  ve Recovery ekranı aynı son koşuda görüldü. Tam telefon firmware'i QEMU'da
  çalıştırılmadı; host aynı RAM provider ve API gözlemci işlevlerini kullandı.
- Android header v1/page4096, aynı 144 bayt BootShim ve özgün DTB'ler korunur.
  Gzip roundtrip/deterministik paketleme geçti; özgün backup değişmedi.

Yeni IMG: `davinci-target-a-handoff-trace.img`, **4.145.152 bayt**.

SHA-256:
`215de3a9fec55063d41412570701a5b584edf742ea63c4505c776ea1d5786ef6`

FD SHA-256:
`b9319ddc7391b18e32f2cbfd4e2143dd20ffe5959fa7211af76b0f76e6bb8106`

Yeni fiziksel test/kararlılık/Recovery garantisi yok. Heap/FD_SIZE/DeviceMemoryMap
büyütülmedi; native UFS/FFU kapıları, salt okunur RAM disk ve bölüm yazma yasağı
korundu. Common Env/CPU/GIC/timer baseline'ı aynı; yeni MMIO/DMA ayarı yok.

Onaylanıp Drive'a teslim edilen önceki `davinci-target-a-dxe-fv2-fix.zip`
değiştirilmedi. Yeni handoff dosyası farklı sürümdür; ikisi karıştırılmamalı.
Yeni ZIP kullanıcıya ulaşıp hash eşleştiğinde:

```powershell
Get-FileHash .\davinci-target-a-handoff-trace.img -Algorithm SHA256
fastboot boot .\davinci-target-a-handoff-trace.img
```

Videoda ACPI PLATFORM raw dönüşü, INSTALLED üçlüsü, CHILD base, API CALL/RETURN
ve varsa child=1/caller/status veya Microsoft Recovery/FINAL dönüşü yakalanmalı.
QEMU'da görülen hata tek başına giderilmesi gereken bir fatal durum sayılmamalı.
Takılmada güç basılı tutup Güç + Ses Kısma ile Fastboot; mevcut TWRP için önceki
Güç + Ses Açma yöntemi. Kalıcı flash/format/GPT işlemi yok.

Günlükler ve ekran kanıtı `evidence/handoff-trace/` altındadır. Yeniden üretim
mevcut `build_verified_target_a.sh`, `run_arm64_smoke.py` ve
`davinci_boot_image.py --profile windows-boot-test --windows-folder ...` ile
Git dışındaki yeni klasörde yapılır. Microsoft içeren IMG/ZIP GitHub'a commit edilmez.
