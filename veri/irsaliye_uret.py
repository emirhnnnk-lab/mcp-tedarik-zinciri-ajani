# -*- coding: utf-8 -*-
"""
Sentetik irsaliye görüntüleri + doğru cevaplar (ground truth). Tümü ÖRNEKTİR.
Gerçekçilik için: hafif döndürme, bulanıklık, gürültü, kağıt tonu, farklı yazı boyutları.
Çıktı: veri/irsaliyeler/*.png ve veri/irsaliyeler/cevaplar.json
"""
import json
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

KLASOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "irsaliyeler")
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_K = "C:/Windows/Fonts/arialbd.ttf"

ORNEKLER = [  # irsaliye_no, tedarikci, urun, miktar, plaka, tarih
    ("IRS-2026-0412", "Delta Emtia SRL", "Mısır", 200.0, "34 ABC 123", "12.11.2026"),
    ("IRS-2026-0413", "Delta Emtia SRL", "Mısır", 187.5, "34 ABC 123", "12.11.2026"),   # eksik teslim
    ("IRS-2026-0420", "Alfa Tahıl A.Ş.", "Buğday", 100.0, "06 TR 4521", "13.11.2026"),
    ("IRS-2026-0431", "Gama Agro S.A.", "Soya küspesi", 250.0, "35 KL 908", "14.11.2026"),
    ("IRS-2026-0432", "Gama Agro S.A.", "Soya küspesi", 251.8, "35 KL 908", "14.11.2026"),  # tolerans içi
    ("IRS-2026-0440", "Beta Grain Ltd.", "Ayçiçek yağı", 30.0, "61 AB 777", "15.11.2026"),
    ("IRS-2026-0447", "Delta Emtia SRL", "Arpa", 150.0, "41 DE 2290", "16.11.2026"),
    ("IRS-2026-0448", "Delta Emtia SRL", "Buğday", 150.0, "41 DE 2290", "16.11.2026"),   # yanlış ürün
    ("IRS-2026-0452", "Alfa Tahıl A.Ş.", "Mısır", 50.0, "06 TR 4521", "17.11.2026"),
    ("IRS-2026-0460", "Epsilon Ticaret Ltd.", "Mısır", 200.0, "34 HZ 001", "18.11.2026"),     # yanlış tedarikçi
    ("IRS-2026-0471", "Beta Grain Ltd.", "Buğday", 520.0, "61 AB 777", "19.11.2026"),
    ("IRS-2026-0475", "Alfa Tahıl A.Ş.", "Arpa", 30.0, "06 TR 4522", "20.11.2026"),
]


def ciz(no, ted, urun, miktar, plaka, tarih, tohum):
    r = random.Random(tohum)
    W, H = 900, 620
    zemin = (r.randint(240, 252), r.randint(236, 248), r.randint(222, 238))
    img = Image.new("RGB", (W, H), zemin)
    d = ImageDraw.Draw(img)
    k = ImageFont.truetype(FONT_K, 34)
    f = ImageFont.truetype(FONT, r.choice([22, 24, 26]))
    d.text((40, 30), "SEVK İRSALİYESİ", font=k, fill=(20, 20, 20))
    d.text((620, 40), f"No: {no}", font=f, fill=(20, 20, 20))
    d.line((40, 85, 860, 85), fill=(60, 60, 60), width=2)
    satirlar = [("Gönderen", ted), ("Alıcı", "Örnek Yem ve Gıda San. A.Ş."), ("Sevk tarihi", tarih),
                ("Araç plakası", plaka)]
    y = 110
    for a, b in satirlar:
        d.text((40, y), f"{a}:", font=f, fill=(40, 40, 40))
        d.text((260, y), b, font=f, fill=(10, 10, 10))
        y += 42
    y += 20
    d.rectangle((40, y, 860, y + 120), outline=(60, 60, 60), width=2)
    d.text((55, y + 10), "Malın cinsi", font=f, fill=(40, 40, 40))
    d.text((480, y + 10), "Miktar", font=f, fill=(40, 40, 40))
    d.line((40, y + 50, 860, y + 50), fill=(60, 60, 60), width=1)
    d.text((55, y + 68), urun, font=f, fill=(10, 10, 10))
    d.text((480, y + 68), f"{miktar:,.1f} ton".replace(".", ","), font=f, fill=(10, 10, 10))
    d.text((40, H - 70), "Teslim eden: ____________     Teslim alan: ____________", font=f, fill=(50, 50, 50))
    img = img.rotate(r.uniform(-2.5, 2.5), expand=False, fillcolor=zemin)
    img = img.filter(ImageFilter.GaussianBlur(r.uniform(0.3, 0.9)))
    px = img.load()
    for _ in range(3000):
        x, yy = r.randrange(W), r.randrange(H)
        g = r.randint(120, 200)
        px[x, yy] = (g, g, g)
    return img


def uret():
    os.makedirs(KLASOR, exist_ok=True)
    cevaplar = {}
    for i, (no, ted, urun, miktar, plaka, tarih) in enumerate(ORNEKLER):
        ad = f"irsaliye_{i + 1:02d}.png"
        ciz(no, ted, urun, miktar, plaka, tarih, i).save(os.path.join(KLASOR, ad))
        cevaplar[ad] = {"irsaliye_no": no, "tedarikci": ted, "urun": urun, "miktar_ton": miktar,
                        "arac_plaka": plaka, "tarih": tarih}
    with open(os.path.join(KLASOR, "cevaplar.json"), "w", encoding="utf-8") as f:
        json.dump(cevaplar, f, ensure_ascii=False, indent=1)
    return len(cevaplar)


if __name__ == "__main__":
    print(uret(), "irsaliye üretildi")
