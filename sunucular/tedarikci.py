# -*- coding: utf-8 -*-
"""MCP sunucusu: TEDARİKÇİ ve TEKLİFLER. Sadece okuma yapar."""
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from sunucular.ortak import denetle, satirlar

sunucu = MCPServer("tedarikci", instructions="Tedarikçi bilgisi ve fiyat teklifleri. Sadece okuma.")
OKU = ToolAnnotations(read_only_hint=True, destructive_hint=False)


@sunucu.tool(annotations=OKU)
def teklifleri_karsilastir(urun: str, miktar_ton: float) -> list[dict]:
    """Bir ürün için geçerli teklifleri getirir ve karşılaştırır.
    Her teklifte: tedarikçi, birim fiyat (USD/ton), toplam tutar, teslim süresi, puan,
    minimum miktar uygun mu ve tedarikçi kara listede mi bilgisi vardır.
    Kara listedeki tedarikçiler listede görünür ama 'uygun' değildir."""
    r = satirlar("""SELECT t.id tedarikci_id, t.ad tedarikci, t.ulke, t.puan, t.teslim_gun, t.kara_liste,
                    k.fiyat birim_fiyat_usd, k.min_miktar, k.gecerlilik
                    FROM teklif k JOIN tedarikci t ON t.id=k.tedarikci_id
                    WHERE k.urun=? ORDER BY k.fiyat""", urun.upper())
    for x in r:
        x["toplam_usd"] = round(x["birim_fiyat_usd"] * miktar_ton, 2)
        x["min_miktar_uygun"] = miktar_ton >= x["min_miktar"]
        x["kara_liste"] = bool(x["kara_liste"])
        x["uygun"] = x["min_miktar_uygun"] and not x["kara_liste"]
    return denetle("tedarikci", "teklifleri_karsilastir", {"urun": urun, "miktar_ton": miktar_ton}, r)


@sunucu.tool(annotations=OKU)
def tedarikci_bilgisi(tedarikci_id: int) -> dict:
    """Tek bir tedarikçinin ülke, kalite puanı (1-5), ortalama teslim süresi ve kara liste durumu."""
    r = satirlar("SELECT * FROM tedarikci WHERE id=?", tedarikci_id)
    sonuc = r[0] if r else {"hata": "tedarikçi yok"}
    return denetle("tedarikci", "tedarikci_bilgisi", {"tedarikci_id": tedarikci_id}, sonuc)


if __name__ == "__main__":
    sunucu.run()
