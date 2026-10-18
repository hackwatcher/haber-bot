"""HaberBot birim ve entegrasyon testleri (haber.py, ozet.py, kart.py, karusel.py, reels.py, bot.py)."""

import os
import shutil
import tempfile
import unittest

from PIL import Image

import bot
import haber
import kart
import karusel
import ozet


class TestHaberBot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ornek_foto = os.path.join(self.tmp, "ornek_kapak.jpg")
        Image.new("RGB", (1200, 800), (40, 80, 140)).save(self.ornek_foto, "JPEG")
        self.ornek_haber = {
            "id": "test12345678",
            "kaynak": "BBC Türkçe",
            "diger_kaynaklar": ["NTV", "Sözcü"],
            "baslik": "100 yıl önce amatör bir hırsızlıkta çalınan nadir pembe elmas",
            "ozet": "Nadir bulunan pembe bir elmas, Fransa'da yeniden sergilenecek.",
            "link": "https://www.bbc.com/turkce/articles/test",
            "zaman": "2026-10-17T18:31:04+03:00",
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        klasor = os.path.join(bot.GORSEL, "test12345678")
        shutil.rmtree(klasor, ignore_errors=True)

    def test_xml_coz_bozuk_karakter_ve_ampersand(self):
        """Hürriyet RSS akışındaki kaçışsız '&' ve kontrol karakterlerini temizleyip ayrıştırmalı."""
        bozuk_xml = b'<?xml version="1.0" encoding="UTF-8"?><rss><channel><item>\x07<title>Test &amp; Deneme & Yeni</title><link>https://ornek.com?a=1&b=2</link></item></channel></rss>'
        kok = haber.xml_coz(bozuk_xml)
        baslik = haber.metni(kok.find(".//item"), "title")
        self.assertIn("Test & Deneme & Yeni", baslik)

    def test_ozet_konu_ve_uzun_tirnakli_cumle(self):
        """Avrupa/Fransa geçen haber 'dunya' olmalı ve kısa özel isim tırnaklı 185 krk cümle elenmemeli."""
        baslik = "Fransa'da 100 yıl önce çalınan nadir elmas"
        govde = "Paris ve Avrupa genelinde büyük yankı uyandıran olay Fransa'da sergilenecek."
        self.assertEqual(ozet.konu_bul(baslik, govde), "dunya")

        cumle = '"Grand Condé" olarak bilinen dokuz karatlık armut biçimli değerli taş, Ekim 1926 tarihinde Chantilly Şatosu\'na yapılan gece baskınında çalınmış ve elma içine saklanmıştı.'
        secilen = ozet.sec([ozet.kisalt(cumle, 170)], 1, [haber.kelimeler(baslik)], haber.kelimeler(baslik))
        self.assertEqual(len(secilen), 1)

    def test_kart_coklu_kaynak_ve_foto(self):
        """Çoklu kaynak rozeti, fotoğraflı kapak ve fotoğraf bulunamadığında güvenli geri dönüş çalışmalı."""
        cikti_foto = os.path.join(self.tmp, "kart_foto.jpg")
        h_foto = dict(self.ornek_haber, konu="dunya", kanca="ELMANIN İÇİNDE ÇALINDI", foto=self.ornek_foto, ozet="")
        kart.ciz_kart(h_foto, "XHABER", "@xhabercom", cikti_foto, sayfa=(1, 5), kaydir=True)
        self.assertTrue(os.path.exists(cikti_foto))
        with Image.open(cikti_foto) as im:
            self.assertEqual(im.size, (1080, 1350))

        # Olmayan fotoğraf yolunda çökmeden düz karta düşmeli
        cikti_yedek = os.path.join(self.tmp, "kart_yedek.jpg")
        h_yedek = dict(self.ornek_haber, konu="gundem", kanca="SON DAKİKA", foto="/olmayan/yol.jpg", ozet="")
        kart.ciz_kart(h_yedek, "XHABER", "@xhabercom", cikti_yedek)
        self.assertTrue(os.path.exists(cikti_yedek))

        acik = kart.aciklama(h_foto, "#haber #gündem", karusel=True)
        self.assertIn("ELMANIN İÇİNDE ÇALINDI", acik)
        self.assertIn("BBC Türkçe, NTV, Sözcü", acik)

    def test_bot_uygula_ve_hazirla_ve_reels(self):
        """bot.hazirla ve ekleri_hazirla özel kanca, görsel, slaytlar ve Reels/Story üretmeli."""
        duzenleme = {
            "konu": "dunya",
            "kanca": "ELMANIN İÇİNDE ÇALINMIŞTI",
            "baslik": "100 yıl önce çalınan nadir pembe elmas ilk kez sergileniyor",
            "foto": {"yol": self.ornek_foto, "not": "Temsili görsel · XHABER"},
            "slaytlar": [
                {"etiket": "Ne oldu?", "metin": "9 karatlık pembe elmas 100 yıl sonra yeniden sergileniyor."},
                {"etiket": "Detaylar", "maddeler": ["Ekim 1926'da çalındı.", "Otelde elma içinde bulundu."]},
                {"etiket": "Rakamlarla", "rakamlar": [("9 karat", "Elmasın ağırlığı")]},
            ],
        }
        h = dict(self.ornek_haber, duzenleme=duzenleme, tg_kanal="sahinozkan000")
        # Web panelinden boş string geldiğinde mevcut düzenlemeyi ezmemeli
        yollar, metin, z = bot.hazirla(h, {"kanca": "", "baslik": ""})
        self.assertEqual(z["kanca"], "ELMANIN İÇİNDE ÇALINMIŞTI")
        self.assertEqual(z["konu"], "dunya")
        self.assertEqual(len(yollar), 5)  # kapak + 3 slayt + kapanış

        klasor = os.path.join(bot.GORSEL, h["id"])
        video, story, hatalar = bot.ekleri_hazirla(z, yollar, klasor)
        self.assertEqual(hatalar, [])
        self.assertTrue(video and os.path.exists(video))
        self.assertTrue(story and os.path.exists(story))

        # hizli.serit_olustur ve bağıl kapak yolu testi
        import hizli
        serit_yol = hizli.serit_olustur(yollar, os.path.join(self.tmp, "serit.jpg"))
        self.assertTrue(os.path.exists(serit_yol))
        k_sonuc = hizli.cmd_kontrol(zorla=True, guncelle=False)
        self.assertIn("hazir", k_sonuc)

    def test_skill_md_gecerliligi(self):
        """haberbot-editor SKILL.md dosyası mevcut olmalı ve zorunlu bölümleri içermeli."""
        skill_yol = r"C:\Users\CASPER\.gemini\config\skills\haberbot-editor\SKILL.md"
        self.assertTrue(os.path.exists(skill_yol))
        with open(skill_yol, encoding="utf-8") as f:
            icerik = f.read()
        self.assertIn("name: haberbot-editor", icerik)
        self.assertIn("hizli.py", icerik)
        self.assertIn("## When to Use", icerik)
        self.assertIn("## Limitations", icerik)

    def test_ai_editor_fallback_ve_mock(self):
        """ai_editor anahtar yokken varsayılana dönmeli, anahtar varken AI kanca ve görseli uygulamalı."""
        import unittest.mock as mock
        import ai_editor

        varsayilan = dict(self.ornek_haber, konu="gundem", kanca="Son dakika", slaytlar=[])
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "API_KEY_PLACEHOLDER"}):
            sonuc = ai_editor.zenginlestir_ai(self.ornek_haber, varsayilan)
            self.assertEqual(sonuc["kanca"], "Son dakika")

        sahte_ai_json = {
            "konu": "dunya",
            "kanca": "ELMANIN İÇİNDE ÇALINDI",
            "baslik": "100 yıl önce çalınan elmas sergileniyor",
            "ozet": "Nadir elmas sergide.",
            "gorsel_prompt": "Rare pink diamond in museum",
            "slaytlar": [
                {"etiket": "Ne oldu?", "metin": "Elmas bulundu."},
                {"etiket": "Detaylar", "maddeler": ["Madde 1", "Madde 2"]},
            ],
        }
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}), \
             mock.patch("ozet.sayfa_oku", return_value=("Spot", ["Paragraf 1"], "Tam metin")), \
             mock.patch("ai_editor.metin_analiz_et", return_value=sahte_ai_json), \
             mock.patch("ai_editor.gorsel_uret", return_value="data/kapaklar/test12345678.jpg"):
            z = ai_editor.zenginlestir_ai(self.ornek_haber, varsayilan)
            self.assertEqual(z["kanca"], "ELMANIN İÇİNDE ÇALINDI")
            self.assertEqual(z["konu"], "dunya")
            self.assertEqual(z["foto"]["yol"], "data/kapaklar/test12345678.jpg")

    def test_telegram_kaynak_ve_akilli_oncelik(self):
        """Telegram HTML ayrıştırıcı foto/video/metin çıkarmalı ve bot.otomatik_sec Akıllı Öncelik uygulamalı."""
        import telegram_kaynak

        ornek_html = '''
        <div class="tgme_widget_message" data-post="sahinozkan000/30276">
          <a class="tgme_widget_message_photo_wrap" style="width:680px;background-image:url('https://cdn4.telesco.pe/file/test.jpg')"></a>
          <div class="tgme_widget_message_text" dir="auto">Fenerbahçe, Alanyaspor'u bugün oynanan maçta 3 - 0 yendi.<br/>İrfancan Kahveci'nin 3 golü de iptal edildi.</div>
          <time datetime="2026-10-17T18:30:00+00:00"></time>
        </div>
        <div class="tgme_widget_message" data-post="sahinozkan000/30272">
          <video src="https://cdn4.telesco.pe/file/test.mp4"></video>
          <div class="tgme_widget_message_text" dir="auto">İstanbul Çekmeköy'de sel felaketini aktaran muhabire otobüs aynası çarptı.</div>
          <time datetime="2026-10-17T18:10:00+00:00"></time>
        </div>
        '''
        liste = telegram_kaynak.html_ayristir(ornek_html, ad="XHABER", kullanici="sahinozkan000")
        self.assertEqual(len(liste), 2)
        self.assertEqual(liste[0]["tg_foto_url"], "https://cdn4.telesco.pe/file/test.jpg")
        self.assertEqual(liste[1]["tg_video_url"], "https://cdn4.telesco.pe/file/test.mp4")

        simdi_dt = bot.simdi()
        simdi_iso = simdi_dt.isoformat()
        sekiz_saat_once = (simdi_dt - bot.dt.timedelta(hours=8)).isoformat()
        d = {
            "haberler": {
                "rss_tek": {"id": "rss_tek", "durum": "yeni", "oncelikli": False, "diger_kaynaklar": [], "zaman": simdi_iso},
                "tg_haber": {"id": "tg_haber", "durum": "yeni", "oncelikli": False, "diger_kaynaklar": [], "tg_kanal": "sahinozkan000", "zaman": sekiz_saat_once},
            }
        }
        cfg = {"otomatik": {"haber_en_eski_dakika": 90, "telegram_en_eski_dakika": 1440, "sadece_oncelikli": False}}
        secilen = bot.otomatik_sec(d, cfg)
        self.assertEqual(secilen["id"], "tg_haber")

    def test_dinamik_hashtagler_ve_ilk_yorum(self):
        """Habere özel 2 dinamik hashtag ve paylaşıma otomatik ilk yorum eklenmeli."""
        h_ai = dict(self.ornek_haber, hashtagler=["#fransa", "#elmas"])
        tags_ai = kart.dinamik_etiketler(h_ai)
        self.assertEqual(tags_ai, ["#fransa", "#elmas"])
        acik_ai = kart.aciklama(h_ai, "#haber #sondakika #gündem")
        self.assertTrue(acik_ai.endswith("#haber #sondakika #gündem #fransa #elmas"))

        # AI etiketi yoksa başlıktan/ilden türetmeli
        h_kural = dict(self.ornek_haber, hashtagler=[], il="Bursa", baslik="Bursa'da yeni teknoloji yatırımı başladı")
        tags_kural = kart.dinamik_etiketler(h_kural)
        self.assertEqual(len(tags_kural), 2)
        self.assertIn("#bursa", tags_kural)

    def test_spiker_hizli_seslendir_ve_story_telegram_siniri(self):
        """Spiker metni hızlı bülten havasında üretilmeli, story sadece Telegram haberinde çalışmalı."""
        import spiker

        h = dict(self.ornek_haber, kanca="TARİHİ ZİRVE", baslik="Liderler masada toplandı", ozet="Ekonomik kararlar alındı.")
        # öncelikli olmayan haber "Flaş" diye açılmaz
        self.assertTrue(spiker.spiker_metni_uret(dict(h, oncelikli=False, diger_kaynaklar=[])).startswith("TARİHİ ZİRVE."))
        h["oncelikli"] = True
        metin = spiker.spiker_metni_uret(h)
        self.assertTrue(metin.startswith("Flaş gelişme: TARİHİ ZİRVE!"))
        self.assertIn("Liderler masada toplandı", metin)

        parcalar = spiker.altyazi_parcala(metin, 8.0)
        self.assertTrue(len(parcalar) >= 2)
        self.assertEqual(parcalar[0][0], 0.0)

        # Story sınırlandırma testi: RSS haberinde Story None olmalı, Telegram'da üretilmeli
        import unittest.mock as mock
        with mock.patch("haber.ayar", return_value={"marka": "XHABER", "kullanici_adi": "@xhabercom", "story": {"acik": True, "sadece_telegram": True}, "reels": {"acik": False}}):
            yollar = [self.ornek_foto]
            klasor = os.path.join(self.tmp, "ekler_test")
            os.makedirs(klasor, exist_ok=True)

            # RSS haberi -> story None
            _, story_rss, _ = bot.ekleri_hazirla(self.ornek_haber, yollar, klasor)
            self.assertIsNone(story_rss)

            # Telegram haberi -> story üretilmeli
            h_tg = dict(self.ornek_haber, tg_kanal="sahinozkan000")
            _, story_tg, _ = bot.ekleri_hazirla(h_tg, yollar, klasor)
            self.assertIsNotNone(story_tg)
            self.assertTrue(os.path.exists(story_tg))

    # ---------- denetim sonrası eklenen testler ----------

    def _kare(self, video, saniye):
        """Videodan belirtilen saniyedeki kareyi PIL görseli olarak döndürür."""
        import subprocess
        import reels
        yol = os.path.join(self.tmp, f"kare_{saniye}.png")
        subprocess.run([reels.ffmpeg_yolu(), "-y", "-loglevel", "error", "-ss", str(saniye), "-i", video,
                        "-frames:v", "1", "-update", "1", yol], check=True)
        with Image.open(yol) as im:
            return im.convert("RGB").copy()

    @staticmethod
    def _parlaklik(img, kutu):
        from PIL import ImageStat
        return sum(ImageStat.Stat(img.crop(kutu)).mean) / 3

    def test_daktilo_kart_yerlesim_sabit(self):
        """Daktilo: tüm harfler görünürken kart normal kartla birebir aynı, kısmi başlıkta farklı olmalı."""
        from PIL import ImageChops
        h = dict(self.ornek_haber, konu="gundem", kanca="SON DAKİKA")
        normal = os.path.join(self.tmp, "normal.jpg")
        tam = os.path.join(self.tmp, "tam.jpg")
        kismi = os.path.join(self.tmp, "kismi.jpg")
        kart.ciz_kart(h, "XHABER", "@xhabercom", normal)
        kart.ciz_kart(dict(h, daktilo_harf=len(h["baslik"]), daktilo_imlec=False), "XHABER", "@xhabercom", tam)
        kart.ciz_kart(dict(h, daktilo_harf=8, daktilo_imlec=True), "XHABER", "@xhabercom", kismi)
        with Image.open(normal) as a, Image.open(tam) as b, Image.open(kismi) as c:
            self.assertIsNone(ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox())
            fark = ImageChops.difference(a.convert("RGB"), c.convert("RGB")).getbbox()
            self.assertIsNotNone(fark)
            # yalnızca başlık bölgesi değişir; üst bilgi (marka/etiket, y<200) sabit kalır = yazı zıplamaz
            self.assertGreater(fark[1], 200)

    def test_daktilo_harf_sayisi(self):
        import reels
        self.assertEqual(reels.daktilo_harf_sayisi(0, 78, 50), 1)
        self.assertEqual(reels.daktilo_harf_sayisi(77, 78, 50), 50)
        self.assertEqual(reels.daktilo_harf_sayisi(5, 0, 50), 50)

    def test_reels_daktilo_ve_yanip_sonen_etiket(self):
        """Kart Reels: başta başlık eksik, sonra tam; SON DAKİKA etiketi daktilo sırasında da yanıp sönmeli."""
        import reels
        from PIL import ImageChops
        h = dict(self.ornek_haber, konu="gundem", kanca="SON DAKİKA")
        slayt = kart.ciz_kart(h, "XHABER", "@xhabercom", os.path.join(self.tmp, "s1.jpg"))

        def ciz(harf, imlec, cikti):
            return kart.ciz_kart(dict(h, daktilo_harf=harf, daktilo_imlec=imlec), "XHABER", "@xhabercom", cikti)

        cikti = os.path.join(self.tmp, "daktilo.mp4")
        reels.video(h, "XHABER", "@xhabercom", [slayt], cikti, spikerli=False, daktilo_ciz=ciz, daktilo_sn=2.6)
        self.assertTrue(os.path.exists(cikti))
        self.assertFalse(os.path.exists(cikti + "_daktilo.jpg"))  # geçici dosya temizlendi

        bas, son = self._kare(cikti, 0.5), self._kare(cikti, 4.0)
        baslik_bolgesi = (0, reels.UST + 300, reels.W, reels.UST + 1100)
        self.assertIsNotNone(ImageChops.difference(bas.crop(baslik_bolgesi), son.crop(baslik_bolgesi)).getbbox())

        _, kutu = reels.zemin_kare(h, "XHABER", "@xhabercom", slayt, 0, 1)
        parlak, sonuk = self._parlaklik(self._kare(cikti, 0.0), kutu), self._parlaklik(self._kare(cikti, 0.6), kutu)
        self.assertGreater(parlak - sonuk, 8)

    def test_gercek_video_etiket_yanip_soner(self):
        """Telegram'dan gelen gerçek videoda da etiket yanıp sönmeli (eskiden sabitti)."""
        import subprocess
        import reels
        kaynak = os.path.join(self.tmp, "kaynak.mp4")
        subprocess.run([reels.ffmpeg_yolu(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=640x360:rate=30:duration=4", "-pix_fmt", "yuv420p", kaynak], check=True)
        h = dict(self.ornek_haber, konu="gundem", kanca="SON DAKİKA")
        cikti = os.path.join(self.tmp, "gercek.mp4")
        reels.gercek_video_reels(h, "XHABER", "@xhabercom", kaynak, cikti)
        self.assertTrue(os.path.exists(cikti))
        self.assertFalse(os.path.exists(cikti + "_etiket.png"))
        self.assertTrue(reels.video_bilgisi(cikti)["ses"])  # sessiz kaynağa sessiz ses izi eklenir
        kisa = os.path.join(self.tmp, "kisa.mp4")
        subprocess.run([reels.ffmpeg_yolu(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=640x360:rate=30:duration=2", "-pix_fmt", "yuv420p", kisa], check=True)
        with self.assertRaises(RuntimeError):  # 3 sn altı Reels olmaz, slayt videosuna dönülür
            reels.gercek_video_reels(h, "XHABER", "@xhabercom", kisa, cikti)
        f = reels.font(reels.KALIN, 46)
        from PIL import ImageDraw
        w = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength("SON DAKİKA", font=f) + 128
        kutu = (int((reels.W - w) / 2), 180, int((reels.W + w) / 2), 266)
        parlak, sonuk = self._parlaklik(self._kare(cikti, 0.0), kutu), self._parlaklik(self._kare(cikti, 0.6), kutu)
        self.assertGreater(parlak - sonuk, 8)

    def test_ses_suresi_ffprobe_yokken(self):
        """ffprobe yoksa süre ffmpeg çıktısından doğru okunmalı (eskiden ~4 kat kısa tahmin ediliyordu)."""
        import subprocess
        import unittest.mock as mock
        import spiker
        mp3 = os.path.join(self.tmp, "ton.mp3")
        subprocess.run([spiker.ffmpeg_yolu(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=3", "-b:a", "48k", mp3], check=True)
        with mock.patch("spiker.ffprobe_yolu", return_value="olmayan_ffprobe_xyz"):
            self.assertAlmostEqual(spiker.ses_suresi(mp3), 3.0, delta=0.3)

    def test_bagimliliklar_ve_ayar_tutarli(self):
        """Canlı bot gerçekçi spikeri kurmalı; config'te daktilo açık, altyazı kapalı olmalı."""
        kok = os.path.dirname(os.path.abspath(__file__))
        for dosya in ("requirements-bot.txt", "requirements.txt"):
            with open(os.path.join(kok, dosya), encoding="utf-8") as f:
                paketler = f.read().split()
            self.assertIn("edge-tts", paketler, dosya)
            self.assertIn("gTTS", paketler, dosya)
        r = haber.ayar()["reels"]
        self.assertTrue(r["daktilo"])
        self.assertFalse(r["altyazi"])
        self.assertAlmostEqual(r["spiker_hiz"], 1.15)

    def test_cift_paylasim_ve_icerik_benzerlik_engeli(self):
        """Aynı link veya %75+ benzer içerik daha önce paylaşıldıysa otomatik_sec ve haberi_paylas engellemeli."""
        import unittest.mock as mock
        h1 = {
            "id": "h1",
            "kaynak": "NTV",
            "baslik": "Fenerbahçe Alanyaspor'u 3-0 yendi",
            "ozet": "Maçta 3 gol atıldı.",
            "link": "https://t.me/kanal/100",
            "zaman": "2026-10-18T00:00:00+03:00",
            "durum": "paylasildi",
            "paylasildi": "2026-10-18T00:10:00+03:00"
        }
        # Aynı linke sahip yeni haber
        h2 = {
            "id": "h2",
            "kaynak": "NTV",
            "baslik": "Fenerbahçe Alanyaspor maçı bitti",
            "ozet": "Farklı özet.",
            "link": "https://t.me/kanal/100",
            "zaman": "2026-10-18T00:05:00+03:00",
            "durum": "yeni"
        }
        # Farklı link ama tıpatıp aynı olayı anlatan haber
        h3 = {
            "id": "h3",
            "kaynak": "Sözcü",
            "baslik": "Fenerbahçe Alanyaspor'u 3-0 mağlup etti",
            "ozet": "Maçta 3 gol kaydedildi.",
            "link": "https://sozcu.com.tr/fb-alanya",
            "zaman": "2026-10-18T00:06:00+03:00",
            "durum": "yeni"
        }
        d = {"haberler": {"h1": h1, "h2": h2, "h3": h3}, "kayit": []}
        cfg = {"otomatik": {"haber_en_eski_dakika": 9999, "gunluk_en_fazla": 50, "iki_paylasim_arasi_dakika": 0}}

        secilen = bot.otomatik_sec(d, cfg)
        self.assertIsNone(secilen, "Aynı link veya benzer içeriğe sahip haberler elenmeliydi")
        self.assertEqual(h2["durum"], "tekrar")
        self.assertEqual(h3["durum"], "tekrar")

        # haberi_paylas doğrudan çağrılsa bile hata fırlatarak engellemeli
        with mock.patch("haber.durum_oku", return_value=d), mock.patch("haber.durum_yaz"):
            with self.assertRaises(RuntimeError):
                bot.haberi_paylas("h2")

    def test_telegram_kaynak_ve_linki_gonderiden_gizlenir(self):
        """Telegram haberlerinde gönderi açıklamasında ve kartlarda sahinozkan / t.me / kaynak yazmamalı."""
        h_tg = {
            "id": "tg_test",
            "kaynak": "XHABER",
            "baslik": "İstanbul'da kaza meydana geldi",
            "ozet": "Olay yerinden görüntüler paylaşıldı.",
            "link": "https://t.me/sahinozkan000/30275",
            "zaman": "2026-10-18T00:00:00+03:00",
            "tg_kanal": "sahinozkan000"
        }
        metin = kart.aciklama(h_tg, "#haber")
        self.assertNotIn("sahinozkan", metin)
        self.assertNotIn("t.me", metin)
        self.assertNotIn("Kaynak:", metin)

        # RSS haberinde ise kaynak ve link normal şekilde kalmalı
        h_rss = dict(self.ornek_haber)
        metin_rss = kart.aciklama(h_rss, "#haber")
        self.assertIn("Kaynak: BBC Türkçe", metin_rss)
        self.assertIn(h_rss["link"], metin_rss)

        # Kart ve karusel kapanış çizimleri hata vermemeli
        kart_cikti = os.path.join(self.tmp, "kart_tg.jpg")
        kart.ciz_kart(h_tg, "XHABER", "@xhabercom", kart_cikti)
        self.assertTrue(os.path.exists(kart_cikti))

        kapanis_cikti = os.path.join(self.tmp, "kapanis_tg.jpg")
        karusel.kapanis(h_tg, "XHABER", "@xhabercom", (7, 7), kapanis_cikti)
        self.assertTrue(os.path.exists(kapanis_cikti))

    def test_hareketli_karusel_ve_reels_zoom(self):
        """Karusel fotoğraf içeren haberlerde hareketli kapak .mp4 üretmeli, video=True durumunda .jpg kalmalı."""
        h = dict(self.ornek_haber, foto=self.ornek_foto, slaytlar=[
            {"etiket": "Bilgi", "metin": "Slayt metni"}
        ])
        klasor = os.path.join(self.tmp, "karusel_test")
        yollar = karusel.karusel(h, "XHABER", "@xhabercom", klasor, video=False)
        self.assertTrue(yollar[0].endswith(".mp4"), "Karusel kapağı hareketli video olmalı")
        self.assertTrue(os.path.exists(yollar[0]))
        # Yanında statik 01.jpg de bulunmalı
        self.assertTrue(os.path.exists(os.path.join(klasor, "01.jpg")))

        # video=True çağrıldığında Reels için tüm slaytlar resim (.jpg) olmalı
        yollar_v = karusel.karusel(h, "XHABER", "@xhabercom", klasor, video=True)
        self.assertTrue(yollar_v[0].endswith(".jpg"), "Reels için kapak statik resim kalmalı")

    def test_otomatik_tur_dinamik_bekleme_ve_oncelik(self):
        """Altın oran ayarları ve öncelikli haberlerde dinamik 20 dk bekleme indirimi doğrulanmalı."""
        import datetime as dt
        from unittest.mock import patch

        cfg = haber.ayar()
        self.assertEqual(cfg["otomatik"]["iki_paylasim_arasi_dakika"], 45)
        self.assertEqual(cfg["otomatik"]["gunluk_en_fazla"], 12)
        self.assertEqual(cfg["otomatik"]["haber_en_eski_dakika"], 180)
        self.assertIn("son dakika", cfg["otomatik"]["oncelikli_kelimeler"])

        # 30 dakika önce yapılmış bir paylaşım simüle edelim
        simdi = dt.datetime(2026, 10, 18, 14, 30, tzinfo=haber.TR)
        onceki_paylasim = (simdi - dt.timedelta(minutes=30)).isoformat()

        # 1. Normal haber adayı (oncelikli değil, tek kaynaklı)
        h_normal = {
            "id": "h_norm", "baslik": "Normal Gelişme", "zaman": simdi.isoformat(),
            "durum": "yeni", "oncelikli": False, "diger_kaynaklar": []
        }
        d_normal = {
            "otomatik": True,
            "haberler": {
                "eski": {"id": "eski", "durum": "paylasildi", "paylasildi": onceki_paylasim, "ig_id": "123"},
                "h_norm": h_normal
            }
        }

        with patch("bot.simdi", return_value=simdi), \
             patch("haber.durum_oku", return_value=d_normal), \
             patch("bot.otomatik_sec", return_value=h_normal), \
             patch("bot.haberi_paylas") as mock_paylas:
            bot.otomatik_tur()
            mock_paylas.assert_not_called()  # 30 < 45 olduğu için beklemeli

        # 2. Öncelikli haber adayı (oncelikli: True veya 2+ çoklu kaynak)
        h_oncelikli = {
            "id": "h_oncelik", "baslik": "Son Dakika Flaş Gelişme", "zaman": simdi.isoformat(),
            "durum": "yeni", "oncelikli": True, "diger_kaynaklar": ["NTV", "Sözcü"]
        }
        d_oncelikli = {
            "otomatik": True,
            "haberler": {
                "eski": {"id": "eski", "durum": "paylasildi", "paylasildi": onceki_paylasim, "ig_id": "123"},
                "h_oncelik": h_oncelikli
            }
        }

        with patch("bot.simdi", return_value=simdi), \
             patch("haber.durum_oku", return_value=d_oncelikli), \
             patch("bot.otomatik_sec", return_value=h_oncelikli), \
             patch("bot.haberi_paylas") as mock_paylas:
            bot.otomatik_tur()
            mock_paylas.assert_called_once_with("h_oncelik", kim="otomatik")  # flaş: kalan aralığın yarısı (~26 dk) geçti, paylaşmalı


    def test_bekleme_gunun_kalanina_yayilir(self):
        """Günlük hak öğleden sonra bitmesin: kalan hak kalan saatlere yayılır, flaş haber yarı sürede gider."""
        import datetime as dt
        o = {"iki_paylasim_arasi_dakika": 45, "flas_bekleme_dakika": 20, "gunluk_en_fazla": 18, "sessiz_saatler": [2, 7]}
        sabah = dt.datetime(2026, 10, 18, 7, 0, tzinfo=haber.TR)
        self.assertAlmostEqual(bot.bekleme_dakika(o, 0, simdi_=sabah), 1020 / 18)       # 17 saat / 18 hak
        self.assertAlmostEqual(bot.bekleme_dakika(o, 0, True, simdi_=sabah), 1020 / 36)
        aksam = dt.datetime(2026, 10, 18, 21, 0, tzinfo=haber.TR)
        self.assertEqual(bot.bekleme_dakika(o, 10, simdi_=aksam), 45)                     # bol hak: alt sınır
        self.assertEqual(bot.bekleme_dakika(o, 17, True, simdi_=aksam), 90)               # son hak: 180 dk'nın yarısı
        gece = dt.datetime(2026, 10, 19, 1, 0, tzinfo=haber.TR)                         # 00-02 yeni günden yer
        self.assertEqual(bot.bekleme_dakika(o, 0, simdi_=gece), 45)
        # 07:00'den itibaren her turda (15 dk) kural izin verince paylaşılırsa son paylaşım akşama kalmalı
        t, son, adet = sabah, None, 0
        while t.date() == sabah.date():
            if adet < 18 and (son is None or (t - son).total_seconds() / 60 >= bot.bekleme_dakika(o, adet, simdi_=t)):
                son, adet = t, adet + 1
            t += dt.timedelta(minutes=15)
        self.assertGreaterEqual(son.hour, 21)

    def test_kart_ozetsiz_baslikta_cokmez(self):
        """Özet satırı 0 olan kart (Telegram/tek kart) uzun özetle 'list index out of range' vermemeli."""
        h = dict(self.ornek_haber, ozet="Çok uzun bir özet metni. " * 20, slaytlar=[])
        cikti = os.path.join(self.tmp, "ozetsiz.jpg")
        kart.ciz_kart(h, "XHABER", "@xhabercom", cikti)
        self.assertTrue(os.path.exists(cikti))

    def test_facebook_haber_basina_tek_gonderi(self):
        """Video varsa Facebook'a yalnız video gider; video başarısızsa fotoğraflar gönderilir."""
        from unittest.mock import MagicMock, patch
        import paylas
        cfg = {"instagram": {"yontem": "meta", "token_dosyasi": "x", "gorsel_repo": "a/b", "kullanici_adi": "x"},
               "facebook": {"acik": True, "reels": True}}
        for reels_hata in (False, True):
            ig, fb = MagicMock(), MagicMock()
            ig.gonder.return_value = "ig1"
            ig.reels.return_value = "r1"
            fb.reels.side_effect = RuntimeError("olmadı") if reels_hata else None
            fb.reels.return_value = "fbv"
            with patch("paylas.Instagram", return_value=ig), patch("paylas.Facebook", return_value=fb),                  patch("paylas.github_yukle", side_effect=lambda y, r: [f"u{i}" for i in range(len(y))]):
                sonuc = paylas.paylas(["a.jpg", "b.jpg"], "metin", cfg, video="v.mp4")
            self.assertEqual(fb.gonder.called, reels_hata)
            self.assertEqual("facebook" in sonuc, reels_hata)


    def test_reels_yalniz_guclu_haberde(self):
        """sadece_guclu açıkken sıradan haberde Reels üretilmez; öncelikli ya da çok kaynaklı haberde üretilir."""
        from unittest.mock import patch
        cfg = dict(haber.ayar(), reels={"acik": True, "sadece_guclu": True}, story={"acik": False})
        yollar = [self.ornek_foto]
        with patch("haber.ayar", return_value=cfg), patch("reels.video", return_value="reels.mp4") as v:
            sirada = dict(self.ornek_haber, oncelikli=False, diger_kaynaklar=[], slaytlar=[])
            self.assertIsNone(bot.ekleri_hazirla(sirada, yollar, self.tmp)[0])
            v.assert_not_called()
            for guclu in (dict(sirada, oncelikli=True), dict(sirada, diger_kaynaklar=["NTV", "AA"])):
                self.assertEqual(bot.ekleri_hazirla(guclu, yollar, self.tmp)[0], "reels.mp4")


if __name__ == "__main__":
    unittest.main()


