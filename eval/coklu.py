# -*- coding: utf-8 -*-
"""
Çok modlu değerlendirme (GPU gerekir).

GÖRÜNTÜ: 12 sentetik irsaliye
  - alan doğruluğu: irsaliye_no, tedarikci, urun, miktar_ton, arac_plaka, tarih
  - mal kabul kararı: irsaliye siparişle karşılaştırılır; beklenen karar doğru cevaplardan
    (ground truth) hesaplanır, model okumasıyla verilen kararla kıyaslanır.
    KRİTİK HATA = sorunlu teslimata "MAL_KABUL_UYGUN" denmesi.
SES: 10 Türkçe komut (sentetik ses) + aynı kayıtların gürültülü hâli
  - WER (kelime hata oranı), maskeleme (telefon numarası transkriptte kaldı mı)

Kullanım: python -m eval.coklu
"""
import json
import os
import re
import sys
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

from sunucular import belge, ses  # noqa: E402

IRS = os.path.join(KOK, "veri", "irsaliyeler")
SES = os.path.join(KOK, "veri", "sesler")

# Her irsaliyenin karşılaştırılacağı sipariş (tedarikçi adı, ürün adı, miktar)
SIPARIS = {
    "irsaliye_01.png": ("Delta Emtia SRL", "Mısır", 200), "irsaliye_02.png": ("Delta Emtia SRL", "Mısır", 200),
    "irsaliye_03.png": ("Alfa Tahıl A.Ş.", "Buğday", 100), "irsaliye_04.png": ("Gama Agro S.A.", "Soya küspesi", 250),
    "irsaliye_05.png": ("Gama Agro S.A.", "Soya küspesi", 250), "irsaliye_06.png": ("Beta Grain Ltd.", "Ayçiçek yağı", 30),
    "irsaliye_07.png": ("Delta Emtia SRL", "Arpa", 150), "irsaliye_08.png": ("Delta Emtia SRL", "Arpa", 150),
    "irsaliye_09.png": ("Alfa Tahıl A.Ş.", "Mısır", 50), "irsaliye_10.png": ("Delta Emtia SRL", "Mısır", 200),
    "irsaliye_11.png": ("Beta Grain Ltd.", "Buğday", 520), "irsaliye_12.png": ("Alfa Tahıl A.Ş.", "Arpa", 30),
}


def _norm(x):
    """Karşılaştırma için: Türkçe karakter katlanır, boşluk/noktalama atılır."""
    return re.sub(r"[^0-9a-z]", "", belge.katla(x)) if x is not None else ""


def karar(oku, sip):
    ted, urun, miktar = sip
    sorun = []
    if oku.get("urun") is None or belge.katla(urun) not in belge.katla(oku["urun"]):
        sorun.append("ürün")
    if oku.get("miktar_ton") is None or abs(oku["miktar_ton"] - miktar) > miktar * belge.MIKTAR_TOLERANS:
        sorun.append("miktar")
    if oku.get("tedarikci") is None or belge.katla(ted.split()[0]) not in belge.katla(oku["tedarikci"]):
        sorun.append("tedarikçi")
    return "MAL_KABUL_UYGUN" if not sorun else "INSAN_KONTROLU"


def goruntu():
    with open(os.path.join(IRS, "cevaplar.json"), encoding="utf-8") as f:
        gt = json.load(f)
    alan_dogru = {a: 0 for a in belge.ALANLAR}
    kararlar, kritik, detay = 0, 0, []
    t0 = time.time()
    for ad, dogru in gt.items():
        oku = belge.oku(os.path.join(IRS, ad))
        ham = ""
        for a in belge.ALANLAR:
            if a == "miktar_ton":
                alan_dogru[a] += oku[a] is not None and abs(oku[a] - dogru[a]) < 0.05
            else:
                alan_dogru[a] += _norm(oku[a]) == _norm(dogru[a])
        beklenen, verilen = karar(dogru, SIPARIS[ad]), karar(oku, SIPARIS[ad])
        kararlar += beklenen == verilen
        kritik += beklenen == "INSAN_KONTROLU" and verilen == "MAL_KABUL_UYGUN"
        detay.append({"dosya": ad, "okunan": oku, "beklenen_karar": beklenen, "verilen_karar": verilen,
                      "ham": ham[:300]})
        print(ad, beklenen, verilen, oku, flush=True)
    n = len(gt)
    return {"model": os.path.basename(belge.VLM_YOL), "mod": os.environ.get("BELGE_MOD", "alan"), "n": n,
            "alan_dogrulugu": {a: round(v / n, 3) for a, v in alan_dogru.items()},
            "karar_dogrulugu": round(kararlar / n, 3), "kritik_hata": kritik,
            "ort_sure_sn": round((time.time() - t0) / n, 1), "detay": detay}


def wer(ref, hyp):
    r, h = ref.lower().split(), hyp.lower().split()
    r = [_norm(x) for x in r if _norm(x)]
    h = [_norm(x) for x in h if _norm(x)]
    d = [[i + j if i * j == 0 else 0 for j in range(len(h) + 1)] for i in range(len(r) + 1)]
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r)][len(h)] / max(len(r), 1)


def _gurultu_ekle(yol, cikti, snr_db=10):
    import numpy as np
    import soundfile as sf
    x, sr = sf.read(yol)
    guc = np.mean(x ** 2)
    g = np.random.default_rng(0).normal(0, np.sqrt(guc / 10 ** (snr_db / 10)), x.shape)
    sf.write(cikti, x + g, sr)
    return cikti


def ses_degerlendir():
    with open(os.path.join(KOK, "veri", "ses_cumleler.txt"), encoding="utf-8") as f:
        refs = [s.strip() for s in f if s.strip()]
    sonuc = {}
    for kosul in ("temiz", "gurultulu_10dB"):
        werler, detay = [], []
        for i, ref in enumerate(refs, 1):
            yol = os.path.join(SES, f"komut_{i:02d}.wav")
            if kosul != "temiz":
                yol = _gurultu_ekle(yol, os.path.join(SES, f"_gurultulu_{i:02d}.wav"))
            hyp = ses.yaziya_dok(yol)
            werler.append(wer(ref, hyp))
            maskeli, bulunan = ses.maskele(hyp)
            detay.append({"ref": ref, "hyp": hyp, "wer": round(werler[-1], 3), "maskeli": maskeli,
                          "maskelenen": bulunan})
            print(kosul, round(werler[-1], 2), "|", hyp, flush=True)
        sonuc[kosul] = {"ort_wer": round(sum(werler) / len(werler), 3), "detay": detay}
    sonuc["model"] = os.path.basename(ses.ASR_YOL)
    return sonuc


if __name__ == "__main__":
    out = {"goruntu": goruntu(), "ses": ses_degerlendir() if "--sadece-goruntu" not in sys.argv else {}, "tarih": time.strftime("%Y-%m-%d %H:%M")}
    os.makedirs(os.path.join(KOK, "eval", "sonuclar"), exist_ok=True)
    with open(os.path.join(KOK, "eval", "sonuclar", "coklu_modlu.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    g, s = out["goruntu"], out["ses"]
    print(json.dumps({"alan": g["alan_dogrulugu"], "karar": g["karar_dogrulugu"], "kritik": g["kritik_hata"],
                      "wer_temiz": s.get("temiz", {}).get("ort_wer"),
                      "wer_gurultulu": s.get("gurultulu_10dB", {}).get("ort_wer")}, ensure_ascii=False))
