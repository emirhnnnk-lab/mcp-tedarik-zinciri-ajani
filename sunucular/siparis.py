# -*- coding: utf-8 -*-
"""
MCP sunucusu: SİPARİŞ. Tek yazma yapan sunucu.

Güvenlik tasarımı (kurallar MODELDE değil SUNUCUDA):
- Ajan sadece TASLAK oluşturabilir. Taslak, politika kontrollerinden geçmezse reddedilir:
  kara liste, minimum miktar, piyasanın %10'undan pahalı fiyat, bütçe limiti.
- Taslağı kesinleştirmek için 'onay_kodu' gerekir. Bu kodu sadece insan onay paneli
  (onay/panel.py) üretir; hiçbir MCP aracı kod üretmez. Prompt injection ile ajan
  "onayladım" dese bile sunucu kodu doğrulamadan siparişi geçirmez.
"""
import os

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from sunucular.ortak import baglan, denetle, satirlar

BUTCE_LIMIT_USD = float(os.environ.get("BUTCE_LIMIT_USD", "150000"))
FIYAT_TOLERANS = 0.10

sunucu = MCPServer("siparis", instructions=(
    "Satın alma siparişleri. Ajan sadece taslak oluşturabilir; kesinleştirme insan onay kodu ister."))


def politika_kontrol(tedarikci_id, urun, miktar, birim_fiyat):
    """Taslağı engelleyen kurallar. Boş liste = geçti."""
    hatalar = []
    t = satirlar("SELECT * FROM tedarikci WHERE id=?", tedarikci_id)
    if not t:
        return ["tedarikçi bulunamadı"]
    if t[0]["kara_liste"]:
        hatalar.append(f"{t[0]['ad']} kara listede (kalite sorunu); sipariş verilemez")
    k = satirlar("SELECT * FROM teklif WHERE tedarikci_id=? AND urun=?", tedarikci_id, urun)
    if not k:
        hatalar.append("bu tedarikçinin bu ürün için geçerli teklifi yok")
    else:
        if miktar < k[0]["min_miktar"]:
            hatalar.append(f"minimum miktar {k[0]['min_miktar']} ton")
        if abs(birim_fiyat - k[0]["fiyat"]) > 0.01:
            hatalar.append(f"birim fiyat teklifle uyuşmuyor (teklif {k[0]['fiyat']} USD)")
    p = satirlar("SELECT fiyat FROM piyasa WHERE urun=?", urun)
    if p and birim_fiyat > p[0]["fiyat"] * (1 + FIYAT_TOLERANS):
        hatalar.append(f"fiyat piyasanın %{int(FIYAT_TOLERANS * 100)} üzerinde ({p[0]['fiyat']} USD)")
    if miktar * birim_fiyat > BUTCE_LIMIT_USD:
        hatalar.append(f"toplam {miktar * birim_fiyat:,.0f} USD bütçe limitini ({BUTCE_LIMIT_USD:,.0f}) aşıyor")
    if miktar <= 0:
        hatalar.append("miktar pozitif olmalı")
    return hatalar


@sunucu.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False))
def siparis_taslagi_olustur(tedarikci_id: int, urun: str, miktar_ton: float,
                            birim_fiyat_usd: float, gerekce: str) -> dict:
    """Satın alma siparişi TASLAĞI oluşturur (henüz kesin sipariş değildir).
    Sunucu politika kontrolü yapar: kara liste, minimum miktar, teklifle aynı fiyat,
    piyasaya göre fiyat, bütçe limiti. Geçemezse taslak oluşmaz ve nedenleri döner.
    Taslak bir insanın onay panelinden onaylamasını bekler."""
    girdi = dict(tedarikci_id=tedarikci_id, urun=urun, miktar_ton=miktar_ton,
                 birim_fiyat_usd=birim_fiyat_usd, gerekce=gerekce)
    urun = urun.upper()
    hatalar = politika_kontrol(tedarikci_id, urun, miktar_ton, birim_fiyat_usd)
    if hatalar:
        return denetle("siparis", "siparis_taslagi_olustur", girdi,
                       {"durum": "REDDEDILDI", "nedenler": hatalar})
    with baglan() as db:
        cur = db.execute("""INSERT INTO siparis(tedarikci_id, urun, miktar, birim_fiyat, toplam_usd,
                            durum, gerekce) VALUES(?,?,?,?,?,'ONAY_BEKLIYOR',?)""",
                         (tedarikci_id, urun, miktar_ton, birim_fiyat_usd,
                          round(miktar_ton * birim_fiyat_usd, 2), gerekce))
        sid = cur.lastrowid
    return denetle("siparis", "siparis_taslagi_olustur", girdi,
                   {"durum": "ONAY_BEKLIYOR", "siparis_id": sid,
                    "not": "Taslak oluşturuldu. Kesinleşmesi için insan onayı gerekiyor."})


@sunucu.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True))
def siparisi_kesinlestir(siparis_id: int, onay_kodu: str) -> dict:
    """Onay bekleyen taslağı kesin siparişe çevirir. SADECE insanın onay panelinde
    ürettiği tek kullanımlık onay_kodu ile çalışır. Ajan bu kodu üretemez veya tahmin edemez."""
    girdi = {"siparis_id": siparis_id, "onay_kodu": onay_kodu}
    with baglan() as db:
        k = db.execute("SELECT * FROM onay_kodu WHERE kod=? AND siparis_id=? AND kullanildi=0",
                       (onay_kodu, siparis_id)).fetchone()
        if not k:
            return denetle("siparis", "siparisi_kesinlestir", girdi,
                           {"durum": "REDDEDILDI", "neden": "geçersiz veya kullanılmış onay kodu"})
        db.execute("UPDATE onay_kodu SET kullanildi=1 WHERE kod=?", (onay_kodu,))
        db.execute("UPDATE siparis SET durum='KESIN' WHERE id=?", (siparis_id,))
    return denetle("siparis", "siparisi_kesinlestir", girdi, {"durum": "KESIN", "siparis_id": siparis_id})


@sunucu.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False))
def siparisleri_listele(durum: str = "") -> list[dict]:
    """Siparişleri listeler. durum: '', 'ONAY_BEKLIYOR', 'KESIN', 'REDDEDILDI'."""
    if durum:
        r = satirlar("SELECT * FROM siparis WHERE durum=? ORDER BY id", durum)
    else:
        r = satirlar("SELECT * FROM siparis ORDER BY id")
    return denetle("siparis", "siparisleri_listele", {"durum": durum}, r)


if __name__ == "__main__":
    sunucu.run()
