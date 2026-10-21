"""Bulut AI Editör (Gemini API): Bilgisayar kapalıyken GitHub Actions üzerinde kanca söz, slayt ve kapak görseli üretir.

GEMINI_API_KEY tanımlı değilse veya bir hata oluşursa hiçbir kesinti olmadan mevcut kural motoruna (ozet.py) geri döner.
"""

import base64
import json
import os
import requests

import haber
import ozet

KOK = haber.KOK
KAPAKLAR = os.path.join(KOK, "data", "kapaklar")
os.makedirs(KAPAKLAR, exist_ok=True)

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models"
METIN_MODEL = "gemini-3-flash-preview"
GORSEL_MODEL = "gemini-3-pro-image-preview"
GECERLI_KONULAR = {"gundem", "afet", "ekonomi", "dunya", "spor", "asayis"}

SISTEM_TALIMATI = """Sen @xhabercom (XHABER) Instagram haber hesabının baş editörüsün.
Verilen haber metninden sadece gerçek bilgilere dayanarak (asla bilgi uydurmadan) şu JSON yapısını üret:
{
  "konu": "gundem | afet | ekonomi | dunya | spor | asayis",
  "kanca": "2-4 kelimelik çarpıcı, merak uyandıran büyük harf uyumlu kanca söz (Örn: ELMANIN İÇİNDE ÇALINMIŞTI, 2 METRELİK DALGALAR, AVRUPA'DA ZİRVE. Asla sıradan 'SON DAKİKA' yazma)",
  "baslik": "6-12 kelimelik net, vurucu Türkçe haber başlığı",
  "ozet": "En fazla 200 karakterlik tek cümlelik özet",
  "gorsel_prompt": "Cinematic editorial photojournalism close-up or wide shot representing the news event, realistic lighting, high contrast, 3:2 aspect ratio, no text, no watermarks, no logos (İngilizce yaz)",
  "slaytlar": [
    {"etiket": "Ne oldu?", "metin": "Olayın en önemli özeti (120-210 karakter)"},
    {"etiket": "Detaylar", "maddeler": ["Madde 1 (maks 160 krk)", "Madde 2 (maks 160 krk)", "Madde 3 (maks 160 krk)"]},
    {"etiket": "Rakamlarla", "rakamlar": [["Rakam ve birim", "Kısa açıklama"]]},
    {"etiket": "Ne dedi?", "alinti": "Haberde geçen doğrudan alıntı söz", "kim": "Söyleyenin unvanı ve adı"}
  ],
  "yorum_sorusu": "Okuyucuları yorum yapmaya davet eden merak uyandırıcı tek bir soru (Örn: '📌 Sizce bu karar doğru mu? Görüşlerinizi yazın.')",
  "hashtagler": ["#habere_ozel_1", "#habere_ozel_2"]
}
Not: Haberde rakam yoksa 'Rakamlarla' slaytını, doğrudan alıntı söz yoksa 'Ne dedi?' slaytını ekleme; onun yerine 'Ayrıca' başlıklı maddeli slayt ekle. En az 3, en fazla 5 slayt olsun."""


def anahtar_oku():
    """Ortam değişkeninden veya .gizli/gemini_key.txt dosyasından Gemini API anahtarını okur."""
    anahtar = (os.environ.get("GEMINI_API_KEY") or "").strip()
    yol = os.path.join(KOK, ".gizli", "gemini_key.txt")
    if not anahtar and os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            anahtar = f.read().strip()
    if anahtar == "API_KEY_PLACEHOLDER":
        return ""
    return anahtar


def metin_analiz_et(h, spot, paragraflar, anahtar):
    """Gemini modeli ile haber metninden kanca, başlık, slaytlar ve görsel promptu içeren JSON üretir."""
    icerik = (
        f"Kaynak: {h.get('kaynak', '')}\n"
        f"Başlık: {h.get('baslik', '')}\n"
        f"Spot: {spot}\n"
        f"Metin:\n" + "\n".join(paragraflar[:12])
    )
    url = f"{GEMINI_API}/{METIN_MODEL}:generateContent"
    govde = {
        "systemInstruction": {"parts": [{"text": SISTEM_TALIMATI}]},
        "contents": [{"parts": [{"text": icerik}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
        },
    }
    r = requests.post(url, params={"key": anahtar}, json=govde, timeout=45)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini metin hatası ({r.status_code})")
    veri = r.json()
    metin = veri["candidates"][0]["content"]["parts"][0]["text"]
    sonuc = json.loads(metin)
    if sonuc.get("konu") not in GECERLI_KONULAR:
        sonuc["konu"] = "gundem"
    return sonuc


def gorsel_uret(prompt, hid, anahtar):
    """Önce Gemini görsel modelini dener; ücretsiz planda kapalıysa Pollinations Flux ile 1080x660 görsel üretir."""
    if not prompt:
        return None
    dosya = os.path.join(KAPAKLAR, f"{hid}.jpg")
    url = f"{GEMINI_API}/{GORSEL_MODEL}:generateContent"
    govde = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    try:
        r = requests.post(url, params={"key": anahtar}, json=govde, timeout=45)
        if r.status_code == 200:
            parcalar = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for p in parcalar:
                inline = p.get("inlineData")
                if inline and inline.get("data"):
                    with open(dosya, "wb") as f:
                        f.write(base64.b64decode(inline["data"]))
                    return f"data/kapaklar/{hid}.jpg"
    except Exception:
        pass

    # Ücretsiz anahtar yedeği: Pollinations Flux (alt filigranı kesmek için 1080x740 çekip üst 1080x660 alınır)
    try:
        import io
        import urllib.parse
        from PIL import Image
        kodlu = urllib.parse.quote(prompt)
        p_url = f"https://image.pollinations.ai/prompt/{kodlu}?width=1080&height=740&nologo=true&model=flux"
        r2 = requests.get(p_url, timeout=45, headers={"User-Agent": "Mozilla/5.0 (haberbot)"})
        if r2.status_code == 200 and len(r2.content) > 10000:
            im = Image.open(io.BytesIO(r2.content)).convert("RGB")
            im = im.crop((0, 0, im.width, int(im.height * 660 / 740)))
            im.save(dosya, "JPEG", quality=92)
            return f"data/kapaklar/{hid}.jpg"
    except Exception:
        pass
    return None


def zenginlestir_ai(h, z_varsayilan=None):
    """GEMINI_API_KEY varsa haberi AI ile zenginleştirir; yoksa veya hata olursa z_varsayilan döndürür."""
    if z_varsayilan is None:
        z_varsayilan = ozet.zenginlestir(h)
    anahtar = anahtar_oku()
    if not anahtar:
        return z_varsayilan

    try:
        spot, paragraflar, _ = ozet.sayfa_oku(h["link"], yedek_metin=h.get("tg_metin", ""))
        if not paragraflar and not spot:
            return z_varsayilan
        ai = metin_analiz_et(h, spot, paragraflar, anahtar)
        z = dict(z_varsayilan)
        for alan in ("konu", "kanca", "baslik", "ozet"):
            if ai.get(alan) and isinstance(ai[alan], str) and ai[alan].strip():
                z[alan] = ai[alan].strip()
        if isinstance(ai.get("slaytlar"), list) and len(ai["slaytlar"]) >= 2:
            # Rakamlarla slaytındaki listeleri tuple/list uyumlu tut
            z["slaytlar"] = ai["slaytlar"][:6]
        if ai.get("yorum_sorusu") and isinstance(ai["yorum_sorusu"], str):
            z["yorum_sorusu"] = ai["yorum_sorusu"].strip()
        if ai.get("hashtagler") and isinstance(ai["hashtagler"], list):
            tags = [t.strip() if t.strip().startswith("#") else f"#{t.strip()}" for t in ai["hashtagler"] if isinstance(t, str) and t.strip()]
            if tags:
                z["hashtagler"] = tags[:2]
        # Kapak görseli AI ile üretilmiyor (kalite düşük); bot.hazirla havuzdan seçer.
        return z
    except Exception as e:
        temiz_hata = str(e).replace(anahtar, "***")
        print(f"AI editör atlandı ({temiz_hata}), kural motoru kullanılıyor.", flush=True)
        return z_varsayilan
