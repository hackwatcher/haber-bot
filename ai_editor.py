"""Bulut AI Editör (Gemini API): Bilgisayar kapalıyken GitHub Actions üzerinde kanca söz ve slayt metinlerini üretir.

GEMINI_API_KEY tanımlı değilse veya bir hata oluşursa hiçbir kesinti olmadan mevcut kural motoruna (ozet.py) geri döner.
"""

import json
import os
import re
import requests

import haber
import kart
import ozet

KOK = haber.KOK
KAPAKLAR = os.path.join(KOK, "data", "kapaklar")
os.makedirs(KAPAKLAR, exist_ok=True)

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models"
METIN_MODEL = "gemini-3-flash-preview"
GECERLI_KONULAR = {"gundem", "afet", "ekonomi", "dunya", "spor", "asayis"}

SISTEM_TALIMATI = """Sen @xhabercom (XHABER) Instagram haber hesabının baş editörüsün.
Verilen haber metninden şu JSON yapısını üret:
{
  "konu": "gundem | afet | ekonomi | dunya | spor | asayis",
  "kanca": "2-4 kelimelik, büyük harf kanca söz",
  "baslik": "6-12 kelimelik net, sade Türkçe haber başlığı",
  "ozet": "En fazla 200 karakterlik tek cümlelik özet",
  "slaytlar": [
    {"etiket": "Ne oldu?", "metin": "Olayın en önemli özeti (120-210 karakter)"},
    {"etiket": "Detaylar", "maddeler": ["Madde 1 (maks 160 krk)", "Madde 2 (maks 160 krk)"]},
    {"etiket": "Rakamlarla", "rakamlar": [["Rakam ve birim", "Kısa açıklama"]]},
    {"etiket": "Ne dedi?", "alinti": "Haberde tırnak içinde geçen sözün BİREBİR kopyası", "kim": "Söyleyenin unvanı ve adı"}
  ],
  "yorum_sorusu": "Haberle ilgili tarafsız, tek bir soru (Örn: 'Sizce bu karar nasıl sonuçlanır?')",
  "hashtagler": ["#habere_ozel_1", "#habere_ozel_2"]
}

KESİN KURALLAR:
1. Sadece metinde yazanı kullan. Metinde olmayan bilgi, tarih, unvan, sonuç, geçmiş bilgisi EKLEME. Emin değilsen yazma.
2. Yorum ve sıfat katma: "muhteşem", "tarihi", "kritik", "şok", "heyecan dolu", "yıldızlaştı", "net bir skor" gibi değerlendirmeler yasak. Haber ajansı dili kullan: kim, ne, nerede, ne zaman, kaç.
3. Kanca haberin en somut ayrıntısını söyler (Örn: ROZETİ ERDOĞAN TAKTI, EV HAPSİNDEN CEZAEVİNE, 2 METRELİK DALGALAR). Olayı büyütme: "alev aldı" ise "alev topu" deme, "başvuru" ise "alarm" deme. KRİTİK, ŞOK, ALARM, FLAŞ, SON DAKİKA, RÜZGAR, GOL YAĞMURU, DEVLER, FIRTINA gibi klişeler yasak. Kanca başlıktaki kelimeleri tekrar etmesin.
4. Ölüm, yaralanma, cinayet, istismar haberlerinde kanca sade ve saygılı olsun; "kaderden kaçamadı", "feci", "kahreden" gibi magazin dili yasak.
5. "Ne dedi?" slaytını yalnız metinde tırnak içinde geçen bir söz varsa ekle ve sözü kelimesi kelimesine kopyala. Söz yoksa bu slaytı ekleme.
6. "Rakamlarla" slaytını yalnız haberin özü olan rakamlar varsa ekle (ceza süresi, zam oranı, kayıp sayısı gibi). Önemsiz sayıları (maç sayısı, hafta numarası) ve başka slaytta yazılan bilgiyi tekrar etme.
7. Slaytlar birbirini tekrar etmesin. Dolgu slayt ekleme. Basit haberde 2-3, detaylı haberde en fazla 4 slayt."""


YASAK_KANCA = ("KRİTİK", "ŞOK", "ALARM", "FLAŞ", "SON DAKİKA", "RÜZGAR", "YAĞMURU", "DEVLER", "FIRTINA",
               "KADERDEN", "FECİ", "KAHREDEN", "ALEV TOPU")


def sade(metin):
    """Alıntı karşılaştırması için: tırnak, noktalama ve boşluk farklarını yok sayar."""
    return " ".join(re.sub(r"[^\w]+", " ", kart.buyuk(metin or "")).split())


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
        if any(k in kart.buyuk(z["kanca"]) for k in YASAK_KANCA):
            z["kanca"] = z_varsayilan.get("kanca", "")
        if isinstance(ai.get("slaytlar"), list):
            kaynak_metin = sade(" ".join([spot] + paragraflar))
            # uydurma alıntı riski: söz kaynak metinde birebir geçmiyorsa slayt atılır
            slaytlar = [s for s in ai["slaytlar"] if isinstance(s, dict)
                        and (not s.get("alinti") or sade(s["alinti"]) in kaynak_metin)]
            if len(slaytlar) >= 2:
                z["slaytlar"] = slaytlar[:4]
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
