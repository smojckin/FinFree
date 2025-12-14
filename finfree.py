import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
import os
import json

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="PROFESYONEL BORSA ANALİZİ",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SABİTLER ---
FAVORI_DOSYASI = "favoriler_gui.json"

INDIKATOR_LISTESI = [
    "RSI", "MACD", "FISHER", "BOLLINGER", "SMA", "EMA", "STOCH", "CCI", "MFI", "ATR",
    "ADX", "WILLIAMS", "ROC", "MOM", "OBV", "ULTIMATE", "CHAIKIN", "PARABOLIC", "ICHIMOKU", "TRIX", 
    "DMI", "KAMA", "TEMA", "WMA", "HMA", "VWAP", "BBWIDTH", "CMO", "CG", "RVI",
    "KST", "PPO", "QQE", "SUPERTREND", "VORTEX", "APO", "BIAS", "BOP", "AROOON", "DONCHIAN",
    "KELTNER", "ACCBANDS", "COPPOCK", "FISHER_K", "STC", "SLOPE", "STDDEV", "VAR", "ZSCORE", "ENTROPY",
    "KURTOSIS", "SKEW", "CMF", "EFI", "EOM", "KVO", "NVI", "PVI", "PVOL", "PVR",
    "PVT", "QSTICK", "AD", "ADOSC", "OBV_OSC", "RSX", "RVGI", "STOCHRSI", "TSI", "UO",
    "WILLR", "ALMA", "DEMA", "FWMA", "LINREG", "MIDPOINT", "MIDPRICE", "PWMA", "RMA", "SINWMA",
    "SSMA", "SWMA", "TRIMA", "VIDYA", "ZLMA", "ABERRATION", "AMAT", "ATER", "CHOP", "DECAY"
]

# --- YARDIMCI FONKSİYONLAR ---
def favorileri_yukle():
    if os.path.exists(FAVORI_DOSYASI):
        try:
            with open(FAVORI_DOSYASI, 'r') as f: return json.load(f)
        except: return []
    return []

def favorileri_kaydet(liste):
    with open(FAVORI_DOSYASI, 'w') as f: json.dump(liste, f)

# --- VERİ HAZIRLAMA MOTORU ---
@st.cache_data(ttl=600)
def verileri_getir(sembol, periyot, secilen_favoriler):
    # Zaman Ayarı
    if periyot in ["6m", "1y", "2y"]: aralik = "1d"
    else: aralik = "1wk"

    try:
        df = yf.download(sembol, period=periyot, interval=aralik, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        
        close = df['Close']; high = df['High']; low = df['Low']; volume = df['Volume']
        
        # --- MANUEL HESAPLAMALAR (Standart Paket) ---
        # 1. RSI (Wilder)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        df['RSI'] = 100 - (100 / (1 + gain/loss))
        
        # 2. MACD
        exp12 = close.ewm(span=12).mean(); exp26 = close.ewm(span=26).mean()
        df['MACD'] = exp12 - exp26; df['MACD_SIG'] = df['MACD'].ewm(span=9).mean()
        
        # 3. FISHER
        mid = (high + low)/2; 
        raw = 2*((mid - low.rolling(9).min())/(high.rolling(9).max()-low.rolling(9).min()+1e-9))-1
        smooth = raw.ewm(span=5).mean().clip(-0.99, 0.99)
        df['FISHER'] = 0.5 * np.log((1+smooth)/(1-smooth)); df['FISHER_SIG'] = df['FISHER'].shift(1)
        
        # 4. Bollinger & Ortalamalar
        df['SMA_20'] = close.rolling(20).mean(); df['EMA_50'] = close.ewm(span=50).mean()
        std20 = close.rolling(20).std()
        df['BB_UP'] = df['SMA_20'] + 2*std20; df['BB_LOW'] = df['SMA_20'] - 2*std20
        df['BB_MID'] = df['SMA_20']

        # --- DİNAMİK HESAPLAMA (AMAT vb. için) ---
        # Listede olup da manuel hesaplanmayanları pandas_ta ile hesapla
        for ind in secilen_favoriler:
            # Eğer sütun zaten yoksa hesapla
            if ind not in df.columns:
                try:
                    # pandas_ta kütüphanesinden dinamik çağır (örn: df.ta.amat())
                    # Bazı indikatör isimleri kütüphanede farklı olabilir, onları yakalayalım
                    if hasattr(df.ta, ind.lower()):
                        method = getattr(df.ta, ind.lower())
                        method(append=True)
                    else:
                        # Özel durumlar
                        if ind == "SUPERTREND": df.ta.supertrend(append=True)
                        elif ind == "PARABOLIC": df.ta.psar(append=True)
                        elif ind == "ICHIMOKU": df.ta.ichimoku(append=True)
                        elif ind == "BBWIDTH": df.ta.bbands(append=True) # Width içinden çıkar
                except:
                    pass

        df = df.dropna()
        return df
    except:
        return None

# --- ARAYÜZ ---
st.sidebar.title("🎛️ KONTROL PANELİ")

sembol_giris = st.sidebar.text_input("Hisse Sembolü:", "THYAO").upper()
if ".IS" not in sembol_giris and "USD" not in sembol_giris: sembol_giris += ".IS"

periyot_secimi = st.sidebar.select_slider(
    "Analiz Süresi",
    options=["6m", "1y", "2y", "3y", "5y", "max"],
    value="1y"
)

# Favoriler
mevcut_favoriler = favorileri_yukle()
secilen_favoriler = st.sidebar.multiselect(
    "Göstergeler:",
    INDIKATOR_LISTESI,
    default=mevcut_favoriler
)

if st.sidebar.button("Ayarları Kaydet"):
    favorileri_kaydet(secilen_favoriler)
    st.sidebar.success("Kaydedildi!")

if st.sidebar.button("ANALİZİ BAŞLAT", type="primary"):
    st.session_state['run'] = True
else:
    if 'run' not in st.session_state: st.session_state['run'] = False

# --- ANA EKRAN ---
st.title(f"📊 {sembol_giris} ANALİZ PLATFORMU")

if st.session_state['run']:
    with st.spinner('Hesaplamalar yapılıyor...'):
        # Favorileri de gönderiyoruz ki eksikleri hesaplasın
        df = verileri_getir(sembol_giris, periyot_secimi, secilen_favoriler)

    if df is None:
        st.error("Veri alınamadı.")
    else:
        # Fiyat Grafiği
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_UP'], line=dict(color='gray', width=1, dash='dot'), name='BB Üst'))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_LOW'], line=dict(color='gray', width=1, dash='dot'), name='BB Alt', fill='tonexty'))
        fig.update_layout(height=600, title="Fiyat & Trend", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        tab1, tab2, tab3 = st.tabs(["İNDİKATÖRLER", "SİNYAL RAPORU", "VERİLER"])

        with tab1:
            if not secilen_favoriler: st.info("İndikatör seçiniz.")
            
            for ind in secilen_favoriler:
                st.subheader(f"{ind}")
                fig_ind = go.Figure()
                
                # Çizim Mantığı
                if ind == "RSI":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'))
                    fig_ind.add_hline(y=70, line_color="red", line_dash="dash")
                    fig_ind.add_hline(y=30, line_color="green", line_dash="dash")
                    fig_ind.update_yaxes(range=[0, 100])
                
                elif ind == "MACD":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue'), name='MACD'))
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['MACD_SIG'], line=dict(color='orange'), name='Sinyal'))
                    fig_ind.add_bar(x=df.index, y=df['MACD']-df['MACD_SIG'], name='Hist')
                
                elif ind == "FISHER":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['FISHER'], line=dict(color='red'), name='Fisher'))
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['FISHER_SIG'], line=dict(color='green'), name='Sinyal'))
                    fig_ind.add_hline(y=2, line_color="gray"); fig_ind.add_hline(y=-2, line_color="gray")

                # Dinamik Çizim (AMAT, KVO vb. için)
                else:
                    found = False
                    # İlgili indikatörün tüm sütunlarını bul (Örn: AMAT_lr, AMAT_sr)
                    target_cols = [c for c in df.columns if c.startswith(ind)]
                    
                    if target_cols:
                        for col in target_cols:
                            fig_ind.add_trace(go.Scatter(x=df.index, y=df[col], name=col))
                        found = True
                    elif ind in df.columns:
                        fig_ind.add_trace(go.Scatter(x=df.index, y=df[ind], name=ind))
                        found = True
                        
                    if not found:
                        st.warning(f"{ind} verisi hesaplanamadı.")

                fig_ind.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
                
                # --- İŞTE DÜZELTME BURADA ---
                # Her grafiğe benzersiz bir 'key' veriyoruz.
                st.plotly_chart(fig_ind, use_container_width=True, key=f"chart_{ind}")

        with tab2:
            st.markdown("### 📋 DETAYLI SİNYAL DURUMU")
            col1, col2, col3 = st.columns(3)
            
            last = df.iloc[-1]
            close = last['Close']
            
            col1.metric("Fiyat", f"{close:.2f}")
            
            # RSI Kartı
            rsi_val = last.get('RSI', 50)
            rsi_delta = "Aşırı Alım" if rsi_val > 70 else ("Aşırı Satım" if rsi_val < 30 else "Nötr")
            col2.metric("RSI", f"{rsi_val:.2f}", delta=rsi_delta, delta_color="inverse")
            
            # Trend Kartı
            sma = last.get('SMA_20', close)
            trend = "YÜKSELİŞ" if close > sma else "DÜŞÜŞ"
            col3.metric("Trend (SMA20)", trend, delta="Pozitif" if trend=="YÜKSELİŞ" else "Negatif")
            
            st.divider()
            
            # Favori İndikatörlerin Son Durumları
            st.write("#### Seçili Göstergelerin Son Değerleri")
            for ind in secilen_favoriler:
                # Sütunları bul
                cols = [c for c in df.columns if c.startswith(ind)]
                if cols:
                    st.write(f"**{ind}:**")
                    c_cols = st.columns(len(cols))
                    for i, c in enumerate(cols):
                        c_cols[i].info(f"{c}: {last[c]:.2f}")
                elif ind in df.columns:
                    st.info(f"**{ind}:** {last[ind]:.2f}")

        with tab3:
            st.dataframe(df.style.highlight_max(axis=0), use_container_width=True)
