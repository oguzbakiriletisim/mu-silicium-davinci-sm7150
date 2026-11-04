# Davinci Windows 11 ARM64 kurulum hazırlık kiti

**Dağıtım şu an engelli.** Bu ZIP sürücüleri eksik bir Windows kurulumunu telefona yazmaz. Staging denetimi, gerçek GPT kimliği doğrulaması, küçük EFI staging ve PC'de yeni offline BCD hazırlığı kullanılabilir.

Bu ortamda kullanıcının yaklaşık25,4GB Windows staging'i/ESP VHD'si bulunmuyor. Gerçek Windows10 üzerinde bcdedit/Storage/Hyper-V entegrasyonu doğrulanmadı. Testler Python/C ve Linux PowerShell sözdizimi/mock/ret akışlarıdır.

1. Python3.10+ ile `python prepare_windows.py inspect --staging 'C:\Mi9T_Win11_Staging'` çalıştırın. Kaynak salt okunur; ARM64 PE ve beş registry hive base-block kontrol edilir. Tam Windows metadata/sürüm/imza kanıtı değildir.
2. `preflight.py gpt` ile aynı LUN'a ait ilk/son1MiB GPT yedeklerinin CRC ve GUID'lerini okuyun. `--primary-gpt`, `--secondary-gpt`, **gerçek** `--sector-size` ve **tam LUN** `--disk-size-bytes` zorunludur. Sayı tahmin etmeyin; win bölüm boyutunu disk boyutu yerine kullanmayın. Yedek GPT'yi canlı boot testi GUID/LBA/boyutlarıyla karşılaştırın. Eski yedek güncel düzen sayılmaz.
3. Gerçek kimliklerle `preflight.py check --staging ... --primary-gpt ... --secondary-gpt ... --sector-size ... --disk-size-bytes ... --disk-guid ... --windows-guid ... --esp-guid ... > preflight.json` çalıştırın. Gerçek ESP yoksa `--esp-guid` vermeyin. Geçerli denetim exit3/deployment_allowed=false; girdi hatası exit2 döndürür. `--drivers` yalnız aday SYS/INF/CAT envanteri/ARM64 biçimi çıkarır; doğrulanmış uyumlu UFS paketi üretmez.
4. `prepare_windows.py stage-efi` yalnız yeni PC kullanıcı klasörüne küçük EFI dosyalarını hazırlar. Gerçek hedefler Windows Storage'da uygun GPT GUID/FAT32 ESP/NTFS bölüm olarak zaten görünüyorsa `plan`/`prepare-efi` kullanılabilir. Bu şartları **PC VHD'sinin harf/GUID'leriyle telefon için sağlanmış saymayın**. Tüm komutlar `WINDOWS_TOOLS_README_TR.md` içindedir. BCD yeni PC klasöründe `/store` ile oluşturulur; host sistem BCD'sine/hedef ESP'ye yazılmaz.
5. `Deploy-AfterApproval.ps1` ayrı `-ApproveDeployment`, disk/Windows/ESP GUID eşleşmesi ister. Bu sürümde onay ve düzgün GUID'lerle bile **koşulsuz durur**: güvenilir telefon aktarımı, doğrulanmış SM7150-AA UFS boot-start paketi ve yeterli ACPI yoktur. JSON'da deployment_allowed=true yazmak bunu açmaz. Bu dosya kurulum tamamlanınca çalışan bir dağıtıcı gibi sunulmaz.

## Hedef bölüm planı ve eksikler

- Mevcut `win` ext4; doğrudan Windows/NTFS dosya kopyası yapılamaz. Bu kit format/GPT değiştirme/NTFS'e çevirme komutu içermez. Gerçek GUID/extent/byte boyutu önce salt okunur doğrulanmalı. /dev/block/sda32, eski51,57GiB/yeni55,37GB değerleri otomatik kimlik sayılmaz.
- PC'deki512MB FAT32 ESP VHD telefon ESP'si değildir. Gerçek ESP yoksa güvenli boş alan/bölümleme/kurtarma planı ayrıca gerekir; VHD bütün disk veya telefon bölümü üzerine yazılmaz.
- Veri/Android userdata kaybı ve GPT yedeklerinin güncelliği ayrı değerlendirilmelidir. Mevcut yedekler değiştirilmez. Bu kit geri dönüşte yeniden bölümleme veya restore komutu çalıştırmaz.
- NTFS hazırlığı olsa bile metadata koruyan gerçek bir apply/aktarım yolu gerekir. Explorer staging'i eksiksiz Windows kurulumu veya uygulanabilir WIM sayılmaz. ACL/hardlink/reparse ve registry bütünlüğü doğrulanmadan düz kopyalama yoktur.
- UFS boot-start SM7150-AA ARM64 INF/SYS/CAT, katalog üyeliği/imza, StartType=0/service eşleşmesi, ACPI namespace/DMA/power/clock/PEP sözleşmesi ve kernel devralması eksiktir. `DRIVER_REPORT.json` bunu açıkça kaydeder. Başka SoC/raphael/sweet sürücüsü eklenmedi.
- Pre-final izolasyon firmware'i ACPI/Boot Manager çalıştırmaz; test başarılı olsa bile bunu doğrudan Windows başlatıcı olarak kullanmayın. Normal profildeki ACPI eksikleri çözülmeden OS kurulumuna geçilmez.

Kurtarma: bu PC araçları telefon bölümlerine yazmaz. Staging, orijinal boot/TWRP, iki GPT yedeği ve Windows hazırlık çıktılarını ayrı tutun. İmaj testinin güç/Fastboot/TWRP dönüşü A paketindedir. Bir sonraki fiziksel testin başarılı olması, bu eksik sürücü ve kurulum yolunu kendiliğinden tamamlamaz.
