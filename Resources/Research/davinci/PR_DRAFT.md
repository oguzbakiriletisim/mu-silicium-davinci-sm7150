# davinci: derleme onarımları, depolama tanılaması ve isteğe bağlı CPU-only ACPI

Taban `89cae67c` kaynakları güncel bağımlılıklarla RTC başlığını bulamıyor ve cihazı 732G olarak tanımlıyor. Bu dal başlık bağımlılığını ve Snapdragon 730 kimliğini düzeltir; Python araçlarının gereken setuptools sürümünü sabitler.

DEBUG depolama tanılaması, mevcut UFS yolunu değiştirmeden protokol/IMEM ve Block I/O metadata'sını raporlar. İsteğe bağlı CPU-only ACPI profili davinci CPU UID/MPIDR topolojisini ve DTS timer kutuplamasını kullanır. Default profil korunur; çevre birimleri için ACPI veya IOMMU çözümü iddia edilmez.

Doğrulama: CPU-only ve varsayılan DEBUG tam FD derlemeleri; Mu PE doğrulaması; 10 Python testi; C host sınır testleri; IASL; FD'deki ARM64 modüller ve değişmemiş UFS SHA-256 kontrolü. Orijinal taban kaynakta RTC başlık hatası aynı hazırlanmış ortamda yeniden üretildi.

Sınırlar: fiziksel cihaz testi yok; UFSDxe'nin IOMMU bypass'ı korunuyor; UFS/DMA, Windows Boot Manager ve Windows masaüstü doğrulanmadı. Touch/USB/güç sürücüleri eklenmedi. Bu PR donanımda kullanılacak firmware yayını değildir.

İnceleme odağı: tanılama modülünün yazma/denetleyici başlatma yapmaması; varsayılan davranışın korunması; CPU-only profilinin çevre birimi tablolarını dışlaması; sabit UFS ikilisinin değişmemesi. Günlük ve kaynak kilit ayrıntıları RAPOR.md ve inceleme paketinde.
