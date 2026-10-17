"""Yapay Zeka Türkçe Haber Spikeri (gTTS + ffmpeg): Reels videoları için hızlı TV spikeri sesi ve altyazı üretir.
"""

import os
import re
import shutil
import subprocess
import gtts

import haber

KOK = haber.KOK
KAPAKLAR = os.path.join(KOK, "data", "kapaklar")
os.makedirs(KAPAKLAR, exist_ok=True)


def spiker_metni_uret(z):
    """Haber kaydından hızlı TV bülteni havasında akıcı 2-3 cümlelik spiker metni çıkarır."""
    if z.get("spiker_metni") and isinstance(z["spiker_metni"], str) and z["spiker_metni"].strip():
        return z["spiker_metni"].strip()

    kanca = (z.get("kanca") or "").strip()
    baslik = (z.get("baslik") or "").strip()
    ozet = (z.get("ozet") or "").strip()

    parcalar = []
    # TV Spikeri Giriş Kancası
    if kanca and len(kanca) <= 35 and kanca.lower() not in ("son dakika", "flaş"):
        parcalar.append(f"Flaş gelişme: {kanca}!")
    else:
        parcalar.append("Son dakika gelişmesi!")

    if baslik:
        temiz_baslik = baslik.rstrip(".!?,")
        parcalar.append(f"{temiz_baslik}.")

    if ozet and not haber.benzer(haber.kelimeler(ozet), haber.kelimeler(baslik)):
        # Özeti tek veya en fazla iki kısa, net cümleye indir
        temiz_ozet = ozet.rstrip(".!?,")
        parcalar.append(f"{temiz_ozet}.")

    metin = " ".join(parcalar)
    # Tırnak ve özel karakterleri temizle
    metin = re.sub(r"[\"“”'’]", "", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin[:350]


def ffmpeg_yolu():
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def ffprobe_yolu():
    p = shutil.which("ffprobe")
    if p:
        return p
    return "ffprobe"


def ses_suresi(mp3_yol):
    """ffprobe ile ses dosyasının süresini saniye cinsinden döndürür."""
    try:
        cmd = [
            ffprobe_yolu(), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            mp3_yol,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        # ffprobe çalışmazsa dosya boyutundan yaklaşık süre (192 kbps)
        try:
            return round(os.path.getsize(mp3_yol) / (192 * 1024 / 8), 2)
        except Exception:
            return 8.0


def altyazi_parcala(metin, toplam_sure):
    """Metni ritmik 3-5 kelimelik parçalara ayırıp süre aralıklarıyla döndürür: [(t_bas, t_bit, parca), ...]"""
    kelimeler = metin.split()
    if not kelimeler:
        return []

    gruplar = []
    simdiki = []
    for k in kelimeler:
        simdiki.append(k)
        # Noktalama işareti varsa veya 4 kelimeye ulaştıysa yeni parça yap
        if len(simdiki) >= 4 or k.endswith((".", "!", "?", ":", ";")):
            gruplar.append(" ".join(simdiki))
            simdiki = []
    if simdiki:
        if gruplar and len(simdiki) <= 2:
            gruplar[-1] += " " + " ".join(simdiki)
        else:
            gruplar.append(" ".join(simdiki))

    n = len(gruplar)
    if n == 0:
        return []

    # Her parçaya kelime sayısına göre orantılı süre ata
    toplam_karakter = sum(len(g) for g in gruplar)
    araliklar = []
    t = 0.0
    for g in gruplar:
        oran = len(g) / max(1, toplam_karakter)
        sure_parca = max(1.2, round(toplam_sure * oran, 2))
        araliklar.append((round(t, 2), round(t + sure_parca, 2), g))
        t += sure_parca

    return araliklar


def seslendir(z, cikti=None, hiz=1.30):
    """Spiker metnini hızlı TV spikeri temposunda (1.30x) seslendirir ve MP3 kaydeder.
    (dosya_yolu, sure_sn, altyazilar) tuple'ı döndürür; hata durumunda (None, 0.0, []) döner.
    """
    hid = z.get("id", "temp")
    if cikti is None:
        cikti = os.path.join(KAPAKLAR, f"spiker_{hid}.mp3")

    metin = spiker_metni_uret(z)
    if not metin:
        return None, 0.0, []

    # 1. Öncelik: Gerçekçi Doğal Microsoft Neural TTS (tr-TR-EmelNeural)
    try:
        import asyncio
        import edge_tts
        yuzde = int(round((hiz - 1.0) * 100))
        rate_str = f"+{yuzde}%" if yuzde >= 0 else f"{yuzde}%"
        comm = edge_tts.Communicate(metin, "tr-TR-EmelNeural", rate=rate_str)
        asyncio.run(comm.save(cikti))
        if os.path.exists(cikti) and os.path.getsize(cikti) > 2000:
            sure = ses_suresi(cikti)
            altyazilar = altyazi_parcala(metin, sure)
            return cikti, sure, altyazilar
    except Exception as e:
        print(f"Neural TTS atlandı ({e}), gTTS yedeğine geçiliyor...", flush=True)

    # 2. Öncelik / Yedek: gTTS + ffmpeg hızlandırma
    gecici_raw = cikti + ".raw.mp3"
    try:
        tts = gtts.gTTS(metin, lang="tr")
        tts.save(gecici_raw)

        # Hızlı spiker temposu (atempo=1.30) ve ses netleştirme filtresi
        # atempo: konuşma hızını 1.30x yapar (pitch/ton bozulmaz)
        # bass ve treble: TV haber spikeri netliği ve varlığı kazandırır
        cmd = [
            ffmpeg_yolu(), "-y", "-loglevel", "error",
            "-i", gecici_raw,
            "-filter:a", f"atempo={hiz:.2f},bass=g=1.5,treble=g=2",
            "-b:a", "192k",
            cikti,
        ]
        subprocess.run(cmd, check=True)

        if os.path.exists(cikti) and os.path.getsize(cikti) > 1000:
            sure = ses_suresi(cikti)
            altyazilar = altyazi_parcala(metin, sure)
            return cikti, sure, altyazilar
    except Exception as e:
        print(f"Spiker seslendirme hatası: {e}")
    finally:
        if os.path.exists(gecici_raw):
            try:
                os.remove(gecici_raw)
            except Exception:
                pass

    return None, 0.0, []
