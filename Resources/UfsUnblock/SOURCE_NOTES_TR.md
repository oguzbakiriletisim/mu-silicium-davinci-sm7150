# Kaynak ve kanıt: HAL/UFS unblock DUU1

Başlangıç `f3016dd43346d63960dda5144c30f26f3824f0ba`.
Yeni kaynak commit'i paketteki SOURCE_COMMIT.txt içindedir; tüm aşağıdaki yollar o commit'e aittir.

| Bulgu / düzeltme | Kaynak |
|---|---|
| Eski profilde HAL yoktu; eski kontrol bağımlılıkları da UFS'den önce engelliyordu. | Başlangıç `Platforms/Xiaomi/davinciPkg/Include/PREFINAL.inc`, `Drivers/PreFinalDxe/PreFinalDxe.c::PreFinalEntry`. |
| HAL yeni profilde FREEFORM, otomatik dispatch yok. Bağımlılıklar ardından DEPEX→LoadImage→StartImage, gerçek EFI status; eksik PUSH GUID'leri ekranda. | Yeni `PREFINAL.inc`, `NativeImages.h`, `PreFinalDxe.c::Depex/StartNative/PreFinalEntry`. |
| HAL file GUID9A00771F… ile protokol GUID54B6D3B4… farklıdır. Protokol GUID bytes HAL PE RVA0x9040 içinde bulundu. Provider entry başarısızsa kurulu ama unload olmuş kodu gösterebilecek protokol asla dereference edilmez. | `PreFinalDxe.c::InitHalTable`; `Binaries/davinci/.../HALIOMMUDxe.efi` SHA72bdfde0fb278a2a5bbaa6eb8a6f72a36d3b3b3e61864f6e6aad6f59c6da52e5. |
| Revision1, void init RVA13BC, tablo90A8, create+0/RVA1904, attach+10/RVA1B70, configure_bypass+40/RVA3160. | `HalUfsBridge.h`, runtimeimage-owned pointer/RVA doğrulaması; önceki `Resources/Scripts/davinci_hal_offline.py` ve phase3 evidence. |
| Gerçek create56-byte domain; gerçek configure_bypass IOC0→SCTLR0xE0, IOC1→0x9F00E0, TCR0. Yeni API zinciri ilk ham hatada durur; sabit context-bank/TTBR yazması yoktur. | `HalUfsBridge.h::RunUfsDomainChain`; `native_hal_probe.py`: gerçek RVA1904,3160, mocked allocator; domain boşken MMIO yok. |
| Eski gerçek UFSDxe rutini create→EnableUfsIOC→configure_bypass(+40)→UFS0 attach(+10), ARID0/MASK0 kullanır. Harici adapter aynı zinciri kullanır; stub dosyası değişmez. | `Resources/Scripts/davinci_ufs_offline.py`; orijinal `ffa8933a6ae7688fcbe3693b698833efdaa3536f` UFS RVA24F8..2648. Paketli patched UFS SHA0576f04f94f267d24736fdfe889d0c29c43330a996a599c40955506aa38ddee1. |
| Gerçek program_smr_s2cr_to_cb RVA2648: TYPE[17:16]=0, düşük byte bank; bank2 girdisi→S2CR2. Mevcut SMR'yi reuse etmez, ilk boş slota yeni SMR yazar; mevcutroute'a attach çoklu eşleme riski taşır. | `native_hal_probe.py` gerçek routine + mocked IDR/SMR/S2CR servisleri. İki fixture testinde existing mapping yok/var; kaydedilen yazmalar yalnız emulator callback argümanlarıdır. |
| UFS0 ARID0→SID300; raw NumIDs16. Dummy SDC1→340, SDC2→2A0, SDC4→2C0 (16'şar), USB3-0→540(1); hepsi SMMU15000000. | Pinlenmiş `DALSYSDxe.efi` SHA0542d91c859baf816f42438cc3472fed84897e7c5dec7cdfc05221e5ede40544; `davinci_dal_iort.py` parser ve phase3 binding. Diğer SoC verisi taşınmaz. |
| Gerçek free-bank rutini2278, TYPE0/TYPE2 veya TYPE1+VMIDFF bankı seçebilir; TYPE0 yalnız raw0 olmak zorunda değildir. Yeni sahiplik koruması bu heuristic'in canlı stream bankını yeniden kullanmasını engeller. | `PreFinalDxe.c::SafePool/NativeProviderSafe`; gerçek disassembly ve phase3 RAM emülasyonu. |
| Context başlangıcı gerçek HAL3690 algoritması; IDR1.page-size/NumPageIndex.4K stride ve CPU-map sınırları doğrulanır. Gözlenen çift yalnız readback fingerprint'tir; register'a yazılmaz. | `HalUfsBridge.h::ContextWindow/NativeLayoutSupported`, `PreFinalDxe.c::CaptureNative`. DeviceMemoryMap değişmedi. |
| Mevcut UFS identity kanıtlıysa korunur; değilse overwrite/detach yapılmaz. Native allocator çalışırsa sonucun SMR/S2CR/CBAR/CBA2R/SCTLR doğrulaması zorunlu. | `PreFinalDxe.c::ReadbackUfs/HasUfsRoute/PreFinalEntry`, `HalUfsBridge.h::NativeBankBypass`. |
| GPT yolu yalnız ReadBlocks; primary/backup CRC/GUID/extent kontrolleri korunur. | `PreFinalDxe.c::Read/Gpt`; `ReadOnlyChecks.h` bu görevde değişmedi. |

Fotoğrafın kendisi bu oturuma dosya olarak verilmedi; kullanıcı metin aktarımı kaynak olarak kullanıldı. TYPE2 ve eski EFI status uyuşmazlığı ham sayılarla ayrı kaydedildi; fiziksel arıza tanısı uydurulmadı. Yeni imaj DUU1 işareti ve ham kontrol kayıtlarıyla bu belirsizliği ayırır.

Host C testleri gerçek coordinator .c/.h dosyalarını mocked UEFI/register servisleriyle derler/çalıştırır. Gerçek HAL probe'u yalnız RAM emülasyonudur; callback yazma argümanları fiziksel register yazması değildir. Build,89 test ve yeni Android roundtrip/FV denetimi fiziksel UFS başarısına eşitlenmez.
