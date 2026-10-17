"""Haber slaytlarından kısa Reels videosu (9:16, müzikli) ve aynı tasarımda story görseli.

Tarz: haber bülteni gibi sade. Üstte hafifçe yanıp sönen "SON DAKİKA" etiketi, slaytlar arasında
kısa (0,15 sn) geçiş, altta ilerleme çubuğu. Uzun efekt yok.
"""

import glob
import math
import os
import random
import subprocess

from PIL import Image, ImageDraw

import kart
from kart import BEYAZ, KALIN, KONULAR, font

KOK = os.path.dirname(os.path.abspath(__file__))
MUZIK = os.path.join(KOK, "muzik")
W, H = 1080, 1920
FPS = 30
UST = 285                  # slaytın üst kenarı (1080x1350 slayt 285..1635 arasında)
GECIS = 0.15               # slaytlar arası geçiş süresi (sn)
NABIZ = 1.2                # etiketin bir yanıp sönme süresi (sn)

# konu -> müzik türü (muzik/ klasöründe genel_*.mp3, agir_*.mp3, hafif_*.mp3)
MUZIK_TURU = {"afet": "agir", "asayis": "agir", "spor": "hafif", "ekonomi": "hafif"}


def konu_renkleri(haber):
    return KONULAR.get(haber.get("konu", "gundem"), KONULAR["gundem"])


def muzik_sec(haber):
    tur = MUZIK_TURU.get(haber.get("konu"), "genel")
    parcalar = sorted(glob.glob(os.path.join(MUZIK, f"{tur}_*.mp3"))) or sorted(glob.glob(os.path.join(MUZIK, "*.mp3")))
    return random.choice(parcalar) if parcalar else None


def etiket(c, y, vurgu, yazi_rengi, yazi="SON DAKİKA"):
    """Ortalanmış canlı yayın etiketi: nokta + yazı. Kutusunu döndürür."""
    f = font(KALIN, 46)
    w = c.textlength(yazi, font=f)
    gen = w + 128
    kutu = [(W - gen) / 2, y, (W + gen) / 2, y + 86]
    c.rounded_rectangle(kutu, radius=14, fill=vurgu)
    c.ellipse([kutu[0] + 32, y + 31, kutu[0] + 56, y + 55], fill=yazi_rengi)
    c.text((kutu[0] + 80, y + 17), yazi, font=f, fill=yazi_rengi)
    return [int(v) for v in kutu]


def zemin_kare(haber, marka, kullanici_adi, slayt, sira, toplam, alt_yazi=None):
    """Bir videodaki sabit kare: üst şerit, slayt, ilerleme çubuğu, kullanıcı adı. (görsel, etiket kutusu)"""
    _, vurgu, zemin, yazi_rengi = konu_renkleri(haber)
    img = Image.new("RGB", (W, H), zemin)
    c = ImageDraw.Draw(img)
    # marka adı slaytın içinde zaten yazıyor; üstte yalnızca yanıp sönen etiket
    kutu = etiket(c, 112, vurgu, yazi_rengi)
    img.paste(Image.open(slayt).convert("RGB"), (0, UST))
    # ilerleme çubuğu: hikâye gibi parçalı
    if toplam > 1:
        bosluk, x0, x1 = 10, 80, W - 80
        pw = (x1 - x0 - bosluk * (toplam - 1)) / toplam
        for i in range(toplam):
            px = x0 + i * (pw + bosluk)
            c.rounded_rectangle([px, 1680, px + pw, 1688], radius=4, fill=vurgu if i <= sira else (60, 66, 78))
    if alt_yazi:  # videoda kullanıcı adı slaytta var, alt kısmı Instagram'ın düğmeleri kaplıyor
        fa = font(KALIN, 38)
        c.text(((W - c.textlength(alt_yazi, font=fa)) / 2, 1740), alt_yazi, font=fa, fill=BEYAZ)
    return img, kutu


def sureler(haber, n):
    """Slayt başına süre (sn): yazısı çok olan slayt biraz daha uzun kalır, video kısa kalır."""
    if n == 1:
        return [7.0]
    yazilar = [len(s.get("metin", "")) + sum(len(m) for m in s.get("maddeler", [])) + len(s.get("alinti", ""))
               + sum(len(a) + 8 for _, a in s.get("rakamlar", [])) for s in haber.get("slaytlar", [])]
    orta = [min(4.5, max(2.6, 1.8 + 0.015 * u)) for u in yazilar][: n - 2]
    return [2.5] + orta + [1.8]


def ffmpeg_yolu():
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def video(haber, marka, kullanici_adi, slaytlar, cikti):
    """slaytlar: 1080x1350 görseller (KAYDIR'sız). Müzikli mp4 yazar, yolunu döndürür."""
    _, vurgu, zemin, _ = konu_renkleri(haber)
    n = len(slaytlar)
    sure = sureler(haber, n)
    kareler = [zemin_kare(haber, marka, kullanici_adi, s, i, n) for i, s in enumerate(slaytlar)]
    kutu = kareler[0][1]
    toplam_sn = sum(sure)
    muzik = muzik_sec(haber)

    cmd = [ffmpeg_yolu(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if muzik:
        cmd += ["-i", muzik, "-filter:a", f"afade=t=in:d=0.3,afade=t=out:st={toplam_sn - 1.2:.2f}:d=1.2,volume=0.85",
                "-c:a", "aac", "-b:a", "160k", "-map", "0:v", "-map", "1:a"]
    cmd += ["-t", f"{toplam_sn:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", cikti]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    gecis_kare = int(GECIS * FPS)
    t = 0.0
    for i, (kare, _) in enumerate(kareler):
        adet = int(round(sure[i] * FPS))
        sonraki = kareler[i + 1][0] if i + 1 < n else None
        # etiketin sönük hali bir kez hazırlanır, her karede iki hal arasında yumuşak geçilir
        parlak = kare.crop(kutu)
        sonuk = Image.blend(parlak, Image.new("RGB", parlak.size, zemin), 0.55)
        for k in range(adet):
            a = 0.5 + 0.5 * math.cos(2 * math.pi * t / NABIZ)  # 1: parlak, 0: sönük
            f = kare.copy()
            f.paste(Image.blend(sonuk, parlak, a), kutu[:2])
            if sonraki is not None and k >= adet - gecis_kare:  # kısa geçiş
                oran = (k - (adet - gecis_kare) + 1) / (gecis_kare + 1)
                f = Image.blend(f, sonraki, oran)
            p.stdin.write(f.tobytes())
            t += 1 / FPS
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg videoyu yazamadı")
    return cikti


def gercek_video_reels(haber, marka, kullanici_adi, kaynak_video, cikti):
    """Telegram veya kaynaktan gelen gerçek .mp4 videoyu sesini koruyarak 1080x1920 XHABER Reels formatına giydirir."""
    v_yol = kaynak_video if os.path.isabs(kaynak_video) else os.path.join(KOK, kaynak_video)
    if not os.path.exists(v_yol):
        raise RuntimeError("Kaynak video bulunamadı")
    _, vurgu, zemin, yazi_rengi = konu_renkleri(haber)
    img = Image.new("RGB", (W, H), zemin)
    c = ImageDraw.Draw(img)
    ust_yazi = kart.buyuk(haber.get("kanca") or "SON DAKİKA")
    if len(ust_yazi) > 26:
        ust_yazi = "SON DAKİKA"
    etiket(c, 180, vurgu, yazi_rengi, yazi=ust_yazi)
    alt_haber = {
        "kanca": haber.get("kaynak", marka),
        "baslik": haber.get("baslik", ""),
        "ozet": "",
    }
    kart.metin_blogu(c, alt_haber, 980, 1460, vurgu, en_buyuk=66, ozet_satir=0)
    c.line([(kart.KENAR, 1490), (W - kart.KENAR, 1490)], fill=(38, 43, 54), width=2)
    c.text((kart.KENAR, 1520), f"{kart.buyuk(marka)}  ·  {kullanici_adi}", font=font(KALIN, 36), fill=kart.GRI)
    zemin_dosya = cikti + "_zemin.jpg"
    img.save(zemin_dosya, "JPEG", quality=95)
    try:
        cmd = [
            ffmpeg_yolu(), "-y", "-loglevel", "error",
            "-loop", "1", "-i", zemin_dosya,
            "-i", v_yol,
            "-filter_complex", "[1:v]scale=1080:640:force_original_aspect_ratio=decrease[vid];[0:v][vid]overlay=(W-w)/2:300:shortest=1[outv]",
            "-map", "[outv]", "-map", "1:a?",
            "-t", "58",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", cikti,
        ]
        subprocess.run(cmd, check=True, timeout=120)
    finally:
        if os.path.exists(zemin_dosya):
            os.remove(zemin_dosya)
    return cikti


def story(haber, marka, kullanici_adi, kapak, cikti):
    """Story görseli: videonun ilk karesi, altta profile yönlendirme."""
    img, _ = zemin_kare(haber, marka, kullanici_adi, kapak, 0, 1, alt_yazi="DETAYLAR PROFİLDE  " + kullanici_adi)
    img.save(cikti, "JPEG", quality=92)
    return cikti

