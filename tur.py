"""Tek tur: haberleri çek, kurallar izin veriyorsa bir haber paylaş, çık. GitHub Actions her 15 dakikada bunu çalıştırır.

    python tur.py            config.json'daki deneme_modu neyse ona göre
    python tur.py --deneme   ne olursa olsun gerçekten paylaşma
"""

import sys
import warnings

warnings.filterwarnings("ignore")

import bot  # noqa: E402
import haber  # noqa: E402


def main():
    if "--baglanti" in sys.argv:  # sadece Instagram ve Facebook bağlantısını kontrol et, hiçbir şey paylaşma
        import paylas
        ig = paylas.Instagram(haber.ayar()["instagram"])
        print("Instagram Bağlantısı:", ig.baglanti())
        print("Facebook Yetki Kontrolü:", ig.facebook_kontrol())
        return
    if "--deneme" in sys.argv:
        cfg = haber.ayar()
        cfg["deneme_modu"] = True
        haber.ayar = lambda: cfg
    yeni = haber.guncelle()
    print(f"{yeni} yeni haber")
    eski = haber.durum_oku().get("kayit", [])
    onceki_ilk = eski[0] if eski else None
    bot.otomatik_tur(zorla=True)
    kayit = haber.durum_oku().get("kayit", [])
    # bu turda eklenen satırlar: bir önceki en yeni satıra kadar olanlar
    yeni_kayit = kayit[:kayit.index(onceki_ilk)] if onceki_ilk in kayit else kayit[:5]
    for satir in reversed(yeni_kayit):
        print(satir)
    if any("başarısız" in k for k in yeni_kayit):
        sys.exit(1)  # GitHub'da kırmızı görünsün, e-posta gelsin


if __name__ == "__main__":
    main()
