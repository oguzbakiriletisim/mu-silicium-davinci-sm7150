# DUU2 — sabit ekran ve reset/exception tanılama paketi

5 Kasım 2026. Başlangıç kaynak `59518c7fbd022a130eebd1270a1a4e4d31c3169c` (DUU1).

**MI logosuna dönüşün kesin nedeni henüz belirlenmedi.** İki hızlı ekran ve elle hissedilen sıcaklık, HAL/IOMMU/UFS veya Windows başarısının kanıtı değildir. DUU2'nin fiziksel testi yapılmadı. Paket, bir sonraki denemede son aşamayı okuyabilmek içindir; Windows kurulumu içermez.

## Önce hangi imaj?

ZIP'i açıp `SHA256SUMS.txt` ile dosya hash'lerini karşılaştırın.

1. **Önce `DUU2-baseline-D010.img`.** DXE tanılama sürücüsüne ulaşıp ekran/exception/reset kancalarını kurduktan sonra durur. SMMU snapshot, HAL, native Clock/UFS başlangıcı veya disk okuması yapılmaz. APSS watchdog'un yalnız bilinen enable register'ı okunur. 20–30 saniye fotoğraf için bekletin; sonra manuel Fastboot'a dönün. Bu noktada da MI logosuna dönmesi HAL/UFS başlatmasına bağlanamaz; tek başına gerçek reset kaynağını belirlemez.
2. Baseline sabit kalırsa **`DUU2-auto.img`** ile ana tanılama denenebilir. Başlangıçtan video alın: kritik çağrı öncesi ekran yaklaşık1s sabit gösterilir. Sonuç/hata/ele geçirilen exception veya ResetSystem isteğinde sonuç ekranı bekler.
3. **`DUU2-before-HAL-B0B6.img`**: akış bu noktaya gerçekten ulaşırsa HAL `LoadImage` sonrasında, `StartImage` çağrısından **önce** durur.
4. **`DUU2-before-UFS-B0C6.img`**: UFS `LoadImage` sonrasında, `StartImage` çağrısından **önce** durur.

Son iki imaj yalnız ilgili aşamaya kadar olan yolu tekrarlar. Önceki bir hata/güvenlik kapısı veya HAL'ın bilinçli atlanması hedef koda ulaşılmasını engelleyebilir; o zaman DFFF sonuç ekranında durur. Hedefe ulaşmayı zorlamak için guard kapatılmaz. D010/DFFF/diğer sabit bekleme durumları kasıtlıdır; USB menüsü veya otomatik MIUI dönüşü beklenmez.

```powershell
Get-FileHash .\DUU2-baseline-D010.img -Algorithm SHA256
fastboot boot .\DUU2-baseline-D010.img
# Baseline sonucu kaydedildikten ve manuel Fastboot'a dönüldükten sonra:
fastboot boot .\DUU2-auto.img
```

Bu komutlar kullanıcı içindir; bu oturumda telefon/ADB/Fastboot kullanılmadı. Önceki geçici davinci yolu kullanılır; yeni imajın çalışması garanti edilmez. Kalıcı flash/format/GPT onarımı/firmware fallback yoktur. Önceki imajları sırf veri elde etmek için tekrar tekrar başlatmak gerekmez.

## Kodlar nasıl okunur?

Panelin başında **DUU2 PHOTO**, **CP=...**, **DUU2_STOP=...** bulunur. Ekranı tamamen fotoğraflayın.

| Kod | Anlamı |
|---|---|
| D010 | Ekran/exception/reset kancaları kuruldu; native bağımlılıklar başlamadı. Hook sonuçları ayrıca gerçek EFI koduyla gösterilir. |
| A000/A001 | Önceki legacy SMMU kontrolü çağrı/dönüş; yeni identity kapısı değildir. |
| A100 | IDR0/IDR1/CR0/CR0NS okuma grubu öncesi. |
| A101 | SMR/S2CR okuma grubu öncesi. |
| A102 | CBAR okumaları öncesi. |
| A103 | CBA2R okumaları öncesi. |
| A104 | SCTLR okumaları öncesi. |
| A105 / A1EF | Snapshot doğrulama dönüşü / global-disable reddi. |
| B0x0..B0x7 | Bir modül için DEPEX-call/return, FV-read-call/return, LoadImage-call/return, StartImage-call/return. Son nibble0..7 bu sıradadır. |
| B0A4/B0A5, B0A6/B0A7 | Clock LoadImage/StartImage çağrı ve dönüşleri. |
| B0B4/B0B5, B0B6/B0B7 | HALIOMMU LoadImage/StartImage çağrı ve dönüşleri. |
| B0C4/B0C5, B0C6/B0C7 | UFSDxe LoadImage/StartImage çağrı ve dönüşleri. |
| C100/C101 | HAL protokolünün void init çağrısı/dönüşü; ABI doğrulaması ayrıca kaydedilir. |
| C200/C201 | Native HAL create çağrısı/dönüşü. |
| C210/C211 | configure_bypass çağrısı/dönüşü. |
| C220/C221 | UFS0 ARID0/MASK0 attach çağrısı/dönüşü. |
| E000/E001 | Block I/O handle taraması çağrı/dönüşü. |
| E100/E101 | Gerçek ReadBlocks çağrısı/dönüşü. |
| E200/E201 | GPT doğrulaması başlangıç/dönüş; iç ReadBlocks kodları araya girebilir. |
| DFFF | Normal sonuç/hata raporu tamamlandı, kasıtlı bekleme. |

B0x modül indeksleri: 0 SMEM,1 DAL,2 HWIO,3 ChipInfo,4 PlatformInfo,5 ULog,6 CmdDb,7 NPA,8 Rpmh,9 Pdc,A Clock,B HALIOMMU,C UFS. Pending ekranı çağrının **henüz dönmediğini** gösterir; öncesindeki1s pencerede çağrı henüz yürütülmemiş olabilir. Bir sonraki return kodu görülmedikçe başarı çıkarılmaz.

Panelde LoadImage/StartImage ve HAL ham create/config/attach sonuçları, SMMU kontrol kayıtları, gerçek okuma/Block I/O/GPT sayıları ayrı durur. `UNREAD`/`PARTIAL` alanları okunmamıştır; başlangıç sıfırı ölçüm gibi gösterilmez. `MMIO(our last)` yalnız kaynak denetleyicinin son denediği adresidir; vendor ikilisinin son register'ı değildir. `DEPEX MISSING` son eksik protokol GUID'ini gösterir. GPT/Windows/ESP GUID'leri ancak gerçek salt okunur doğrulama sonrasında görünür; etiket/type bulunması OS kurulu demek değildir.

## Exception / ResetSystem / watchdog ayrımı

- SYNC HOOK ve SERROR HOOK, CPU Architectural Protocol üzerinden gerçek kayıt sonucudur. IRQ/FIQ ve önceden kayıtlı handler'lar kaldırılmaz. Kayıt başarısızsa o exception'ın yakalanacağı garanti edilmez.
- Yakalanan exception'da ELR,ESR,FAR,LR ve bilinen native image/RVA gösterilir. Stack/PDB yürüyüşü yapılmaz; handler geri dönmez veya reset çağırmaz. SERROR asenkron olabilir; FAR her exception'da geçerli adres değildir. Bu değerler otomatik olarak "UFS register hatası" ilan edilmez.
- RESET HOOK, runtime services tablosundaki ResetSystem işaretçisini **yalnız RAM'de** tanılama handler'ına bağlar; tablo CRC'si yeniden hesaplanır. Yakalanan istek yürütülmez; type/status ve son checkpoint sabit kalır. Bu, DUU1'deki resetin aynı çağrıdan geldiğini tek başına kanıtlamaz. Bir sürücü işaretçiyi sonradan değiştirebilir veya farklı bir reset yolu kullanabilir.
- EFI WATCHDOG CANCEL, artık gerçek dönüş kodudur. Sağlayıcı yoksa NOT_AVAILABLE/NOT_FOUND benzeri sonuç tüm watchdog'lar kapandı demek değildir.
- APSS WDT EN init/now, mevcut kaynakta PrePi'nin kapattığı **0x17C10008** register'ının salt okunur gözlemidir. Yeni watchdog yazması/pet/bark/bite ayarı yoktur. Enable değişimi bir ilişki gösterebilir; reset nedenini tek başına kanıtlamaz. TZ/AOP/PMIC watchdog/reset kaynakları denetlenmiş veya kapatılmış sayılmaz.
- Source serial framebuffer günlüğü fotoğraf profilinde çizimi durdurur; panel sabit satırlardan oluşur. Private vendor logger'lar bunu atlayabilir. Çağrı öncesi1s ve stop imajları bu nedenle önemlidir. Donanım/TZ reseti framebuffer'ı silebilir; bu resetleri "asla olmaz" diye sunamayız.

Bekleme, source tight-spin yerine WFI kullanır. Bu bir güç/termal yönetim çözümü değildir; kesmeler WFI'yi uyandırabilir. Sıcaklık sensörü okunmadı; elle hissedilen değişimin nedeni belirlenmedi. Eklenen1s beklemeler watchdog zamanlamasını DUU1'e göre değiştirebilir.

## Güvenlik sınırı ve kurtarma

HAL/IOMMU sahiplik, identity-readback, mevcut eşlemeyi koruma ve salt okunur GPT kuralları korundu. Yeni SMMU bank ataması, koşulsuz DMA veya binary patch yoktur. UFS register'larına ilave kör bir probe eklenmedi; vendor UFS entry/ReadBlocks checkpoint'leri ve varsa exception FAR/ELR ayrımı kullanılır. Snapshot'ta mapped MMIO olmak, secure/power-gated bir register'ın her durumda okunabilir olduğunu kanıtlamaz; yeni A10x işaretleri bu yolu ayırır.

Reset/hata yakalanırsa ekrandaki bütün paneli kaydedin. Güç tuşunu10–20sn tutun; Fastboot için güç+ses kısma. Mevcut TWRP için güç+ses açma, Mi logosunda gücü bırakıp ses açmayı tutma. Her arıza durumunda dönüş garantisi yoktur. Orijinal boot/TWRP/GPT yedeklerini koruyun. Bu pakette restore/flash komutu yoktur.

## Bilgisayarda yeniden üretme

Önceki EDK2/toolchain/submodule ortamında:

```sh
export DAVINCI_SYSTEM_NASM=1
bash Resources/Duu2Photo/build_photo.sh /path/boot_clean.zip /path/NEW-baseline 0xD010
bash Resources/Duu2Photo/build_photo.sh /path/boot_clean.zip /path/NEW-auto 0
bash Resources/Duu2Photo/build_photo.sh /path/boot_clean.zip /path/NEW-before-hal 0xB0B6
bash Resources/Duu2Photo/build_photo.sh /path/boot_clean.zip /path/NEW-before-ufs 0xB0C6
```

Üretilen `davinci-prefinal-experimental.img` teslimatta yalnız yeniden adlandırılır. Header/page/adresler/14 DTB aynı orijinal128MiB boot yedeğinden alınır; davinci.sh parametreleri tahmin edilmez. Aynı FD/shim/backup ile paketleme birebir doğrulanır; build timestamp'leri yeniden derleme hash'ini değiştirebilir.
