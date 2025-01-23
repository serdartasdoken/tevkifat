import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from pathlib import Path
import logging
import traceback
import re
from functools import lru_cache
import unicodedata
from typing import Dict, Any, Optional, Union, List

# View fonksiyonlarını import et
from views import musteri_ekle_view, musteri_sil_view, veri_yukle_view, analiz_yap_view

# Logging ayarları
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='debug.log',
    filemode='a'
)

class FileHandler:
    """Dosya işlemleri için yardımcı sınıf"""
    
    @staticmethod
    def read_excel_file(file) -> Optional[pd.DataFrame]:
        """Excel dosyalarını oku (XLS, XLSX)"""
        try:
            # Dosyayı başa sar
            file.seek(0)
            file_content = file.read()
            file.seek(0)
            
            if file.name.endswith('.xls'):
                # XLS dosyaları için xlrd kullan
                import xlrd
                book = xlrd.open_workbook(file_contents=file_content)
                sheet = book.sheet_by_index(0)
                data = []
                headers = [str(cell.value) for cell in sheet.row(0)]
                
                for row_idx in range(1, sheet.nrows):
                    row_data = {}
                    for col_idx, header in enumerate(headers):
                        cell = sheet.cell(row_idx, col_idx)
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            value = xlrd.xldate.xldate_as_datetime(cell.value, book.datemode)
                        else:
                            value = cell.value
                        row_data[header] = value
                    data.append(row_data)
                
                return pd.DataFrame(data)
            elif file.name.endswith('.xlsx'):
                # XLSX dosyaları için pandas kullan
                return pd.read_excel(file)
            else:
                # XLSX dosyaları için openpyxl kullan
                import tempfile
                import os
                
                # Geçici dosya oluştur
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                    temp_file.write(file_content)
                    temp_path = temp_file.name
                
                try:
                    df = pd.read_excel(temp_path, engine='openpyxl')
                    return df
                except Exception as e:
                    logging.error(f"Excel okuma hatası: {str(e)}")
                    raise ValueError(f"Excel dosyası okunamadı: {str(e)}")
                finally:
                    # Geçici dosyayı temizle
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                        
        except Exception as e:
            logging.error(f"Excel okuma hatası: {str(e)}")
            raise ValueError(f"Excel dosyası okunamadı: {str(e)}")

    @staticmethod
    def save_excel_file(df: pd.DataFrame, output_path: str) -> None:
        """Excel dosyasını kaydet"""
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, index=False, sheet_name='Veri')
                worksheet = writer.sheets['Veri']
                
                # Sütun genişliklerini ayarla
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    ) + 2
                    col_letter = ''
                    temp = idx
                    while temp >= 0:
                        col_letter = chr(65 + (temp % 26)) + col_letter
                        temp = (temp // 26) - 1
                    worksheet.column_dimensions[col_letter].width = min(max_length, 50)
        except Exception as e:
            logging.error(f"Excel kaydetme hatası: {str(e)}")
            raise ValueError(f"Excel dosyası kaydedilemedi: {str(e)}")

    @staticmethod
    def read_csv_file(file) -> pd.DataFrame:
        """CSV dosyalarını oku"""
        try:
            # Dosyayı başa sar
            file.seek(0)
            return pd.read_csv(file)
        except Exception as e:
            logging.error(f"CSV okuma hatası: {str(e)}")
            raise ValueError(f"CSV dosyası okunamadı: {str(e)}")

class DataProcessor:
    """Veri işleme ve analiz sınıfı"""
    
    @staticmethod
    @lru_cache(maxsize=1000)
    def tevkifat_kontrol(fatura_metni: str, detayli_rapor: bool = False) -> Union[bool, Dict[str, Any]]:
        """Tevkifat riski analizi"""
        try:
            with open("anahtar_kelimeler.json", 'r', encoding='utf-8') as f:
                anahtar_kelimeler = json.load(f)
                kelime_gruplari = anahtar_kelimeler.pop("Özel Gruplar", [])
                for kategori, regex_listesi in anahtar_kelimeler.items():
                    anahtar_kelimeler[kategori] = [re.compile(r, re.IGNORECASE) for r in regex_listesi]
        except Exception as e:
            logging.error(f"Anahtar kelimeler yükleme hatası: {str(e)}")
            return False

        fatura_metni = str(fatura_metni).lower()
        sonuc = {"risk_skoru": 0, "eslesmeler": {}}

        # Kelime grupları kontrolü
        for grup in kelime_gruplari:
            if re.search(grup, fatura_metni, re.IGNORECASE):
                sonuc["eslesmeler"].setdefault("Özel Grup", []).append(grup)
                sonuc["risk_skoru"] += 3

        # Kategori bazlı kontrol
        for kategori, regex_listesi in anahtar_kelimeler.items():
            for regex in regex_listesi:
                if regex.search(fatura_metni):
                    sonuc["eslesmeler"].setdefault(kategori, []).append(regex.pattern.strip(r"\b"))
                    sonuc["risk_skoru"] += 1

        # Risk seviyesi belirleme
        risk_seviyeleri = {
            8: "Çok Yüksek Risk",
            5: "Yüksek Risk",
            3: "Orta Risk",
            0: "Düşük Risk"
        }
        
        sonuc["uyari_seviyesi"] = next(
            (seviye for esik, seviye in sorted(risk_seviyeleri.items(), reverse=True)
             if sonuc["risk_skoru"] >= esik),
            "Düşük Risk"
        )

        return sonuc if detayli_rapor else bool(sonuc["eslesmeler"])

class ConfigManager:
    """Konfigürasyon yönetimi sınıfı"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_folders()

    def load_config(self) -> Dict[str, Any]:
        """Konfigürasyon dosyasını yükle"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"musteriler": {}, "column_mappings": {}}
        except Exception as e:
            logging.error(f"Konfig yükleme hatası: {str(e)}")
            return {"musteriler": {}, "column_mappings": {}}

    def save_config(self) -> None:
        """Konfigürasyonu kaydet"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Konfig kaydetme hatası: {str(e)}")
            raise

    def setup_folders(self) -> None:
        """Gerekli klasörleri oluştur"""
        Path("data").mkdir(exist_ok=True)
        for musteri_id in self.config["musteriler"]:
            Path(f"data/{musteri_id}").mkdir(exist_ok=True)

class TevkifatAnalyzer:
    """Ana analiz sınıfı"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.file_handler = FileHandler()
        self.data_processor = DataProcessor()

    def musteri_ekle(self, musteri_adi: str) -> Optional[str]:
        """Yeni müşteri ekle"""
        try:
            musteri_id = str(len(self.config_manager.config["musteriler"]) + 1)
            self.config_manager.config["musteriler"][musteri_id] = {
                "ad": musteri_adi,
                "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d")
            }
            Path(f"data/{musteri_id}").mkdir(exist_ok=True)
            self.config_manager.save_config()
            return musteri_id
        except Exception as e:
            logging.error(f"Müşteri ekleme hatası: {str(e)}")
            return None

    def musteri_sil(self, musteri_id: str) -> bool:
        """Müşteri sil"""
        try:
            del self.config_manager.config["musteriler"][musteri_id]
            if musteri_id in self.config_manager.config["column_mappings"]:
                del self.config_manager.config["column_mappings"][musteri_id]
            self.config_manager.save_config()
            return True
        except Exception as e:
            logging.error(f"Müşteri silme hatası: {str(e)}")
            return False

    def veri_yukle(self, musteri_id: str, file, mapping: Dict[str, str]) -> Optional[pd.DataFrame]:
        """Veri yükleme ve analiz"""
        try:
            # Dosya okuma
            if file.name.endswith(('.xlsx', '.xls')):
                df = self.file_handler.read_excel_file(file)
            else:
                df = self.file_handler.read_csv_file(file)

            # Mapping kontrol
            empty_mappings = [col for col, mapped in mapping.items() if not mapped]
            if empty_mappings:
                raise ValueError(f"Lütfen şu sütunları eşleştirin: {', '.join(empty_mappings)}")

            # Mapping uygula
            reverse_mapping = {v: k for k, v in mapping.items()}
            df = df.rename(columns=reverse_mapping)

            # Gerekli sütunları kontrol et
            required_columns = ['tarih', 'aciklama', 'tutar']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Eksik sütunlar: {', '.join(missing_columns)}")

            # Veri temizleme ve dönüştürme
            df = self._clean_data(df)
            
            # Tevkifat analizi
            df['tevkifat_riski'] = df['aciklama'].apply(self.data_processor.tevkifat_kontrol)
            df['detayli_analiz'] = df['aciklama'].apply(
                lambda x: self.data_processor.tevkifat_kontrol(x, detayli_rapor=True)
            )

            # Dosyayı kaydet
            output_path = f"data/{musteri_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
            if not output_path.endswith('.xlsx'):
                output_path = output_path + '.xlsx'
                
            self.file_handler.save_excel_file(df, output_path)
            
            # Mapping'i kaydet
            self.config_manager.config["column_mappings"][musteri_id] = mapping
            self.config_manager.save_config()
            
            return df

        except Exception as e:
            logging.error(f"Veri yükleme hatası: {str(e)}\n{traceback.format_exc()}")
            raise

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Veri temizleme ve dönüştürme"""
        try:
            # Tarih sütununu düzenle
            df['tarih'] = pd.to_datetime(df['tarih'], format='mixed')
            
            # Tutar sütununu düzenle
            df['tutar'] = pd.to_numeric(
                df['tutar'].astype(str).str.replace(',', '.'),
                errors='coerce'
            )
            
            # Metin sütunlarını temizle
            df['aciklama'] = df['aciklama'].astype(str).apply(
                lambda x: unicodedata.normalize('NFKD', x).encode('ASCII', 'ignore').decode()
            )
            
            return df
        except Exception as e:
            logging.error(f"Veri temizleme hatası: {str(e)}")
            raise ValueError(f"Veri temizleme hatası: {str(e)}")

    def analiz_yap(self, musteri_id: str, baslangic_tarih: datetime, bitis_tarih: datetime) -> Optional[pd.DataFrame]:
        """Tevkifat analizi yap"""
        try:
            musteri_klasoru = f"data/{musteri_id}"
            if not os.path.exists(musteri_klasoru):
                raise ValueError("Müşteri klasörü bulunamadı!")
            
            # En son yüklenen dosyayı bul
            dosyalar = sorted([f for f in os.listdir(musteri_klasoru) if f.endswith(('.xlsx', '.csv'))])
            if not dosyalar:
                raise ValueError("Henüz veri yüklenmemiş!")
            
            son_dosya = os.path.join(musteri_klasoru, dosyalar[-1])
            
            # Excel engine'i belirterek dosyayı oku
            if son_dosya.endswith('.xlsx'):
                df = pd.read_excel(son_dosya, engine='openpyxl')
            else:
                df = pd.read_csv(son_dosya)
            
            # Analiz için gerekli sütunları geçici olarak yeniden adlandır
            temp_df = df.copy()
            column_mapping = {}
            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ['tarih', 'date']:
                    column_mapping[col] = 'tarih'
                elif col_lower in ['aciklama', 'açıklama', 'description']:
                    column_mapping[col] = 'aciklama'
                elif col_lower in ['tutar', 'amount']:
                    column_mapping[col] = 'tutar'
                elif col_lower in ['satıcı ünvanı', 'satici unvani', 'satıcı unvanı', 'satici ünvanı', 'tedarikçi', 'tedarikci']:
                    column_mapping[col] = 'satici_unvani'
                elif col_lower in ['fatura no', 'fatura numarası', 'invoice no', 'belge no']:
                    column_mapping[col] = 'fatura_no'
            
            if column_mapping:
                temp_df = temp_df.rename(columns=column_mapping)
            
            # Tarih filtreleme
            temp_df['tarih'] = pd.to_datetime(temp_df['tarih'])
            mask = (temp_df['tarih'].dt.date >= baslangic_tarih.date()) & (temp_df['tarih'].dt.date <= bitis_tarih.date())
            
            # Orijinal DataFrame'i filtrele
            filtered_df = df[mask].copy()
            if filtered_df.empty:
                return None
            
            # Tevkifat analizi için gerekli sütunu kullan
            aciklama_col = next(col for col, mapped in column_mapping.items() if mapped == 'aciklama')
            
            # Önce tevkifat_riski sütununu ekle
            filtered_df['tevkifat_riski'] = filtered_df[aciklama_col].apply(
                lambda x: bool(self.data_processor.tevkifat_kontrol(x, detayli_rapor=True))
            )
            
            # Detaylı analiz sonuçlarını ekle
            analiz_sonuclari = filtered_df[aciklama_col].apply(
                lambda x: self.data_processor.tevkifat_kontrol(x, detayli_rapor=True)
            )
            
            # Analiz sonuçlarını ayrı sütunlara ekle
            def extract_risk_info(x):
                if isinstance(x, dict):
                    return pd.Series({
                        'Risk Seviyesi': x.get('uyari_seviyesi', ''),
                        'Risk Skoru': x.get('risk_skoru', 0),
                        'Eşleşen Kategoriler': ', '.join(x.get('eslesmeler', {}).keys())
                    })
                return pd.Series({'Risk Seviyesi': '', 'Risk Skoru': 0, 'Eşleşen Kategoriler': ''})
            
            # Analiz sonuçlarını ekle
            risk_info = analiz_sonuclari.apply(extract_risk_info)
            filtered_df = pd.concat([filtered_df, risk_info], axis=1)
            
            return filtered_df
            
        except Exception as e:
            logging.error(f"Analiz hatası: {str(e)}\n{traceback.format_exc()}")
            raise

def main():
    st.set_page_config(page_title="Tevkifat Analiz Sistemi", layout="wide")
    st.title("Tevkifat Analiz Sistemi")
    
    analyzer = TevkifatAnalyzer()
    
    # Debug modu
    with st.sidebar:
        if st.checkbox("Debug Modu"):
            if os.path.exists('debug.log'):
                with open('debug.log', 'r') as f:
                    st.text_area("Debug Log", f.read(), height=300)
    
    # Ana menü
    menu_items = ["Müşteri Ekle", "Müşteri Sil", "Veri Yükle", "Analiz Yap"]
    islem = st.sidebar.radio("İşlem Seçin:", menu_items)
    
    # İşlem yönlendirme
    menu_functions = {
        "Müşteri Ekle": musteri_ekle_view,
        "Müşteri Sil": musteri_sil_view,
        "Veri Yükle": veri_yukle_view,
        "Analiz Yap": analiz_yap_view
    }
    
    menu_functions[islem](analyzer)

if __name__ == "__main__":
    main()
