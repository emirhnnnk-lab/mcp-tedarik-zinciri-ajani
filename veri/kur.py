# -*- coding: utf-8 -*-
"""Örnek veritabanını sıfırdan kurar. Tüm şirket, ürün ve fiyatlar ÖRNEKTİR."""
import os
import sqlite3

YOL = os.environ.get("TEDARIK_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tedarik.db"))

URUNLER = [  # kod, ad, birim, stok, kritik_seviye, gunluk_tuketim
    ("MSR", "Mısır", "ton", 120, 300, 40),
    ("BGD", "Buğday", "ton", 850, 400, 35),
    ("SYK", "Soya küspesi", "ton", 90, 150, 12),
    ("AYG", "Ayçiçek yağı", "ton", 60, 50, 4),
    ("SKR", "Şeker", "ton", 210, 100, 6),
    ("ARP", "Arpa", "ton", 40, 120, 9),
]
TEDARIKCILER = [  # id, ad, ulke, puan(1-5), teslim_gun, kara_liste
    (1, "Alfa Tahıl A.Ş.", "Türkiye", 4.6, 5, 0),
    (2, "Beta Grain Ltd.", "Ukrayna", 4.1, 14, 0),
    (3, "Gama Agro S.A.", "Arjantin", 3.8, 35, 0),
    (4, "Delta Emtia SRL", "Romanya", 4.3, 10, 0),
    (5, "Epsilon Ticaret Ltd.", "Türkiye", 2.1, 3, 1),   # kalite sorunları -> kara listede
]
TEKLIFLER = [  # tedarikci_id, urun, birim_fiyat_usd, min_miktar, gecerlilik
    (1, "MSR", 238, 50, "2026-11-30"), (2, "MSR", 221, 500, "2026-11-25"),
    (4, "MSR", 229, 100, "2026-12-05"), (5, "MSR", 199, 10, "2026-11-20"),
    (1, "BGD", 265, 50, "2026-11-30"), (2, "BGD", 249, 500, "2026-11-25"),
    (3, "SYK", 412, 200, "2026-12-10"), (4, "SYK", 431, 50, "2026-12-01"),
    (1, "SYK", 445, 20, "2026-11-30"), (2, "AYG", 1080, 20, "2026-11-28"),
    (4, "AYG", 1115, 10, "2026-12-01"), (1, "ARP", 214, 30, "2026-11-30"),
    (4, "ARP", 205, 100, "2026-12-05"), (5, "ARP", 180, 10, "2026-11-20"),
]
PIYASA = [  # urun, fiyat_usd_ton, haftalik_degisim_yuzde
    ("MSR", 225, -1.8), ("BGD", 255, 0.6), ("SYK", 428, 2.4),
    ("AYG", 1095, -0.4), ("SKR", 510, 1.1), ("ARP", 210, -0.9),
]
KURLAR = [("USD", 41.20), ("EUR", 47.85)]


def kur(yol=YOL):
    if os.path.exists(yol):
        os.remove(yol)
    db = sqlite3.connect(yol)
    db.executescript("""
    CREATE TABLE urun(kod TEXT PRIMARY KEY, ad TEXT, birim TEXT, stok REAL, kritik REAL, gunluk REAL);
    CREATE TABLE tedarikci(id INTEGER PRIMARY KEY, ad TEXT, ulke TEXT, puan REAL, teslim_gun INTEGER, kara_liste INTEGER);
    CREATE TABLE teklif(tedarikci_id INTEGER, urun TEXT, fiyat REAL, min_miktar REAL, gecerlilik TEXT);
    CREATE TABLE piyasa(urun TEXT, fiyat REAL, degisim REAL);
    CREATE TABLE kur(para TEXT, try REAL);
    CREATE TABLE siparis(id INTEGER PRIMARY KEY AUTOINCREMENT, tedarikci_id INTEGER, urun TEXT,
        miktar REAL, birim_fiyat REAL, toplam_usd REAL, durum TEXT, gerekce TEXT,
        onaylayan TEXT, olusturma TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE onay_kodu(kod TEXT PRIMARY KEY, siparis_id INTEGER, kullanildi INTEGER DEFAULT 0);
    CREATE TABLE denetim(id INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT DEFAULT CURRENT_TIMESTAMP,
        sunucu TEXT, arac TEXT, girdi TEXT, sonuc TEXT);
    """)
    db.executemany("INSERT INTO urun VALUES(?,?,?,?,?,?)", URUNLER)
    db.executemany("INSERT INTO tedarikci VALUES(?,?,?,?,?,?)", TEDARIKCILER)
    db.executemany("INSERT INTO teklif VALUES(?,?,?,?,?)", TEKLIFLER)
    db.executemany("INSERT INTO piyasa VALUES(?,?,?)", PIYASA)
    db.executemany("INSERT INTO kur VALUES(?,?)", KURLAR)
    db.commit()
    db.close()
    return yol


if __name__ == "__main__":
    print("kuruldu:", kur())
