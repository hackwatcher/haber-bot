"""Yapay zekâ olmadan, kurallarla: haberin tam metnini çeker, konu/il/rakam/kanca bulur, karusel slaytlarını doldurur.

Tam cümleler haberden olduğu gibi alınır (yeniden yazılmaz). Rakam açıklamaları ise kısa yan cümlelerden kurallarla
kurulur ("...kurtarıldığını söyledi" -> "kurtarıldı"). Bilgi azsa karusel zorlanmaz, tek kart paylaşılır.
"""

import json
import os
import re

import requests

import haber

KOK = haber.KOK
with open(os.path.join(KOK, "assets", "tr-iller.json"), encoding="utf-8") as f:
    ILLER = [ft["properties"]["name"] for ft in json.load(f)["features"]]

# sayfa menüsü, telif notu, betik gibi haber olmayan paragraflar
COP = ["document.", "function", "Copyright", "telif hakk", "çerez", "e-posta", "Font Boyutu", "BBC News, Türkçe",
       "Kullanım Koşulları", "son dakika haberleri için", "DOLAR", "Kiraz Hesap", "Reklam", "Keşfetmeye Devam",
       "Abone ol", "Haberin Devamı", "Tüm Hakları", "KVKK", "Haber Merkezi", "tıklayın", "TIKLAYIN", "Google News",
       "WhatsApp kanal", "Instagram'da", "takip edin"]

KONU_KELIMELERI = {
    "afet": ["deprem", "sel", "sağanak", "yağış", "fırtına", "dalga", "yangın", "afad", "meteoroloji", "heyelan",
             "su baskın", "kar yağ", "hortum", "turuncu kod", "sarı kod"],
    "spor": ["maç", "gol", "galatasaray", "fenerbahçe", "beşiktaş", "trabzonspor", "milli takım", "uefa", "lig",
             "transfer", "teknik direktör", "futbol", "basketbol", "şampiyon"],
    "ekonomi": ["dolar", "euro", "faiz", "enflasyon", "borsa", "merkez bankası", "asgari ücret", "emekli", "maaş",
                "zam", "vergi", "ekonomi", "akaryakıt", "benzin", "motorin", "ihracat", "piyasa"],
    "dunya": ["abd", "trump", "rusya", "ukrayna", "israil", "gazze", "avrupa birliği", "almanya", "iran", "suriye",
              "nato", "putin", "çin", "yemen", "beyaz saray", "husi", "suudi", "bm ", "birleşmiş milletler",
              "fransa", "ingiltere", "japonya", "lübnan", "irak", "azerbaycan", "yunanistan", "kremlin", "pentagon"],
    "asayis": ["operasyon", "gözaltı", "tutukla", "cinayet", "öldürdü", "saldırı", "kaza", "silahlı", "uyuşturucu",
               "şüpheli", "yakalandı", "cezaevi"],
}
KANCA_KALIBI = {"gundem": "Son dakika", "afet": "Dikkat", "spor": "Spor", "ekonomi": "Ekonomi",
                "dunya": "Dünyadan", "asayis": "Son dakika"}

# ---------- rakamlar ----------

# zaman birimleri (saat, gün, yıl) bilinçli olarak yok: "2 saatte" gibi ifadeler rakam slaytına yakışmıyor
BIRIM = r"(?:metre|kilogram|kg|kişi|derece|santim|ton|TL|lira|dolar|euro|uçuş|bina|araç|yaralı|şüpheli|gol|" \
        r"heyelan|ihbar|su baskını|hane|köy|ev|konut|asker|polis|çocuk|öğrenci|hasta|vaka|sefer|çağrı)"
SAYI = r"\d+(?:[.,]\d+)?(?:\s+(?:bin|milyon|milyar)(?:\s+\d+)?)?"
RAKAM = re.compile(r"(?<![\d.,'’])(?:(?P<yuzde>yüzde\s+\d+(?:[.,]\d+)?)|(?P<sayi>" + SAYI + r")"
                   r"(?P<fazla>['’][a-zçğıöşü]+\s+(?:fazla|aşkın))?\s+(?P<birim>" + BIRIM + r"))"
                   r"(?P<ek>[a-zçğıöşü]*)", re.I)
FIIL_SONU = re.compile(r"(?:[dt][ıiuü]|[ae]c[ae]k|yor|m[ıiuü]ş|[dt][ıiuü]r|[ıiuüae]r|var|yok|[ıiuü]z|"
                       r"m[ae]l[ıi]|[dt][ıiuü]l[ae]r)$")
AKTARMA = {"söyledi", "açıkladı", "belirtti", "bildirdi", "duyurdu", "kaydetti", "dedi", "vurguladı", "aktardı",
           "ifade", "etti", "bildirildi", "açıklandı", "belirtildi"}
BAGLAC = re.compile(r"^(?:Buna göre|Buna ek olarak|Öte yandan|Diğer yandan|Bu arada|Öte taraftan|"
                    r"Bununla birlikte|Ayrıca|Ancak|Aynı zamanda),?\s+")
TIRNAK = re.compile(r"[“\"]([^”\"]{30,170})[”\"]")


def sayi_bicim(m):
    if m.group("yuzde"):
        return "%" + m.group("yuzde").split()[-1]
    s = m.group("sayi")
    p = s.split()
    try:
        if len(p) == 3 and p[1] == "bin":  # "3 bin 50" -> 3.050
            s = f"{int(p[0]) * 1000 + int(p[2]):,}".replace(",", ".")
        elif len(p) == 2 and p[1] == "bin" and p[0].isdigit():
            s = f"{int(p[0]) * 1000:,}".replace(",", ".")
        elif s.isdigit() and int(s) >= 1000:
            s = f"{int(s):,}".replace(",", ".")
    except ValueError:
        pass
    if m.group("fazla"):
        s += "+"
    birim = m.group("birim").lower()
    birim = {"kilogram": "kg"}.get(birim, birim)
    return f"{s} {birim}"


SIRA = {"birinci", "ikinci", "üçüncü", "dördüncü", "beşinci", "altıncı", "yedinci", "sekizinci", "dokuzuncu",
        "onuncu", "son", "ilk"}
UNVAN = {"bakanı", "valisi", "başkanı", "başkanvekili", "sözcüsü", "müdürü", "valiliği", "bakanlığı", "komutanı",
         "yardımcısı", "sekreteri", "üyesi", "rektörü", "kaymakamı", "başsavcılığı", "milletvekili"}


def fiil_cek(metin):
    """Aktarma kipini düz cümleye çevirir: "...kurtarıldığını söyledi" -> "...kurtarıldı".

    Aktarma fiili atılınca baştaki konuşan kişi ("İçişleri Bakanı Mustafa Çiftçi ...") de atılır; yoksa
    "Bakan ... yağış düştü" gibi bozuk bir cümle kalır.
    """
    w = metin.split()
    aktarma = False
    while w and w[-1].strip(".,").lower() in AKTARMA:
        w.pop()
        aktarma = True
    if aktarma:
        i = 0
        while i < len(w) and (w[i][:1].isupper() or w[i].lower() in UNVAN):
            i += 1
        if i >= 2:
            w = w[i:]
    if not w:
        return ""
    son = w[-1].strip(".,")
    son = re.sub(r"([dt])([ıiuü])ğ[ıiuü]n[ıiuü]$", r"\1\2", son)        # kurtarıldığını -> kurtarıldı
    son = re.sub(r"([ae])c([ae])ğ[ıi]n[ıi]$", r"\1c\2k", son)             # katılacağını -> katılacak
    son = re.sub(r"([dt])([ıiuü])ğ[ıiuü]$", r"\1\2", son)                 # olduğu -> oldu
    w[-1] = son
    return " ".join(w)


def bas_harf(s):
    return s[:1].upper() + s[1:] if s else s


def rakam_aciklamasi(cumle, m, son_fiil):
    """Rakamın geçtiği yan cümleden rakamı çıkarıp kısa bir açıklama kurar."""
    bas = cumle.rfind(", ", 0, m.start())
    son = cumle.find(", ", m.end())
    yan = cumle[bas + 2 if bas >= 0 else 0: son if son > 0 else len(cumle)]
    once = yan[:m.start() - (bas + 2 if bas >= 0 else 0)]
    sonra = yan[m.end() - (bas + 2 if bas >= 0 else 0):]
    sonra = re.sub(r"^\s*(?:olayı|olay|ihbarı|vakası|kişilik)\b", "", sonra)  # "su baskını olayı" -> artık söz yok
    yan = once + " " + sonra
    yan = BAGLAC.sub("", re.sub(r"\s+", " ", yan).strip(" .,"))
    yan = fiil_cek(yan)
    if yan and not FIIL_SONU.search(yan.split()[-1]) and son_fiil:  # fiilsiz yan cümle: cümlenin fiilini ödünç al
        odunc = son_fiil.split()
        if yan.split()[-1].lower() in SIRA and odunc[0].lower() in SIRA:
            odunc = odunc[1:]  # "ikinci" + "üçüncü sırada yer aldı" -> "ikinci sırada yer aldı"
        yan = yan + " " + " ".join(odunc)
    yan = re.sub(r"\s+", " ", yan).strip(" .,")
    return bas_harf(yan)


def rakamlar_bul(cumleler, baslik, haric):
    sonuc, gorulen = [], set()
    baslik_sayilari = set(re.findall(r"\d+", baslik))
    for c in cumleler:
        if c in haric or "?" in c:
            continue
        eslesmeler = list(RAKAM.finditer(c))
        # cümlenin son yan cümlesindeki rakamdan sonraki kelimeler = ortak fiil ("...50 kilogram yağış düştü")
        son_fiil = ""
        if eslesmeler and c.rfind(", ") < eslesmeler[-1].start():
            son_fiil = fiil_cek(c[eslesmeler[-1].end():].strip(" ."))
        for m in eslesmeler:
            yazi = sayi_bicim(m)
            if yazi.lower() in gorulen or len(yazi) > 18:
                continue
            if set(re.findall(r"\d+", m.group(0))) & baslik_sayilari:  # başlıktaki rakam tekrar edilmesin
                continue
            aciklama = rakam_aciklamasi(c, m, son_fiil)
            if not 12 <= len(aciklama) <= 80:
                continue
            gorulen.add(yazi.lower())
            sonuc.append((yazi, aciklama, c))
    return sonuc


# ---------- metin çekme ----------

def sayfa_oku(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    metin = r.text
    spot = ""
    m = re.search(r'<meta[^>]+(?:property|name)="(?:og:description|description)"[^>]+content="([^"]*)"', metin)
    if m:
        spot = haber.temizle(m.group(1))
    paragraflar = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", metin, flags=re.S):
        p = haber.temizle(p)
        # Hürriyet: paylaş düğmeleri + tarih paragrafın başına yapışık
        p = re.sub(r"^.*Oluşturulma Tarihi: \w+ \d+, \d{4} \d\d:\d\d", "", p)
        p = p.split("Haberlerimizi Google")[0].strip()
        if len(p) < 40 or any(k in p for k in COP) or not re.search(r"[.!?\"”]$", p):
            continue
        paragraflar.append(p)
    return spot, paragraflar, haber.temizle(re.sub(r"<script.*?</script>", " ", metin, flags=re.S))


def sadelestir(c):
    """Kaynak metindeki boşluk hatalarını ve cümle başındaki bağlaçları temizler."""
    c = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", c)).strip()
    c = re.sub(r"\b(\w+) \1\b", r"\1", c)                                   # "kişi kişi" -> "kişi"
    c = re.sub(r"\s+(['’][a-zçğıöşü]+)", r"\1", c)                     # "Bakanlığı 'nda" -> "Bakanlığı'nda"
    c = re.sub(r"^(?:Anadolu Ajansı|AA|DHA|İHA|Reuters|AFP)\s+(?=[A-ZÇĞİÖŞÜ])", "", c)
    yeni = BAGLAC.sub("", c)
    return bas_harf(yeni) if yeni != c else c


def cumlelere_bol(metin):
    parca = re.split(r"(?<=[.!?])\s+(?=[\"“A-ZÇĞİÖŞÜ0-9])", metin)
    # tırnak içindeki cümleler bölünmesin: tırnak kapanana kadar parçaları birleştir
    birlesik, acik = [], ""
    for p in parca:
        acik = (acik + " " + p).strip()
        if (acik.count('"') % 2 == 0) and acik.count("“") <= acik.count("”"):
            birlesik.append(acik)
            acik = ""
    if acik:
        birlesik.append(acik)
    return [sadelestir(c) for c in birlesik if len(c.strip()) > 25]


# tırnaksız kalmış konuşma cümleleri: "...kurtaramadık.", "...diliyoruz.", "Başkanımızın mekânı cennet olsun."
BIRINCI_SAHIS = re.compile(r"(yorum|yoruz|d[ıiuü]k|t[ıiuü]k|[ae]c[ae]ğ[ıi]z|d[ıiuü]m|t[ıiuü]m|olsun)[.!]?$"
                           r"|\b\w+(ımız|imiz|umuz|ümüz)\w*\b")


def kisalt(c, sinir=170):
    if len(c) <= sinir:
        return c
    kes = c[:sinir]
    virgul = kes.rfind(", ")
    return (kes[:virgul] if virgul > 60 else kes.rsplit(" ", 1)[0]) + "…"


# ---------- bulucular ----------

def konu_bul(baslik, govde):
    b, g = " " + haber.kucult(baslik) + " ", " " + haber.kucult(govde[:800]) + " "

    def say(metin, ws):
        return sum(len(re.findall(r"\b" + re.escape(w), metin)) for w in ws)
    puan = {k: 3 * say(b, ws) + say(g, ws) for k, ws in KONU_KELIMELERI.items()}  # başlık 3 kat sayılır
    en = max(puan, key=puan.get)
    return en if puan[en] >= 3 else "gundem"


def il_bul(baslik, cumleler, konu):
    def iller(metin):
        return [il for il in ILLER if re.search(r"(?<![\wçğıöşü])" + re.escape(il) + r"(?=['’\s,.:;!?]|$)", metin)]
    b = iller(baslik)
    if b:  # birden fazla ilse başlıkta önce geçen (olayın yeri genelde odur)
        return min(b, key=lambda il: baslik.index(il))
    if konu == "dunya":
        return None
    for c in cumleler[:2]:
        b = iller(c)
        if b:
            return min(b, key=lambda il: c.index(il))
    if konu != "afet":  # gövdenin derinindeki bir il adı başka olaydan olabilir, harita yanıltmasın
        return None
    sayac = {}
    for c in cumleler:
        for il in iller(c):
            sayac[il] = sayac.get(il, 0) + 1
    return max(sayac, key=sayac.get) if sayac else None


def kanca_ve_baslik(baslik, konu):
    """Başlık "X: Y" ise kısa X kanca olur. Değilse başlıktaki rakamlı ifade, o da yoksa konuya göre kalıp."""
    if ":" in baslik:
        on, arka = baslik.split(":", 1)
        if 1 <= len(on.split()) <= 5 and len(arka.split()) >= 3:
            return on.strip(), bas_harf(arka.strip())
    m = baslik_rakami(baslik)
    if m:
        return sayi_bicim(m), baslik
    return KANCA_KALIBI[konu], baslik


def baslik_rakami(baslik):
    # başlıklarda "bin 530 uçuş" gibi başında 1 olmayan yazımlar var
    return RAKAM.search(re.sub(r"(?<!\d )\bbin (\d+)", r"1 bin \1", baslik))


def alinti_bul(cumleler, tam_metin):
    for c in cumleler:
        m = TIRNAK.search(c)
        if not m:
            continue
        soz = m.group(1).strip(" ,.")
        if len(soz.split()) < 5 or not FIIL_SONU.search(soz.split()[-1].strip("!?.")):
            continue  # "...sisteme karşı" gibi yarım alıntılar olmasın
        once = c[:m.start()].split()
        sonra = c[m.end():].split()[:4]
        kim = (next((w.strip(",.:") for w in reversed(once[1:]) if w[:1].isupper()), "")
               or next((w.strip(",.:") for w in sonra if w[:1].isupper()), "")
               or (once[0].strip(",.:") if once and once[0][:1].isupper()
                   and haber.kucult(once[0].strip(",.:")) not in BASLANGIC else ""))
        kim = re.sub(r"['’]\w+$", "", kim)
        if kim:  # metinde geçen en uzun hali: "Gül" -> "İstanbul Valisi Davut Gül"
            adlar = re.findall(r"((?:[A-ZÇĞİÖŞÜ][\wçğıöşü]+\s){1,3}" + re.escape(kim) + r")\b", tam_metin)
            if adlar:
                kim = max(adlar, key=len)
        if not kim:
            continue  # kimin söylediği belli olmayan söz yayımlanmaz
        return bas_harf(soz), kim, c
    return None, None, None


BASLANGIC = {"bu", "ancak", "ama", "fakat", "o", "bunun", "şu", "bir", "açıklamada", "açıklamasında", "bence"}


# ---------- cümle seçimi ----------

def ortak(a, b):
    return min(len(a), len(b)) >= 3 and len(a & b) / min(len(a), len(b)) >= 0.5


def puanla(c, baslik_kel):
    p = 0.0
    if re.search(r"\d", c):
        p += 2
    if re.search(r"\s[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}", c):  # cümle içinde özel isim
        p += 1
    p += len(haber.kelimeler(c) & baslik_kel) * 0.5
    if 50 <= len(c) <= 150:
        p += 1
    if re.search(r"(m[ıiuü]şt[ıiuü]|[dt][ıiuü]yd[ıiuü])\.$", c):  # "-mişti": eski, arka plan bilgisi
        p -= 2
    if re.match(r"(Bu |Söz konusu |Aynı |O |Bunun |Şu )", c):  # neye işaret ettiği belli olmayan cümle
        p -= 1
    return p


def sec(adaylar, n, kullanilan_kel, baslik_kel):
    """Puanı yüksek, birbirini tekrar etmeyen n cümle; haberdeki sırasıyla."""
    secilen = []
    for c in sorted(adaylar, key=lambda c: -puanla(c, baslik_kel)):
        if re.match(r"(Bu |Söz konusu |Bunun |Şu )", c):  # tek başına okununca neyi kastettiği belli değil
            continue
        if BIRINCI_SAHIS.search(c) or re.search(r"[\"“”]", c):  # birinin sözü: tırnaksız madde olarak yanıltır
            continue
        k = haber.kelimeler(c)
        if any(ortak(k, u) for u in kullanilan_kel):
            continue
        secilen.append(c)
        kullanilan_kel.append(k)
        if len(secilen) == n:
            break
    return sorted(secilen, key=adaylar.index)


# ---------- ana iş ----------

def zenginlestir(h):
    """Haber kaydına konu, il, kanca ve karusel slaytlarını ekler. Az bilgi varsa slayt listesi boş kalır (tek kart)."""
    try:
        spot, paragraflar, tam_metin = sayfa_oku(h["link"])
    except Exception:
        spot, paragraflar, tam_metin = "", [], ""
    cumleler = []
    for p in paragraflar:
        cumleler += cumlelere_bol(p)
    if not spot or spot.endswith(("...", "…")):
        spot = h.get("ozet", "") if len(h.get("ozet", "")) > len(spot) else (cumleler[0] if cumleler else spot)
    baslik_kel = haber.kelimeler(h["baslik"])
    spot_cumleleri = [c for c in cumlelere_bol(spot) if not haber.benzer(haber.kelimeler(c), baslik_kel)]
    tum = []
    for c in spot_cumleleri + cumleler:
        if c not in tum and "?" not in c:
            tum.append(c)

    konu = konu_bul(h["baslik"], " ".join(tum))
    kanca, baslik = kanca_ve_baslik(h["baslik"], konu)
    ilk = tum[0] if tum else ""
    sonuc = dict(h, konu=konu, kanca=kanca, baslik=baslik, ozet=kisalt(ilk, 220))
    il = il_bul(h["baslik"], tum, konu)
    m = baslik_rakami(h["baslik"])
    if il and konu in ("afet", "asayis"):
        sonuc["il"] = il
    elif m and not m.group("yuzde"):  # kapakta büyük rakam: "1.530" + "uçuş"
        sonuc["rakam"], sonuc["rakam_birim"] = sayi_bicim(m).rsplit(" ", 1)
        if kanca == sayi_bicim(m):  # rakam zaten kapakta kocaman yazıyor, kanca onu tekrarlamasın
            sonuc["kanca"] = KANCA_KALIBI[konu]
    elif il:
        sonuc["il"] = il

    slaytlar = {}
    kullanilan_kel = [baslik_kel]
    if ilk:
        slaytlar["ne"] = {"etiket": "Ne oldu?", "metin": kisalt(ilk, 240)}
        kullanilan_kel.append(haber.kelimeler(ilk))
    havuz = [c for c in tum[1:] if 40 <= len(c) <= 170 and not TIRNAK.search(c)]

    rakamlar = rakamlar_bul(tum, h["baslik"], {ilk})[:3]
    if len(rakamlar) >= 2:
        slaytlar["rakam"] = {"etiket": "Rakamlarla", "rakamlar": [(r, a) for r, a, _ in rakamlar]}
    elif rakamlar:
        r, a, c = rakamlar[0]
        slaytlar["rakam"] = {"etiket": "Rakamla", "rakam": r, "metin": c if len(c) <= 200 else a}
    for _, _, c in rakamlar:  # rakamı gösterilen cümle detaylarda tekrar etmesin
        kullanilan_kel.append(haber.kelimeler(c))

    detay = sec(havuz, 3, kullanilan_kel, baslik_kel)
    if len(detay) >= 2:
        slaytlar["detay"] = {"etiket": "Detaylar", "maddeler": detay}

    soz, kim, c = alinti_bul(tum, " ".join(cumleler))  # ad, sayfa menüsünden değil haber metninden tamamlanır
    if soz:
        slaytlar["soz"] = {"etiket": "Ne dedi?", "alinti": soz, "kim": kim}
        kullanilan_kel.append(haber.kelimeler(c))

    kalan = sec([c for c in havuz if c not in detay], 3, kullanilan_kel, baslik_kel)
    if len(kalan) >= 2:
        slaytlar["ayrica"] = {"etiket": "Ayrıca", "maddeler": kalan}

    sira = [slaytlar[k] for k in ("ne", "detay", "rakam", "soz", "ayrica") if k in slaytlar]
    # "Ne oldu?" dışında en az iki dolu slayt yoksa karusel zorlama olur: tek kart paylaşılır
    sonuc["slaytlar"] = sira if len(sira) >= 3 else []
    return sonuc


if __name__ == "__main__":
    import sys
    d = haber.durum_oku()["haberler"]
    for hid in sys.argv[1:]:
        print(json.dumps(zenginlestir(d[hid]), ensure_ascii=False, indent=1))
