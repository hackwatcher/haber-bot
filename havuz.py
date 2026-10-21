"""Konu görsel havuzu (havuz/<konu>_NN.jpg): habere konusuna ve anahtar kelimelerine en uygun temsili görseli seçer.

Görseller gorsel_promptlari.txt ile üretildi; etiketler o promptlardaki sahnelere göre yazıldı.
Eşit puanlı görseller arasında haber kimliğine göre seçilir, böylece aynı konu hep aynı görseli almaz.
"""

import hashlib
import os
import re

import haber

KOK = haber.KOK
HAVUZ = os.path.join(KOK, "havuz")

ETIKET = {
    "gundem_01": "meclis tbmm milletvekil yasa teklif", "gundem_02": "meclis genel kurul oturum milletvekil",
    "gundem_03": "açıklama basın toplantı konuştu dedi", "gundem_04": "bayrak millet",
    "gundem_05": "seçim sandık oy ysk", "gundem_06": "seçim oy sandık seçmen",
    "gundem_07": "ankara kızılay", "gundem_08": "anıtkabir atatürk",
    "gundem_09": "miting parti kongre", "gundem_10": "basın toplantı açıklama",
    "gundem_11": "gazeteci soru röportaj", "gundem_12": "sayım oy sonuç seçim",
    "gundem_13": "istanbul", "gundem_14": "bakanlık genelge karar resmi gazete",
    "gundem_15": "seçim kampanya afiş", "gundem_16": "canlı yayın tartışma televizyon",
    "gundem_17": "bakanlık kurum", "gundem_18": "ankara", "gundem_19": "bayram tören kutlama",
    "gundem_20": "yasa kanun düzenleme anayasa",
    "afet_01": "enkaz arama kurtarma afad göçük", "afet_02": "enkaz yıkıl çöktü göçtü ağır hasar",
    "afet_03": "çadır depremzede barınma", "afet_04": "orman yangın itfaiye alev",
    "afet_05": "yangın uçak helikopter orman", "afet_06": "sel su baskın yağış sağanak",
    "afet_07": "sel kurtarma bot mahsur", "afet_08": "kar tipi yol kapandı buzlanma",
    "afet_09": "ambulans yaralı acil hastane", "afet_10": "çatlak yarıldı hasar",
    "afet_11": "yardım bağış gönüllü kızılay", "afet_12": "heyelan toprak kayması karadeniz",
    "afet_13": "fırtına yıldırım meteoroloji uyarı", "afet_14": "fırtına dalga sahil hortum",
    "afet_15": "deprem büyüklü kandilli sarsıntı artçı", "afet_16": "yangın küle döndü hektar",
    "ekonomi_01": "lira para maaş", "ekonomi_02": "lira para enflasyon",
    "ekonomi_03": "dolar euro döviz kur", "ekonomi_04": "borsa hisse bist endeks",
    "ekonomi_05": "banka merkez faiz şirket", "ekonomi_06": "market fiyat zam",
    "ekonomi_07": "pazar sebze meyve gıda", "ekonomi_08": "akaryakıt benzin motorin mazot",
    "ekonomi_09": "altın gram çeyrek", "ekonomi_10": "ihracat ithalat liman ticaret",
    "ekonomi_11": "fabrika üretim sanayi işçi", "ekonomi_12": "fatura harcama alım gücü",
    "ekonomi_13": "büyüme rekor artış yüzde", "ekonomi_14": "esnaf alışveriş çarşı",
    "ekonomi_15": "fatura bütçe kira emekli", "ekonomi_16": "çiftçi tarım buğday hasat",
    "dunya_01": "zirve nato", "dunya_02": "görüşme müzakere diplomasi",
    "dunya_03": "istanbul boğaz", "dunya_04": "orta doğu bölge",
    "dunya_05": "ziyaret havalimanı uçak", "dunya_06": "hava saldırı savaş uçağı",
    "dunya_07": "donanma gemi akdeniz", "dunya_08": "sınır kapı göç",
    "dunya_09": "küresel dünya", "dunya_10": "insani yardım gazze",
    "dunya_11": "bm birleşmiş milletler", "dunya_12": "boğaz tanker petrol enerji",
    "dunya_13": "büyükelçi elçilik", "dunya_14": "savaş bombardıman saldırı çatışma",
    "dunya_15": "anlaşma mutabakat imza", "dunya_16": "uydu bölge harita",
    "spor_01": "galatasaray", "spor_02": "fenerbahçe", "spor_03": "beşiktaş",
    "spor_04": "maç süper lig gol", "spor_05": "gol futbolcu transfer",
    "spor_06": "kaleci kurtarış", "spor_07": "milli takım ay-yıldız", "spor_08": "taraftar seyirci stadyum",
    "spor_09": "basketbol", "spor_10": "voleybol filenin sultanları",
    "spor_11": "şampiyon kupa final", "spor_12": "teknik direktör hoca",
    "spor_13": "hakem kırmızı kart penaltı", "spor_14": "derbi maç önü",
    "spor_15": "güreş", "spor_16": "maraton koşu atletizm",
    "asayis_01": "polis ekip", "asayis_02": "cinayet olay yeri öldürüldü",
    "asayis_03": "adliye mahkeme dava", "asayis_04": "gözaltı tutuklandı yakalandı kelepçe",
    "asayis_05": "denetim kontrol uygulama", "asayis_06": "jandarma kırsal",
    "asayis_07": "mahkeme karar hapis cezası hakim", "asayis_08": "soruşturma inceleme delil",
    "asayis_09": "cezaevi hapis tahliye", "asayis_10": "kaza trafik çarpıştı devrildi",
    "asayis_11": "uyuşturucu operasyon ele geçirildi kaçakçılık", "asayis_12": "kamera görüntü güvenlik",
    "asayis_13": "helikopter operasyon", "asayis_14": "sahil güvenlik göçmen tekne",
    "asayis_15": "dolandırıcılık siber bilişim", "asayis_16": "avukat duruşma iddianame",
}


# Ağır ya da takım renkli görseller yalnız habere anahtar kelimeyle eşleşince seçilir, yedek olarak asla.
SADECE_ESLESINCE = {"afet_01", "afet_02", "afet_03", "afet_10", "afet_16", "asayis_02", "asayis_09", "dunya_14",
                    "spor_01", "spor_02", "spor_03", "spor_15", "spor_09", "spor_10", "spor_16", "spor_11",
                    "dunya_06", "dunya_07", "dunya_08", "dunya_10", "asayis_11", "asayis_13"}


def kucuk(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def sec(z, marka):
    """Haber için havuzdan temsili görsel seçer; uygun görsel yoksa None döner."""
    konu = z.get("konu") or "gundem"
    adaylar = [k for k in ETIKET if k.startswith(konu + "_") and os.path.exists(os.path.join(HAVUZ, k + ".jpg"))]
    if not adaylar:
        return None
    kelimeler = re.findall(r"[\w-]+", kucuk(" ".join(str(z.get(a) or "") for a in ("baslik", "kanca", "ozet"))))
    puan = {k: sum(1 for e in ETIKET[k].split() if any(w.startswith(e) for w in kelimeler)) for k in adaylar}
    en_iyi = max(puan.values())
    adaylar = sorted(k for k in adaylar if puan[k] == en_iyi and (en_iyi > 0 or k not in SADECE_ESLESINCE))
    sira = int(hashlib.md5(str(z.get("id") or kelimeler).encode()).hexdigest(), 16)
    secilen = adaylar[sira % len(adaylar)]
    return {"yol": f"havuz/{secilen}.jpg", "not": f"Temsili görsel · {marka}"}
