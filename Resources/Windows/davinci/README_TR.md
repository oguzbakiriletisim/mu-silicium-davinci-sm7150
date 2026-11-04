# Davinci: mevcut Windows dosyalarından bilgisayarda EFI/BCD hazırlığı

Bu araçlar telefonu kurmaz. UFS/Block I/O veya Windows boot-start sürücü desteği sağlamaz. Mevcut ext4 `win` bölümünü değiştirmez. Hedef GUID'ler ve sürücü harfleri tahmin edilmez.

Gerekenler: Python 3.10+, mevcut Windows ARM64 staging klasörü. Yerel BCD oluşturmak için Windows, bcdedit ve Windows Storage PowerShell cmdlet'leri gerekir. Bu oturumda gerçek Windows bcdedit/Hyper-V işlemleri çalıştırılmadı; Python doğrulama/kopyalama ve hata yolları test edildi, Windows çağrıları testlerde sahte servislerdi.

## 1. Dosyaları yeniden indirmeden veya büyük kopyalama yapmadan kontrol

Depo kökünde Windows PowerShell terminali:

```powershell
python Resources\Windows\davinci\prepare_windows.py inspect `
  --staging 'C:\Mi9T_Win11_Staging'
```

Kaynakta `Windows\Boot\EFI\bootmgfw.efi`, `Windows\System32\winload.efi`, `ntoskrnl.exe` ve `config` altında SYSTEM/SOFTWARE/SAM/SECURITY/DEFAULT gerekir. Üç PE için ARM64 PE32+; hive'lar için base-block, sequence, boyut ve checksum kontrol edilir. HBIN ağacı, ACL, hardlink, reparse metadata, imza güveni ve Windows 11 sürümü doğrulanmış sayılmaz. Düz dosya kopyası, uygulanmış bir Windows kurulumu değildir.

Hata halinde araç dosya indirmez veya kaynak klasörünü düzeltmeye çalışmaz. Hangi dosyanın/hive'ın eksik ya da uygunsuz olduğunu bildirir.

## 2. Yalnız küçük EFI dosyalarını yeni bir PC klasörüne hazırla

```powershell
python Resources\Windows\davinci\prepare_windows.py stage-efi `
  --staging 'C:\Mi9T_Win11_Staging' `
  --output "$env:USERPROFILE\Mi9T_EFI_Files"
```

Çıktı klasörü yeni olmalı ve kullanıcı profilinin altında kalmalıdır. Kaynak klasör değişmez. Windows/Program Files kopyalanmaz. Boot manager, bulunan küçük EFI/policy/locale yardımcıları, fontlar ve bootres.dll hazırlanır; EFI yardımcılarının mimarisi denetlenir.

```text
Mi9T_EFI_Files/
  STAGING.json                 # EFI_FILES_ONLY_NO_BCD, boot kanıtı değildir
  EFI/
    Boot/bootaa64.efi
    Microsoft/Boot/bootmgfw.efi
    Microsoft/Boot/<bulunan küçük yardımcılar>
    Microsoft/Boot/Fonts/<bulunan fontlar>
    Microsoft/Boot/Resources/bootres.dll  # kaynakta varsa
```

Bu aşamada BCD yoktur. Gerçek hedef bölüm bilgisi olmadan bootable ESP hazırlandığı iddia edilmez.

## 3. Gerçek disk düzeni varsa salt okunur envanter ve BCD planı

**Mevcut telefon UEFI depolaması doğrulanmış değil. Telefon Windows'a disk olarak sunulmuyorsa PC diskini telefon sanarak seçmeyin.** Aşağıdaki adım gerçek hedef bölümler Windows Storage cmdlet'lerinde görünüyorsa veya ayrı bir PC laboratuvar diskiyle çalışılıyorsa anlamlıdır. Envanter tek başına telefon UEFI'sinin bunları görebildiğini kanıtlamaz.

```powershell
powershell.exe -NoProfile -File Resources\Windows\davinci\Collect-DiskInventory.ps1 |
  Out-File -Encoding utf8 "$env:USERPROFILE\Mi9T-layout.json"
```

Üç değeri envanterdeki **gerçek** GPT GUID'lerinden doldurun; örnek sabit disk GUID'i yoktur:

```powershell
$Mi9TDiskGuid = 'GERCEK-DISK-GUID'
$Mi9TEspGuid = 'GERCEK-ESP-PARTITION-GUID'
$Mi9TWindowsGuid = 'GERCEK-WINDOWS-PARTITION-GUID'

python Resources\Windows\davinci\prepare_windows.py plan `
  --staging 'C:\Mi9T_Win11_Staging' `
  --inventory "$env:USERPROFILE\Mi9T-layout.json" `
  --disk-guid $Mi9TDiskGuid --esp-guid $Mi9TEspGuid --windows-guid $Mi9TWindowsGuid `
  --output "$env:USERPROFILE\Mi9T_Offline_BCD"
```

`plan` yalnız JSON basar, klasör bile oluşturmaz. Disk GPT olmalı; ESP doğru type GUID'iyle FAT32, Windows bölümü Microsoft Basic Data type GUID'iyle NTFS olmalı; GUID'ler benzersiz, extent'ler sınırlar içinde ve çakışmasız, harfler mevcut olmalı. Host boot/system diski veya bölümü reddedilir. Ext4, eksik ESP veya atanmış harf yokluğu halinde otomatik format/mount yapılmaz.

## 4. Gerçek hedef eşlemeleriyle yeni bir OFFLINE BCD oluştur

Aynı GUID değişkenleriyle, **plan çıktısından ayrı, henüz bulunmayan** bir PC klasörü seçin:

```powershell
python Resources\Windows\davinci\prepare_windows.py prepare-efi `
  --staging 'C:\Mi9T_Win11_Staging' `
  --disk-guid $Mi9TDiskGuid --esp-guid $Mi9TEspGuid --windows-guid $Mi9TWindowsGuid `
  --output "$env:USERPROFILE\Mi9T_Offline_BCD"
```

Bu işlem:

1. Windows Storage envanterini tekrar okuyup seçilen GUID/FS/harfleri yeniden doğrular.
2. Yalnız yeni PC klasörüne küçük EFI dosyalarını kopyalar.
3. `EFI\Microsoft\Boot\BCD` için **yeni** store oluşturur. Kaynak BCD'yi ve host sistem BCD'sini değiştirmez.
4. Boot manager device/path ve Windows loader `device`, `osdevice`, `path`, `systemroot`, default/displayorder ayarlarını yapar. Varsayılan loader GUID'i kullanıcının `{8af49d28-d85c-11f1-8157-f0038c0eb282}` değeridir; `--loader-guid` ile değiştirilebilir.
5. Hedefin o anda doğrulanmış harflerini `partition=S:` / `partition=W:` gibi bcdedit argümanlarına dönüştürür. Harfler sabit değildir; gerçek envanterden gelir. GPT kimliğinin store'a kodlanmasını Windows bcdedit gerçekleştirir; bu Linux ortamında native olarak test edilmedi.
6. `/enum all` çıktısını ve yeni hive base-block doğrulamasını saklar. Hata halinde kısmi çıktı silinmez; `BCD-CREATION.json` hata kaydını korur.

Hiçbir dosya hedef ESP/Windows bölümüne kopyalanmaz; store hep PC klasöründedir. `bcdboot`, DISM driver ekleme, `/sysstore`, `/import`, sistem BCD değişikliği veya telefona dağıtım yoktur. Doğru Windows sürücü zinciri bulunmadığından sürücü ekleme uydurulmadı.

## NTFS için telefon yerine isteğe bağlı boş PC laboratuvar diski

`New-LabDisk.ps1` mevcut fiziksel diski seçmez. Varsayılan olarak yalnız plan verir:

```powershell
powershell.exe -NoProfile -File Resources\Windows\davinci\New-LabDisk.ps1 `
  -Path "$env:USERPROFILE\Mi9T-empty-lab.vhdx"
```

`-Create` açıkça verilirse, Hyper-V cmdlet'leri bulunan bir Windows ortamında **yeni** dinamik VHDX oluşturmak, dosyadan dönen DiskNumber'ı yeniden doğrulamak, yalnız bu yeni RAW sanal diskte ESP/MSR/NTFS hazırlamak ve detach etmek üzere yazılmıştır. Mevcut dosya, host boot/system diski veya reparse-point üst dizinleri reddedilir. Hyper-V yoksa fiziksel diske fallback yapmaz.

Bu PowerShell/Hyper-V yolu burada çalıştırılmadı. Boş NTFS laboratuvar imajı, Windows kurulumu değildir ve telefonun GPT/NTFS düzenine çözüm olarak sunulmaz. Telefonun `win` bölümünü biçimlendirecek bir komut/betik bu teslimatta yoktur.

PowerShell dosyalarının sözdizimi, sahte Storage cmdlet'leriyle envanter akışı ve Windows dışı lab koruması PowerShell 7.4.6 Linux runtime ile test edildi. Bu testler native Windows bcdedit/Storage/Hyper-V çalıştırması değildir. Python unittest koşusunda isteğe bağlı runtime `DAVINCI_PWSH` ile seçilebilir; yoksa bu üç test açıkça skip olur.
