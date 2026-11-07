# -*- coding: utf-8 -*-
"""
MCP sunucusu: BELGE (görüntü). İrsaliye/teslim fişi fotoğrafını okur, siparişle karşılaştırır.

Model: lokal görüntü-dil modeli (varsayılan SmolVLM-500M-Instruct, GPU'da ~1.5 GB).
Çıkarılan alanlar şemaya göre doğrulanır; okunamayan alan uydurulmaz, null döner.
Siparişle karşılaştırma kural tabanlıdır (model karar vermez, sadece okur).
"""
import json
import os
import re

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from sunucular.ortak import denetle, satirlar

VLM_YOL = os.environ.get("VLM_YOL", "HuggingFaceTB/SmolVLM-500M-Instruct")
MIKTAR_TOLERANS = 0.02  # kantarda %2'ye kadar fark normal kabul edilir

sunucu = MCPServer("belge", instructions="İrsaliye fotoğrafı okuma ve siparişle karşılaştırma.")
_M = {}

ALANLAR = ["irsaliye_no", "tedarikci", "urun", "miktar_ton", "arac_plaka", "tarih"]
# v2: alanların belgede HANGİ ETİKETİN yanında olduğu söyleniyor (v1'de model "alıcı"yı ürün sandı)
SORU = ("This is a Turkish delivery note (Sevk İrsaliyesi). Copy values exactly as written.\n"
        "- irsaliye_no: the code after 'No:' (top right)\n"
        "- tedarikci: the company name after 'Gönderen:' (only the name)\n"
        "- urun: the product written under the column 'Malın cinsi' inside the table\n"
        "- miktar_ton: the number under the column 'Miktar' (number only)\n"
        "- arac_plaka: the value after 'Araç plakası:'\n"
        "- tarih: the date after 'Sevk tarihi:'\n"
        "Ignore 'Alıcı'. Return ONLY JSON with these 6 keys. Use null if unreadable.")

_KATLA = str.maketrans("çğıöşüÇĞİÖŞÜâî", "cgiosuCGIOSUai")


def katla(x):
    """Türkçe karakterleri sadeleştirir: model 'Tahıl'ı 'Tahil' okursa karşılaştırma bozulmasın."""
    return str(x).translate(_KATLA).lower() if x is not None else ""


def _yukle():
    if not _M:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        cihaz = "cuda" if torch.cuda.is_available() else "cpu"
        _M["p"] = AutoProcessor.from_pretrained(VLM_YOL)
        _M["m"] = AutoModelForImageTextToText.from_pretrained(
            VLM_YOL, dtype=torch.float16 if cihaz == "cuda" else torch.float32).to(cihaz).eval()
        _M["c"] = cihaz
    return _M


def vlm_oku(gorsel_yolu: str, soru: str = SORU, max_yeni: int = 160) -> str:
    import torch
    from PIL import Image
    m = _yukle()
    mesaj = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": soru}]}]
    metin = m["p"].apply_chat_template(mesaj, add_generation_prompt=True)
    girdi = m["p"](text=metin, images=[Image.open(gorsel_yolu).convert("RGB")],
                   return_tensors="pt").to(m["c"])
    with torch.no_grad():
        cikti = m["m"].generate(**girdi, max_new_tokens=max_yeni, do_sample=False)
    return m["p"].batch_decode(cikti[:, girdi["input_ids"].shape[1]:], skip_special_tokens=True)[0]


def ayikla(ham: str) -> dict:
    """Model çıktısından JSON al, şemaya zorla. Bozuk/eksik alan -> None (uydurma yok)."""
    m = re.search(r"\{.*\}", ham, re.S)
    try:
        v = json.loads(m.group()) if m else {}
    except json.JSONDecodeError:
        v = {}
    sonuc = {a: v.get(a) for a in ALANLAR}
    for a in ("tedarikci", "tarih", "arac_plaka"):  # "Gönderen: X" gibi etiket kopyalarını temizle
        if isinstance(sonuc[a], str) and ":" in sonuc[a]:
            sonuc[a] = sonuc[a].split(":", 1)[1].strip() or None
    try:
        sonuc["miktar_ton"] = float(str(sonuc["miktar_ton"]).replace(",", ".").split()[0]) \
            if sonuc["miktar_ton"] is not None else None
    except ValueError:
        sonuc["miktar_ton"] = None
    return sonuc


# v3: her alan için ayrı, kısa soru. Küçük VLM tek seferde 6 alanlı JSON üretirken şema
# uydurdu (v2); tek soruya tek değer cevabında çok daha tutarlı.
ALAN_SORULARI = {
    "irsaliye_no": "What is the document number written after 'No:'? Answer with the code only.",
    "tedarikci": "What company name is written after 'Gönderen:'? Answer with the name only.",
    # v4'te soruya "ör. Mısır" örneği konmuştu: model görüntüyü okumak yerine ÖRNEĞİ KOPYALADI
    # (Soya küspesine "Mısır" dedi). v5: örnek yok; başlık/boş gelirse tablo okuma yedeği devreye girer.
    "urun": "In the table, the first column lists the goods. What product name is written in the row below the header? Answer with the product name only.",
    "miktar_ton": "In the table, what quantity is written under 'Miktar'? Answer with the number only.",
    "arac_plaka": "What is written after 'Araç plakası:'? Answer with the plate only.",
    "tarih": "What date is written after 'Sevk tarihi:'? Answer with the date only.",
}


def alan_alan_oku(gorsel_yolu: str) -> dict:
    ham = {a: vlm_oku(gorsel_yolu, s, max_yeni=24).strip() for a, s in ALAN_SORULARI.items()}
    sonuc = {}
    for a, v in ham.items():
        v = v.strip(" .\"'").split("\n")[0]
        if ":" in v:
            v = v.split(":", 1)[1].strip()
        sonuc[a] = v or None
    try:
        sayi = re.search(r"\d[\d.,]*", sonuc["miktar_ton"] or "")
        sonuc["miktar_ton"] = float(sayi.group().replace(".", "").replace(",", ".")
                                    if "," in sayi.group() else sayi.group()) if sayi else None
    except ValueError:
        sonuc["miktar_ton"] = None
    # v5: ürün sorusuna başlık kelimesi ("Miktar", "Malın cinsi") ya da boş cevap gelirse modele
    # tabloyu satır satır OKUTUP ürünü kodda ayıkla: model sadece okur, ayrıştırmayı kural yapar.
    if not sonuc["urun"] or katla(sonuc["urun"]).strip() in BASLIKLAR:
        sonuc["urun"] = tablodan_urun(vlm_oku(gorsel_yolu, TABLO_SORU, max_yeni=60))
    return sonuc


BASLIKLAR = {"miktar", "malin cinsi", "urun", "null", "none"}
TABLO_SORU = "Copy the text inside the table box exactly, one table row per line."


def tablodan_urun(metin: str):
    """'Mısır 200,0 ton' gibi bir satırdan ürün adını çıkarır; başlık satırını atlar."""
    for satir in metin.splitlines():
        m = re.match(r"\s*([^\d|]+?)\s*[|:]?\s*\d[\d.,]*\s*ton", satir, re.I)
        if m and katla(m.group(1)).strip() not in BASLIKLAR:
            return m.group(1).strip(" |:-")
    return None


def oku(gorsel_yolu: str) -> dict:
    return alan_alan_oku(gorsel_yolu) if os.environ.get("BELGE_MOD", "alan") == "alan" \
        else ayikla(vlm_oku(gorsel_yolu))


@sunucu.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False))
def irsaliye_oku(gorsel_yolu: str) -> dict:
    """İrsaliye/teslim fişi fotoğrafından alanları okur: irsaliye_no, tedarikci, urun,
    miktar_ton, arac_plaka, tarih. Okunamayan alanlar null döner."""
    sonuc = oku(gorsel_yolu)
    return denetle("belge", "irsaliye_oku", {"gorsel_yolu": gorsel_yolu}, sonuc)


@sunucu.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False))
def irsaliye_siparis_karsilastir(gorsel_yolu: str, siparis_id: int) -> dict:
    """İrsaliyeyi okur ve kesinleşmiş siparişle karşılaştırır: ürün aynı mı, miktar
    toleransta mı (%2), tedarikçi aynı mı. Uyuşmazlık varsa mal kabulü insan kontrolüne düşer."""
    oku = globals()["oku"](gorsel_yolu)
    s = satirlar("""SELECT s.*, t.ad tedarikci_ad, u.ad urun_ad FROM siparis s
                    JOIN tedarikci t ON t.id=s.tedarikci_id JOIN urun u ON u.kod=s.urun
                    WHERE s.id=?""", siparis_id)
    if not s:
        return denetle("belge", "irsaliye_siparis_karsilastir", {"siparis_id": siparis_id},
                       {"hata": "sipariş yok"})
    s = s[0]
    sorunlar = []
    if oku["urun"] is None or katla(s["urun_ad"]) not in katla(oku["urun"]):
        sorunlar.append(f"ürün uyuşmuyor/okunamadı (sipariş: {s['urun_ad']}, irsaliye: {oku['urun']})")
    if oku["miktar_ton"] is None:
        sorunlar.append("miktar okunamadı")
    elif abs(oku["miktar_ton"] - s["miktar"]) > s["miktar"] * MIKTAR_TOLERANS:
        sorunlar.append(f"miktar farkı: sipariş {s['miktar']} t, irsaliye {oku['miktar_ton']} t")
    ilk_kelime = katla(s["tedarikci_ad"].split()[0])
    if oku["tedarikci"] is None or ilk_kelime not in katla(oku["tedarikci"]):
        sorunlar.append(f"tedarikçi uyuşmuyor/okunamadı (irsaliye: {oku['tedarikci']})")
    sonuc = {"irsaliye": oku, "siparis_id": siparis_id,
             "karar": "MAL_KABUL_UYGUN" if not sorunlar else "INSAN_KONTROLU", "sorunlar": sorunlar}
    return denetle("belge", "irsaliye_siparis_karsilastir",
                   {"gorsel_yolu": gorsel_yolu, "siparis_id": siparis_id}, sonuc)


if __name__ == "__main__":
    sunucu.run()
