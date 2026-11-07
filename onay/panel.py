# -*- coding: utf-8 -*-
"""
İnsan onay paneli: ajanın oluşturduğu sipariş taslaklarını bir insan onaylar/reddeder.
Bu panel MCP üzerinden ERİŞİLEMEZ; ajan bu işlemi yapamaz.

Çalıştır: python -m uvicorn onay.panel:app --port 8010   ->  http://localhost:8010
"""
import html
import secrets

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from sunucular.ortak import baglan, satirlar

app = FastAPI(title="Satın Alma Onay Paneli")

STIL = """<style>body{font-family:system-ui;margin:24px;background:#0b0f14;color:#e6edf3}
table{border-collapse:collapse;width:100%;margin-bottom:28px}td,th{border:1px solid #30363d;padding:6px 8px;
font-size:14px;text-align:left}th{background:#161b22}button{padding:5px 12px;border:0;border-radius:6px;
cursor:pointer;margin-right:4px}.ok{background:#238636;color:#fff}.no{background:#da3633;color:#fff}
h2{margin-top:30px}.k{color:#8b949e;font-size:13px}</style>"""


def _tablo(satir, sutunlar, ek=None):
    bas = "".join(f"<th>{c}</th>" for c in sutunlar) + ("<th></th>" if ek else "")
    govde = ""
    for r in satir:
        govde += "<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in sutunlar)
        govde += (f"<td>{ek(r)}</td>" if ek else "") + "</tr>"
    return f"<table><tr>{bas}</tr>{govde}</table>"


@app.get("/", response_class=HTMLResponse)
def ana():
    bekleyen = satirlar("""SELECT s.id, t.ad tedarikci, s.urun, s.miktar, s.birim_fiyat, s.toplam_usd, s.gerekce
                           FROM siparis s JOIN tedarikci t ON t.id=s.tedarikci_id
                           WHERE durum='ONAY_BEKLIYOR' ORDER BY s.id""")
    diger = satirlar("""SELECT s.id, t.ad tedarikci, s.urun, s.miktar, s.toplam_usd, s.durum, s.onaylayan
                        FROM siparis s JOIN tedarikci t ON t.id=s.tedarikci_id
                        WHERE durum!='ONAY_BEKLIYOR' ORDER BY s.id DESC LIMIT 20""")
    gunluk = satirlar("SELECT zaman, sunucu, arac, girdi, substr(sonuc,1,120) sonuc FROM denetim "
                      "ORDER BY id DESC LIMIT 25")

    def butonlar(r):
        return (f"<form method=post action=/karar style=display:inline><input type=hidden name=sid value={r['id']}>"
                f"<button class=ok name=karar value=onay>Onayla</button>"
                f"<button class=no name=karar value=red>Reddet</button></form>")

    return (f"<html><head><meta charset=utf-8><title>Onay Paneli</title>{STIL}</head><body>"
            f"<h1>🧾 Satın Alma Onay Paneli</h1><p class=k>Ajan sadece taslak oluşturur. "
            f"Kesinleştirme sadece buradan, bir insan tarafından yapılır.</p>"
            f"<h2>Onay bekleyen taslaklar ({len(bekleyen)})</h2>"
            + _tablo(bekleyen, ["id", "tedarikci", "urun", "miktar", "birim_fiyat", "toplam_usd", "gerekce"], butonlar)
            + "<h2>Son kararlar</h2>" + _tablo(diger, ["id", "tedarikci", "urun", "miktar", "toplam_usd", "durum", "onaylayan"])
            + "<h2>Denetim günlüğü (son 25 MCP çağrısı)</h2>"
            + _tablo(gunluk, ["zaman", "sunucu", "arac", "girdi", "sonuc"]) + "</body></html>")


@app.post("/karar")
def karar(sid: int = Form(...), karar: str = Form(...)):
    with baglan() as db:
        if karar == "onay":
            kod = secrets.token_hex(4)
            db.execute("INSERT INTO onay_kodu(kod, siparis_id, kullanildi) VALUES(?,?,1)", (kod, sid))
            db.execute("UPDATE siparis SET durum='KESIN', onaylayan='satin_alma_muduru' "
                       "WHERE id=? AND durum='ONAY_BEKLIYOR'", (sid,))
        else:
            db.execute("UPDATE siparis SET durum='REDDEDILDI', onaylayan='satin_alma_muduru' "
                       "WHERE id=? AND durum='ONAY_BEKLIYOR'", (sid,))
    return RedirectResponse("/", status_code=303)
