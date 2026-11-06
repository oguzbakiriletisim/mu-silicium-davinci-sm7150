# DUU3 — UFS StartImage öncesi süre karşılaştırması

Amaç: DUU2-auto'da B0C6'dan sonra görüntünün kaybolması ile genel süre/reset
ilişkisini ayırmak. MOV burada bağımsız izlenmedi; kullanıcının tam zaman
çizelgesi esas alındı. Reset nedeni henüz belirlenmedi.

Bu paket Windows yüklemez, disk okumaz, bölüm değiştirmez. Yeni imajlarda
UFSDxe StartImage **zorunlu olarak engellenir**. Eski HAL/IOMMU sahiplik ve
identity kontrolleri korunur. Yeni register yazması/binary patch yoktur;
önceden kullanılan native bağımlılıklar kendi mevcut başlatma kodlarını yürütür.
Donanım/TZ resetini engelleme veya brick olmayacağını garanti etme iddiası yoktur.

## İlk deneme: mevcut imajı değişmeden kullanın

1. ZIP'i bilgisayarda çıkarın. IMAGE_SHA256SUMS.txt ile dosyayı doğrulayın.
   Windows PowerShell örneği:

   ```powershell
   (Get-FileHash .\DUU2-before-UFS-B0C6.img -Algorithm SHA256).Hash
   ```

   Beklenen: `739074fd14c6bfd0b719d794a6defc02a6c863944c96b92ba2630462b9ed541b`.
2. Cihazı bildiğiniz tuş yöntemiyle Fastboot'a alın. Bilgisayarda, paket
   dizininden **yalnız geçici başlatma**:

   ```powershell
   fastboot boot .\DUU2-before-UFS-B0C6.img
   ```

3. B0C6'ya ulaşırsa ekrana dokunmadan **en az90 saniye**, harici kronometreyle
   bekleyin. Timer panelde canlı saymaz. Komuttan önce başlayan kesintisiz
   videoyu varsa kararma, MI ve MIUI logosunu da kapsayacak kadar sürdürün.
4. B0C6 öncesinde başka CP/hata kalırsa veya kendi kendine yeniden başlarsa
   sonraki ileri imaja geçmeyin; CP/status, süre ve videoyu kaydedin.
5. D010 denemesi daha önce süreli yapılmadığı için, aynı şekilde mevcut
   `DUU2-baseline-D010.img` ile en az90 saniyelik kontrol alın. Bu görüntü
   önceki fiziksel testteki imajla aynıdır; yeniden derlenmedi.

Buradaki Fastboot komutları kullanıcı içindir; geliştirme ortamında telefona
bağlanılmadı. Eski DUU2'nin geçici boot yolu bu cihazda çalıştı. Yeni türevlerin
aynı biçimde paketlenmesi, yeni imajın fiziksel başarı garantisi değildir.

## Yalnız önceki sınır kararlıysa: yeni karşılaştırmalar

| Dosya | Sabit sonuç | Fark / yorum |
|---|---|---|
| DUU2-before-UFS-B0C6.img | B0C6; UFS StartImage öncesi | Değiştirilmemiş ilk kontrol. |
| DUU3-UFS-before-slow-B0C6.img | B0C6; START FORBIDDEN | DUU3, pending gecikmesi1s; son8 olay panelde. |
| DUU3-UFS-before-fast-B0C6.img | B0C6; START FORBIDDEN | Aynı DUU3, pending gecikmesi0; daha erken aynı sınır. |
| DUU3-UFS-loaded-B0C5.img | B0C5; LoadImage dönüşü | Loader+FreePool sonrasını, PhotoImage/Start öncesini ayırır. |

Her dosya için aynı `fastboot boot .\DOSYA.img` biçimi, tek tek; stop'tan
itibaren90 saniye. Hepsini otomatik ardışık başlatan betik yoktur.
İlk anomali sonrası durun. B0C5'te gerçek LAST EFI/LoadImage kodunu okuyun;
B0C5'e varmak kendi başına başarılı loader anlamına gelmez, sıfır dönüş gerekir.
Yeni B0C6'da CALL PENDING, **çağrı yapılmadan bilinçli durulduğu** anlamındadır;
START FORBIDDEN etiketi başarı değildir. HAL/UFS alanlarındaki EFI_NOT_STARTED
başlangıç değeri hata dönüşü veya çalışmış bir init olarak okunmamalıdır.

Kaydedilecekler:

- Komut, D010/panel ilk görünümü, hedef CP, ekran kararması, MI logosu zamanları.
- Hedefte90 saniye kararlı mı; CP ve son8 milisaniye satırı; LAST EFI,
  Load/Start, IOMMU/readback, hook ve APSS enable alanları.
- Exception varsa ELR/ESR/FAR/LR, reset callback yakalanırsa type/status.
- READS/BLOCKS/GPT0 kalması bu pakette beklenir. UFS başarı testi değildir.

B0C6 sabit kalıp auto kararıyorsa UFS StartImage veya onun ardından oluşan
akışla ilişki güçlenir; belirli register/fault/watchdog kesinleşmez.
Stop imajı da kararıyorsa UFSDxe entry çalışmadan olay oluşmuştur; önceki
native sürücüler/asenkron güç/reset kaynakları ve zamanlama incelenir.
Slow/fast aynı toplam sürede reset oluyorsa zaman tabanı adaydır; olayın aynı
modül veya duruma bağlı olması da mümkündür. Harici zamanları raporlayın.

## Çıkış ve kurtarma

Sabit panelde normal bekleme nedeniyle otomatik çıkış yoktur. Güç tuşunu
cihaz yeniden başlayana kadar basılı tutun; ardından daha önce doğruladığınız
Güç+Ses Kısma yöntemiyle Fastboot'a girin. TWRP gerekiyorsa cihazınızda zaten
çalışan kurtarma tuş yöntemini kullanın. MIUI denemesi döngüye girerse Fastboot'a
dönün ve testi bırakın. Bölüm onarımı, flash, erase, format veya yeni firmware
gerekmez/önerilmez. Tuşlarla dönüş olmazsa bu paketin yazılımsal kurtarma
sağladığını varsaymayın; yeni depolama müdahalesi yapmayın.

## Yeniden üretim ve doğrulama

Kaynak dalı `davinci-win11-uefi-research`; kesin commit SOURCE_COMMIT.txt içinde.
Standart repo toolchain/submodule kurulumunu kullanın; Resources/Research ve
önceki DUU2 belgeleri gereksinimleri içerir. Teslim derlemesinde Clang19,
IASL ve CLANGPDB kullanıldı. Orijinal boot_clean.zip gerektiğinde yerel girdi;
pakete veya Git'e konulmadı. Yeni çıktı dizinleri zorunludur.

```bash
bash Resources/Duu3Timing/build_timing.sh /path/boot_clean.zip /tmp/duu3-ufs-before-slow 0xB0C6 1000000 12
bash Resources/Duu3Timing/build_timing.sh /path/boot_clean.zip /tmp/duu3-ufs-before-fast 0xB0C6 0 12
bash Resources/Duu3Timing/build_timing.sh /path/boot_clean.zip /tmp/duu3-ufs-loaded 0xB0C5 1000000 12
python3 Resources/Duu3Timing/validate_timing.py --backup /path/boot_clean.zip --prefix /tmp/duu3
python3 -m unittest discover -s Resources/Tests -v
```

Gerçek kullanılan flag'ler/loglar evidence içindedir. FD=9FC00000/300000,
BootShim SHA53d8b901cb9818850207c6ab30ce184212fd78d7a8eca029500ded9e84ab0adc.
Android header v1/page4096 ve header adresleri, DTB'ler orijinal yedekten
okunur; davinci.sh tahminleri kullanılmaz. Zaman damgalı derleme metadata'sı
farklı ortamlarda farklı firmware SHA üretebilir; dağıtılan baytların SHA'ları
IMAGE_SHA256SUMS.txt içindedir. Android paketleyici aynı girdilerle birebirdir.

Analiz: ANALIZ_TR.md. 93 host testinin ve3 DEBUG derlemesinin başarısı fiziksel
UFS/Block I/O/GPT çalışması değildir. Bu paket Windows dağıtımını başlatmaz.
