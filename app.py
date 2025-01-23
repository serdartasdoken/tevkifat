import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from pathlib import Path
from tevkifat import tevkifat_kontrol
import logging
import traceback

# Logging ayarları
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='debug.log',
    filemode='a'
)

class TevkifatApp:
    def __init__(self):
        self.config_file = "config.json"
        self.load_config()
        self.setup_folders()
        
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "musteriler": {},
                    "column_mappings": {}
                }
                self.save_config()
        except Exception as e:
            logging.error(f"Konfig yükleme hatası: {str(e)}")
            st.error(f"Konfig yükleme hatası: {str(e)}")
            self.config = {"musteriler": {}, "column_mappings": {}}

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Konfig kaydetme hatası: {str(e)}")
            st.error(f"Konfig kaydetme hatası: {str(e)}")

    def setup_folders(self):
        Path("data").mkdir(exist_ok=True)
        for musteri_id in self.config["musteriler"]:
            Path(f"data/{musteri_id}").mkdir(exist_ok=True)

    def musteri_ekle(self, musteri_adi):
        try:
            musteri_id = str(len(self.config["musteriler"]) + 1)
            self.config["musteriler"][musteri_id] = {
                "ad": musteri_adi,
                "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d")
            }
            Path(f"data/{musteri_id}").mkdir(exist_ok=True)
            self.save_config()
            return musteri_id
        except Exception as e:
            logging.error(f"Müşteri ekleme hatası: {str(e)}")
            st.error(f"Müşteri ekleme hatası: {str(e)}")
            return None

    def musteri_sil(self, musteri_id):
        try:
            del self.config["musteriler"][musteri_id]
            if musteri_id in self.config["column_mappings"]:
                del self.config["column_mappings"][musteri_id]
            self.save_config()
            return True
        except Exception as e:
            logging.error(f"Müşteri silme hatası: {str(e)}")
            st.error(f"Müşteri silme hatası: {str(e)}")
            return False

    def veri_yukle(self, musteri_id, file, mapping):
        try:
            # Dosya okuma
            if file.name.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)

            # Boş mapping değerlerini kontrol et
            empty_mappings = [col for col, mapped in mapping.items() if not mapped]
            if empty_mappings:
                raise ValueError(f"Lütfen şu sütunları eşleştirin: {', '.join(empty_mappings)}")

            # Mapping'i ters çevir (hedef_sutun: kaynak_sutun şeklinde)
            reverse_mapping = {v: k for k, v in mapping.items()}
            
            # Mapping uygula
            df = df.rename(columns=reverse_mapping)

            # Gerekli sütunları kontrol et
            required_columns = ['tarih', 'aciklama', 'tutar']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Eksik sütunlar: {', '.join(missing_columns)}")

            # Tarih sütununu düzenle
            try:
                df['tarih'] = pd.to_datetime(df['tarih'])
            except Exception as e:
                raise ValueError("Tarih sütunu uygun formatta değil. Lütfen tarih formatını kontrol edin.")

            # Tutar sütununu sayısal formata çevir
            try:
                df['tutar'] = pd.to_numeric(df['tutar'].astype(str).str.replace(',', '.'), errors='coerce')
            except Exception as e:
                raise ValueError("Tutar sütunu sayısal formata çevrilemedi. Lütfen tutar formatını kontrol edin.")

            # Dosyayı kaydet
            output_path = f"data/{musteri_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
            df.to_excel(output_path, index=False)
            
            return df
        except Exception as e:
            logging.error(f"Veri yükleme hatası: {str(e)}\n{traceback.format_exc()}")
            st.error(f"Veri yükleme hatası: {str(e)}")
            return None

def main():
    st.set_page_config(page_title="Tevkifat Analiz Sistemi", layout="wide")
    st.title("Tevkifat Analiz Sistemi")
    
    app = TevkifatApp()
    
    # Debug modu
    with st.sidebar:
        if st.checkbox("Debug Modu"):
            if os.path.exists('debug.log'):
                with open('debug.log', 'r') as f:
                    st.text_area("Debug Log", f.read(), height=300)
    
    # Ana menü
    islem = st.sidebar.radio("İşlem Seçin:", 
                            ["Müşteri Ekle", "Müşteri Sil", "Veri Yükle", "Analiz Yap"])
    
    if islem == "Müşteri Ekle":
        st.subheader("Yeni Müşteri Ekle")
        musteri_adi = st.text_input("Müşteri Adı:")
        if st.button("Ekle") and musteri_adi:
            musteri_id = app.musteri_ekle(musteri_adi)
            if musteri_id:
                st.success(f"Müşteri başarıyla eklendi. ID: {musteri_id}")
    
    elif islem == "Müşteri Sil":
        st.subheader("Müşteri Sil")
        musteriler = app.config["musteriler"]
        if musteriler:
            secilen_musteri = st.selectbox(
                "Müşteri Seçin:",
                options=list(musteriler.keys()),
                format_func=lambda x: f"{x} - {musteriler[x]['ad']}"
            )
            if st.button("Sil"):
                if app.musteri_sil(secilen_musteri):
                    st.success("Müşteri başarıyla silindi!")
        else:
            st.info("Henüz müşteri eklenmemiş.")
    
    elif islem == "Veri Yükle":
        st.subheader("Veri Yükleme")
        musteriler = app.config["musteriler"]
        if musteriler:
            secilen_musteri = st.selectbox(
                "Müşteri Seçin:",
                options=list(musteriler.keys()),
                format_func=lambda x: f"{x} - {musteriler[x]['ad']}"
            )
            
            uploaded_file = st.file_uploader("Excel/CSV Dosyası Seçin", 
                                           type=['xlsx', 'csv'])
            
            if uploaded_file:
                try:
                    df_preview = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
                    st.write("Önizleme:", df_preview.head())
                    
                    # Sütun eşleştirme
                    st.subheader("Sütun Eşleştirme")
                    st.info("""
                    Lütfen aşağıdaki sütunları eşleştirin:
                    - tarih: Fatura tarihi sütunu
                    - aciklama: Fatura açıklaması/detayı sütunu
                    - tutar: Fatura tutarı sütunu
                    """)
                    
                    mapping = {}
                    required_columns = ['tarih', 'aciklama', 'tutar']
                    
                    # Kayıtlı mapping'i kontrol et
                    saved_mapping = app.config.get("column_mappings", {}).get(secilen_musteri, {})
                    
                    for req_col in required_columns:
                        default_value = saved_mapping.get(req_col, "")
                        col_options = [""] + list(df_preview.columns)
                        default_index = 0 if not default_value else col_options.index(default_value)
                        
                        mapping[req_col] = st.selectbox(
                            f"{req_col} sütununu seçin:",
                            options=col_options,
                            index=default_index,
                            help=f"Lütfen {req_col} için uygun sütunu seçin"
                        )
                    
                    # Tüm sütunlar seçili mi kontrolü
                    all_columns_selected = all(mapping.values())
                    
                    if not all_columns_selected:
                        st.warning("Lütfen tüm gerekli sütunları eşleştirin!")
                    
                    if st.button("Yükle", disabled=not all_columns_selected):
                        # Mapping'i kaydet
                        app.config["column_mappings"][secilen_musteri] = mapping
                        app.save_config()
                        
                        # Veriyi yükle
                        df = app.veri_yukle(secilen_musteri, uploaded_file, mapping)
                        if df is not None:
                            st.success("Veri başarıyla yüklendi!")
                            st.write("Yüklenen veri önizlemesi:", df.head())
                            
                except Exception as e:
                    logging.error(f"Veri yükleme hatası: {str(e)}\n{traceback.format_exc()}")
                    st.error(f"Veri yükleme hatası: {str(e)}")
        else:
            st.info("Henüz müşteri eklenmemiş.")
    
    elif islem == "Analiz Yap":
        st.subheader("Tevkifat Analizi")
        musteriler = app.config["musteriler"]
        if musteriler:
            secilen_musteri = st.selectbox(
                "Müşteri Seçin:",
                options=list(musteriler.keys()),
                format_func=lambda x: f"{x} - {musteriler[x]['ad']}"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                baslangic_tarih = st.date_input("Başlangıç Tarihi")
            with col2:
                bitis_tarih = st.date_input("Bitiş Tarihi")
            
            if st.button("Analiz Et"):
                try:
                    with st.spinner('Analiz yapılıyor...'):
                        musteri_klasoru = f"data/{secilen_musteri}"
                        tum_veriler = pd.DataFrame()
                        
                        # Tüm dosyaları oku ve birleştir
                        for dosya in os.listdir(musteri_klasoru):
                            if dosya.endswith(('.xlsx', '.csv')):
                                df = pd.read_excel(f"{musteri_klasoru}/{dosya}")
                                tum_veriler = pd.concat([tum_veriler, df])
                        
                        if not tum_veriler.empty:
                            # Tarih filtreleme
                            tum_veriler['tarih'] = pd.to_datetime(tum_veriler['tarih'])
                            mask = (tum_veriler['tarih'].dt.date >= baslangic_tarih) & \
                                   (tum_veriler['tarih'].dt.date <= bitis_tarih)
                            filtered_df = tum_veriler[mask]
                            
                            if not filtered_df.empty:
                                sonuclar = []
                                for _, row in filtered_df.iterrows():
                                    fatura_metni = f"{row['aciklama']} {row['tutar']}"
                                    analiz = tevkifat_kontrol(fatura_metni, detayli_rapor=True)
                                    if analiz:
                                        sonuclar.append({
                                            'Tarih': row['tarih'].strftime('%Y-%m-%d'),
                                            'Açıklama': row['aciklama'],
                                            'Tutar': row['tutar'],
                                            'Risk Skoru': analiz['risk_skoru'],
                                            'Uyarı Seviyesi': analiz['uyari_seviyesi'],
                                            'Eşleşen Kategoriler': ', '.join(analiz['eslesmeler'].keys()),
                                            'Eşleşen Kelimeler': '; '.join([', '.join(v) for v in analiz['eslesmeler'].values()])
                                        })
                                
                                if sonuclar:
                                    # Excel dosyası oluştur
                                    output_file = f"data/{secilen_musteri}/tevkifat_analiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                                    df_sonuc = pd.DataFrame(sonuclar)
                                    
                                    # Excel yazıcı oluştur
                                    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                                        # Analiz sonuçları
                                        df_sonuc.to_excel(writer, sheet_name='Analiz Sonuçları', index=False)
                                        
                                        # Özet bilgiler
                                        ozet_data = {
                                            'Metrik': [
                                                'Toplam Kayıt Sayısı',
                                                'Risk Tespit Edilen Kayıt Sayısı',
                                                'Ortalama Risk Skoru',
                                                'Yüksek Riskli Kayıt Sayısı',
                                                'Analiz Tarihi',
                                                'Tarih Aralığı'
                                            ],
                                            'Değer': [
                                                len(filtered_df),
                                                len(sonuclar),
                                                round(df_sonuc['Risk Skoru'].mean(), 2),
                                                len(df_sonuc[df_sonuc['Uyarı Seviyesi'].isin(['Yüksek Risk', 'Çok Yüksek Risk'])]),
                                                datetime.now().strftime('%Y-%m-%d %H:%M'),
                                                f"{baslangic_tarih} - {bitis_tarih}"
                                            ]
                                        }
                                        pd.DataFrame(ozet_data).to_excel(writer, sheet_name='Özet', index=False)
                                    
                                    # Download butonu
                                    with open(output_file, 'rb') as f:
                                        bytes_data = f.read()
                                    st.download_button(
                                        label="Analiz Raporunu İndir",
                                        data=bytes_data,
                                        file_name=f"tevkifat_analiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                                    st.success(f"Analiz tamamlandı! {len(sonuclar)} adet risk tespit edildi.")
                                else:
                                    st.warning("Seçilen tarih aralığında risk tespit edilmedi.")
                            else:
                                st.warning("Seçilen tarih aralığında veri bulunamadı!")
                        else:
                            st.warning("Müşteriye ait veri bulunamadı!")
                            
                except Exception as e:
                    logging.error(f"Analiz hatası: {str(e)}\n{traceback.format_exc()}")
                    st.error(f"Analiz hatası: {str(e)}")
        else:
            st.info("Henüz müşteri eklenmemiş.")

if __name__ == "__main__":
    main() 