import re
import json
from functools import lru_cache

def anahtar_kelimeleri_yukle(dosya_yolu="anahtar_kelimeler.json"):
    """
    Anahtar kelime ve kelime gruplarını JSON dosyasından yükler.

    Args:
        dosya_yolu (str): JSON dosyasının yolu.

    Returns:
        tuple: (anahtar_kelimeler, kelime_gruplari)
               Yükleme başarısız olursa (None, None) döndürür.
    """
    try:
        with open(dosya_yolu, 'r', encoding='utf-8') as f:
            veri = json.load(f)
            # Regex'leri önceden derleme
            for kategori, regex_listesi in veri.items():
                if kategori != "Özel Gruplar":
                    # re.IGNORECASE flag'ini derleme sırasında ekle
                    veri[kategori] = [re.compile(r, re.IGNORECASE) for r in regex_listesi]
            return veri, veri.pop("Özel Gruplar", [])
    except Exception as e:
        print(f"Hata: {str(e)}")
        raise

@lru_cache(maxsize=1000)
def tevkifat_kontrol(fatura_metni, detayli_rapor=False):
    """
    Fatura metninde KDV tevkifatı riskini analiz eder.

    Args:
        fatura_metni (str): Kontrol edilecek metin (case-insensitive).
        detayli_rapor (bool): Kategori bazlı detay gösterim seçeneği.

    Returns:
        dict: Kategoriye göre eşleşen kelimeler ve risk skoru veya False.
               Eğer detaylı rapor istenmiyorsa ve risk varsa True, yoksa False döndürür.
    """
    anahtar_kelimeler, kelime_gruplari = anahtar_kelimeleri_yukle()

    if anahtar_kelimeler is None or kelime_gruplari is None:
        return False

    fatura_metni = fatura_metni.lower()
    sonuc = {"risk_skoru": 0, "eslesmeler": {}}

    # 1. Kelime Grupları Kontrolü (Tam Eşleşme)
    for grup in kelime_gruplari:
        if re.search(grup, fatura_metni, re.IGNORECASE):
            kategori = "Özel Grup"
            sonuc["eslesmeler"].setdefault(kategori, []).append(grup)
            sonuc["risk_skoru"] += 3  # Kelime grupları için +3 puan

    # 2. Kategori Bazlı Regex Kontrolü
    for kategori, regex_listesi in anahtar_kelimeler.items():
        for regex in regex_listesi:
            # Önceden derlenmiş regex'ler için flags argümanı kullanma
            if regex.search(fatura_metni):  # re.IGNORECASE zaten derleme sırasında eklendi
                sonuc["eslesmeler"].setdefault(kategori, []).append(regex.pattern.strip(r"\b"))
                sonuc["risk_skoru"] += 1  # Anahtar kelimeler için +1 puan

    # Risk seviyesi belirleme
    if sonuc["risk_skoru"] >= 8:
        sonuc["uyari_seviyesi"] = "Çok Yüksek Risk"
    elif sonuc["risk_skoru"] >= 5:
        sonuc["uyari_seviyesi"] = "Yüksek Risk"
    elif sonuc["risk_skoru"] >= 3:
        sonuc["uyari_seviyesi"] = "Orta Risk"
    else:
        sonuc["uyari_seviyesi"] = "Düşük Risk"

    # 3. Sonuç Formatlama
    if not sonuc["eslesmeler"]:
        return False if not detayli_rapor else sonuc
    else:
        return sonuc if detayli_rapor else True

# Örnek Kullanım:
fatura_metinleri = [
    "Şantiyede yapılan inşaat ve tadilat işleri için mühendislik hizmeti ile beton kalıp ve yıkım işleri. Ayrıca bina tadilatı da yapıldı.",
    "XYZ Kırtasiye firmasından alınan kalem, defter ve silgi faturası. Toplam tutar 50 TL",
    "DEF Taşımacılık A.Ş. tarafından gerçekleştirilen personel servis hizmeti faturasıdır.",
    "ABC Ltd. Şti.'ye verilen metal geri dönüşüm hizmetleri.",
    "Özel güvenlik personeli kiralama hizmet bedeli.",
    "Yemek servisi ve organizasyon hizmetleri kapsamında catering hizmeti sunulmuştur."
]

for i, fatura_metni in enumerate(fatura_metinleri):
    print(f"Fatura {i+1}:")
    sonuc = tevkifat_kontrol(fatura_metni, detayli_rapor=True)
    if sonuc:
        print(f"  Risk Skoru: {sonuc['risk_skoru']}")
        print(f"  Uyarı Seviyesi: {sonuc['uyari_seviyesi']}")
        print("  Eşleşmeler:")
        for kategori, eslesenler in sonuc['eslesmeler'].items():
            print(f"    {kategori}: {', '.join(eslesenler)}")
    else:
        print("  KDV Tevkifatı Riski Düşük")
    print("-" * 20)