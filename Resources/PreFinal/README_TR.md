# Davinci: tek deneysel boot testi ve Windows hazırlığı

Başlangıç: `8bfaa630b6b6d3efa293982b5e2cc60507458a2f`.
Kullanıcı önceki `f1db62fc…` PrePi imajının gerçek Mi 9T'de geçici Fastboot başlatma/BootShim/SEC/PrePi/ekran başarısını bildirdi. Bu başarı kabul edildi; yeni DXE/UFS imajının fiziksel testi yapılmadı.

**Bu teslimat tam HALIOMMU/UFS düzeltmesi değildir; pre-final başarı ölçütleri henüz karşılanmış sayılmaz.** Yeni Android boot imajı gerçektir. Koşullu UFS okuma yolu içerir; sadece DXE mesajı gösteren bir imaj değildir. Ancak mevcut eşleme çevrilmiş, eksik veya belirsizse UFS çalıştırılmaz. Bu durumda yeni donanım bilgisi/geliştirme gerekir; bir sonraki testten sonra Windows'a geçiş garanti edilemez.

## A: imajın gerçek davranışı

1. Önceki yedekten türetilen aynı Android v1 header/page4096/adres/DTB zinciri ve aynı BootShim kullanılır. `davinci.sh` kullanılmaz. PrePi halt kaldırılır **yalnız yeni opt-in profilde**; `PREPI: PASS; NEXT DXE` mesajı yazılır.
2. DXE Core, PCD/Env/CPU/GIC/metronome/timer ve kaynaklı `PreFinalDxe` çalışır. Giriş gerçekten ulaşırsa DXE PASS yazılır. Buraya gelmeden kalırsa DXE başarısı yoktur.
3. `0x15000000` SMMU bölgesinde **yalnız okuma**: IDR0(+0x20), IDR1(+0x24), non-secure CR0 alias(+0x400), SMRn(+0x800+4*n), S2CRn(+0xC00+4*n). Bunlar Arm SMMUv2 register yerleşimidir; IDR0/1 adresleri gerçek HAL accessor disassembly'siyle de eşleşir. NumSMRG>128/0, SMS yokluğu, EXIDS veya değişen CR0 kabul edilmez. UFS0/ARID0 → SID0x300 eşlemesi pinlenmiş davinci DAL tablosundan gelir; farklı telefondan alınmaz.
4. **Dar izin kapısı:** ihtiyatlı SID0x300..0x30F aralığının tamamında yalnız bir aktif SMR eşleşmesi ve S2CR TYPE=1 açık bypass olmalı; CR0.CLIENTPD=0 olmalı. Çevrilmiş bir context-bank, SCTLR.M=0 gibi görünse bile bu sürümde kabul edilmez. Eşleşmemiş stream'in varsayılan bypass davranışına güvenilmez. Bu konservatif aralık ham firmware `NumberIDs=16` değerinin OS count-minus-one yorumu değildir; ARID0 dışındaki stream'lerin gerçekten kullanıldığını kanıtlamaz. Context-bank değeri atanmaz, SMMU register'ı yazılmaz.
5. Kapı geçmezse `EFI_SECURITY_VIOLATION` (0x800000000000001A) veya `EFI_UNSUPPORTED` ile **UFS/DMA başlatılmaz**. Snapshot son durum ekranında kalır. Bu beklenen bir başarısızlık seçeneğidir; UFS düzeldi denmez.
6. Kapı geçerse, pinlenmiş davinci SMEM/DAL/HWIO/ChipInfo/PlatformInfo/ULog/CmdDb/Npa/Rpmh/Pdc/Clock ikilileri özgün DEPEX'leri kontrol edilerek yüklenir. Her `LoadImage/StartImage` dönüşü gerçek EFI status olarak yazılır. Başarısız veya eksik bağımlılık UFS'yi durdurur. `START X` satırında kalması X girişinin dönmediği anlamına gelir. İşlem içi takılmadan yazılımsal timeout ile güvenilir kurtarma iddia edilmez.
7. SMMU kapısı yeniden geçerse **değiştirilmemiş** UFSDxe (`0576f04f…`) yüklenir. Stub korunur; kaldırılmış native IOMMU kurulumunu yaptığını iddia etmeyiz. Bu yol yalnız bootloader'dan miras kalan açık identity/bypass durumuna dayanır. Böyle bir durum yoksa kaynaklı HAL create/configure_bypass/attach düzeltmesi hâlâ gereklidir. Yeni snapshot sonrasında Block I/O taranır. `UFS LOAD/START PATH STATUS=SUCCESS` tek başına UFS PASS değildir; UFS READ ACCESS için gerçek başarılı ReadBlocks dönüşü gerekir.
8. Yalnız yerel, medyası mevcut, whole-LUN Block I/O handle'larında ReadBlocks yapılır. 512/4096 sektör, IoAlign, sınırlar, iki GPT header CRC'si/karşılıklı LBA/disk GUID, iki entry array CRC'si ve birebir eşitliği, bölüm GUID benzersizliği ve çakışmasız extent'ler kontrol edilir. Bozuk GPT onarılmaz. Her LUN ayrı raporlanır; GPT'siz boot LUN bulunması ana veri LUN'u GPT'sini otomatik başarısız yapmaz.
9. `win` etiketi ve ESP **type GUID** adayları; gerçek disk/bölüm GUID, entry number, LBA, byte boyutu gösterilir. `FOUND` etiketi Windows kurulu veya dosya sistemi mount edildi demek değildir. İlk sektör NTFS/FAT32 imzası ve 4K sektörde ext magic bilgi amaçlıdır; tam dosya sistemi doğrulaması değildir. `win` adayının tek olması ve beklenen GUID/boyutla kullanıcı tarafından eşleşmesi gerekir. /dev/block/sda32 ve geçmiş boyut tahminleri firmware'e sabitlenmez.
10. Sonuç ekranından sonra koşulsuz döngü. BDS/Boot Manager/Windows başlatılmaz. HALIOMMU dummy client, PartitionDxe, FAT, kalıcı variable sürücüsü, USB depolama ve SCM listener sağlayıcısı bu profilde yoktur. Kaynak denetleyicide WriteBlocks/Erase/Format/GPT repair/partition Reset çağrısı yoktur. Kapı açılırsa vendor UFS ve clock başlatması mevcut sürücünün normal donanım işlemlerini/DMA'sını gerçekleştirir; kapalı ikilinin tüm iç işlemleri için fiziksel yazmasızlık veya güvenlik garantisi verilemez.

**HALIOMMU sonucu:** `LocateProtocol` sonucu gerçek varlık kontrolüdür. `HALIOMMU INIT: NOT RUN` bilerek yazılır: orijinal provider girişindeki SDC/USB dummy attach işlemleri bu testte etkinleştirilmez. Protokol varlığı PASS olsa dahi domain hazır sonucu çıkarılmaz. Bu teslimat kullanıcının native HAL başlangıcı başarı ölçütünü karşılamaz; bunu gizlemek için sahte PASS veya yeni SMMU patch'i yoktur.

## Uygulama: yalnız kullanıcı çalıştırır

Zip'i açın; Windows PowerShell'de paketin klasörüne geçin. Önce `SHA256SUMS.txt` ile imaj hash'ini karşılaştırın:

```powershell
Get-FileHash .\davinci-prefinal-experimental.img -Algorithm SHA256
```

Telefonun gerçekten davinci olduğundan ve önceki geçici testte kullanılan aynı cihaz/bootloader olduğundan emin olun. Orijinal boot/TWRP/GPT yedeklerini saklayın. İlk fiziksel komut:

```powershell
fastboot boot .\davinci-prefinal-experimental.img
```

Bu oturumda ADB/Fastboot çalıştırılmadı. Önceki geçici başlatma kullanıcı tarafından doğrulandı; **yeni imajın kabulü/önyüklemesi ayrıca denenmemiştir**. Auth/unsupported/hata durumunda durun; flash fallback yoktur. Ekranı mümkünse baştan videoya alın. Sonuçlarda GUID/extent satırlarını ve son ekranı kaydedin. `IOMMU INHERITED BYPASS: FAIL` halinde başka ayar/patch/imaj denemeyin.

Normal dönüş: güç tuşuna 10–20 saniye basılı tutun. Fastboot için güç+ses kısma; mevcut TWRP için güç+ses açma, Mi logosunda gücü bırakıp ses açmayı tutma. Bunlar standart tuş yöntemleridir; her hata durumunda dönüş garantisi değildir. İmaj kasıtlı halt eder; USB/menü/Android'e otomatik dönüş beklenmez. Bölüm yazılmadığı için bu prosedür bir geri-flash komutu içermez.

## Derleme / paketleme

Önceki pinlenmiş toolchain/submodule ortamında:

```sh
export DAVINCI_SYSTEM_NASM=1
bash Resources/PreFinal/build_prefinal.sh /path/boot_clean.zip /path/NEW-output
PYTHONPATH=/path/uefi_firmware python3 Resources/PreFinal/audit_prefinal.py /path/NEW-output/DAVINCI_PREFINAL.fd
```

FD tabanı0x9FC00000, boyutu0x300000 ve BootShim sabitleri önceki fiziksel başarılı porttan gelir; Android header alanları orijinal yedekten doğrulanır. Yeni paketçi için açık `--profile prefinal` gerekir; varsayılan eski halt profili korunur. Derleme timestamp'leri nedeniyle kaynaklardan tekrar derlemek aynı hash'i garanti etmez. Aynı FD/shim/backup ve Python/zlib sürümüyle paketleme birebir yeniden üretilebilir; teslimattaki roundtrip denetimi bunu kontrol eder.

## B: Windows kurulum hazırlık paketi

Bu kit **bugün telefon üzerine Windows dağıtan bir kurucu değildir**. Kullanıcının 25,4 GB staging'i ve ESP VHD'si bu ortamda bulunmadığından yerel gerçek dosyalar üzerinde test edildiği iddia edilmez. Var olan araçlar yeniden kullanılır; Windows dosyaları indirilmez/telefona kopyalanmaz.

1. Python3.10+ ile `python prepare_windows.py inspect --staging 'C:\Mi9T_Win11_Staging'`: üç ARM64 PE, beş registry base-block/sequence/checksum kontrolü. Windows 11 sürümü, imza güveni, ACL/hardlink/reparse metadata ve eksiksiz kurulum doğrulanmış sayılmaz.
2. GPT yedeklerinden gerçek kimlikleri öğrenmek için (sayıları **gerçek LUN verilerinden** doldurun; örnek boyut/sector seçmeyin):

```powershell
python preflight.py gpt --primary-gpt .\gpt-first-1MiB.bin --secondary-gpt .\gpt-last-1MiB.bin --sector-size $ActualSectorSize --disk-size-bytes $ActualLunBytes
```

İki dosya aynı LUN'un tam ilk/son1MiB yedeği olmalı. Sektör ve tüm-LUN byte boyutu zorunlu; Windows bölüm boyutunu disk boyutu diye kullanmayın. Yedek eskiyse canlı düzeni ispatlamaz. Çıktıdaki GUID'ler yeni boot ekranındaki GUID/LBA/boyutla eşleşmeden ilerlemeyin.

3. Gerçek GUID'lerle bütün ön denetim (ESP yoksa `--esp-guid` vermeyin):

```powershell
python preflight.py check --staging 'C:\Mi9T_Win11_Staging' --primary-gpt .\gpt-first-1MiB.bin --secondary-gpt .\gpt-last-1MiB.bin --sector-size $ActualSectorSize --disk-size-bytes $ActualLunBytes --disk-guid $ActualDiskGuid --windows-guid $ActualWinGuid --esp-guid $ActualEspGuid > preflight.json
```

Geçerli rapor **exit3/deployment_allowed=false** üretir; girdi hatası exit2. Bu hata gizlenmez. `--drivers` isteğe bağlı aday envanteri çıkarır; x64 SYS reddedilir, ARM64 SYS/INF/CAT varlığı boot-start/SM7150-AA uyumluluğu veya CAT üyeliği kanıtı yapılmaz.

4. `prepare_windows.py stage-efi` ile yalnız yeni PC kullanıcı klasörüne küçük EFI/font/resource dosyaları hazırlanır. Gerçek hedef bölümler Windows Storage'da doğru GPT GUID'leri, FAT32 ESP ve NTFS Windows olarak görünmüyorsa BCD `plan`/`prepare-efi` durur. Telefon Fastboot cihazı olarak görünüyorsa PC diski değildir; harf atayıp PC diskini telefon sanmayın. Ayrıntı `WINDOWS_TOOLS_README_TR.md` içindedir. Offline BCD her zaman yeni PC klasöründe `/store` ile oluşturulur; host sistem BCD'sine dokunmaz. PC ESP VHD'sinin GUID/harflerini telefonunkiler diye vermeyin; VHD'ye bağlı BCD hedef telefona taşınabilir sayılmaz.
5. Ayrı dağıtım giriş noktası `Deploy-AfterApproval.ps1`, açık `-ApproveDeployment` ve disk/Windows/ESP GUID eşleşmesi ister. Bu sürümde bütün kontroller/onay verilse bile eksik native sürücü/ACPI/aktarım yolu nedeniyle **koşulsuz durur**; düzenlenebilir JSON'da true yazmak korumayı kaldırmaz. Onay kurulum kanıtı değildir.

### Gerçek bölüm ve Windows planı

- Mevcut `win` ext4. Windows ext4 üzerine uygulanamaz. Şu an format/GPT/deploy komutu yoktur. Önce canlı salt okunur GPT kimliği, tüm-LUN ve bölüm byte boyutları, eski yedeklerin geçerliliği ve kayıp userdata durumu netleşmelidir. Önemli kullanıcı verileri ve kurtarma dosyaları ayrı saklanmalıdır.
- Telefon GPT'sinde gerçek ESP varsa kimliği/type/extent ve FAT32 içeriği doğrulanır. Yoksa 512MB PC ESP VHD telefon ESP'si değildir; yeni ESP için boş/saklanabilir alan ve yeniden bölümleme/geri dönüş planı ayrıca geliştirilip açık onaylanmalıdır. Bu kit ESP oluşturmaz.
- Gerçek Windows bölümü NTFS olarak hazırlanabilse bile, hedefe dosya/metadata koruyan güvenilir apply/aktarım yolu yoktur. Staging yalnız Explorer düz kopyasıysa WIM/FFU benzeri uygulanabilir kaynak veya ACL/hardlink/reparse/registry doğrulaması gerekir. ext4 üzerine NTFS dosya kopyası ya da PC VHD'yi sda32'ye yazma önerilmez.
- Doğrulanmış SM7150-AA ARM64 boot-start UFS INF/SYS/CAT + ACPI kaynak/DMA/power sözleşmesi yok. SM7180/SM8150/raphael/sweet dosyası sürücü yerine konulmadı. UEFI Block I/O, Windows kernel depolama desteğinin yerine geçmez.
- Pre-final izolasyon profili Windows için uygun ACPI/UEFI değildir; kasıtlı olarak ACPI platform/Boot Manager dispatch yoktur. Normal profildeki eksik DSDT ve geçersiz RAW IORT/CSRT checksum/power sözleşmeleri hâlâ engeldir. CPU-only APIC/GTDT/FADT/PPTT/DSDT derlenebilmesi tam Windows platformu değildir. HAL firmware DAL/IORT tablosu Windows IORT tablosu diye kopyalanmadı.
- Windows Boot Manager aşaması için gerçek UEFI FAT32 ESP/BCD/NTFS erişimi, yeterli UEFI bellek/runtime/ACPI/interrupt/timer ortamı; kernel aşaması için boot-start UFS, IOMMU, PEP/clock/power ve kaynak eşleşmesi gerekir. GOP'un önceki fiziksel başarısı Windows görüntü devralmasını ispatlamaz.

Önceki fiziksel PrePi başarısı korunmuştur. Yeni DXE/UFS/GPT sonucu kullanıcı tarafından bildirilecek; doğrulanmış bu sonuçlar olmadan Windows dağıtımı başlatılmayacak. Bu eksikler nedeniyle görevdeki tam pre-final ve direkt Windows kurulum hedefleri **henüz tamamlanmış değildir**.
