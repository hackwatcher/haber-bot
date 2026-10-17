"""Tek bir haberden karusel: kapak kartı + bilgi slaytları + kaynak/takip slaytı.

Bilgi slaytları haber["slaytlar"] listesinden gelir; her biri {"etiket", "metin" | "maddeler", "rakam"?, "rakam_birim"?}.
Metinler haberin tam metninden kendi cümlelerimizle özetlenir (birebir kopya değil).
"""

import math
import os
import subprocess

from PIL import Image, ImageDraw

import haber
import kart
from kart import BEYAZ, G, GRI, KALIN, KENAR, KONULAR, NORMAL, SOLUK, Y, buyuk, font, sar
import reels

GENIS = G - 2 * KENAR


def zemin(haber, marka, sayfa):
    konu = KONULAR.get(haber.get("konu", "gundem"), KONULAR["gundem"])
    img = Image.new("RGB", (G, Y), konu[2])
    c = ImageDraw.Draw(img)
    kart.ust_serit(c, marka, konu, sayfa=sayfa)
    return img, c, konu[1]


def _yerlesim(c, slayt, k):
    """Slayt içeriğini k ölçeğinde parçalara böler: [(tür, veri, font, yükseklik)]."""
    p = [("etiket", buyuk(slayt["etiket"]), font(KALIN, 46), 100)]
    if slayt.get("rakam"):
        boy = int(200 * k)
        while boy > 90 and c.textlength(slayt["rakam"], font=font(KALIN, boy)) > GENIS:
            boy -= 10
        p.append(("rakam", slayt["rakam"], font(KALIN, boy), int(boy * 1.1)))
    for r, aciklama in slayt.get("rakamlar", []):
        boy = int(110 * k)
        while boy > 60 and c.textlength(r, font=font(KALIN, boy)) > GENIS:
            boy -= 6
        fa = font(NORMAL, int(38 * k))
        sat = sar(c, aciklama, fa, GENIS)
        p.append(("rakamsatiri", (r, sat), (font(KALIN, boy), fa), int(boy * 1.08) + len(sat) * int(fa.size * 1.35) + 44))
    if slayt.get("metin"):
        tek = not (slayt.get("rakam") or slayt.get("maddeler"))  # "Ne oldu?": tek paragraf, büyük ve kalın
        f = font(KALIN, int(60 * k)) if tek else font(NORMAL, int(42 * k))
        sat = sar(c, slayt["metin"], f, GENIS)
        p.append(("metin", sat, f, len(sat) * int(f.size * 1.38)))
    for m in slayt.get("maddeler", []):
        f = font(NORMAL, int(44 * k))
        sat = sar(c, m, f, GENIS - 60)
        p.append(("madde", sat, f, len(sat) * int(f.size * 1.42) + 36))
    if slayt.get("alinti"):
        f = font(KALIN, int(56 * k))
        sat = sar(c, slayt["alinti"], f, GENIS)
        p.append(("tirnak", "“", font(KALIN, 200), 120))
        p.append(("metin", sat, f, len(sat) * int(f.size * 1.32) + 30))
        if slayt.get("kim"):
            fk = font(NORMAL, int(38 * k))
            ks = sar(c, "— " + slayt["kim"], fk, GENIS)
            p.append(("kim", ks, fk, len(ks) * int(fk.size * 1.4)))
    return p


def bilgi_slayti(haber, slayt, marka, sayfa, cikti, kaydir=True):
    img, c, vurgu = zemin(haber, marka, sayfa)
    alan = 1160 - 180
    for k in [x / 100 for x in range(125, 55, -5)]:  # az yazıda büyük başla, sığana kadar küçült
        parcalar = _yerlesim(c, slayt, k)
        toplam = sum(p[3] for p in parcalar)
        if toplam <= alan:
            break
    y = 180 + max(0, (alan - toplam) // 2)

    for tur, veri, f, h in parcalar:
        if tur == "etiket":
            c.rectangle([KENAR, y + 6, KENAR + 12, y + 50], fill=vurgu)
            c.text((KENAR + 32, y), veri, font=f, fill=vurgu)
        elif tur == "rakam":
            c.text((KENAR - 6, y - int(f.size * 0.12)), veri, font=f, fill=BEYAZ)
        elif tur == "rakamsatiri":
            (r, sat), (fr, fa) = veri, f
            c.text((KENAR - 4, y - int(fr.size * 0.1)), r, font=fr, fill=vurgu)
            yy = y + int(fr.size * 1.08)
            for s in sat:
                c.text((KENAR, yy), s, font=fa, fill=BEYAZ)
                yy += int(fa.size * 1.35)
        elif tur == "metin":
            satir = int(f.size * (1.32 if slayt.get("alinti") else 1.38))
            for i, s in enumerate(veri):
                c.text((KENAR, y + i * satir), s, font=f, fill=BEYAZ)
        elif tur == "madde":
            c.ellipse([KENAR + 4, y + int(f.size * .45), KENAR + 22, y + int(f.size * .45) + 18], fill=vurgu)
            for i, s in enumerate(veri):
                c.text((KENAR + 60, y + i * int(f.size * 1.42)), s, font=f, fill=BEYAZ)
        elif tur == "tirnak":
            c.text((KENAR - 10, y - 40), veri, font=f, fill=vurgu)
        elif tur == "kim":
            for i, s in enumerate(veri):
                c.text((KENAR, y + i * int(f.size * 1.4)), s, font=f, fill=GRI)
        y += h

    c.line([KENAR, 1190, G - KENAR, 1190], fill=(45, 50, 60), width=2)
    if kaydir:
        kart.kaydir_oku(c, vurgu)
    img.save(cikti, "JPEG", quality=92)
    return cikti


def kapanis(haber, marka, kullanici_adi, sayfa, cikti):
    konu = KONULAR.get(haber.get("konu", "gundem"), KONULAR["gundem"])
    img, c, vurgu = zemin(haber, marka, sayfa)
    bu_tg = bool(haber.get("tg_kanal") or "t.me/" in haber.get("link", ""))
    y = 330
    if not bu_tg:
        c.text((KENAR, y), "KAYNAK", font=font(KALIN, 40), fill=vurgu)
        y += 70
        kaynaklar = [haber["kaynak"]] + haber.get("diger_kaynaklar", [])
        c.text((KENAR, y), ", ".join(kaynaklar), font=font(KALIN, 64), fill=BEYAZ)
        y += 100
        for s in sar(c, "Haberin tamamı için kaynağa bakabilirsin. Linki açıklamada.", font(NORMAL, 36), GENIS):
            c.text((KENAR, y), s, font=font(NORMAL, 36), fill=GRI)
            y += 52
        y += 120
    else:
        y = 480
    fb = font(KALIN, 92)
    for s in ["GÜNDEMİ", "KAÇIRMA."]:
        c.text((KENAR - 4, y), s, font=fb, fill=BEYAZ)
        y += 106
    y += 40
    fk = font(KALIN, 44)
    yazi = "TAKİP ET  " + kullanici_adi
    w = c.textlength(yazi, font=fk)
    c.rounded_rectangle([KENAR, y, KENAR + w + 70, y + 96], radius=14, fill=vurgu)
    c.text((KENAR + 35, y + 24), yazi, font=fk, fill=konu[3])
    c.text((KENAR, y + 140), "Kaydet, ihtiyacı olana gönder.", font=font(NORMAL, 32), fill=SOLUK)
    img.save(cikti, "JPEG", quality=92)
    return cikti


def hareketli_kapak(haber_veri, marka, kullanici_adi, cikti_mp4, sayfa=None, sure_sn=4.0):
    """Karuselin 1. slaytı için Ken Burns yakınlaşması, daktilo başlık, canlı etiket ve kaydır animasyonlu MP4 video üretir."""
    fps = 30
    toplam_kare = int(fps * sure_sn)
    baslik_len = len(haber_veri.get("baslik") or "")
    foto_var = bool(haber_veri.get("foto"))
    daktilo_sn = min(2.4, max(1.2, sure_sn * 0.55))
    muzik = reels.muzik_sec(haber_veri)

    cmd = [
        reels.ffmpeg_yolu(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{kart.G}x{kart.Y}", "-r", str(fps), "-i", "-"
    ]
    if muzik and os.path.exists(muzik):
        cmd += [
            "-i", muzik,
            "-filter:a", f"afade=t=in:d=0.3,afade=t=out:st={sure_sn - 0.8:.2f}:d=0.8,volume=0.45",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v", "-map", "1:a"
        ]
    cmd += [
        "-t", f"{sure_sn:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", cikti_mp4
    ]

    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    gecici_jpg = cikti_mp4 + "_kare.jpg"
    try:
        for f_no in range(toplam_kare):
            t = f_no / fps
            oran = f_no / max(1, toplam_kare - 1)
            zoom = round(1.00 + 0.08 * (0.5 - 0.5 * math.cos(math.pi * oran)), 3) if foto_var else 1.0
            kaydir_dx = int(16 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 1.0)))
            harf = max(1, int(baslik_len * (t / daktilo_sn))) if t < daktilo_sn else baslik_len
            imlec = (int(t * 7) % 2 == 0) if t < daktilo_sn else ((int(t * 4) % 2 == 0) if t < (sure_sn - 0.6) else False)
            nabiz_alfa = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(2 * math.pi * t / 1.2))

            h_kare = dict(haber_veri, ozet="", foto_zoom=zoom, kaydir_dx=kaydir_dx,
                          daktilo_harf=harf, daktilo_imlec=imlec, nabiz_alfa=nabiz_alfa)
            kart.ciz_kart(h_kare, marka, kullanici_adi, gecici_jpg, sayfa=sayfa, kaydir=True)
            with Image.open(gecici_jpg) as im:
                p.stdin.write(im.convert("RGB").tobytes())
        p.stdin.close()
        if p.wait() != 0:
            raise RuntimeError("ffmpeg hareketli kapağı yazamadı")
    finally:
        if os.path.exists(gecici_jpg):
            try:
                os.remove(gecici_jpg)
            except Exception:
                pass
    return cikti_mp4


def karusel(haber_veri, marka, kullanici_adi, klasor, video=False):
    """Slayt yollarını döndürür (Instagram en fazla 10 slayt alır).

    video=True: Reels için; "KAYDIR" oku ve sayfa numarası yok (video kendisi akıyor).
    """
    os.makedirs(klasor, exist_ok=True)
    slaytlar = haber_veri.get("slaytlar", [])[:8]
    toplam = len(slaytlar) + 2
    no = (lambda i: None) if video else (lambda i: (i, toplam))
    on = "v" if video else ""

    kapak_jpg = os.path.join(klasor, f"{on}01.jpg")
    kart.ciz_kart(dict(haber_veri, ozet=""), marka, kullanici_adi, kapak_jpg,
                  sayfa=no(1), kaydir=not video)

    cfg = haber.ayar() if hasattr(haber, "ayar") else {}
    k_cfg = cfg.get("karusel", {}) if isinstance(cfg, dict) else {}
    hareketli_acik = k_cfg.get("hareketli_kapak", True)

    yollar = []
    if not video and hareketli_acik and haber_veri.get("foto"):
        kapak_mp4 = os.path.join(klasor, f"{on}01.mp4")
        try:
            hareketli_kapak(haber_veri, marka, kullanici_adi, kapak_mp4,
                            sayfa=no(1), sure_sn=float(k_cfg.get("sure_sn", 4.0)))
            if os.path.exists(kapak_mp4):
                yollar.append(kapak_mp4)
            else:
                yollar.append(kapak_jpg)
        except Exception as e:
            print(f"Hareketli karusel kapağı atlandı: {e}", flush=True)
            yollar.append(kapak_jpg)
    else:
        yollar.append(kapak_jpg)

    for i, s in enumerate(slaytlar, 2):
        yollar.append(bilgi_slayti(haber_veri, s, marka, no(i), os.path.join(klasor, f"{on}{i:02d}.jpg"),
                                   kaydir=not video))
    yollar.append(kapanis(haber_veri, marka, kullanici_adi, no(toplam), os.path.join(klasor, f"{on}{toplam:02d}.jpg")))
    return yollar
