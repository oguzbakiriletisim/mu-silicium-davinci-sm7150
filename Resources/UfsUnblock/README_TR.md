# DAVINCI UFS UNBLOCK V1 / DUU1

5 Kasım 2026 (Türkiye). Başlangıç kaynak commit'i `f3016dd43346d63960dda5144c30f26f3824f0ba`.

**Yeni deneysel imaj; fiziksel UFS başarısı henüz yok.** PrePi/DXE başarınız korunmuş başlangıç noktasıdır. Windows kurulum kiti yeniden üretilmedi. Bu paket yalnız geçici UEFI/UFS okuma testidir.

## Uygulama

Zip'i açın. Paketteki `SHA256SUMS.txt` ile imaj hash'ini karşılaştırın:

```powershell
Get-FileHash .\davinci-ufs-unblock-experimental.img -Algorithm SHA256
fastboot boot .\davinci-ufs-unblock-experimental.img
```

Yalnız daha önce test ettiğiniz aynı **davinci / SM7150-AA** cihazını kullanın. Bootloader kabulü ve bu yeni sürümün fiziksel çalışması garanti edilmez. Bu oturumda telefona erişilmedi, ADB/Fastboot çalıştırılmadı. Flash/GPT/format talimatı yoktur. Auth/unsupported durumunda durun; kalıcı flash fallback yoktur.

Yeni sürümü ayırt eden ilk sürücü mesajı: **`DAVINCI UFS UNBLOCK V1 / DUU1`**. Ekranı başlangıçtan kaydedin. Özellikle son ekrandaki `LAST UFS SMR/S2CR/TYPE/CB`, `LAST CBAR/CBA2R/SCTLR/M/IOC`, `HAL ENTRY`, `HAL INIT ABI`, `UFS DOMAIN`, Block I/O ve GPT satırları gereklidir.

## Gerçek düzeltme ve üç çalışma durumu

1. Önceki profilde HALIOMMU ikilisi paketlenmiyordu; Not Found beklenen yazılım sonucuydu. Şimdi özgün davinci HAL ikilisi değişmeden FREEFORM PE32 olarak paketlenir. Yalnız bağımlılıklar gerçek DEPEX ile hazırsa ve sahiplik kontrolü izin verirse `LoadImage/StartImage` ile yüklenir. Eksik protokol GUID'leri ve gerçek EFI dönüşleri yazılır. HAL dosya GUID'i ile yayınlanan protokol GUID'i birbirine karıştırılmaz.
2. Eşleme zaten mevcutsa **üzerine ikinci SMR eklenmez**. Fresh register okumaları açık stream-bypass veya native S1-identity/S2-bypass durumunu doğrularsa mevcut eşleme korunur. Bu durumda kaynaklı HAL attach zinciri gerekli değildir; ekranda `EXISTING VERIFIED IDENTITY ... ATTACH NOT NEEDED` veya `... HAL PROVIDER SKIPPED` yazılır. Çalıştırılmamış HAL aşamaları NOT_STARTED olarak kalır; sahte PASS üretilmez.
3. UFS aralığı eşlenmemişse, güvenli boş kaynaklar bulunduğunda gerçek HAL sağlayıcısı normal entry üzerinden yüklenir. Yayınlanan revision1/void-init ABI ve image-owned function table doğrulanır. Kaynaklı köprü `create → configure_bypass(EnableUfsIOC) → attach("\_SB_.UFS0", ARID0, MASK0)` çağırır. Her ham HAL dönüşü ayrı yazılır, ilk hatada durulur. Bank numarasını kaynak kodu seçmez; özgün HAL canlı CBAR durumundan seçer. Ardından SMR/S2CR/CBAR/CBA2R/SCTLR geri okumaları zorunludur.
4. Mevcut UFS route'u identity/bypass olarak doğrulanamazsa, farklı/kararsız register düzeni görülürse veya native sağlayıcı canlı bankları bozabilecekse o yazma yolu engellenir. Mevcut route'u körlemesine detach/yeniden programlama yoktur. `CBAR/CBA2R/SCTLR` değerleri önceden paylaşılmadığı için mevcut CB2'nin uygun olup olmadığı **bu yeni fiziksel testte** ayrılacaktır.

**HAL sağlayıcısının ek davranışı:** özgün entry SDC1/2/4 ve USB3-0 dummy client'larını da başlatır. Yeni sahiplik kapısı bunlar için mevcut bir SMR eşleşmesi veya native allocator'ın boş sanacağı canlı bir bank bulursa HAL entry'yi çalıştırmaz. Buna rağmen UFS'nin mevcut identity durumu bütünüyle doğrulanmışsa UFS okuma yolu kullanılabilir. Bu dalda HAL başarı kriteri tamamlanmış sayılmaz; sonuçlar bunu açıkça gösterir.

UFS'den önce ve entry dönüşünden sonra IOMMU geri okuması geçmelidir. UFSDxe binary stub'ı değiştirilmedi; yeni patch yoktur. Eşleme gerektiğinde stub'ın yapmadığı iş ayrı kaynaklı köprüde gerçekleştirilir. UFS entry başarısı tek başına UFS PASS değildir: `UFS READ ACCESS` için gerçek başarılı ReadBlocks, `GPT PASS` için iki header/entry array CRC, aynı disk kimliği, benzersiz GUID ve çakışmasız extent doğrulaması gerekir.

GPT/Windows/ESP kontrolleri önceki kaynaklı salt okunur yolla aynıdır. `win FOUND` yalnız etiket adayı; ESP FOUND yalnız type GUID adayıdır. Gerçek GUID/LBA/boyutu kaydedin. Hiçbir GPT onarımı yapılmaz. BDS, PartitionDxe, FAT ve SCM/RPMB/GPT listener sağlayıcısı yoktur; Windows başlatılmaz. Kaynakta SMMU'ya doğrudan MMIO yazması veya disk WriteBlocks/erase/format yoktur. Native HAL/UFS/Clock sürücüleri çalıştıkları dalda gerçek donanım register/DMA işlemleri yapar; bunlar bu cihazda henüz doğrulanmadı ve fiziksel güvenlik garantisi verilmez.

## Paylaştığınız sayısal sonucun düzeltilmiş yorumu

`IDR0=40017E4F`, `IDR1=6000003D`, `CR0NS=0`, `SMR=800F0300`, `S2CR=2` alındı.

- Gerçek HAL programlama rutini, bank2 test girdisi için S2CR=2 üretir. TYPE bitleri [17:16], CB bitleri [7:0]: **TYPE0, CB2**. TYPE2 fault değeri aynı bank için `0x00020002` olur. `TYPE=2` şeklindeki önceki metin ham S2CR ile tutarlı değildir.
- TYPE0 tek başına etkin çeviri demek değildir. Native `configure_bypass` S1 context/S2 bypass kurarken SCTLR.M=0 kullanır. Bunun için CB2'nin gerçek kontrol kayıtları gerekir; yalnız S2CR=2'den güvenli DMA sonucu çıkarılmaz.
- Eski SMS-bit kontrolü bu IDR0 ile Unsupported döndürür; bildirilen Security Violation ile birebir uyuşmaz. Bu fark donanım arızası diye yorumlanmadı. DUU1 aynı değerleri fresh okumalarla tekrar kod çözer ve ayrı build işareti gösterir.
- Yeni düzen doğrulayıcı, SMS=0 olan özel dalı yalnız **bildirdiğiniz exact IDR0/IDR1 çifti** için kabul eder; EXIDS, S1 desteği, sayımlar, kararlılık, global disable ve CPU-map sınırları denetlenir. Register'a bu ID değerleri yazılmaz. Context dizisi başlangıcı bank sabitlemesiyle değil, native HAL'ın IDR1 formülünden hesaplanır: bu çift için offset0x80000,61 bank. Readback bank indeksini canlı S2CR'den alır.

## Sonuç ekranı ve dönüş

- `HALIOMMU LOADIMAGE`: gerçek LoadImage sonucu veya NOT_STARTED. `HALIOMMU ENTRY`: gerçek sağlayıcı StartImage sonucu veya NOT_STARTED. DEPEX/section/path hatası entry dönüşü diye yazılmaz.
- `HALIOMMU INIT ABI`: void init'in dönüş kodu değildir; protokol/tablo doğrulamasının sonucudur.
- `HAL UFS DOMAIN CHAIN`, raw create/cfg/attach ve completed0..3: gerçekten yapılan çağrılar; yapılmayanlar `FFFFFFFF`.
- `IOMMU NATIVE/IDENTITY READBACK`: doğrulama gerçekten çalışmadıysa NOT_STARTED; önceki PASS tekrar basılarak taklit edilmez.
- `UFS LOAD/START PATH STATUS`: yükleme yolu; yalnız başarılı entry gerçek disk kanıtı değildir.
- `UFS READ ACCESS`, `BLOCK IO COUNT`, `GPT`, win/ESP: gerçek okunmuş sonuçlar.

`START ...` veya `HAL ... CALL (pending)` son satırda kalırsa çağrı dönmemiştir; PASS sayılmaz. Sonuçlardan sonra kasıtlı halt vardır. Ekranın/videonun tamamını kaydedin.

Geri dönüş: güç tuşunu10–20sn tutun. Fastboot için güç+ses kısma; mevcut TWRP için güç+ses açma, Mi logosunda gücü bırakıp ses açmayı tutma. Her hata durumunda dönüş garantisi yoktur. Orijinal boot/TWRP/GPT yedeklerini koruyun; bu prosedür flash/restore komutu içermez.

## Bilgisayarda yeniden üretme

Önceki pinlenmiş Linux EDK2/toolchain ortamında, kaynak commit'ini checkout ettikten sonra:

```sh
export DAVINCI_SYSTEM_NASM=1
bash Resources/PreFinal/build_prefinal.sh /path/original-boot_clean.zip /path/NEW-output
python3 Resources/PreFinal/validate_artifacts.py --backup /path/original-boot_clean.zip --directory /path/NEW-output
python3 Resources/PreFinal/audit_prefinal.py /path/NEW-output/DAVINCI_PREFINAL.fd
```

Derleme çıktısının adı hâlâ `davinci-prefinal-experimental.img`; teslimatta aynı dosya `davinci-ufs-unblock-experimental.img` adıyla bulunur. Header v1/page4096/adresler ve14 DTB aynı orijinal boot yedeğinden doğrulanır; eski davinci.sh kullanılmaz. BootShim, PrePi kaynağı ve DeviceMemoryMap bu görevde değiştirilmedi. Yeni FD build timestamp'i nedeniyle kaynaklardan yeniden derleme aynı hash'i garanti etmez; aynı FD/shim/backup ile yeniden paketleme birebir doğrulanır.

PE doğrulayıcısına FREEFORM profil adı tanıtıldı; ARM64 varsayılan W^X ve4K alignment koşulları aynen korunur. İlk denemedeki "Profile type FREEFORM invalid" sessizce geçilmiş başarı sayılmadı; son build günlüklerinde bu hata yoktur. `native_hal_probe.py` gerçek HAL rutinlerini RAM'de sahte allocator/register servisleriyle yürütür; telefon testi değildir.
