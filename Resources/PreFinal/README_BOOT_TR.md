> Bu belge f3016dd4 öncesi paket içindir. DUU1 HAL/UFS sürümü için `Resources/UfsUnblock/README_TR.md` kullanın; HAL artık yalnız koşullu ve kontrollü yüklenebilir.

# Mi 9T / davinci — deneysel pre-final boot testi

**Yeni imaj fiziksel olarak denenmedi. Tam HALIOMMU/UFS düzeltmesi değildir. Windows kurulumu yapmaz.** Önceki PrePi/ekran/geçici Fastboot başarınız başlangıç kabul edildi.

Paketteki `SHA256SUMS.txt` ile karşılaştırın:

```powershell
Get-FileHash .\davinci-prefinal-experimental.img -Algorithm SHA256
fastboot boot .\davinci-prefinal-experimental.img
```

Komutu yalnız daha önce test ettiğiniz aynı davinci üzerinde kendiniz çalıştırın. Bu işlem kalıcı flash komutu içermez. Yeni imajın bootloader kabulü garanti edilmez; hata durumunda flash fallback uygulamayın.

- `PREPI: PASS` → erken kod; `DXE: PASS` → kaynaklı tanılama sürücüsünün gerçek DXE girişi.
- `HALIOMMU … PRESENCE ONLY` gerçek LocateProtocol kodudur. `HALIOMMU INIT: NOT RUN`: native dummy driver bilinçli olarak yoktur; HAL başlatıldı sayılmaz.
- `IOMMU INHERITED BYPASS` canlı, salt okunur SMMU kontrolüdür. SID0x300..0x30F için tekil açık TYPE=bypass eşlemesi yoksa `FAIL` verir ve **UFS/DMA başlatmaz**. `0x800000000000001A` EFI_SECURITY_VIOLATION; `0x8000000000000003` EFI_UNSUPPORTED. Context-bank/register değerleri tahmin edilmez veya yazılmaz.
- Kapı geçerse özgün bağımlılıklar gerçek DEPEX/LoadImage/StartImage kodlarıyla yüklenir. `START X` satırında kalması X girişinin dönmediğini gösterir; başarılı dönüş gibi yorumlamayın.
- `UFS LOAD/START PATH STATUS` tek başına UFS PASS değildir. `UFS READ ACCESS` ancak gerçek başarılı ReadBlocks varsa PASS olur. Block I/O COUNT yalnız uygun dahili whole-LUN medyayı sayar.
- `GPT: PASS` en az bir LUN'da primary+backup header/array CRC, disk kimliği ve çakışmasız GUID/extent kontrolü geçti demektir. GPT'siz boot LUN'lar ayrıca reddedilir; GPT onarılmaz.
- `WINDOWS PARTITION: FOUND` yalnız `win` etiketli GPT adayı; `ESP: FOUND` yalnız doğru type GUID adayıdır. Ekrandaki gerçek disk/bölüm GUID, LBA ve byte boyutunu kaydedin. Bunlar NTFS/FAT32 mount veya Windows boot kanıtı değildir. Birden fazla win adayı veya geçmiş yedekle uyuşmazlık varsa durun.
- Sonunda kasıtlı `HALTED` döngüsü vardır. Windows, UEFI menüsü veya otomatik Android dönüşü beklenmez.

Ekranı başlangıçtan videoya alın; son ekran ve GUID/extent satırlarının fotoğrafını saklayın. Native HAL init NOT RUN kaldığı için bu imajın başarılı bir okuma yapması bile görevdeki bütün HAL başarı ölçütlerini tamamlamaz.

**Dönüş:** güç tuşunu10–20sn tutun. Fastboot: güç+ses kısma. Mevcut TWRP: güç+ses açma; Mi logosunda gücü bırakıp ses açmayı tutma. Her arıza durumunda dönüş garantisi yoktur. Orijinal boot/TWRP/GPT yedeklerini koruyun; kritik bootloader veya bölüm tablosunu değiştirmeyin.

Kaynakta WriteBlocks/Erase/GPT repair yoktur; PartitionDxe/BDS/FAT/SCM listener sağlayıcısı yüklenmez. Kapı geçerse vendor UFS/clock sürücülerinin normal donanım başlatması/DMA'sı çalışır. Kapalı ikilinin bütün iç işlemleri için fiziksel güvenlik/yazmasızlık garantisi yoktur.

Tam davranış, sınırlar ve PC'de yeniden üretme komutları `TEKNIK_NOTLAR_TR.md`; gerçek imaj parametreleri `MANIFEST.json`; bilgisayar kontrolleri `evidence/` altındadır. Bilgisayar testleri donanım başarısı değildir.
