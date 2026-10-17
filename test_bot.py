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
        h = dict(self.ornek_haber, duzenleme=duzenleme)
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


if __name__ == "__main__":
    unittest.main()
