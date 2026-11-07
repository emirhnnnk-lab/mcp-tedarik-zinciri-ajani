# -*- coding: utf-8 -*-
"""MCP sunucusu: PİYASA (emtia fiyatı, döviz kuru). Örnek veri, sadece okuma."""
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from sunucular.ortak import denetle, satirlar

sunucu = MCPServer("piyasa", instructions="Emtia referans fiyatları ve kurlar (örnek veri).")
OKU = ToolAnnotations(read_only_hint=True, destructive_hint=False)


@sunucu.tool(annotations=OKU)
def emtia_fiyati(urun: str) -> dict:
    """Ürünün piyasa referans fiyatı (USD/ton) ve haftalık değişimi (%).
    Bir teklifin pahalı mı ucuz mu olduğunu anlamak için kullanılır."""
    r = satirlar("SELECT * FROM piyasa WHERE urun=?", urun.upper())
    return denetle("piyasa", "emtia_fiyati", {"urun": urun}, r[0] if r else {"hata": "fiyat yok"})


@sunucu.tool(annotations=OKU)
def doviz_kuru(para: str = "USD") -> dict:
    """Para biriminin TL karşılığı (USD veya EUR)."""
    r = satirlar("SELECT * FROM kur WHERE para=?", para.upper())
    return denetle("piyasa", "doviz_kuru", {"para": para}, r[0] if r else {"hata": "kur yok"})


if __name__ == "__main__":
    sunucu.run()
