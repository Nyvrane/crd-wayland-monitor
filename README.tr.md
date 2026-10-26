# Chrome Uzaktan Masaüstü — Mevcut Wayland Ekranı

Kayıtlı Chrome Uzaktan Masaüstü cihazını **açık KDE Plasma Wayland masaüstüne** bağlar. Ayrı masaüstü açmaz ve RDP kullanmaz.

Google veya KDE'nin resmî ürünü değildir. Deneysel uyumluluk yardımcısıdır; şu an tek bir Arch tabanlı KDE/Wayland sisteminde CRD **157.0.8103.19** ile doğrulanmıştır.

## Kurulum

Önce Chrome Uzaktan Masaüstü ana makine paketinin kurulu ve Google hesabına kayıtlı olması gerekir. İlk kayıt için [Google kurulum sayfasını](https://remotedesktop.google.com/headless) kullanın.

Gereksinimler: Arch Linux veya türevi, KDE Plasma Wayland, çalışan KDE ekran portalı, RemoteDesktop portalı sürüm 2, PipeWire/EIS ve derleme araçları. Eksik araçları normal paket yönetiminizle kurun:

```sh
sudo pacman -S --needed base-devel glib2 python pkgconf
```

GitHub'dan kaynak arşivini indirin, açın ve **Install.desktop** dosyasını çalıştırın. KDE ilk açılışta izin/güven onayı isteyebilir. Alternatif olarak klasörde:

```sh
sh install.sh
```

**sudo ile çalıştırmayın.** Kurucu yardımcı kitaplığı yerelde hazırlar, kullanıcı servisini ekler ve eski ayrı masaüstü servisi açıksa sistemin normal yetkilendirmesiyle durdurur. Önceki servis durumu geri almak için kaydedilir.

İlk ekran paylaşım penceresinde fiziksel ekranınızı seçip izin verin. Sonraki açılışlarda kaydedilen izin yeniden kullanılır. Uygulama adı artık **Chrome Uzaktan Masaüstü (Wayland)** olarak görünür. Uygulama kimliği değiştiği için eski “tanımlanamayan uygulama” izni bir kez daha sorulabilir.

Telefonda kayıtlı cihazınıza normal **Uzaktan Erişim** listesinden bağlanın. Google/PIN doğrulaması değişmez. Masaüstü oturumu açılmış olmalıdır; bu araç Linux'a otomatik giriş yapmaz ve kilit ekranını atlamaz.

Bu, **önceden kayıtlı bir bilgisayar için tek başlatmayla kurulumdur**. Google hesabı kaydını, paket bağımlılıklarını ve ilk paylaşım onayını kullanıcı adına sessizce tamamlamaz.

## Durum ve geri alma

```sh
sh install.sh --status
sh install.sh --uninstall --restore-previous
```

Kaldırma, kullanıcı servisini ve uygulama girişini kaldırır; istenirse önceki sistem servisini geri açar. Google kaydınız değişmez. Kurtarma için özel izin verileri ve kitaplık yerelde tutulur.

Ekran paylaşım simgesi KDE'ye aittir. Paneldeki sistem tepsisi görünürlük ayarından ana panelden gizlemek işlevi durdurmaz; genişletilmiş tepside kalabilir. Kurucu bunu kendiliğinden değiştirmez.

**Google kayıt dosyalarını, izin anahtarlarını veya yerel durum klasörünü GitHub'a yüklemeyin.** Depo bunları içermez. Chrome güncellemeleri sonrasında bağlantıyı ve günlükleri kontrol edin; bu yardımcı Google'ın D-Bus çağrı yöntemine bağlıdır.

Ayrıntılar ve geliştirme kontrolleri için [İngilizce belgeye](README.md) bakın.
