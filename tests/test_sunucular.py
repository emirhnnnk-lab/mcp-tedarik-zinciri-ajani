# -*- coding: utf-8 -*-
"""MCP sunucularının ve güvenlik kurallarının testleri (LLM gerekmez)."""
import os
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
os.environ["TEDARIK_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest  # noqa: E402
from mcp import Client  # noqa: E402

from veri.kur import kur  # noqa: E402
from sunucular import siparis, stok, tedarikci, ses  # noqa: E402
from sunucular.ortak import baglan, satirlar  # noqa: E402
from ajan.ajan import sonucu_coz  # noqa: E402


@pytest.fixture(autouse=True)
def temiz_db():
    kur(os.environ["TEDARIK_DB"])


async def cagir(sunucu, arac, arg=None):
    async with Client(sunucu.sunucu) as c:
        r = await c.call_tool(arac, arg or {})
        return sonucu_coz(r)


@pytest.mark.anyio
async def test_kritik_stoklar_en_acil_once():
    r = await cagir(stok, "kritik_stoklar")
    kodlar = [x["kod"] for x in r]
    assert set(kodlar) == {"MSR", "SYK", "ARP"}
    assert kodlar[0] == "MSR"  # 120/40 = 3 gün


@pytest.mark.anyio
async def test_kara_liste_teklifte_uygun_degil():
    r = await cagir(tedarikci, "teklifleri_karsilastir", {"urun": "MSR", "miktar_ton": 200})
    hizli = [x for x in r if x["tedarikci_id"] == 5][0]
    assert hizli["kara_liste"] and not hizli["uygun"]
    assert r[0]["tedarikci_id"] == 5  # en ucuz o ama uygun değil


@pytest.mark.anyio
@pytest.mark.parametrize("arg,neden", [
    ({"tedarikci_id": 5, "urun": "MSR", "miktar_ton": 100, "birim_fiyat_usd": 199}, "kara listede"),
    ({"tedarikci_id": 2, "urun": "MSR", "miktar_ton": 100, "birim_fiyat_usd": 221}, "minimum miktar"),
    ({"tedarikci_id": 1, "urun": "MSR", "miktar_ton": 100, "birim_fiyat_usd": 150}, "uyuşmuyor"),
    ({"tedarikci_id": 2, "urun": "MSR", "miktar_ton": 900, "birim_fiyat_usd": 221}, "bütçe"),
])
async def test_politika_reddeder(arg, neden):
    r = await cagir(siparis, "siparis_taslagi_olustur", {**arg, "gerekce": "test"})
    assert r["durum"] == "REDDEDILDI"
    assert any(neden in n for n in r["nedenler"])
    assert satirlar("SELECT * FROM siparis") == []


@pytest.mark.anyio
async def test_gecerli_taslak_onay_bekler():
    r = await cagir(siparis, "siparis_taslagi_olustur", {
        "tedarikci_id": 4, "urun": "MSR", "miktar_ton": 200, "birim_fiyat_usd": 229, "gerekce": "kritik"})
    assert r["durum"] == "ONAY_BEKLIYOR"


@pytest.mark.anyio
async def test_onay_kodu_olmadan_kesinlesmez():
    r = await cagir(siparis, "siparis_taslagi_olustur", {
        "tedarikci_id": 4, "urun": "MSR", "miktar_ton": 200, "birim_fiyat_usd": 229, "gerekce": "x"})
    sid = r["siparis_id"]
    sahte = await cagir(siparis, "siparisi_kesinlestir", {"siparis_id": sid, "onay_kodu": "ONAYLANDI"})
    assert sahte["durum"] == "REDDEDILDI"
    with baglan() as db:
        db.execute("INSERT INTO onay_kodu(kod, siparis_id) VALUES('k-123', ?)", (sid,))
    ok = await cagir(siparis, "siparisi_kesinlestir", {"siparis_id": sid, "onay_kodu": "k-123"})
    assert ok["durum"] == "KESIN"
    tekrar = await cagir(siparis, "siparisi_kesinlestir", {"siparis_id": sid, "onay_kodu": "k-123"})
    assert tekrar["durum"] == "REDDEDILDI"  # tek kullanımlık


@pytest.mark.anyio
async def test_her_cagri_denetime_yazilir():
    await cagir(stok, "stok_sorgula", {"urun": "Mısır"})
    assert satirlar("SELECT arac FROM denetim")[-1]["arac"] == "stok_sorgula"


def test_ses_maskeleme():
    m, b = ses.maskele("Beni 0532 111 22 33'ten arayın, mail ali@firma.com")
    assert "0532" not in m and "ali@" not in m and set(b) == {"TELEFON", "EPOSTA"}


def test_belge_ayiklama_uydurmaz():
    from sunucular.belge import ayikla
    r = ayikla('{"urun": "Mısır", "miktar_ton": "24,5 ton"}')
    assert r["miktar_ton"] == 24.5 and r["arac_plaka"] is None
    assert ayikla("okuyamadım")["urun"] is None


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_ses_maskeleme_whisper_bicimleri():
    """Whisper'ın gerçek çıktısında görülen biçim: '0-5-132-11-22-33' (değerlendirmede yakalandı)."""
    for t in ["Beni 0-5-132-11-22-33 numaradan arayın.", "0532.111.22.33", "+90 532 111 22 33"]:
        m, b = ses.maskele(t)
        assert "TELEFON" in b and not any(ch.isdigit() for ch in m.replace("90", "")), m
    assert ses.maskele("200 ton mısır, tarih 12.11.2026")[1] == []
