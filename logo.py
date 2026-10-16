"""@xhabercom profil logosu: kartlarla aynı renkler (koyu zemin, haber kırmızısı) ve Montserrat.

Instagram profil fotoğrafını yuvarlak kırpar; her şey ortadaki daireye sığacak şekilde çizilir.
Düz beyaz-siyah tek "X" bilinçli olarak yok: X (Twitter) logosuna benziyor.
"""

import os

from PIL import Image, ImageDraw, ImageFont

KOK = os.path.dirname(os.path.abspath(__file__))
KALIN = os.path.join(KOK, "fonts", "Montserrat-ExtraBold.ttf")
CIKTI = os.path.join(KOK, "logo")
B = 2160  # büyük çiz, sonra küçült: kenarlar yumuşak olsun
KOYU = (14, 17, 23)
KIRMIZI = (230, 30, 42)
BEYAZ = (255, 255, 255)


def ortala(c, metin, f, y, renk):
    w = c.textlength(metin, font=f)
    x0, y0, x1, y1 = c.textbbox((0, 0), metin, font=f)
    c.text(((B - w) / 2, y - y0), metin, font=f, fill=renk)
    return y + (y1 - y0)


def yukseklik(c, metin, f):
    x0, y0, x1, y1 = c.textbbox((0, 0), metin, font=f)
    return y1 - y0


def kaydet(img, ad):
    img = img.resize((1080, 1080), Image.LANCZOS)
    img.save(os.path.join(CIKTI, ad + ".png"))
    return img


def v1_kirmizi():
    """Kırmızı zemin, beyaz X, altında HABER."""
    img = Image.new("RGB", (B, B), KIRMIZI)
    c = ImageDraw.Draw(img)
    fx, fh, fc = ImageFont.truetype(KALIN, 900), ImageFont.truetype(KALIN, 230), ImageFont.truetype(KALIN, 130)
    h = yukseklik(c, "X", fx) + 90 + yukseklik(c, "HABER", fh) + 50 + yukseklik(c, ".com", fc)
    y = (B - h) / 2
    y = ortala(c, "X", fx, y, BEYAZ) + 90
    y = ortala(c, "HABER", fh, y, BEYAZ) + 50
    ortala(c, ".com", fc, y, (255, 205, 208))
    return kaydet(img, "logo1_kirmizi")


def v2_koyu():
    """Tam siyah zemin, kırmızı X, beyaz HABER, X'in altında kartlardaki kırmızı çizgi."""
    img = Image.new("RGB", (B, B), (0, 0, 0))
    c = ImageDraw.Draw(img)
    fx, fh, fc = ImageFont.truetype(KALIN, 860), ImageFont.truetype(KALIN, 220), ImageFont.truetype(KALIN, 125)
    h = yukseklik(c, "X", fx) + 150 + yukseklik(c, "HABER", fh) + 50 + yukseklik(c, ".com", fc)
    y = (B - h) / 2
    y = ortala(c, "X", fx, y, KIRMIZI) + 60
    c.rectangle([B / 2 - 170, y, B / 2 + 170, y + 34], fill=KIRMIZI)
    y = ortala(c, "HABER", fh, y + 90, BEYAZ) + 50
    ortala(c, ".com", fc, y, KIRMIZI)
    return kaydet(img, "logo2_koyu")


def v3_rozet():
    """Koyu zemin, ortada kırmızı yuvarlatılmış kare içinde X, altında XHABER yazısı."""
    img = Image.new("RGB", (B, B), KOYU)
    c = ImageDraw.Draw(img)
    kare = 820
    fx, fh = ImageFont.truetype(KALIN, 660), ImageFont.truetype(KALIN, 200)
    fc = ImageFont.truetype(KALIN, 115)
    h = kare + 110 + yukseklik(c, "XHABER", fh) + 45 + yukseklik(c, ".com", fc)
    y = (B - h) / 2
    c.rounded_rectangle([(B - kare) / 2, y, (B + kare) / 2, y + kare], radius=150, fill=KIRMIZI)
    ortala(c, "X", fx, y + (kare - yukseklik(c, "X", fx)) / 2, BEYAZ)
    # XHABER: X kırmızı, HABER beyaz
    wx, wh = c.textlength("X", font=fh), c.textlength("HABER", font=fh)
    x = (B - wx - wh) / 2
    yy = y + kare + 110 - c.textbbox((0, 0), "X", font=fh)[1]
    c.text((x, yy), "X", font=fh, fill=KIRMIZI)
    c.text((x + wx, yy), "HABER", font=fh, fill=BEYAZ)
    ortala(c, ".com", fc, y + kare + 110 + yukseklik(c, "XHABER", fh) + 45, (150, 158, 170))
    return kaydet(img, "logo3_rozet")


def yuvarlak(img):
    """Instagram'daki gibi daire kırpılmış önizleme."""
    k = 4
    maske = Image.new("L", (img.width * k, img.height * k), 0)
    ImageDraw.Draw(maske).ellipse([0, 0, maske.width, maske.height], fill=255)
    maske = maske.resize(img.size, Image.LANCZOS)
    out = Image.new("RGB", img.size, (250, 250, 250))
    out.paste(img, (0, 0), maske)
    return out


if __name__ == "__main__":
    os.makedirs(CIKTI, exist_ok=True)
    logolar = [v1_kirmizi(), v2_koyu(), v3_rozet()]
    # önizleme: üstte büyük daireler, altta profil boyutunda (küçük) daireler
    sayfa = Image.new("RGB", (3 * 520 + 80, 520 + 60 + 180), (250, 250, 250))
    for i, img in enumerate(logolar):
        y = yuvarlak(img)
        sayfa.paste(y.resize((480, 480), Image.LANCZOS), (40 + i * 540, 40))
        kucuk = y.resize((150, 150), Image.LANCZOS)
        sayfa.paste(kucuk, (40 + i * 540 + 165, 560))
    sayfa.save(os.path.join(CIKTI, "onizleme.png"))
    print("tamam")
