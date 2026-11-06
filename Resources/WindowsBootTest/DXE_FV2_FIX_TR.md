# Target A — ikinci fiziksel test: DXE / Boot Manager sınırı

Kullanıcının fiziksel testi, önceki PrePi düzeltmesiyle DXE, RAM FAT/SFS,
Microsoft dosyasının okunması ve LoadImage başarısını doğruluyor. Recovery
ve Windows çekirdeği doğrulanmadı. Aşağıdaki yeni imaj telefonda denenmedi.

Başlangıç: `ae77c8730794268d692e803ad5f6630a520f8b44`.
Kaynak değişikliği: `fe538372432cb2323c498d169fb1c4b8e171b626`.
Dal: `davinci-windows-boot-test`.

## Fiziksel satırların gerçek kaynakları

| Gözlem | Kaynak ve kanıtın sınırı |
|---|---|
| FAT dosya okuma / structural map / boot option / LoadImage Success | `Platforms/Xiaomi/davinciPkg/Drivers/WindowsBootTestDxe/WindowsBootTestDxe.c`, `WindowsBdsEntry`. Gerçek EFI dönüşleri. Memory-map structural pass; kapasite, firmware ownership ve Windows uyumluluğu garantisi değildir. |
| BCD Open Not Found | Aynı fonksiyondaki gerçek `Root->Open(...BCD...)`. Girdide BCD yok. |
| StartImage CALL | Aynı fonksiyon, API çağrısının hemen önündeki Stage. Buradaki EFI_NOT_STARTED bir pending etiketidir; StartImage dönüşü değildir. Eski videoda dönüş satırı gözlenmedi. |
| AllocatePoolPages: failed to allocate 10513 pages | `Mu_Basecore/MdeModulePkg/Core/Dxe/Mem/Page.c:2487`, `CoreAllocatePoolPages`. FindFreePages sıfır döndürmüştür; **DXE pool allocator** mesajıdır, eski PrePi allocator mesajı değildir. |
| ConvertPages: failed to find range | Aynı dosya 1093, `CoreConvertPagesEx`. İstenen başlangıç adresini kapsayan memory-map entry bulunamadığı için EFI_NOT_FOUND. Exact adresler verilmeden hangi bölge olduğuna karar verilemez. |
| Error: Image at ... start failed | `Mu_Basecore/MdeModulePkg/Core/Dxe/Image/Image.c:1927`, `CoreExit`. Yazdıran modül DXE Core; başarısız olan imajın kimliği ayrıca ImageBase ile eşleştirilmelidir. Adres paylaşılmadığından bunun Microsoft olduğunu söylemiyoruz. |
| SecurityLock::LockType: SOFTWARE_LOCK | `MdeModulePkg/Library/SecurityLockAuditDebugMessageLib/...c:43`. Normal audit bildirimi de DEBUG_ERROR seviyesinde basılır. Örnek gerçek çağrı `VariablePolicyLib.c:1038`, `LockVariablePolicy` / "VariablePolicy Lock". Tam Module/Function/Output olmadan bu örneği kesin olay diye sunmuyoruz. |

Mu_Basecore commit'i `evidence/dxe-fv2-fix/` yanındaki önceki SUBMODULES
kayıtlarında ve sabitlenmiş Git submodule referansında bulunur. Yeni kaynak
Mu_Basecore alt modülüne müdahale etmez.

`CoreStartImage` (Image.c:1663–1845), handle/önceki LoadImageStatus/machine
kontrolü ve jump-buffer tahsisinden sonra entry point'i çağırır. API çağrı
noktasına gelmek entry point'in mutlaka çalıştığını kanıtlamaz. CoreExit'in
1927 logu, `Image->Status` alanını yazdırır; doğrudan Exit() yolunda bu log,
geçirilen Status alanına atamadan **önce** gelir. Bu yüzden video kırpıntısı
`00000001` tek başına güvenilir StartImage dönüş kaydı değildir. Tam
`0x8000000000000001` EFI_LOAD_ERROR'dır; sadece alt 32 bit/eksik yüksek bit
ile bunu kesin kod diye etiketlemiyoruz.

## 10.513 sayfanın güçlü kaynak adayı: aynı FV'nin DXE'de tekrar açılması

Başlatılan önceki FD'nin (SHA
`2b57835cc29cfcb407fd6af7b3fe7c4720705af0ee93123298af272cf4dd24a4`)
dış `FVMAIN_COMPACT` header'ında **ExtHeaderOffset=0**, yani isim GUID'i yok.
Açılan FV_IMAGE section 43.057.160 bayt, FV payload 43.057.152 bayttır.

- PrePi `WindowsPrePiLib/FwVol.c`, `FfsProcessFvFile`, FV2 HOB'a **parent FV
  ismi + kapsayıcı dosyanın GUID'ini** yazar.
- Aynı kütüphanedeki `FfsGetVolumeInfo`, FvName'i ancak extension header varsa
  doldurur. Önceki caller `ParentVolumeInfo`'yu sıfırlamıyordu: isim alanı
  başlatılmamış kalabiliyordu. Bunun gerçek cihazdaki bitlerini bilmiyoruz.
- DXE `Dispatcher.c:921`, `FvFoundInHobFv2`, hem parent hem dosya GUID'ini
  karşılaştırır. `Dispatcher.c:1350` civarında bu eşleşme bulunmazsa aynı FV
  dosyasını yeniden ReadSection yoluna sokar.
- `SectionExtraction/CoreSectionExtraction.c:1550–1610`, guided GetInfo'nun
  bildirdiği açılım boyutu için AllocatePool ister. Pool overhead ile bu
  43 MB istek 10.513 sayfaya oturur. `Mem/Pool.c:411–430` overhead ve sayfa
  hesabının gerçek kaynağıdır.
- FV memory-mapped olduğunda `FwVol/FwVol.c:346–357` FV'yi gerçekten yeniden
  cache'lemez; tüm FV cache tahsisi yalnız memory-mapped olmayan dalda yapılır.
  Bu build'de MEMORY_MAPPED set olduğundan ilk güçlü aday tekrar section
  extraction yoludur.

**Kesin bulgu:** parent FV kimliği sözleşmesi eksiktir ve başlangıçsız alan
vardır. **Henüz kesinleşmeyen:** telefondaki 10.513 sayfa isteğinin tam çağrı
stack'i ve videodaki diğer mesajlarla zaman sırası. Aynı sayfa sayısı tek
başına stack trace değildir. Bu kaynak hatasının giderilmesi Recovery'nin
kesin açılacağı anlamına gelmez. Başarısız bir tahsis zaten alan tutmamış
olabilir; düzeltme 43 MB ek serbest RAM kazandırmış diye sunulmaz.

## Uygulanan düzeltmeler

1. `davinci.fdf`, yalnız WINDOWS_BOOT_TEST dış FV'sine deterministik isim
   GUID'i ekler: `9dc2feb1-ef18-5f5f-aebe-0f4f7bf176d4`. Bu bir **firmware
   volume metadata kimliğidir**; donanım/ACPI/telefon GPT kimliği değildir.
2. `Library/WindowsPrePiLib/FwVol.c`, ParentVolumeInfo'yu sıfırlar ve gerçek
   `WBT FV2 parent=... file=... base=... size=...` kaydını ekler. Böylece
   PrePi ve DXE aynı gerçek parent ismini kullanır. Önceki SECTION2 hizalama
   düzeltmesi korunur. `UPSTREAM.diff/json` güncellendi.
3. `Resources/WindowsBootTest/audit.py`, gerçek FD'deki dış FV extension
   ismini ve sınırlarını kontrol eder. Extension'ın HeaderLength dışında,
   PAD alanında bulunması geçerlidir; denetim FV sınırına göre yapılır.
4. `WindowsBootTestDxe.c`, LoadImage öncesi ve StartImage öncesi gerçek map'i,
   conventional toplam/en büyük serbest sayfa sayısını ve loaded child
   ImageBase/ImageSize/ParentHandle bilgisini gösterir.
5. StartImage dönerse child unload edilmiş olabilir. Önceden kaydedilmiş
   scalar base/size kullanılır; stale LoadedImage pointer'ı okunmaz. Ekran
   temizlenir, gerçek `%r`, tam 64 bit durum ve EFI_ERROR sonucu yazılır.
   Harita sonrasında `FINAL: StartImage returned ... CHILD=...` satırı
   kalır. Pending etiketinden farklı, yalnız API gerçekten dönerse oluşur.

Memory snapshot küçük, geçici normal pool buffer kullanıp serbest bırakır;
fixed-address allocation/remap veya donanım register işlemi yoktur. MAP
satırlarının son adresi **inclusive**'dir. `ConvertPages` Start–End de
inclusive; yeni videoda aynı aralıklar karşılaştırılabilir. Memory type
7 conventional, 3/4 boot-services code/data, 5/6 runtime code/data'dır.

## Runtime ve kalan belirsizlikler

Boot Services gerçek DXE Core servisleridir. Toplam 69 MiB heap'in büyük
kısmında FV duruyor; largest-free, toplam-free ile aynı değildir. Windows
Boot Manager'ın daha büyük veya belirli adresli isteği başarısız olabilir.
Reserved Android/secure alanları serbest RAM sayılmadı; heap büyütülmedi.

RuntimeDxe/EmuNvMode variables korunur; RTC unsupported, capsule unsupported,
ResetSystem kasıtlı halt trap'tir. Kernel runtime/VA-map/ExitBootServices
uyumluluğu kanıtlanmış değildir. Önceki QEMU'nun platformu, RNG/SMBIOS ve
kullanılabilir RAM'i telefonla aynı değildir. Memory-map structural pass bu
farkları çözmez. SecurityLock kapatılmadı, genel bellek korumaları kaldırılmadı.

## Test ve teslimat

Gerçek DEBUG derlemesi başarılı. **117 test geçti, hata/skip yok.** Yeni test
`test_target_a_fv2.py`, gerçek DXE `FvFoundInHobFv2` fonksiyonunu derleyerek
parent+file eşleşmesini ve yanlış kimlikle yeniden açılma koşulunu kontrol
eder. HOB servisleri test double'dır; bu test telefon DXE dispatcher'ını
çalıştırmış sayılmaz. İlk test-harness hataları düzeltilip full suite geçti.

FD/FV LZMA bağlantısı, FFS/ARM64/ACPI/RAW/GPT denetimleri geçti. Native lock
listesindeki UFS/FFU/HAL bağımlılıkları hâlâ FV'de yok. Gerçek Microsoft dosya
hash'leri değiştirilmedi. FD_SIZE=3 MiB, heap ve DeviceMemoryMapLib aynı.
Yeni FV 43.061.248 bayt; tanılama koduyla bir sayfa büyüdü.

Yeni dosya: `davinci-target-a-dxe-fv2-fix.img`, **4.145.152 bayt**.

IMG SHA-256:
`3302aa02f8dc56cc412094340c14c4667cde4a98b5ddac555ac923f490243e4a`

FD SHA-256:
`f6a34253b1ed628d09cfc90d4953379c8b6a45dea3ecc07ffd1a8c82263dc0c3`

Özgün boot backup ve DTB'ler korundu; header v1/page4096/aynı BootShim ve
adresler. Gzip roundtrip ve deterministik yeniden paketleme doğrulandı.
Yeni fiziksel başarı/kararlılık garantisi yok. Telefona biz bağlanmadık.

ZIP kullanıcıya ulaşıp hash doğrulandıktan sonra:

```powershell
Get-FileHash .\davinci-target-a-dxe-fv2-fix.img -Algorithm SHA256
fastboot boot .\davinci-target-a-dxe-fv2-fix.img
```

İstenen yeni kanıt: FV2 parent/file, 10.513 tahsis mesajının tekrarlayıp
tekrarlamadığı, WBT CHILD base, BEFORE START free/largest/MAP, varsa FINAL
raw dönüşü veya gerçek Microsoft ekranı. Tam ilk ekran geçişleri ve
ConvertPages adresleri videoya alınmalı. Microsoft ekranı görülmezse
kaynak düzeltmesi fiziksel Hedef A başarısı olarak raporlanmayacak.

Takılırsa güç basılı tutma; Güç + Ses Kısma ile Fastboot. Mevcut TWRP'ye
önceki Güç + Ses Açma yöntemi. Flash/format/GPT değişikliği gerekmiyor.

Yeniden üretim, mevcut `build_verified_target_a.sh` ve
`davinci_boot_image.py --profile windows-boot-test --windows-folder ...`
ile yeni özel klasörde yapılır. Günlükler `evidence/dxe-fv2-fix/` altında.
Microsoft içeren IMG/ZIP GitHub'a commit edilmez; kaynak ve kanıtlar commit edilir.
