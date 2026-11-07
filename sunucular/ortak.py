# -*- coding: utf-8 -*-
"""Sunucuların ortak yardımcıları: veritabanı bağlantısı ve denetim günlüğü."""
import contextlib
import json
import os
import sqlite3

DB = os.environ.get("TEDARIK_DB", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "veri", "tedarik.db"))


@contextlib.contextmanager
def baglan():
    """Bağlantıyı açar, iş bitince commit edip KAPATIR (Windows'ta dosya kilidi kalmasın)."""
    db = sqlite3.connect(os.environ.get("TEDARIK_DB", DB))
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def denetle(sunucu, arac, girdi, sonuc):
    """Her araç çağrısı denetim tablosuna yazılır (kim, ne, hangi girdiyle, ne döndü)."""
    with baglan() as db:
        db.execute("INSERT INTO denetim(sunucu, arac, girdi, sonuc) VALUES(?,?,?,?)",
                   (sunucu, arac, json.dumps(girdi, ensure_ascii=False),
                    json.dumps(sonuc, ensure_ascii=False)[:2000]))
    return sonuc


def satirlar(sorgu, *p):
    with baglan() as db:
        return [dict(r) for r in db.execute(sorgu, p)]
