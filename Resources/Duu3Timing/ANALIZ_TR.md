# DUU2 tam zaman çizelgesi → DUU3 UFS çağrı sınırı deneyi

Kaynak başlangıcı: `a33b564b8a413b26c59ad7673ebbf416a6107af6`.
Yeni kaynak commit'i teslim paketindeki SOURCE_COMMIT.txt ve Git geçmişindedir.
Aşağıdaki kaynak yolları aksi belirtilmedikçe bu yeni commit'e aittir.

## Değişen kanıt

Bu oturuma MOV dosyası verilmedi. Kullanıcının IMG_0986.mov için aktardığı
78,50 saniyelik zaman çizelgesi ve ekran değerleri kullanıldı; video izlenmiş
veya kareler bağımsız incelenmiş gibi sunulmadı.

İlk 31 saniyelik kesitte son B094 görülmesi PDC'nin takıldığını göstermiyordu.
Sonraki tam süreç aktarımı B0C4 ve B0C6'yı içeriyor. Kaynakta aradaki PDC ve
Clock aşamalarının hata dönüşü Summary'ye gider; normal yol UFS'ye geçmez.
Dolayısıyla bildirilen son ekran bu normal akışla tutarlıysa önceki PDC/Clock
çağrıları başarıyla dönmüş olmalıdır. Bu, PDC/Clock donanım işlevlerinin tam
çalıştığını kanıtlamaz. Yeni öncelik PDC tekrar testleri değil UFS çağrı sınırıdır.

| Video zamanı, yaklaşık | Bildirilen gözlem | Sınır |
|---|---|---|
| 0–1 s | fastboot boot çıktı/komut | Kesin başlatma karesi yok. |
| 4–5 s | DUU2 paneli | Timer başlangıcı ile video sıfırı aynı değil. |
| 39 s | B0C4 UFSDxe LOAD CALL | LoadImage henüz çağrılmadan render edilir. |
| 40 s | B0C6 UFSDxe START CALL; LoadImage=0 | Loader döndü, image yüklendi; entry başarısı değil. |
| 40,5 s | Panel kayboldu/ekran karardı | Görüntü kaybı; resetin kesin anı değil. |
| 62 s | MI logosu | Sonraki boot girişimiyle uyumlu, reset nedenini/tam anını ölçmez. |
| 73 s | MIUI logosu | UEFI normal handoff veya Windows başarısı değil. |

D010 önceki denemede sabitti ancak tutulma süresi ölçülmedi. Bu nedenle
"30/60 saniyelik watchdog baseline ile kesin dışlandı" denemez.

## B094'ten B0C6'ya gerçek kaynak yolu

`Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/PreFinalDxe.c::StartNative`
(satır285–303), `NativeImages.h` (PDC index9, Clock10, HAL11, UFS12),
`PhotoDiag.h::PhotoModule/PhotoCheckpoint`:

- B094 render → pending için1 saniye bekleme → PDC LoadImage → FreePool → B095.
- Başarılı loader dönüşü → image bilgisi → B096 → PDC StartImage → B097.
- Bağımlılık döngüsü Clock dahil ilerler; sonra CaptureNative, identity-readback
  ve provider/ownership kontrolleri yapılır (`PreFinalEntry`, satır396–460).
- UFS için B0C4 → LoadImage → FreePool → B0C5 → PhotoImage → B0C6 →
  pending gecikmesi → gBS->StartImage → dönüş olursa B0C7.

B0C6'daki StartImage=0x8000000000000013, henüz dönüş yazılmadığını belirten
EFI_NOT_STARTED başlangıç değeridir; native fonksiyonun döndürdüğü hata değildir.
B0C7 görüntüsü veya başka dönüş kanıtı yok. B0C6 ile ekran kararması arası
aktarılan yaklaşık0,5 saniye, kaynakta pending için1 saniye gecikme bulunmasıyla
birlikte düşünülmelidir: kare zamanları yaklaşık, render süresi/timer başlangıcı
farklı; entry'nin kesin çağrıldığı veya çağrılmadığı bu tahminle belirlenemez.

`Mu_Basecore/MdeModulePkg/Core/Dxe/Image/Image.c::CoreStartImage`
(altmodül `3609e51f683e4d9eed13df8dccbb05b0a64ebab2`, satır1666–1790)
loaded-image durumunu doğrular, bağlam oluşturur ve Image->EntryPoint çağırır.
Burada yerleşik bir30 saniyelik deadline yoktur. Native entry wrapper'ı
constructor'ları da çalıştırır. Pinli `Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.efi`
SHA `0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1`:
entry RVA1000→1040, constructor zinciri112C, sonraki module-entry yolu13F0.
Dolayısıyla StartImage çağrısı başladıysa bile sadece B0C6 ile constructor,
ana UFS init, protokol callback'i veya register erişimi ayrılamaz.
`evidence/NATIVE_SCAN.json` gerçek komutları ve çağrı adreslerini içerir.
Mevcut RVA24F8 IOMMU stub'ı değiştirilmedi; stub donanım yapılandırmasının
başarısını kanıtlamaz. Önceki dış readback/ownership kapıları korundu.

## Reset / zaman aşımı: ne biliniyor?

- Coordinator normal sonu PhotoFinish/WFI'dir, MIUI'ye dönüş isteği değildir.
  `Include/PREFINAL.inc` profilinde BDS/Windows başlatma yolu bulunmaz.
- `PhotoDiag.h::PhotoInit` EFI watchdog iptali ister; sonuç ayrıca gösterilir.
  APSS enable register'ı yalnız okunur. `PlatformPrePiLib.c::PlatformInitialize`
  içindeki mevcut APSS kapatma değiştirilmedi. APSS init/now0, yalnız örneklenen
  anda o enable alanının0 olduğunu gösterir; diğer watchdog alanlarını ölçmez.
- SYNC/SERROR/RESET hook0, handler kayıt/kurulum sonucudur. Reset kaynağı kodu
  değildir. Standart runtime ResetSystem isteği yakalanabilir; TZ/AOP/PMIC,
  doğrudan firmware reseti, farklı handler veya ekran gücü kaybı dışlanmaz.
- PDC ikilisindeki `Time out` metni genel EFI durum tablosundadır;30 saniyelik
  PDC deadline kanıtı değildir. RVA1454 assert/status-code yolu, değer03000007
  ve type2 kullanır; bunlar reset isteği olarak yorumlanmadı. RVA1530 yazılım
  bekleme döngüsü içerir. PDC/Clock/RPMh/NPA doğrusal SMC taramasında komut
  bulunmaması dolaylı Env/TZ çağrılarının yokluğunu kanıtlamaz; Env'de SMC vardır.
- Kaynak/ikili taraması ve tek auto kayıtla TZ/AOP/PMIC zaman aşımı, UFS entry
  fault/hang, private logger/display müdahalesi veya sonradan watchdog yeniden
  kurulması arasında kesin seçim yapılamıyor. Yeni PMIC/SPMI/TZ probe eklenmedi.

## Canlı SMMU değerleri ve başarı sınırı

Aktarılan IDR0=4C017E4F, IDR1=6000003D, CR0=00200406, CR0NS0;
SMR800F0300, S2CR2: TYPE[17:16]=0 ve CB=2. S2CR'nin düşük2 değeri TYPE2
anlamına gelmez. CBAR1F000, CBA2R1, SCTLR E0 (M0), IOC0.
`HalUfsBridge.h::NativeBankBypass` ve `PreFinalDxe.c::ReadbackUfs` kontrolleri
bu UEFI denemesinde EFI_SUCCESS göstermiş. Bu kapının mevcut kaynak koşullarını
sağladığını bildirir; UFS DMA/coherency/host controller veya Windows sürücü
başarısını kanıtlamaz. HAL gerçekten init edildi sonucu da çıkarılmaz: mevcut
identity route ile HAL provider atlanmış olabilir. Son kayıt READS/BLOCKS/GPT-LUN0;
Block I/O ve GPT başarısı hâlâ yok. Yeni kod context-bank/S2CR atamaz.

## Yeni DUU3 değişikliği ve karşılaştırma

`PhotoDiag.h`: Aynı panelde son8 checkpoint'in milisaniye, pending ve EFI
sonucunu RAM'de tutar. Zamanlar PhotoInit başlangıcına göredir; panel durduğunda
saat de donar. Harici kronometre/video gerekir. RET etiketi genel checkpoint'te
Pending=false demektir; her satırın donanım başarı dönüşü olduğu sanılmamalı.

`davinci.dsc`: driver'a özgü delay0/1000000us, phase-test ve ceiling bayrakları.
`PhotoModule`: Seçilen stop'a ek olarak UFSDxe Stage>=6 için **zorunlu park**;
yeni DUU3 hiçbir koşulda bu çağrı yerinden UFSDxe StartImage'a geçmez.
HAL veya bağımlılıkların eski güvenlik kapıları aynıdır; native ikililer değişmez.
Bağımlılık ceiling9/10 seçenekleri HAL/UFS'ye geçişi ayrıca yasaklar; yeni
kullanıcı teslimatında max12 ve yalnız B0C5/B0C6 stop profilleri kullanılır.
Yanlış max/stop/gecikme yapılandırmaları compile-time reddedilir.

Asıl ilk kontrol eski DUU2-before-UFS-B0C6.img'nin aynı baytlarıdır. Önce bu
sabit sınırda ve D010'da en az90 saniye harici süre ölçülür. Yeni slow/fast
aynı yerden önce1s/0s pending beklemesi kullanır. Bir modüle girilmeden beklerken
reset varsa o modülün entry'si bu olay için gerekli değildir. B0C6 stabil,
auto kararıyorsa UFS StartImage sınırı veya devam eden aktif/asenkron akış öne
çıkar; tek başına belirli UFS register'ı veya watchdog kanıtı oluşmaz.
WFI beklemesi CPU/güç/asenkron işleyişi değiştirir; aynı süre/aynı checkpoint
deneyi bile bütün zamanlama etkilerini eşitlemez. Bu yüzden test güvenli
bir sınırlandırma sağlar ama mutlak neden kanıtı değildir.

93 bilgisayar testi, yeni3 DEBUG derlemesi, ARM64/FV/native hash denetimleri
ve Android imajının orijinal header/DTB ile birebir yeniden paketleme kontrolü
başarılı. Günlükler ve sonuç JSON dosyaları ektedir. Bu testler fiziksel yeni
imaj başarısı değildir. Windows kurulumu veya UFS DMA denemesi otomatik başlamaz.
