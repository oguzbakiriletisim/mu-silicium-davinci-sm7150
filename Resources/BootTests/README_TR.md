# Davinci: ilk UEFI giriş deneyi — geçici RAM boot adayı

**Bu imaj telefonda denenmedi. Android boot biçimi, BootShim ve paket bütünlüğü bilgisayarda kontrol edildi. Davinci bootloader'ınızın `fastboot boot` komutunu veya imzasız içeriği kabul ettiği doğrulanmadı. Kalıcı flash yapılmamalıdır.**

Bu deney Windows/Boot Manager/UFS testi değildir. Amaç yalnız UEFI SEC/PrePi giriş mesajını görmektir. İmaj, mesajdan sonra koşulsuz döngüde durur; DXE/UFSDxe/HALIOMMU sürücüleri başlatılmaz. Mevcut platformun erken CPU/watchdog/framebuffer işlemleri korunur; yeni DMA veya SMMU register yazması yoktur. Fiziksel güvenlik garantisi verilmez.

## Üretilen dosya

`davinci-prepi-halt-experimental.img`

- Boyut: **4.182.016 bayt**.
- SHA-256: **`f1db62fc7a0f1bb98687e41b8b3d8257b4820126d00209c3540dce6ff76a5123`**.
- Kullanılan FD: 3 MiB; SHA-256 `af82208de2c01347369ab85d0bd5550f4ea3d8c439cfea349ec135aee06e5442`.
- BootShim: 144 bayt; SHA-256 `53d8b901cb9818850207c6ab30ce184212fd78d7a8eca029500ded9e84ab0adc`.
- Yeni imaj **AVB imzalı değildir** ve AVB footer içermez. Orijinal yedeğin artık geçersiz olacak hash/footer'ı kopyalanmadı. Stock vbmeta ile doğrulanmış sayılmaz. Bootloader açık olması kabul garantisi değildir.

## Yedekten okunan değerler

Kaynak `boot_clean.zip`: SHA-256 `a2039677bce239d44813d4c28825e04f38ce60be309639101fae45a1437575c5`.
İçindeki `boot_clean.img`: 134.217.728 bayt (128 MiB), SHA-256 `a25d36cb56d8ee3cc110dece98fee39e4ce9729c8eeeb0d007e8faf1723f2cda`.
ZIP ve yedek içerikleri değiştirilmedi. 128 MiB, bölüm yedeğinin uzunluğudur; geçici boot dosyasının da 128 MiB olması gerektiği anlamına gelmez.

| Alan | Gerçek yedek değeri / işlem |
|---|---|
| Magic / version | ANDROID!, v1 |
| Header size / page size | 1648 / 4096 |
| Kernel file offset | 0x1000 |
| Original kernel size | 15.720.488 bayt |
| kernel_addr | 0x00008000, korundu |
| ramdisk_size / ramdisk_addr | 0 / 0x01000000, korundu |
| second_size / second_addr | 0 / 0x00F00000, korundu |
| tags_addr | 0x00000100, korundu |
| recovery_dtbo size / offset | 0 / 0, korundu |
| OS version / patch | 10.0.0 / 2021-05, korundu |
| Board / cmdline / header padding | Orijinal byte'ları korundu |
| DTB konumu | Kernel gzip member'ından sonra concatenated FDT'ler; ayrı v2 dtb bölümü yok |
| Değişen header alanları | Yalnız kernel_size ve Android SHA-1 image ID |

Bu küçük adresler **header alanlarıdır**; bootloader'ın fiziksel kernel RAM adresinin 0x8000 olduğu söylenmiyor. Qualcomm yükleyici platform belleğine göre başka adres seçebilir. Orijinal Linux ARM64 header text_offset değeri 0x80000'dir; BootShim'in UEFI taşıma hedefi 0x9FC00000 ise mevcut `Resources/Configs/davinci.conf` değeridir. Bunlar aynı parametre değildir.

Orijinal gzip kernel member'ı 13.246.098 bayt, açılmış Linux Image 40.265.744 bayt; devamındaki ek 2.474.390 bayt ve **14 FDT** içerir. Bu ekin SHA-256 değeri `80343237651179447d50c2d0cefa08a398c3b50e3428a12415ce87f1638d5ec2` olarak aynen korundu. Başka depodan DTB eklenmedi veya repo `davinci.dtb` dosyasıyla değiştirilmedi.

Yedekte farklı SoC/model FDT'leri de bulunuyor; bunların hepsi davinci'ye uyumlu ilan edilmiyor. Aynı ekte SDMMAGPIE (qcom msm-id 0x16D) ve SDMMAGPIEP (0x16E) blokları vardır. Bu bloklardaki cont_splash rezervasyonu 0x9C000000 / 0x01800000 olup portun framebuffer rezervasyonuyla örtüşür. Hangi FDT'nin bu telefonda seçildiği veya panelin aktif kaldığı fiziksel olarak görülmedi. Header tek başına yedeğin üretici orijinalliğini/cihaz kimliğini ispatlamaz; dosya kullanıcının davinci yedeği olarak verilmiştir.

Orijinal AVB footer, image_size=0xF00000, vbmeta_offset=0xF00000, vbmeta_size=704 belirtir. İçindeki boot SHA-256 hash descriptor yedek verisiyle eşleşti. Gömülü vbmeta algorithm_type=0 (NONE); bu, cihazın bütün verified-boot zincirinin kapalı olduğu anlamına gelmez. Yeni kernel'e eski hash'i taşımak yanlış olurdu; bu paket bilinçli olarak footer'sız, imzasız ve yalnız geçici deneme adayıdır.

## Kaynakla doğrulanan yükleme yolu

```text
Android v1 boot container
  kernel = gzip(BootShim + first-entry DEBUG FD) + yedekten aynı DTB eki
  ABL kabul eder / doğru DTB'yi seçer / gzip'i açarsa:
    BootShim -> 0x9FC00000'e FD taşıma -> SEC/PrePi
      -> framebuffer debug mesajı -> sonsuz döngü
```

`BootShim/BootShim.S` source ve çalıştırılmış RAM testi taşıma/atlamayı doğrular. `Resources/Scripts/mkbootimg.py` ile bağımsız paket karşılaştırması yapıldı: tek fark boş ramdisk/second adreslerinin stock byte'larının korunmasıdır; mkbootimg onları sıfırlar. Mevcut `davinci.sh` doğrudan kullanılmadı: varsayılan base/page size ve ürettiği OS/patch değerleri yedekle aynı değildi.

Qualcomm ABL referansındaki gzip/DTB ve kernel entry akışı ayrıca incelendi:
https://github.com/Project-Aloha/mu_aloha_platforms/blob/d8aab0e2c272caeef5329716ff554c08cfebd6bd/Platforms/QcomModulePkg/Library/BootLib/BootLinux.c
Bu kaynak **sizin cihazınızdaki ABL'nin birebir kaynağı veya fastboot-boot destek kanıtı değildir**. Son yükleme/kabul davranışı doğrulanmamıştır.

## İlk komutlar ve deneme

Telefonu bilinen Fastboot moduna alın; önce tek ve doğru cihazın bağlı olduğunu kontrol edin. Aşağıdaki komutlar bu çalışma sırasında telefonda çalıştırılmadı.

Windows PowerShell, imajın bulunduğu klasörde ilk kontrol:

```powershell
Get-FileHash .\davinci-prepi-halt-experimental.img -Algorithm SHA256
```

Hash yukarıdakiyle aynı olmalı. Ardından mevcut çalışan Fastboot aracınızla:

```powershell
fastboot devices
fastboot getvar product
```

Bağlı cihazın Xiaomi Mi 9T / davinci olduğu belirsizse veya raphael/sweet gibi başka bir kimlik görülürse durun. Birden çok cihaz bağlıyken hedefi belirsiz bırakmayın.

**Tek yükleme denemesi**, yalnız geçici boot talebi:

```powershell
fastboot boot .\davinci-prepi-halt-experimental.img
```

Raw `.fd` veya `BootShim.bin` bu komuta verilmez. Komut boot/recovery/GPT yazma komutu içermez; ancak indirilen kodun fiziksel çalışma güvenliği garanti edilmez.

- `unknown command` / `not supported`: geçici boot desteği yok veya sunulmuyor; **durun**. Flash/recovery/vbmeta alternatifi bu pakette yoktur.
- Authentication/AVB/DTB/invalid image hatası: host çıktısını saklayın; başka header/adres denemeyin, verification bypass veya vbmeta değişikliği yapmayın.
- `Booting ... OKAY` yalnız bootloader'ın isteği kabul ettiğini gösterir; UEFI giriş kanıtı değildir.

Beklenen ekran yazıları:

```text
DAVINCI FIRST BOOT: PREPI REACHED
HALTED BEFORE DXE / UFS / HALIOMMU
HOLD POWER TO RESTART; NO UEFI MENU EXPECTED
```

Ekran burada **bilerek donar**. UEFI menüsü, Fastboot/ADB USB aygıtı veya Windows beklenmez. İlk mesajın fotoğrafı/video kaydı PrePi giriş kanıtı olabilir; UFS/Windows kanıtı değildir. Panel handoff doğrulanmadığı için siyah ekran başarı/başarısızlık aşamasını tek başına belirlemez. Böyle bir durumda sürekli farklı imaj denemek yerine host çıktısını ve gözlenen ekranı kaydedin.

## Fastboot / TWRP'ye dönüş

CPU kasıtlı döngüdeyken telefonda Fastboot USB servisi yoktur; PC'den `fastboot reboot` yanıtı beklemeyin.

1. Güç tuşunu yaklaşık 10–20 saniye tutarak zorla yeniden başlatmayı deneyin.
2. Fastboot için yeniden başlatırken **Güç + Ses Kısma** kombinasyonunu tutun; Fastboot ekranını bekleyin.
3. Mevcut recovery/TWRP için olağan Mi 9T yöntemi **Güç + Ses Açma**; Mi logosunda Güç'ü bırakıp Ses Açma'yı tutmaktır. Kullanıcının daha önce çalıştırdığı mevcut TWRP korunur; yeni recovery yüklenmez.

Bu tuş yöntemleri her arıza için kurtarma garantisi değildir. Yanıt alınamazsa rastgele kritik firmware/GPT yazmaları yapılmamalıdır. Bu RAM denemesi için boot_clean.img'yi flash ederek geri yükleme adımı verilmez; host komutu boot/recovery bölümünü değiştirmeyi istemez.

## Bilgisayarda yeniden üretim

Paketin FD ve BootShim dosyalarıyla **Windows Python'da da** yeniden paketleme yapılabilir; WSL veya 25 GB Windows dosyası kopyası gerekmez. Yeni çıktı adı kullanın:

```powershell
python .\davinci_boot_image.py --backup .\boot_clean.zip `
  --shim .\BootShim.bin --fd .\DAVINCI_FIRST_BOOT.fd `
  --output .\davinci-prepi-halt-repacked.img > .\REPACK-MANIFEST.json
Get-FileHash .\davinci-prepi-halt-repacked.img -Algorithm SHA256
```

Gzip timestamp=0 ve OS byte=255 sabittir. Deflate çıktısı Python/zlib sürümüne göre farklılaşabilir; aynı bileşenlerle yeniden üretim sonrası hash hesaplanmalıdır. Testte Python 3.12.14 kullanıldı. Paketçi mevcut dosyanın üzerine yazmayı reddeder.

Kaynaklardan DEBUG/BootShim derlemek için hazırlanmış EDK2 toolchain ortamında:

```sh
export DAVINCI_SYSTEM_NASM=1  # yalnız sistem NASM'ı önceki ortamda seçtiyseniz
bash Resources/BootTests/build_davinci_first_boot.sh \
  /path/to/boot_clean.zip /path/to/NEW-first-boot-output
```

Bu script `DAVINCI_FIRST_BOOT_HALT=1` opt-in profilini seçer; normal DEBUG varsayılanı 0'dır. İçeride kullanılan esas komutlar:

```sh
python3 Platforms/Xiaomi/davinciPkg/DeviceBuild.py TARGET=DEBUG \
  FD_BASE=0x9FC00000 FD_SIZE=0x00300000 FD_BLOCKS=0x300 \
  BLD_DEBUG_DAVINCI_FIRST_BOOT_HALT=1
clang --target=aarch64-linux-gnu -c BootShim/BootShim.S -o BootShim.elf \
  -DCREATE_FDT_POINTER=0 -DFDT_POINTER_ADDRESS=0 \
  -DUEFI_BASE=0x9FC00000 -DUEFI_SIZE=0x00300000
llvm-objcopy -O binary BootShim.elf BootShim.bin
```

Derleme zamanı firmware banner'ında yer aldığından kaynaklardan yeni FD derlemek aynı hash'i garanti etmez. Yeni FD/BootShim ile manifest yeniden üretilir.

## Yapılan doğrulamalar ve sınırı

- 68 otomatik test geçti, 0 skip. Yeni 9 test paket/header/AVB/FDT hata yollarını, gerçek BootShim taşımasını ve derlenen SEC'in durma döngüsünü kapsar.
- İlk-giriş DEBUG derlemesi ve normal DEBUG regresyon derlemesi başarılı.
- Derlenen CEntryPoint sonunda `bl CpuDeadLoop; b <aynı çağrı>` döngüsü disassembly ile doğrulandı. Normal DEBUG'da ilk-boot marker'ı yok; profil varsayılanı değişmedi.
- Yeni gzip içeriği BootShim+FD ile, ek DTB'ler yedekle birebir eşleştirildi; Android SHA-1 ID ve SHA-256'lar kontrol edildi.
- Kaynak ve FD içindeki mevcut UFSDxe hash'i değişmedi. Bu sürücü ilk-giriş profilinde çalıştırılmaz.
- Orijinal ZIP SHA-256 değişmedi. Telefona bağlanılmadı; ADB/Fastboot veya flash uygulanmadı.

**Dosya hazırlanmış ve bilgisayarda doğrulanmış bir deney adayıdır; fiziksel olarak çalıştığı doğrulanmış firmware değildir.**
