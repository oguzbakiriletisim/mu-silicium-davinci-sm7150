# UFS entry: uygulanmış düzeltme ve ilk açılış engeli

Başlangıç771d94424f8802931f1bf8846435301681df09b8; fiziksel DUU2 imajları
a33b564b8a413b26c59ad7673ebbf416a6107af6. Yeni değişiklik Git geçmişindedir.

**Çalışan UFS Block I/O düzeltmesi üretilmedi.** Uygulanan kod, PREFINAL'ın
salt-okunur sözleşmesindeki bir açığı kapatır: native UFSDxe girişinin koşullu
FFU ve özel reset yolları vardır. Sadece driver döndükten sonra ReadBlocks
çağırmak girişin salt-okunur olduğunu göstermez. Önceki değerlendirme bu sınırı
kapsamıyordu; bu eksiklik şimdi gerçek ikili kodu üzerinden düzeltildi.

## Kesin ikili kanıt

Dosya `Binaries/davinci/QcomPkg/Drivers/UFSDxe/UFSDxe.efi`, SHA256
0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1.
İkili değiştirilmedi. Adresler PE RVA'dır, fiziksel register adresi değildir.

- UEFI wrapper1000→1040→constructor112C; modül entry14D0→2ABC.
- Boot-device kontrolü5304, native IOMMU stub24F8, UFS open CE40.
- Entry2E4C/2E50 ilk-LUN/chip-id koşullarını kontrol eder;2E70 gerçek BL2694.
- 2694 inquiry vendor/product/revision alanlarını okur;11C358'den başlayan5
  kayıtla karşılaştırır. Koşul sağlanırsa29D0→D44C aktarımını yapar.
  D44C, mode0x0E ile DC88'e geçer (FFU transfer yolu).
- Başarılı güncelleme dalında2A24→13F8C reset hazırlığı ve2A94→13E78 özel
  reset yolu bulunur.13E78 özel reset/PMIC yardımcılarına gider; standart
  gRT->ResetSystem hook'undan geçmek zorunda değildir.
- Tabloda MICRON128GB eski9QSQ/9QST/9QSU→9QSV, SAMSUNG KM8B8001JM-BC01
  eski0100/0400→0600 örnekleri var. **Telefonun gerçek inquiry/revision bilgisi
  bilinmiyor; bu kayıtların cihazla eşleştiği veya güncellendiği iddia edilmiyor.**

`native_entry_review.py`: Gerçek2694 makine kodu bounded Unicorn RAM ortamında
çalıştırıldı. Update, reset ve format/log hizmetleri tamamen mock; fiziksel disk,
MMIO, DMA veya gerçek reset yok. Eşleşen iki ayrı fixture'da update+reset callback
istekleri gözlendi; güncel revision/bilinmeyen vendor fixture'larında gözlenmedi;
güncelleme hata fixture'ında reset dalına girilmedi. Bunlar donanım sonucu değil,
belirli koşullarda ikilinin hangi hizmetleri çağırdığına ilişkin yazılım kanıtıdır.
Ham disassembly ve fixture çıktıları evidence/NATIVE_ENTRY.json içindedir.

DUU2-auto kararmasının FFU'dan geldiği **kanıtlanmadı**: B0C7 yok, gerçek inquiry
ve chip-id yok, constructors/PHY/clock/power/MMIO arızaları da dışlanmadı.
D010'un geç reseti bu UFS girişini gerektirmez; ayrı olay olarak kalır.

## Kaynak düzeltmesi

`Platforms/Xiaomi/davinciPkg/Drivers/PreFinalDxe/PreFinalDxe.c::StartNative`:
indeks sınırını doğrular; son native imaj UFSDxe'yi, DEPEX/LoadImage/StartImage
hizmetlerinden önce EFI_WRITE_PROTECTED ile reddeder. Gerçekte StartImage
çağrılmadığı için mStartStatus EFI_NOT_STARTED kalır; politika ret kodu mUfs ve
C0F0 checkpoint'inde ayrıdır. Sahte StartImage dönüşü veya sahte PASS yok.
Mevcut HAL/sahiplik/identity kapıları kaldırılmadı, binary patch, context-bank
ataması veya yeni register yazması eklenmedi. Bu koruma sadece bu kaynak
coordinator'ına aittir; normal DXE profilindeki otomatik UFSDxe dispatch'i için
aynı güvenlik iddiası yapılmıyor. Normal profil telefona önerilmiyor.

`Resources/Tests/davinci_ufs_unblock_host.c`: gerçek StartNative fonksiyonunun
native UFSDxe için LoadImage/StartImage'ı çağırmadığını ve geçersiz indeksi
reddettiğini çalıştırır. `test_davinci_native_entry.py`3 FFU dal testi ekler.
96 host testi ve opt-in DEBUG/PREFINAL/PHOTO derlemesi başarılıdır.

Yeni boot.img hazırlanmadı: yalnız bu engelde duran imaj, kullanıcıya daha önce
sabit B0C6 testinin tekrarını yaptırır ve Block I/O düzeltmesi olmaz. Derlenen FD
bilgisayarda denetlendi; hash ve FV raporu evidence içindedir. Fiziksel kullanım
veya Windows kurulumu için onaylanmış imaj olarak sunulmaz.

## PHY/clock/reset/regulator ve DMA değerlendirmesi

Kaynaklar bu yeni commit'teki `Resources/DTBs/davinci.dts:4680–4738`,
`Platforms/Xiaomi/davinciPkg/Library/DeviceMemoryMapLib/DeviceMemoryMapLib.c:39`,
`Drivers/PreFinalDxe/PreFinalDxe.c::ReadbackUfs/NativeProviderSafe`,
`HalUfsBridge.h::NativeBankBypass`, `Include/PREFINAL.inc`, `NativeImages.h`.

| Alan | Somut kaynak | Açık engel |
|---|---|---|
| HCI/ICE | 1D84000/3000 ve1D90000/8000 | CPU map içindeler; okunabilirlik/link/DMA çalışması kanıtı değil. |
| PHY | 1D87000/DDC, qcom,ufs-phy-qmp-v3, tek lane | Doğru clock/rail/reset sırasının native entry'de başarıyla geçtiği görülmedi. |
| Clock | core,bus_aggr,iface,unipro,ice,ref,tx_lane0,rx_lane0 | ClockDxe Start dönüşü her clock'un açık/doğru frekansta olduğu anlamına gelmez. |
| Reset | core_reset ve dev-reset-assert/deassert pinctrl | Tahmini GCC/GPIO yazması eklenmedi; Windows kaynak sözleşmesi yok. |
| Regulator | PHY vdda-phy/vdda-pll; HBA, vcc, vccq2 ve vddp-ref-clk | Mevcut rayların gerilim/oy/ownership durumu bilinmiyor; native PMIC/RPMh desteği kendiliğinden varsayılamaz. |
| SMMU | UFS0 ARID0→SID300;15000000; gözlenen CB2/SCTLR E0 | Identity kapısı geçmesi DMA buffer cache, controller listleri ve Windows handoff'unu çözmez. |
| DEPEX | UFS gerçek .depex yalnız SMEM GUID PUSH+END | Clock/SCM/power/KernelInterface constructor gereksinimlerinin tam sözleşmesi değil. |
| Gizli bağımlılıklar | DXE services/HOB config tables; native KernelInterface protokolü veya schedule-HOB fallback; clock/DAL yardımcıları | Salt bir LocateProtocol eksiğini düzeltmenin UFS'yi açacağına dair yeterli runtime veri yok. |

Constructor GUID b5062be7… **Qualcomm KernelInterface**'dir, Microsoft/EDK2 PCD
protokolü değildir.8EC2BD8D… schedule-interface HOB fallback'idir. Bunların yokluğu
tek başına kök neden ilan edilmedi; fallback ve caller davranışı denetlenmelidir.

## Sonraki gerçek geliştirme kararı

Mevcut binary'de yeni patch, vendor/chip/revision taklidi veya FFU koşulunu
sahte veriyle atlatma yapılmadı. Kullanılabilir en küçük **çalıştırma** düzeltmesi
henüz gerekçelendirilemiyor. Gerekli provider ya kaynak seviyesinde FFU, RPMB
provisioning, descriptor/config yazımları ve private reset dışlanarak geliştirilmiş
olmalı ya da başka bir native provider'ın init/read çağrı grafiği aynı ölçüde
denetlenmeli. Eski Cl1nkkk0.2 yalnız çevrimdışı karşılaştırma kaynağı olarak kalır;
başka cihaz firmware'i kullanılmaz. Sonra mevcut IOMMU readback+DMA sahiplik
şartları altında tek hedef ReadBlocks+GPT CRC/GUID olur. Windows koşulları
WINDOWS_NEXT_STEPS_TR.md içindedir; otomatik bölüm/kurulum komutu yoktur.
