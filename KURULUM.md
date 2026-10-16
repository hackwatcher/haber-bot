# Haber Botu

NTV, Sözcü, Hürriyet ve BBC Türkçe'den haberleri çeker ve Instagram'a kendisi paylaşır.
**GitHub Actions'ta çalışır** (`.github/workflows/haber.yml`, 15 dakikada bir); bilgisayarın açık olması gerekmez.

Her turda bot (`tur.py`):
1. Dört sitenin RSS akışını okur, yeni haberleri `data/durum.json`'a ekler (tur sonunda repoya kaydedilir).
2. Kurallar izin veriyorsa (sessiz saat değil, son paylaşımdan 20 dk geçmiş, günlük 25 dolmamış) en uygun haberi seçer.
3. Haberin tamamını sitesinden okur (yapay zekâ yok, `ozet.py` kuralları): konuyu (renk), ili (harita), başlıktaki
   rakamı, kancayı bulur ve 4-7 slaytlık karusel yapar: kapak → Ne oldu? → Detaylar → Rakamlarla → Ne dedi? →
   Ayrıca → kaynak/takip et. Bilgi azsa karusel zorlanmaz, tek kart paylaşılır.
4. Slaytları bu reponun `media` dalına koyar (Instagram görseli internet adresinden indirir), Instagram'a gönderir.

Cümleler haberden alıntıdır; kaynak kapakta ve son slaytta, link açıklamada yazar.

## Tekrar engelleme
- Aynı link bir daha gelmez.
- Başka sitede aynı olay (başlıkların kelime benzerliği) varsa ayrı haber sayılmaz, ilk gelen habere bağlanır.
  Paylaşılan haberin kopyaları da paylaşılamaz.
- 90 dakikadan eski haber paylaşılmaz (GitHub bir turu atlarsa biriken haberler bir anda dökülmez).

## Ayarlar (`config.json`)
- `marka`, `kullanici_adi`, `hashtagler`: kartta ve açıklamada görünür.
- `otomatik`: iki paylaşım arası (20 dk), günlük en fazla (25; Instagram'ın API sınırı 24 saatte 50),
  sessiz saatler (02–07 TR), öncelikli kelimeler (şu an boş).
- `engellenen_kelimeler`: "deprem mi oldu", "namaz vakti" gibi tekrar eden SEO haberleri.
- `deneme_modu: true` iken hiçbir şey gerçekten paylaşılmaz. Kurulum bitince `false` yap.

## Instagram bağlantısı (bir kez, Son Koz'daki gibi)
1. Yeni haber hesabını Instagram'da **İşletme hesabı** yap, yeni bir Facebook sayfasına bağla.
2. Bu sayfayı akistudyo portföyüne ekle ve "doku bot" sistem kullanıcısına sayfa yetkisi ver.
3. GitHub'da repo → Settings → Secrets and variables → Actions → **META_TOKEN** secret'ını ekle
   (doku-sistem-token ile aynı). PowerShell pipe token'ı bozuyor; bash ile:
   `tr -cd 'A-Za-z0-9' < doku-sistem-token.txt | gh secret set META_TOKEN -R hackwatcher/haber-bot`
4. `config.json`: `marka`, `kullanici_adi` ve `instagram.kullanici_adi` (hesabın adı, @ olmadan).
5. Actions → "Haber paylaşımı" → Run workflow, "Sadece dene" işaretli: hata yoksa `deneme_modu: false` yap.

## Bilgisayarda panel (isteğe bağlı)
`baslat.bat` → http://localhost:5055: haberleri listeler, elle paylaşma ve slayt önizleme. GitHub ile aynı anda
otomatik modu açma; ikisi ayrı `durum.json` tutar ve aynı haberi iki kez paylaşabilir.

## Dikkat
- Haber fotoğrafları telifli olduğu için kullanılmıyor; kart sade tasarım + kaynak adı + link.
- Partilerden para alınan paylaşımlar Instagram'da "Ücretli ortaklık" etiketiyle yapılmalı.
- Seçim yasakları döneminde (seçimden önceki son gün akşamından oy verme bitişine kadar) anket/tahmin yayını
  yasaktır; o saatlerde workflow'u durdur (Actions → ... → Disable workflow).
