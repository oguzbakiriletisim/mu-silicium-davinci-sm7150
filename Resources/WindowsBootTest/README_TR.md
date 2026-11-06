# Windows Boot Manager — geliştirme teslimatı

**Telefon test paketi değildir.** Bu ZIP'teki firmware FD ve FAT32 yalnız host
fixture'ıdır; Microsoft EFI içermez. FD, Android boot.img değildir. Flash veya
fastboot boot girdisi olarak kullanılmamalı. Gerçek Boot Manager çalıştırılmadı;
telefonda yeni UFS/GPT/ESP/NTFS işlemi yapılmadı.

## Bu teslimatta çalışan bilgisayar tarafı

- Ayrı WINDOWS_BOOT_TEST profili: RAM-only BlockIo→DiskIo→FAT32/SFS→BDS loader.
- Gerçek Microsoft dosyaları mevcutsa bunları değiştirmeden küçük RAM FAT32
  dosya sistemine hazırlayan araç. Windows/ESP VHD'si veya telefon bölümü değildir.
- GOP kaynak düzeltmeleri, kapalı storage ACPI geliştirme SSDT'si, UFS/FV audit.
- 105 host testi, WBT DEBUG ve ayrı PREFINAL regression build günlükleri.
  Test sayısı fiziksel veya Windows başarı ölçütü değildir.

## Windows bilgisayarında somut sonraki işlem

ZIP'i çıkarın. Windows staging VHD'niz W: ise, PowerShell'de paket kökünden:

```powershell
.\Resources\WindowsBootTest\Prepare-TargetA.ps1 -Staging 'W:\' -OutputDirectory "$env:USERPROFILE\Desktop\davinci-target-a"
```

Python3.9 veya üstü gerekir (`python --version`). Başka harfteyse yalnız -Staging'i gerçek
staging köküne göre değiştirin. Çıktı klasörü yeni olmalı; betik üzerine yazmaz.
Yalnız bilgisayarınızdaki dosyalar okunur, USERPROFILE altında yeni dosyalar
oluşturulur. Disk bağlama, bölümleme, formatlama, registry/system-BCD veya
telefon komutu yoktur. PowerShell çalıştırma politikası burada değiştirilmez.

Betik gerçek bootmgfw.efi için Microsoft Authenticode Valid ister, ARM64 PE'yi
kontrol eder, hash'i FAT'a kopyalanan dosyanın hash'iyle eşler. Aynı input'tan
bootaa64.efi kopyası, varsa Latin/en-US boot font/MUI/resource dosyaları eklenir. Hiçbir SYS/
INF dosyası değiştirilmez. Varsayılan BCD yoktur; ilk hedef için Windows'un
kendi BCD hatası olası sonuçtur, garanti değildir. Mevcut host-VHD BCD'sini
telefona aitmiş gibi kullanmaz. İstenirse -Bcd yalnız kopyalar; GUID'leri düzeltmez.

Çıktı `davinci-target-a-input.zip`: efi-fat32.img, FAT_MANIFEST.json ve
AUTHENTICODE.json. **Bu bir Android boot imajı değildir.** Firmware derlemesine
ve ARM64 UEFI host entegrasyon testine girdi olacaktır. Gerçek Microsoft dosyaları
bu çalışma ortamında yoktu; bu yüzden dağıtılan fixture ile karıştırmayın.

## Kaynak profilini yeniden derleme (Linux/EDK2 ortamı)

Kaynak repo ve sabit altmodüller gerekir. Toolchain bilgisi evidence/TOOLCHAIN.txt.
Mevcut proje toolchain kurulumuyla, kaynak kökünde:

```bash
bash Resources/WindowsBootTest/build_windows.sh /tmp/wbt-fixture --fixture
# Gerçek staging erişilebiliyorsa ayrı, yeni çıktı:
bash Resources/WindowsBootTest/build_windows.sh /tmp/wbt-real --staging /path/to/staging
```

İkinci komutun çalışması burada denenmedi; gerçek EFI kaynakları yok.
Varsayılan ELF/FD adresleri büyütülmez; payload3MiB FD'ye sığmazsa build durmalıdır.
Firmware volume'a36MiB FAT, sıkıştırılmış RAW olarak paketlenir; gerçek FAT RAM'de
FV açılınca bulunur. Büyük FFS/SECTION başlıklarını kontrol eden zero-copy C yolu
host audit ile gerçek oluşturulan FV'ye karşı sınandı. RAM bütçesi/Boot Manager
allocation davranışı fiziksel veya EFI host'ta ölçülmedi.

Üretilen firmware `.fd` dosyası yalnız geliştirme çıktısıdır. Betik Android imajı
paketlemez, telefonu başlatmaz ve fiziksel hazırlık bayrağı üretmez.

## Durum ve inceleme

- READINESS_TR.md: Hedef A/B engelleri ve tek sonraki adım.
- PROTOCOL_MATRIX.md: modül/protokol/gerçek çalışma ayrımı ve donanım etkileri.
- evidence/RESULTS.json: net durum; physical_ready=false, target_a=NOT ACHIEVED.
- evidence/FV_AUDIT.json: gerçek FD SHA, PE/DEPEX/FAT/ACPI envanteri.
- evidence/MODULE_INVENTORY.json: kaynak INF'lerle gerçek FV eşleşmesi.
- SHA256SUMS.txt / SOURCE_COMMIT.txt / changes.diff / commits.patch: teslim
  kökünde bulunur. Kaynak dalı davinci-windows-boot-test; eski araştırma dalı korunur.

İleride fiziksel IMG teslim edilmeden önce gerçek Microsoft FAT girdisi,
ARM64 UEFI entegrasyon testi, GOP/runtime/bellek koşulları ve eksik güvenilir
UFS sağlayıcısı değerlendirilmelidir. Bugün yeni telefon boot komutu verilmez.
