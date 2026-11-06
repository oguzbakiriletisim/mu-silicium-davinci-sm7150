# Target A — PrePi Out of Resources düzeltmesi

**Durum:** Kullanıcının fiziksel `PrePi.c(189)` hatasına yol açabilecek
belirleyici bir hizalama/çift tahsis kusuru gerçek kaynakla host'ta yeniden
üretildi ve düzeltildi. DEBUG derlemesi ve 116 test geçti. Yeni imaj
**telefonda henüz denenmedi; DXE'ye ulaştığı iddia edilmiyor**.

Başlangıç commit: `66278c1a457db4952237bab1720909e5b8a5eb28`.
Düzeltme commit: `b23115b44b8a41621e26fd0254801ff12eb9e924`.
Dal: `davinci-windows-boot-test`.

## 189. satırın anlamı ve çağrı zinciri

Derlemenin `PrePi.obj.deps` kaydı gerçek dosyayı
`Silicon/Silicium/SiliciumPkg/PrePi/PrePi.c` olarak gösteriyor. Bu dosyada
186 `Status = DecompressFirstFv()`, 189 `ASSERT_EFI_ERROR(Status)`.
**189 tahsis yapan satır değildir; alt çağrının hata durumunu gösterir.**

Kaynak zinciri:

`CEntryPoint → PrePiMain → DecompressFirstFv → FfsProcessFvFile →
FfsFindSectionDataWithHook → FfsProcessSection → guided GetInfo /
scratch+destination AllocatePages → guided Decode → FV section →
FfsGetVolumeInfo → gerekirse AllocateAlignedPages(FvSize)`.

Asıl upstream: `Common/Mu_Tiano_Plus`, commit
`2dd1beb9cd7631030dfc8e74cb4840a89b5d008d`.
`EmbeddedPkg/Library/PrePiLib/FwVol.c` 379 scratch tahsisi, 387 destination
 + ek sayfa; 397–401 dış section başlığına göre ofset; 865 FV alignment;
873–876 hizasız FV'nin ikinci tahsisi ve EFI_OUT_OF_RESOURCES dönüşü.
`PrePiMemoryAllocationLib/MemoryAllocationLib.c` 30–54 gerçek PHIT page
allocator; 143 aligned tahsis için ek sayfa; FreePages bu ortamda alanı
serbest bırakmıyor.

Fotoğraftaki tek assert, bu üç tahsis noktasından hangisinin cihazda ilk
hata verdiğinin adresini içermez. O yüzden **telefonda tam tahsis adresini
ölçtüğümüzü iddia etmiyoruz**. Buna karşılık aşağıdaki çift tahsis kusuru,
verilen build'in bu heap içinde tamamlanmasını matematiksel olarak engeller.

## Gerçek FD ile kanıtlanan neden

Başlatılan eski IMG SHA-256:
`9633ff286df1d288a0fe02210f9adc444a7ed9a27c8e341e7edec3e7640e7ce6`.
Eski FD SHA-256:
`5092905551b96e96d5336da37ffdff9a5c33e339790c48175b1899fc5ba87e59`.

FD'den çıkarılıp gerçek LZMA açılımıyla doğrulanan boyutlar:

| Alan | Gerçek değer |
|---|---:|
| Dış GUIDED section common header | 4 bayt |
| Dış sıkıştırılmış section | 1.637.681 bayt |
| Açılan iç FV_IMAGE section header / SECTION2 | 8 bayt |
| Açılan section | 43.057.160 bayt |
| FVMAIN | 43.057.152 bayt |
| FV header alignment | 8 bayt |
| LZMA scratch | 65.536 bayt |

Eski kod `DstBuffer = page_base + 4096 - 4` kullanıyor. İç başlık 8 olduğu
 için FV başlangıcı `page_base + 4100`: **8'e göre kalan 4**. Ardından
`FfsProcessFvFile` ikinci bir FV kopyası için AllocateAlignedPages çağırıyor.

| Gereksinim | Bayt |
|---|---:|
| LZMA scratch, 16 sayfa | 65.536 |
| Destination + hizalama sayfası, 10.514 sayfa | 43.065.344 |
| İkinci FV + alignment payı, 10.513 sayfa | 43.061.248 |
| Eski toplam, diğer tahsisler hariç | **86.192.128** |
| Tüm DXE Heap | **72.351.744 (69 MiB)** |
| Düzeltmeyle scratch + tek destination | **43.130.880** |

FV tek başına mevcut alana sığıyor. Asıl kusur büyük iç başlığın yanlış
hizalanmasıyla doğan ikinci kopya. Heap/FD büyütmek gerekmiyor.

## PrePi ve memory-map karşılaştırması

- DXE Heap: `0x97700000..0x9bc00000`, 69 MiB; PHIT burada kurulur.
- PrePi PHIT başlangıç serbest üst sınırı, diğer tahsislerden önce:
  `heap_base + heap_length - 0x40000 = 0x9bbc0000`.
- Mevcut kod heap sonunda 256 KiB stack HOB payı ayırır. Gerçek stack PCD
  `0x9ff90000`, boyut `0x40000`'dır; bu iki değer aynı değildir. Miras alınan
  rezervasyon davranışı değişmedi; bu fark 43 MB ikinci kopyayı açıklamaz.
- SEC Heap: `0x9ff00000..0x9ff8c000`; CPU vectors ve page tables sonraki
  mevcut bölgelerdedir. Bu SEC alanı 69 MiB PHIT heap'e ek bellek sayılmadı.
- FD: `0x9fc00000..0x9ff00000`, 3 MiB; display:
  `0x9c000000..0x9d800000`. FV açılımı FD'nin 3 MiB sınırında yapılmaz;
  PHIT heap'inden tahsis edilen destination'a yapılır.
- Burada geleneksel PEI temporary-RAM migration çalıştırılmıyor;
  ArchInitialize/POSTMEM ve HobConstructor sonrasında PrePi allocator PHIT'in
  top/bottom sınırlarını kullanıyor. Yerleşim veya RAM ownership tahmini yok.

**DeviceMemoryMapLib, FD_SIZE, heap boyutu, adresler, PrePi.c ve PREFINAL
kaynakları değiştirilmedi.** Yeni ve eski FVMAIN dosyaları birebir aynı.
Değişen SEC/PrePi link'i, yeni library implementation'ını kullanıyor.

## Düzeltme

`Platforms/Xiaomi/davinciPkg/Library/WindowsPrePiLib/` upstream BSD kaynaklarının
sabitlenmiş yerel kopyasıdır. `UPSTREAM.json` kökeni, `UPSTREAM.diff` yalnız
fonksiyonel farkı gösterir; satır sonları LF'e normalize edildi. Alt modül
çalışma ağacı değiştirilmedi.

`FwVol.c` 400–404: decoder destination'ı önce en büyük iç başlık için,
`page_base + 4096 - sizeof(EFI_COMMON_SECTION_HEADER2)` konumuna alır.
Gerçek iç başlık açıldıktan sonra okunur. İç başlık 4 baytsa sahip olunan
buffer içinde overlap-safe CopyMem ile 4 bayt kaydırılır; 8 baytsa kopya yok.
Input alias döndüren non-processing handler'ın belleği taşınmaz. Böylece
FV payload sayfa hizasındadır ve ikinci FV tahsisine ihtiyaç kalmaz.

`davinci.dsc`: yalnız `WINDOWS_BOOT_TEST=1` SEC sınıfında bu PrePiLib seçilir.
Gerçek `static_library_files.lst` yeni kütüphanenin linklendiğini doğruluyor.
Araştırma/PREFINAL/default kütüphane seçimi değişmedi.

## Testler ve erken ekran kayıtları

`test_target_a_prepi_memory.py`, eski/yeni **gerçek FfsProcessSection**,
**gerçek InternalAllocatePages/AllocateAlignedPages** ve gerçek downstream
alignment dalını derleyip 69 MiB host arena'da çalıştırır. Codec mock'tur;
LZMA'nın gerçek FD açılımı ayrıca FV audit'inde yapılır. Donanım testi değildir.

Eski büyük FV: `offset_mod_8=4`, `realign_status=9` (host EFI OOR etiketi).
Yeni büyük FV: `offset_mod_8=0`, `realign_status=0`; 4 bayt iç başlıklı küçük FV
de geçer. Full suite: **116 geçti, sıfır hata/skip**. DEBUG build başarılı;
FD/FV/RAW/GPT/ACPI/native-exclusion denetimleri geçti. Yeni tam davinci
firmware'i QEMU'da çalıştırılmış gibi sunulmaz; önceki host Boot Manager
kanıtı bu PrePi düzeltmesinin fiziksel kanıtı değildir.

Erken framebuffer/DEBUG çıktıları gerçek değerleri verir:

```text
WBT FV REQUEST dst=... scratch=... top=... bottom=...
WBT FV SCRATCH address=... status=...
WBT FV DEST pages=... address=... status=...
WBT FV DECODE status=... inner-header=... section=... payload=...
WBT FV RESULT start=... size=... alignment=...
```

Gerekirse `WBT FV REALIGN requested size=...` da çıkar. Adresler sabit başarılı
mesajlar değildir. Tek sayısal panelde OOR tekrar ederse hangi tahsisin
başarısız olduğu bu satırlardan anlaşılabilir. `FV RESULT` tek başına DXE
kanıtı değildir; sonraki gerçek WBT/BDS aşamasına geçiş ayrıca görülmelidir.

## Yeni deneysel imaj

Dosya: `davinci-target-a-prepi-fix.img`, **4.145.152 bayt**.

SHA-256:
`439736272d3a740fc32befac28c8efd589368d8fe2e4fa75fa9061acf341e251`

FD SHA-256:
`2b57835cc29cfcb407fd6af7b3fe7c4720705af0ee93123298af272cf4dd24a4`

Orijinal 128 MiB boot backup değişmedi. Android v1/page4096 ve header adres
alanları korundu; yalnız kernel_size/image_id güncellendi. Aynı 144 bayt
BootShim, aynı FD base/size, birebir özgün DTB'ler kullanıldı. Gzip shim+FD
roundtrip ve deterministik tekrar paketleme geçti. Yeni imaj AVB imzalı
değil; geçici açılış kabulü/kararlılığı yeni donanım testini bekliyor.

Özel ZIP kullanıcıya ulaştırılıp hash eşleştiğinde Windows PowerShell:

```powershell
Get-FileHash .\davinci-target-a-prepi-fix.img -Algorithm SHA256
fastboot boot .\davinci-target-a-prepi-fix.img
```

İlk hedef PrePi ASSERT yerine `WBT FV RESULT` ve ardından gerçek DXE/WBT
akışını görmek. Lütfen ilk ekran geçişlerini videoya alın. Yeni OOR varsa
REQUEST/top/bottom, SCRATCH, DEST ve RESULT satırları gerekli kanıttır.
Takılırsa güç tuşunu basılı tutup Güç + Ses Kısma ile Fastboot'a dönün;
mevcut kurulu TWRP için önceki Güç + Ses Açma yöntemi geçerlidir.

Telefona biz bağlanmadık; flash, bölüm yazması veya yeni MMIO/DMA ayarı yok.
Native UFS/FFU engelleri aynı. Başarılı DXE veya Microsoft ekranı fiziksel
olarak doğrulanmadan sonraki aşama tamamlanmış sayılmayacak.

Yeniden üretim: mevcut `build_verified_target_a.sh` aynı özel Microsoft ZIP
ile; ardından `davinci_boot_image.py --profile windows-boot-test` ve
`--windows-folder` yeni derleme klasörüyle kullanılır. Eski belgelerdeki
komutlar aynıdır; çıktılar yeni klasöre yazılmalıdır. Derleme zamanı
makroları FD hash'ini değiştirebilir; aynı FD/shim/backup ile paketleme
birebir aynı hash'i üretir. Günlükler `evidence/prepi-oor-fix/` altındadır.
