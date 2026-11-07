# -*- coding: utf-8 -*-
"""
MCP sunucusu: SES. Sesli komutu / telefon kaydını Türkçe yazıya döker.

Model: lokal Whisper (varsayılan whisper-small). Ses bilgisayardan dışarı çıkmaz.
Transkriptteki kişisel veriler (telefon, TC no, IBAN, e-posta) maskelenir: ajan ve
denetim günlüğü sadece maskeli metni görür (KVKK).
"""
import os
import re

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from sunucular.ortak import denetle

ASR_YOL = os.environ.get("ASR_YOL", "openai/whisper-small")
sunucu = MCPServer("ses", instructions="Türkçe ses kaydını yazıya döker (lokal Whisper, KVKK maskeli).")
_M = {}

DESENLER = [
    ("[TCKN]", re.compile(r"\b[1-9]\d{10}\b")),
    ("[IBAN]", re.compile(r"\bTR\d{2}(?:\s?\d{4}){5}\s?\d{2}\b", re.I)),
    ("[EPOSTA]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("[TELEFON]", re.compile(r"(?:\+90|0)?\s?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b")),
]


# Whisper telefon numarasını "0-5-132-11-22-33" / "0532.111.22.33" gibi yazabiliyor (ölçüldü).
# Rakamlar arasındaki boşluk/tire/nokta yok sayılarak 05xx ile başlayan 10-11 haneli diziler yakalanır.
_RAKAM_DIZISI = re.compile(r"(?<![\d])(?:\+?9?0?[\s.\-]?)?5(?:[\s.\-]?\d){9}(?![\d])")


def maskele(metin):
    bulunan = []
    if _RAKAM_DIZISI.search(metin):
        bulunan.append("TELEFON")
        metin = _RAKAM_DIZISI.sub("[TELEFON]", metin)
    for etiket, d in DESENLER:
        if d.search(metin):
            bulunan.append(etiket.strip("[]"))
            metin = d.sub(etiket, metin)
    return metin, bulunan


def _yukle():
    if not _M:
        import torch
        from transformers import pipeline
        cihaz = 0 if torch.cuda.is_available() else -1
        # NOT: GTX 16xx serisinde Whisper fp16 ile BOŞ çıktı veriyor (ölçüldü) -> fp32
        _M["asr"] = pipeline("automatic-speech-recognition", model=ASR_YOL, device=cihaz,
                             dtype=torch.float32)
    return _M["asr"]


def yaziya_dok(ses_yolu: str, dil: str = "turkish") -> str:
    import librosa
    asr = _yukle()
    x, _ = librosa.load(ses_yolu, sr=16000, mono=True)  # ffmpeg gerektirmez
    return asr({"raw": x, "sampling_rate": 16000}, generate_kwargs={"language": dil, "task": "transcribe"},
               return_timestamps=True)["text"].strip()


@sunucu.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False))
def sesi_yaziya_dok(ses_yolu: str) -> dict:
    """Türkçe ses kaydını (wav/mp3) yazıya döker. Kişisel veriler maskelenmiş metin döner.
    Sesli komutlar ve tedarikçi telefon görüşmesi kayıtları için kullanılır."""
    ham = yaziya_dok(ses_yolu)
    maskeli, bulunan = maskele(ham)
    return denetle("ses", "sesi_yaziya_dok", {"ses_yolu": ses_yolu},
                   {"metin": maskeli, "maskelenen": bulunan})


if __name__ == "__main__":
    sunucu.run()
