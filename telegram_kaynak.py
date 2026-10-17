"""Herkese açık (public) Telegram kanallarından (t.me/s/<kanal>) haber, gerçek fotoğraf ve video (.mp4) çekici.

Hiçbir API anahtarı, oturum veya ek kütüphane (sadece standart kütüphane + requests + ffmpeg) gerektirmez.
Paylaşım anında ?embed=1&mode=tme üzerinden taze medya bağlantısı alarak CDN token süresinin dolmasını önler.
"""

import datetime as dt
import hashlib
import html
import os
import re
import subprocess
import requests

import haber
import reels

KOK = haber.KOK
KAPAKLAR = os.path.join(KOK, "data", "kapaklar")
os.makedirs(KAPAKLAR, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _foto_url_cikar(blok_html):
    """HTML bloğundaki .tgme_widget_message_photo_wrap veya video_thumb stilinden fotoğraf URL'sini ayıklar."""
    m = re.search(
        r"tgme_widget_message_(?:photo_wrap|video_thumb)[^>]*style=\"[^\"]*url\(['\"]?(https://[^'\")]+)['\"]?\)",
        blok_html,
    )
    return m.group(1) if m else ""


def _video_url_cikar(blok_html):
    """HTML bloğundaki <video src='...'> etiketinden doğrudan .mp4 URL'sini ayıklar."""
    m = re.search(r"<video[^>]+src=[\"'](https://[^\"']+)[\"']", blok_html)
    return m.group(1) if m else ""


def _metin_cikar(blok_html):
    """HTML bloğundaki .tgme_widget_message_text içeriğini satır sonlarını koruyarak düz metne çevirir."""
    m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', blok_html, flags=re.S)
    if not m:
        return ""
    ic = re.sub(r"<br\s*/?>", "\n", m.group(1), flags=re.I)
    ic = re.sub(r"<[^>]+>", "", ic)
    ic = html.unescape(ic)
    satirlar = [re.sub(r"[ \t]+", " ", s).strip() for s in ic.splitlines()]
    return "\n".join(s for s in satirlar if s)


def _baslik_ve_spot(tam_metin):
    """Telegram mesaj metninden temiz bir başlık ve özet/spot çıkarır."""
    satirlar = [haber.temizle(s) for s in tam_metin.splitlines() if haber.temizle(s)]
    if not satirlar:
        return "", ""
    ilk = re.sub(r"^(son dak[iİı]ka|flaş|flas)\W*", "", satirlar[0], flags=re.I).strip()
    ilk = ilk[:1].upper() + ilk[1:] if ilk else ""
    cumleler = re.split(r"(?<=[.!?])\s+", ilk)
    baslik = cumleler[0] if cumleler and len(cumleler[0]) >= 20 else ilk
    if len(baslik) > 150:
        baslik = baslik[:147].rsplit(" ", 1)[0] + "..."
    kalan = " ".join(satirlar[1:]) if len(satirlar) > 1 else (" ".join(cumleler[1:]) if len(cumleler) > 1 else ilk)
    return baslik, haber.ozet_kisalt(kalan or ilk, baslik)


def html_ayristir(sayfa_html, ad="XHABER", kullanici="sahinozkan000"):
    """t.me/s/<kullanici> HTML içeriğini ayrıştırıp haber sözlüğü listesi döndürür."""
    parcalar = re.split(r'(?=<div class="tgme_widget_message\b)', sayfa_html)
    sonuc = []
    for blok in parcalar:
        pm = re.search(r'data-post="([^"]+)"', blok)
        if not pm:
            continue
        post_kod = pm.group(1)
        tam_metin = _metin_cikar(blok)
        if len(tam_metin) < 25:
            continue
        baslik, ozet_metin = _baslik_ve_spot(tam_metin)
        if not baslik:
            continue
        tm = re.search(r'<time[^>]+datetime="([^"]+)"', blok)
        zaman_str = tm.group(1) if tm else ""
        try:
            zaman = dt.datetime.fromisoformat(zaman_str.replace("Z", "+00:00")).astimezone(haber.TR).isoformat()
        except Exception:
            zaman = dt.datetime.now(haber.TR).isoformat()

        link = f"https://t.me/{post_kod}"
        sonuc.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:12],
            "kaynak": ad,
            "baslik": baslik,
            "ozet": ozet_metin,
            "link": link,
            "zaman": zaman,
            "tg_kanal": kullanici,
            "tg_metin": tam_metin,
            "tg_foto_url": _foto_url_cikar(blok),
            "tg_video_url": _video_url_cikar(blok),
        })
    return sonuc


def kanal_oku(kanal):
    """t.me/s/<kullanici> sayfasından son mesajları okuyup haber sözlüğü listesi döndürür."""
    kullanici = kanal["kullanici"].lstrip("@").strip("/").split("/")[-1]
    ad = kanal.get("ad", kullanici)
    url = f"https://t.me/s/{kullanici}"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return html_ayristir(r.text, ad=ad, kullanici=kullanici)


def taze_medya_ve_metin(link, yedek_metin="", yedek_foto="", yedek_video=""):
    """Paylaşım anında ?embed=1&mode=tme sayfasından taze CDN foto/video URL'sini ve metni alır."""
    metin, foto_url, video_url = yedek_metin, yedek_foto, yedek_video
    try:
        embed_url = link + ("&" if "?" in link else "?") + "embed=1&mode=tme"
        r = requests.get(embed_url, headers=UA, timeout=20)
        if r.status_code == 200:
            yeni_metin = _metin_cikar(r.text)
            if yeni_metin:
                metin = yeni_metin
            foto_url = _foto_url_cikar(r.text) or foto_url
            video_url = _video_url_cikar(r.text) or video_url
    except Exception:
        pass
    return metin, foto_url, video_url


def sayfa_oku_tg(link, yedek_metin=""):
    """Telegram haber linkinden (spot, paragraflar, tam_metin) üretir."""
    metin, _, _ = taze_medya_ve_metin(link, yedek_metin=yedek_metin)
    satirlar = [haber.temizle(s) for s in metin.splitlines() if len(haber.temizle(s)) >= 15]
    spot = satirlar[0] if satirlar else ""
    return spot, satirlar, metin


def medya_indir(h, marka="XHABER"):
    """Telegram haberinin gerçek fotoğrafını veya videosunu indirip kapak karesi ve video yolunu döndürür."""
    link = h.get("link", "")
    if "t.me/" not in link and not h.get("tg_foto_url") and not h.get("tg_video_url"):
        return None, None

    hid = h["id"]
    kapak_yol = os.path.join(KAPAKLAR, f"{hid}.jpg")
    video_yol = os.path.join(KAPAKLAR, f"{hid}.mp4")

    _, foto_url, video_url = taze_medya_ve_metin(
        link,
        yedek_metin=h.get("tg_metin", ""),
        yedek_foto=h.get("tg_foto_url", ""),
        yedek_video=h.get("tg_video_url", ""),
    )

    gercek_video = None
    if video_url:
        try:
            rv = requests.get(video_url, headers=UA, timeout=45)
            if rv.status_code == 200 and len(rv.content) > 20000:
                with open(video_yol, "wb") as f:
                    f.write(rv.content)
                gercek_video = f"data/kapaklar/{hid}.mp4"
                if not foto_url:
                    subprocess.run(
                        [reels.ffmpeg_yolu(), "-y", "-loglevel", "error", "-ss", "00:00:01", "-i", video_yol, "-frames:v", "1", kapak_yol],
                        check=True,
                        timeout=30,
                    )
                    if os.path.exists(kapak_yol):
                        return {"yol": f"data/kapaklar/{hid}.jpg", "not": f"Video Görüntüsü · {marka}"}, gercek_video
        except Exception:
            pass

    if foto_url:
        try:
            rf = requests.get(foto_url, headers=UA, timeout=25)
            if rf.status_code == 200 and len(rf.content) > 5000:
                with open(kapak_yol, "wb") as f:
                    f.write(rf.content)
                not_yazisi = f"Video Görüntüsü · {marka}" if gercek_video else f"Fotoğraf · {marka}"
                return {"yol": f"data/kapaklar/{hid}.jpg", "not": not_yazisi}, gercek_video
        except Exception:
            pass

    return None, gercek_video
