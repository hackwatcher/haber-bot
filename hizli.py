"""Antigravity × HaberBot hızlı CLI aracı.

Kullanım:
  python hizli.py kontrol [--zorla]
  python hizli.py liste [--adet 8]
  python hizli.py oku <hid>
  python hizli.py uret <hid> --dosya <duzenleme.json> [--video] [--serit <cikti.jpg>]
"""

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import warnings

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image  # noqa: E402

import bot  # noqa: E402
import haber  # noqa: E402
import ozet  # noqa: E402

KAPAKLAR = os.path.join(haber.KOK, "data", "kapaklar")
os.makedirs(KAPAKLAR, exist_ok=True)


def serit_olustur(yollar, cikti):
    """Slayt görsellerini tek bakışta önizlemek için yan yana tek bir JPEG şeridine birleştirir."""
    imgs = []
    for y in yollar:
        if y.lower().endswith(".mp4"):
            jpg = os.path.splitext(y)[0] + ".jpg"
            if os.path.exists(jpg):
                imgs.append(Image.open(jpg).convert("RGB"))
            else:
                try:
                    import subprocess
                    import reels
                    kare_gecici = cikti + "_tmpkare.jpg"
                    subprocess.run([reels.ffmpeg_yolu(), "-y", "-loglevel", "error", "-ss", "00:00:01",
                                    "-i", y, "-frames:v", "1", kare_gecici], check=True, timeout=10)
                    if os.path.exists(kare_gecici):
                        imgs.append(Image.open(kare_gecici).convert("RGB"))
                        try:
                            os.remove(kare_gecici)
                        except Exception:
                            pass
                except Exception:
                    pass
        else:
            imgs.append(Image.open(y).convert("RGB"))
    if not imgs:
        return cikti
    w, h = 540, 675
    bosluk = 12
    serit = Image.new("RGB", (w * len(imgs) + bosluk * max(0, len(imgs) - 1), h), (8, 10, 14))
    for i, im in enumerate(imgs):
        serit.paste(im.resize((w, h), Image.LANCZOS), (i * (w + bosluk), 0))
    os.makedirs(os.path.dirname(os.path.abspath(cikti)), exist_ok=True)
    serit.save(cikti, "JPEG", quality=92)
    return cikti


def cmd_kontrol(zorla=False, guncelle=True):
    """15 dakikalık zamanlayıcı için: paylaşım kurallarını kontrol eder, uygunsa sıradaki haberi ve metnini döndürür."""
    cfg = haber.ayar()
    o = cfg["otomatik"]
    simdi = bot.simdi()

    if not zorla:
        sa = simdi.hour
        bas, son = o.get("sessiz_saatler", [0, 0])
        if bas <= sa < son:
            sonuc = {"hazir": False, "neden": f"Sessiz saatler ({bas:02d}:00-{son:02d}:00)"}
            print(json.dumps(sonuc, ensure_ascii=False, indent=2))
            return sonuc

        d_on = haber.durum_oku()
        bugun_adet = len(bot.bugun_paylasilan(d_on))
        if bugun_adet >= o["gunluk_en_fazla"]:
            sonuc = {"hazir": False, "neden": f"Günlük sınır doldu ({bugun_adet}/{o['gunluk_en_fazla']})"}
            print(json.dumps(sonuc, ensure_ascii=False, indent=2))
            return sonuc

        tum = [h["paylasildi"] for h in d_on["haberler"].values() if h.get("paylasildi") and h.get("ig_id") != "deneme"]
        if tum:
            gecen_dk = (simdi - dt.datetime.fromisoformat(max(tum))).total_seconds() / 60
            if gecen_dk < o["iki_paylasim_arasi_dakika"]:
                kalan = int(round(o["iki_paylasim_arasi_dakika"] - gecen_dk))
                sonuc = {"hazir": False, "neden": f"Son paylaşımdan {int(gecen_dk)} dk geçti ({kalan} dk daha beklenmeli)"}
                print(json.dumps(sonuc, ensure_ascii=False, indent=2))
                return sonuc

    yeni_sayi = haber.guncelle() if guncelle else 0
    d = haber.durum_oku()
    secilen = bot.otomatik_sec(d, cfg)
    if not secilen:
        sonuc = {"hazir": False, "yeni_cekilen": yeni_sayi, "neden": "Son 90 dakikada paylaşılmamış uygun aday haber yok"}
        print(json.dumps(sonuc, ensure_ascii=False, indent=2))
        return sonuc

    try:
        spot, paragraflar, _ = ozet.sayfa_oku(secilen["link"])
    except Exception as e:
        spot, paragraflar = f"Hata: {e}", []

    varsayilan = ozet.zenginlestir(secilen)
    varsayilan.pop("kelimeler", None)
    sonuc = {
        "hazir": True,
        "yeni_cekilen": yeni_sayi,
        "haber": {
            "id": secilen["id"],
            "zaman": secilen["zaman"][:16].replace("T", " "),
            "kaynak": secilen["kaynak"],
            "diger_kaynaklar": secilen.get("diger_kaynaklar", []),
            "baslik": secilen["baslik"],
            "link": secilen["link"],
            "spot": spot,
            "paragraflar": paragraflar[:15],
            "varsayilan_analiz": varsayilan,
        },
    }
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    return sonuc


def cmd_liste(adet=8, guncelle=True):
    """Paylaşılmamış güncel haberleri öncelik, çoklu kaynak ve zamana göre listeler."""
    yeni_sayi = haber.guncelle() if guncelle else 0
    d = haber.durum_oku()
    adaylar = [h for h in d["haberler"].values() if h["durum"] == "yeni" and not h.get("tekrar_of")]
    adaylar.sort(
        key=lambda h: (h["zaman"][:10], h.get("oncelikli", False), len(h.get("diger_kaynaklar", [])), h["zaman"]),
        reverse=True,
    )
    sonuc = {
        "yeni_cekilen": yeni_sayi,
        "toplam_aday": len(adaylar),
        "haberler": [
            {
                "id": h["id"],
                "zaman": h["zaman"][:16].replace("T", " "),
                "kaynak": h["kaynak"],
                "diger_kaynaklar": h.get("diger_kaynaklar", []),
                "baslik": h["baslik"],
                "ozet": h.get("ozet", ""),
                "link": h["link"],
            }
            for h in adaylar[:adet]
        ],
    }
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    return sonuc


def cmd_oku(hid):
    """Haberin tam makale metnini ve kural tabanlı varsayılan analizini JSON olarak döndürür."""
    d = haber.durum_oku()
    h = d["haberler"].get(hid)
    if not h:
        raise RuntimeError(f"Haber bulunamadı: {hid}")
    try:
        spot, paragraflar, _ = ozet.sayfa_oku(h["link"])
    except Exception as e:
        spot, paragraflar = f"Hata: {e}", []
    varsayilan = ozet.zenginlestir(h)
    varsayilan.pop("kelimeler", None)
    sonuc = {
        "id": hid,
        "kaynak": h["kaynak"],
        "diger_kaynaklar": h.get("diger_kaynaklar", []),
        "baslik": h["baslik"],
        "link": h["link"],
        "spot": spot,
        "paragraflar": paragraflar[:15],
        "varsayilan_analiz": varsayilan,
    }
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    return sonuc


def cmd_uret(hid, duzenleme, video=False, serit_hedef=None):
    """Özel kanca, AI kapak görseli ve slaytlarla karusel (+ Reels/story + yan yana şerit) üretir."""
    duz = dict(duzenleme)
    foto = duz.get("foto")
    if foto:
        kaynak_yol = foto["yol"] if isinstance(foto, dict) else foto
        if not os.path.isabs(kaynak_yol):
            kaynak_yol = os.path.join(haber.KOK, kaynak_yol)
        not_metni = (
            foto.get("not", f"Temsili görsel · {haber.ayar()['marka']}")
            if isinstance(foto, dict)
            else f"Temsili görsel · {haber.ayar()['marka']}"
        )
        if os.path.exists(kaynak_yol):
            kalici_dosya = os.path.join(KAPAKLAR, f"{hid}.jpg")
            if os.path.abspath(kaynak_yol) != os.path.abspath(kalici_dosya):
                shutil.copy(kaynak_yol, kalici_dosya)
            # Windows ve GitHub Actions (Linux) uyumluluğu için bağıl yol kaydedilir
            duz["foto"] = {"yol": f"data/kapaklar/{hid}.jpg", "not": not_metni}

    res = bot.haberi_ozellestir(hid, duz, video_uret=video)
    klasor = os.path.join(bot.GORSEL, hid)
    serit_yol = serit_olustur(res["yollar"], os.path.join(klasor, "serit.jpg"))
    if serit_hedef:
        shutil.copy(serit_yol, serit_hedef)

    cikti = {
        "id": hid,
        "konu": res["haber"]["konu"],
        "kanca": res["haber"]["kanca"],
        "baslik": res["haber"]["baslik"],
        "slayt_sayisi": len(res["yollar"]),
        "kapak": res["yollar"][0],
        "serit": serit_hedef or serit_yol,
        "slaytlar": res["yollar"],
        "video": res["video"],
        "story": res["story"],
        "hatalar": res["hatalar"],
        "aciklama": res["aciklama"],
    }
    print(json.dumps(cikti, ensure_ascii=False, indent=2))
    return cikti


def main():
    p = argparse.ArgumentParser(description="HaberBot × Antigravity Hızlı Üretim Aracı")
    sub = p.add_subparsers(dest="komut", required=True)

    p_kontrol = sub.add_parser("kontrol", help="Zamanlayıcı için paylaşım uygunluğunu ve sıradaki haberi kontrol et")
    p_kontrol.add_argument("--zorla", action="store_true", help="Saat/süre sınırlarını atla")
    p_kontrol.add_argument("--guncelleme-yok", action="store_true")

    p_liste = sub.add_parser("liste", help="Güncel paylaşılmamış haberleri listele")
    p_liste.add_argument("--adet", type=int, default=8)
    p_liste.add_argument("--guncelleme-yok", action="store_true")

    p_oku = sub.add_parser("oku", help="Haberin tam metnini ve analizini oku")
    p_oku.add_argument("hid")

    p_uret = sub.add_parser("uret", help="Özel kanca, görsel ve slaytlarla kart/karusel/Reels üret")
    p_uret.add_argument("hid")
    p_uret.add_argument("--dosya", required=True, help="Düzenleme JSON dosya yolu")
    p_uret.add_argument("--video", action="store_true", help="Reels (.mp4) ve Story (.jpg) de üret")
    p_uret.add_argument("--serit", help="Yan yana şerit görselinin kopyalanacağı ek yol")

    args = p.parse_args()
    if args.komut == "kontrol":
        cmd_kontrol(zorla=args.zorla, guncelle=not args.guncelleme_yok)
    elif args.komut == "liste":
        cmd_liste(adet=args.adet, guncelle=not args.guncelleme_yok)
    elif args.komut == "oku":
        cmd_oku(args.hid)
    elif args.komut == "uret":
        with open(args.dosya, encoding="utf-8") as f:
            duz = json.load(f)
        cmd_uret(args.hid, duz, video=args.video, serit_hedef=args.serit)


if __name__ == "__main__":
    main()
