# views.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import logging
import traceback
from pathlib import Path
from typing import Dict, Any
import json

__all__ = ['musteri_ekle_view', 'musteri_sil_view', 'veri_yukle_view', 'analiz_yap_view']

# Views fonksiyonları
def musteri_ekle_view(analyzer) -> None:
    """Müşteri ekleme view fonksiyonu"""
    st.subheader("Yeni Müşteri Ekle")
    musteri_adi = st.text_input("Müşteri Adı:")
    if st.button("Ekle") and musteri_adi:
        musteri_id = analyzer.musteri_ekle(musteri_adi)
        if musteri_id:
            st.success(f"Müşteri başarıyla eklendi. ID: {musteri_id}")

def musteri_sil_view(analyzer) -> None:
    """Müşteri silme view fonksiyonu"""
    st.subheader("Müşteri Sil")
    musteriler = analyzer.config_manager.config["musteriler"]
    if musteriler:
        secilen_musteri = st.selectbox(
            "Müşteri Seçin:",
            options=list(musteriler.keys()),
            format_func=lambda x: f"{x} - {musteriler[x]['ad']}"
        )
        if st.button("Sil"):
            if analyzer.musteri_sil(secilen_musteri):
                st.success("Müşteri başarıyla silindi!")
    else:
        st.info("Henüz müşteri eklenmemiş.")

def veri_yukle_view(analyzer) -> None:
    """Veri yükleme view fonksiyonu"""
    st.subheader("Veri Yükleme")
    musteriler = analyzer.config_manager.config["musteriler"]
    if musteriler:
        secilen_musteri = st.selectbox(
            "Müşteri Seçin:",
            options=list(musteriler.keys()),
            format_func=lambda x: f"{x} - {musteriler[x]['ad']}"
        )
        
        uploaded_file = st.file_uploader(
            "Excel/CSV Dosyası Seçin", 
            type=['xlsx', 'xls', 'csv']
        )
        
        if uploaded_file:
            try:
                # Dosya önizleme
                if uploaded_file.name.endswith('.csv'):
                    df_preview = pd.read_csv(uploaded_file)
                else:
                    df_preview = pd.read_excel(uploaded_file, engine='openpyxl')
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
                saved_mapping = analyzer.config_manager.config.get("column_mappings", {})
                saved_mapping = saved_mapping.get(secilen_musteri, {})
                
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
                    with st.spinner('Veri yükleniyor ve analiz ediliyor...'):
                        df = analyzer.veri_yukle(secilen_musteri, uploaded_file, mapping)
                        if df is not None:
                            st.success("Veri başarıyla yüklendi!")
                            st.write("Yüklenen veri önizlemesi:", df.head())
                            
            except Exception as e:
                st.error(f"Veri yükleme hatası: {str(e)}")
    else:
        st.info("Henüz müşteri eklenmemiş.")

def analiz_yap_view(analyzer) -> None:
    """Analiz yapma view fonksiyonu"""
    st.subheader("Tevkifat Analizi")
    
    # Set display options for pandas
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    
    musteriler = analyzer.config_manager.config["musteriler"]
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
        
        if st.button("Analiz Yap"):
            try:
                # Tarihleri datetime'a çevir
                baslangic = datetime.combine(baslangic_tarih, datetime.min.time())
                bitis = datetime.combine(bitis_tarih, datetime.max.time())
                
                # Analiz yap
                with st.spinner('Analiz yapılıyor...'):
                    df = analyzer.analiz_yap(secilen_musteri, baslangic, bitis)
                
                if df is None:
                    st.warning("Seçilen tarih aralığında veri bulunamadı!")
                    return
                
                # Analiz sonuçlarını göster
                st.subheader("Analiz Sonuçları")
                
                if 'tevkifat_riski' not in df.columns:
                    st.error("Analiz sonuçları oluşturulamadı. Lütfen veriyi tekrar yükleyin.")
                    return
                    
                # Tevkifat riski olan faturaları filtrele
                riskli_faturalar = df[df['tevkifat_riski'] == True].copy()
                
                if not riskli_faturalar.empty:
                    try:
                        # Sütun isimlerini string olarak birleştir ve tekrar edenleri kaldır
                        riskli_faturalar.columns = [str(''.join(col)) if isinstance(col, tuple) else str(col) 
                                                  for col in riskli_faturalar.columns]
                        
                        # Tekrarlanan sütunları kaldır
                        riskli_faturalar = riskli_faturalar.loc[:, ~riskli_faturalar.columns.duplicated()]
                        
                        # Analiz sütunlarını tanımla
                        analiz_sutunlari = ['Risk Seviyesi', 'Risk Skoru', 'Eşleşen Kategoriler']
                        temel_sutunlar = ['satici_unvani', 'fatura_no', 'tarih', 'aciklama', 'tutar']
                        mevcut_sutunlar = riskli_faturalar.columns.tolist()
                        
                        # Analiz sütunlarını ve tevkifat_riski sütununu çıkar
                        diger_sutunlar = [col for col in mevcut_sutunlar 
                                        if col not in analiz_sutunlari + ['tevkifat_riski'] and 
                                        col.lower() not in [s.lower() for s in temel_sutunlar]]
                        
                        # Temel sütunları ekle (eğer varsa)
                        temel_mevcut_sutunlar = [col for col in mevcut_sutunlar 
                                               if col.lower() in [s.lower() for s in temel_sutunlar]]
                        
                        # Sadece mevcut olan analiz sütunlarını ekle
                        mevcut_analiz_sutunlari = [col for col in analiz_sutunlari 
                                                 if col in mevcut_sutunlar]
                        
                        # Yeni sütun sırasını oluştur
                        yeni_sutun_sirasi = temel_mevcut_sutunlar + diger_sutunlar + mevcut_analiz_sutunlari
                        
                        # Sütunları yeniden düzenle
                        riskli_faturalar = riskli_faturalar[yeni_sutun_sirasi]
                        
                        # Risk seviyesine göre renklendirme
                        def risk_rengi(df):
                            if 'Risk Seviyesi' not in df.columns:
                                return df
                            
                            # Boş stil matrisi oluştur
                            styles = pd.DataFrame('', index=df.index, columns=df.columns)
                            
                            # Risk seviyelerine göre stilleri uygula
                            mask_cok_yuksek = df['Risk Seviyesi'] == 'Çok Yüksek Risk'
                            mask_yuksek = df['Risk Seviyesi'] == 'Yüksek Risk'
                            mask_orta = df['Risk Seviyesi'] == 'Orta Risk'
                            
                            # Tüm sütunlara stil uygula
                            for col in df.columns:
                                styles.loc[mask_cok_yuksek, col] = 'background-color: red; color: white'
                                styles.loc[mask_yuksek, col] = 'background-color: orange'
                                styles.loc[mask_orta, col] = 'background-color: yellow'
                            
                            return styles
                        
                        # Stil uygula ve göster
                        styled_df = riskli_faturalar.style.apply(risk_rengi, axis=None)
                        
                        # Streamlit dataframe gösterimini genişlet
                        st.dataframe(
                            styled_df,
                            use_container_width=True,
                            height=600
                        )
                        
                        # Tüm sütunları göster seçeneği
                        if st.checkbox("Tüm veriyi tablo olarak göster"):
                            st.write("Tüm Veriler:")
                            st.write(riskli_faturalar.to_html(index=False), unsafe_allow_html=True)
                        
                        # Excel'e aktar
                        output = f"data/{secilen_musteri}/analiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        
                        # Excel yazarken sütun genişliklerini ayarla
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            riskli_faturalar.to_excel(writer, index=False, sheet_name='Analiz')
                            worksheet = writer.sheets['Analiz']
                            
                            # Excel sütun genişliklerini ayarla
                            for idx, col in enumerate(riskli_faturalar.columns):
                                # Excel sütun harfini hesapla (A, B, C, ... , Z, AA, AB, ...)
                                col_letter = ''
                                temp = idx
                                while temp >= 0:
                                    col_letter = chr(65 + (temp % 26)) + col_letter
                                    temp = (temp // 26) - 1
                                
                                # Sütun genişliğini ayarla
                                max_length = max(
                                    riskli_faturalar[col].astype(str).apply(len).max(),
                                    len(str(col))
                                ) + 2
                                worksheet.column_dimensions[col_letter].width = min(max_length, 50)
                        
                        # İndirme butonu
                        with open(output, 'rb') as f:
                            st.download_button(
                                label="Analiz Sonuçlarını İndir",
                                data=f,
                                file_name=f"tevkifat_analizi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    except Exception as e:
                        st.error(f"Stil uygulama hatası: {str(e)}")
                        # Hata durumunda stili olmadan göster
                        st.dataframe(riskli_faturalar, use_container_width=True)
                else:
                    st.info("Seçilen tarih aralığında tevkifat riski olan fatura bulunamadı.")
                    
            except Exception as e:
                st.error(f"Analiz hatası: {str(e)}")
                logging.error(f"Analiz hatası: {str(e)}\n{traceback.format_exc()}")
    else:
        st.info("Henüz müşteri eklenmemiş.")