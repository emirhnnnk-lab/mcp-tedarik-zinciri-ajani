# -*- coding: utf-8 -*-
"""MCP sunucusu: STOK. Sadece okuma yapar."""
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from sunucular.ortak import denetle, satirlar

sunucu = MCPServer("stok", instructions="Depo stok durumu. Sadece okuma.")
OKU = ToolAnnotations(read_only_hint=True, destructive_hint=False)


def _gun(r):
    return round(r["stok"] / r["gunluk"], 1) if r["gunluk"] else None


@sunucu.tool(annotations=OKU)
def stok_sorgula(urun: str) -> dict:
    """Bir ürünün stok miktarını, kritik seviyesini ve kaç günlük stok kaldığını verir.
    urun: ürün kodu (MSR, BGD, SYK, AYG, SKR, ARP) veya Türkçe adı (ör. 'Mısır')."""
    r = satirlar("SELECT * FROM urun WHERE kod=? OR lower(ad)=lower(?)", urun.upper(), urun)
    if not r:
        return denetle("stok", "stok_sorgula", {"urun": urun}, {"hata": f"ürün bulunamadı: {urun}"})
    r = r[0]
    sonuc = {**r, "kalan_gun": _gun(r), "kritik_mi": r["stok"] < r["kritik"]}
    return denetle("stok", "stok_sorgula", {"urun": urun}, sonuc)


@sunucu.tool(annotations=OKU)
def kritik_stoklar() -> list[dict]:
    """Stoğu kritik seviyenin altına düşmüş tüm ürünleri, en acilden başlayarak listeler."""
    r = [{**x, "kalan_gun": _gun(x)} for x in satirlar("SELECT * FROM urun WHERE stok < kritik")]
    r.sort(key=lambda x: x["kalan_gun"] or 0)
    return denetle("stok", "kritik_stoklar", {}, r)


if __name__ == "__main__":
    sunucu.run()
