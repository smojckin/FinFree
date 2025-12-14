import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
import os
import json
import requests

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

# -----------------------------------------------------------------------------
# İŞ YATIRIM SCRAPER (KAMUFLAJLI)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    # .IS uzantısını kaldır (İş Yatırım saf kod ister: THYAO)
    saf_sembol = sembol.replace(".IS", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    
    veriler = {"temettu": None, "sermaye": None, "oranlar": None}
    
    # Anti-Bot Header Ayarları
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        
        tablolar = pd.read_html(response.content, match=".")
        
        for df in tablolar:
            cols = [str(c).lower() for c in df.columns]
            if any("temettü" in c for c in cols) or any("dağıtma" in c for c in cols):
                veriler["temettu"] = df
            elif any("bedelli" in c for c in cols) or any("bedelsiz" in c for c in cols) or any("bölünme" in c for c in cols):
                veriler["sermaye"] = df
            elif any("f/k" in c for c in cols) or any("pd/dd" in c for c in cols) or any("özsermaye" in c for c in cols):
                veriler["oranlar"] = df
        return veriler
    except: return None

# --- VERİ HAZIRLAMA MOTORU ---
@st.cache_data(ttl=600)
def verileri_getir(sembol, periyot, secilen_favoriler):
    if periyot in ["6m", "1y", "2y"]: aralik = "1d"
    else: aralik = "1wk"

    try:
        df = yf.download(sembol, period=periyot, interval=aralik, progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        
        close = df['Close']; high = df['High']; low = df['Low']; volume = df['Volume']
        
        # --- MANUEL HESAPLAMALAR ---
        delta = close.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, min_periods=14).mean()
        df['RSI'] = 100 - (100 / (1 + gain/loss))
        
        exp12 = close.ewm(span=12).mean(); exp26 = close.ewm(span=26).mean()
        df['MACD'] = exp12 - exp26; df['MACD_SIG'] = df['MACD'].ewm(span=9).mean()
        
        mid = (high + low)/2; 
        raw = 2*((mid - low.rolling(9).min())/(high.rolling(9).max()-low.rolling(9).min()+1e-9))-1
        smooth = raw.ewm(span=5).mean().clip(-0.99, 0.99)
        df['FISHER'] = 0.5 * np.log((1+smooth)/(1-smooth)); df['FISHER_SIG'] = df['FISHER'].shift(1)
        
        df['SMA_20'] = close.rolling(20).mean(); df['EMA_50'] = close.ewm(span=50).mean()
        std20 = close.rolling(20).std()
        df['BB_UP'] = df['SMA_20'] + 2*std20; df['BB_LOW'] = df['SMA_20'] - 2*std20
        df['BB_MID'] = df['SMA_20']

        # --- DİNAMİK HESAPLAMA (Eksikler için) ---
        for ind in secilen_favoriler:
            if ind not in df.columns:
                try:
                    if hasattr(df.ta, ind.lower()):
                        method = getattr(df.ta, ind.lower())
                        method(append=True)
                    else:
                        if ind == "SUPERTREND": df.ta.supertrend(append=True)
                        elif ind in ["PARABOLIC", "PSAR"]: df.ta.psar(append=True)
                        elif ind == "ICHIMOKU": df.ta.ichimoku(append=True)
                        elif ind == "BBWIDTH": df.ta.bbands(append=True)
                except: pass

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
    with st.spinner('Veriler ve Analizler Hazırlanıyor...'):
        df = verileri_getir(sembol_giris, periyot_secimi, secilen_favoriler)

    if df is None:
        st.error("Veri alınamadı. Sembolü kontrol ediniz.")
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

        # SEKMELER (İş Yatırım Dahil)
        tab1, tab2, tab3, tab4 = st.tabs(["İNDİKATÖRLER", "SİNYAL RAPORU", "VERİ TABLOSU", "🏛️ ŞİRKET KARTI (İŞ YATIRIM)"])

        with tab1:
            if not secilen_favoriler: st.info("İndikatör seçiniz.")
            for ind in secilen_favoriler:
                st.subheader(f"{ind}")
                fig_ind = go.Figure()
                
                if ind == "RSI":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'))
                    fig_ind.add_hline(y=70, line_color="red", line_dash="dash"); fig_ind.add_hline(y=30, line_color="green", line_dash="dash")
                    fig_ind.update_yaxes(range=[0, 100])
                elif ind == "MACD":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue'), name='MACD'))
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['MACD_SIG'], line=dict(color='orange'), name='Sinyal'))
                    fig_ind.add_bar(x=df.index, y=df['MACD']-df['MACD_SIG'], name='Hist')
                elif ind == "FISHER":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['FISHER'], line=dict(color='red'), name='Fisher'))
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['FISHER_SIG'], line=dict(color='green'), name='Sinyal'))
                    fig_ind.add_hline(y=2, line_color="gray"); fig_ind.add_hline(y=-2, line_color="gray")
                else:
                    found = False
                    target_cols = [c for c in df.columns if c.startswith(ind)]
                    if target_cols:
                        for col in target_cols: fig_ind.add_trace(go.Scatter(x=df.index, y=df[col], name=col))
                        found = True
                    elif ind in df.columns:
                        fig_ind.add_trace(go.Scatter(x=df.index, y=df[ind], name=ind))
                        found = True
                    if not found: st.warning(f"{ind} verisi hesaplanamadı.")

                fig_ind.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_ind, use_container_width=True, key=f"chart_{ind}")

        with tab2:
            st.markdown("### 📋 DETAYLI SİNYAL DURUMU")
            col1, col2, col3 = st.columns(3)
            last = df.iloc[-1]; close = last['Close']
            
            col1.metric("Fiyat", f"{close:.2f}")
            
            rsi_val = last.get('RSI', 50)
            rsi_delta = "Aşırı Alım" if rsi_val > 70 else ("Aşırı Satım" if rsi_val < 30 else "Nötr")
            col2.metric("RSI", f"{rsi_val:.2f}", delta=rsi_delta, delta_color="inverse")
            
            sma = last.get('SMA_20', close)
            trend = "YÜKSELİŞ" if close > sma else "DÜŞÜŞ"
            col3.metric("Trend (SMA20)", trend, delta="Pozitif" if trend=="YÜKSELİŞ" else "Negatif")
            
            st.divider()
            st.write("#### Seçili Göstergelerin Son Değerleri")
            for ind in secilen_favoriler:
                cols = [c for c in df.columns if c.startswith(ind)]
                if cols:
                    st.write(f"**{ind}:**")
                    c_cols = st.columns(len(cols))
                    for i, c in enumerate(cols): c_cols[i].info(f"{c}: {last[c]:.2f}")
                elif ind in df.columns: st.info(f"**{ind}:** {last[ind]:.2f}")

        with tab3:
            st.dataframe(df.style.highlight_max(axis=0), use_container_width=True)

        with tab4:
            st.markdown(f"### {sembol_giris} Temel Analiz Verileri (Kaynak: İş Yatırım)")
            if ".IS" in sembol_giris:
                with st.spinner("İş Yatırım verileri çekiliyor..."):
                    is_veri = is_yatirim_verileri(sembol_giris)
                
                if is_veri:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.subheader("💰 Temettü Geçmişi")
                        if is_veri["temettu"] is not None: st.dataframe(is_veri["temettu"], use_container_width=True)
                        else: st.info("Temettü verisi bulunamadı.")
                    with col_b:
                        st.subheader("🏗️ Sermaye Artırımları")
                        if is_veri["sermaye"] is not None: st.dataframe(is_veri["sermaye"], use_container_width=True)
                        else: st.info("Sermaye artırım verisi bulunamadı.")
                    st.divider()
                    st.subheader("📊 Finansal Oranlar (Özet)")
                    if is_veri["oranlar"] is not None: st.dataframe(is_veri["oranlar"], use_container_width=True)
                    else: st.info("Oranlar çekilemedi.")
                else:
                    st.error("Veri çekilemedi. Bağlantı hatası veya hisse bulunamadı.")
            else:
                st.warning("Bu sekme sadece BIST hisseleri içindir.")
