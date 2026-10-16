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
    if "--baglanti" in sys.argv:  # sadece Instagram bağlantısını kontrol et, hiçbir şey paylaşma
        import paylas
        ig = paylas.Instagram(haber.ayar()["instagram"])
        print("Bağlantı:", ig.baglanti())
        return
    if "--deneme" in sys.argv:
        cfg = haber.ayar()
        cfg["deneme_modu"] = True
        haber.ayar = lambda: cfg
    yeni = haber.guncelle()
    print(f"{yeni} yeni haber")
    onceki = haber.durum_oku().get("kayit", [""])[0] if haber.durum_oku().get("kayit") else ""
    bot.otomatik_tur(zorla=True)
    kayit = haber.durum_oku().get("kayit", [])
    if kayit and kayit[0] != onceki:
        print(kayit[0])
    if kayit and "başarısız" in kayit[0]:
        sys.exit(1)  # GitHub'da kırmızı görünsün, e-posta gelsin


if __name__ == "__main__":
    main()
