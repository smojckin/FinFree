import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
import os
import json
import requests
import warnings  # <-- İŞTE EKSİK OLAN BU SATIRDI

# Uyarıları sustur
warnings.filterwarnings("ignore")

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
# İŞ YATIRIM SCRAPER
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    saf_sembol = sembol.replace(".IS", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    veriler = {"temettu": None, "sermaye": None, "oranlar": None}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }
    
    try:
        # verify=False SSL hatasını önlemek içindir
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code != 200: return None
        
        tablolar = pd.read_html(response.text, match=".")
        for df in tablolar:
            cols = [str(c).lower() for c in df.columns]
            if any("temettü" in c for c in cols) or any("dağıtma" in c for c in cols): veriler["temettu"] = df
            elif any("bedelli" in c for c in cols) or any("bedelsiz" in c for c in cols) or any("bölünme" in c for c in cols): veriler["sermaye"] = df
            elif any("f/k" in c for c in cols) or any("pd/dd" in c for c in cols) or any("özsermaye" in c for c in cols): veriler["oranlar"] = df
        return veriler
    except Exception as e: return None

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
        
        # --- TEMEL HESAPLAMALAR ---
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
        
        lowest14 = low.rolling(14).min(); highest14 = high.rolling(14).max()
        df['STOCH_K'] = 100*((close-lowest14)/(highest14-lowest14+1e-9)); df['STOCH_D'] = df['STOCH_K'].rolling(3).mean()
        
        tp = (high+low+close)/3
        df['CCI'] = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).apply(lambda x: abs(x-x.mean()).mean()))
        df['WILLR'] = -100 * ((highest14 - close) / (highest14 - lowest14 + 1e-9))
        df['ROC'] = ((close - close.shift(12)) / close.shift(12)) * 100

        # Ekstra hesaplamalar (Favoriler için)
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
    except: return None

# -----------------------------------------------------------------------------
# PUANLAMA MOTORU
# -----------------------------------------------------------------------------
def puanlama_yap(df):
    if df is None or df.empty: return None
    
    last = df.iloc[-1]; close = last['Close']
    
    trend_puan = 0; trend_max = 0; trend_detay = []
    
    trend_max += 3
    if close > last['SMA_20']: trend_puan += 3; trend_detay.append("Fiyat SMA20 Üzerinde")
    
    trend_max += 3
    if close > last['EMA_50']: trend_puan += 3; trend_detay.append("Fiyat EMA50 Üzerinde")
    
    if 'SUPERTREND_DIR' in df.columns:
        trend_max += 3
        if last['SUPERTREND_DIR'] == 1: trend_puan += 3; trend_detay.append("SuperTrend: AL")

    osc_puan = 0; osc_max = 0; osc_detay = []
    
    osc_max += 2
    if last['RSI'] < 30: osc_puan += 2; osc_detay.append("RSI: Aşırı Satım (AL)")
    elif last['RSI'] > 50 and last['RSI'] < 70: osc_puan += 1; osc_detay.append("RSI: Pozitif Bölge")
    
    osc_max += 2
    if last['MACD'] > last['MACD_SIG']: osc_puan += 2; osc_detay.append("MACD: Pozitif Kesişim")
    
    osc_max += 2
    if last['FISHER'] > last['FISHER_SIG']: 
        if last['FISHER'] < -1.5: osc_puan += 3; osc_detay.append("Fisher: Dipten Dönüş (GÜÇLÜ)") 
        else: osc_puan += 2; osc_detay.append("Fisher: AL")
        
    osc_max += 2
    if close < last['BB_LOW']: osc_puan += 2; osc_detay.append("Bollinger: Bant Dışı (Ucuz)")

    mom_puan = 0; mom_max = 0; mom_detay = []
    
    mom_max += 1
    if last['STOCH_K'] < 20 and last['STOCH_K'] > last['STOCH_D']: mom_puan += 1; mom_detay.append("Stoch: Dip Kesişimi")
    
    mom_max += 1
    if last['CCI'] < -100: mom_puan += 1; mom_detay.append("CCI: Aşırı Satım")
    
    mom_max += 1
    if last['WILLR'] < -80: mom_puan += 1; mom_detay.append("WillR: Aşırı Satım")
    
    mom_max += 1
    if last['ROC'] > 0: mom_puan += 1; mom_detay.append("ROC: Pozitif Momentum")

    toplam_puan = trend_puan + osc_puan + mom_puan
    toplam_max = trend_max + osc_max + mom_max
    genel_yuzde = (toplam_puan / toplam_max) * 100 if toplam_max > 0 else 0
    
    trend_yuzde = (trend_puan / trend_max) * 100 if trend_max > 0 else 0
    osc_yuzde = (osc_puan / osc_max) * 100 if osc_max > 0 else 0
    mom_yuzde = (mom_puan / mom_max) * 100 if mom_max > 0 else 0
    
    return {
        "genel_skor": genel_yuzde,
        "trend": {"skor": trend_yuzde, "detay": trend_detay},
        "osc": {"skor": osc_yuzde, "detay": osc_detay},
        "mom": {"skor": mom_yuzde, "detay": mom_detay}
    }

# --- ARAYÜZ ---
st.sidebar.title("🎛️ KONTROL PANELİ")
sembol_giris = st.sidebar.text_input("Hisse Sembolü:", "THYAO").upper()
if ".IS" not in sembol_giris and "USD" not in sembol_giris: sembol_giris += ".IS"

periyot_secimi = st.sidebar.select_slider("Analiz Süresi", options=["6m", "1y", "2y", "3y", "5y", "max"], value="1y")
mevcut_favoriler = favorileri_yukle()
secilen_favoriler = st.sidebar.multiselect("Göstergeler:", INDIKATOR_LISTESI, default=mevcut_favoriler)

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
    with st.spinner('Piyasa Konseyi Toplanıyor...'):
        df = verileri_getir(sembol_giris, periyot_secimi, secilen_favoriler)

    if df is None:
        st.error("Veri alınamadı.")
    else:
        skor_kart = puanlama_yap(df)
        
        # ÜST BİLGİ KARTLARI
        last = df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fiyat", f"{last['Close']:.2f}")
        c2.metric("RSI", f"{last['RSI']:.2f}", delta="Aşırı Alım" if last['RSI']>70 else ("Aşırı Satım" if last['RSI']<30 else "Nötr"), delta_color="inverse")
        
        skor = skor_kart["genel_skor"]
        durum = "GÜÇLÜ AL" if skor >= 70 else ("AL (Zayıf)" if skor >= 50 else "SAT / NÖTR")
        c3.metric("GENEL TEKNİK SKOR", f"{skor:.0f}/100", delta=durum)
        
        # Grafik
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'))
        fig.update_layout(height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # SEKMELER
        tab1, tab2, tab3, tab4 = st.tabs(["📊 KONSEY (SKOR) RAPORU", "📈 İNDİKATÖRLER", "🔢 VERİLER", "🏛️ ŞİRKET KARTI"])

        with tab1:
            st.subheader("TEKNİK PUANLAMA DETAYLARI")
            col_t, col_o, col_m = st.columns(3)
            with col_t:
                st.info(f"**TREND TAKİPÇİLERİ**\nSkor: %{skor_kart['trend']['skor']:.0f}")
                st.progress(int(skor_kart['trend']['skor']))
                for d in skor_kart['trend']['detay']: st.write(f"✅ {d}")
                if not skor_kart['trend']['detay']: st.write("❌ Olumlu sinyal yok")
            with col_o:
                st.warning(f"**OSİLATÖRLER**\nSkor: %{skor_kart['osc']['skor']:.0f}")
                st.progress(int(skor_kart['osc']['skor']))
                for d in skor_kart['osc']['detay']: st.write(f"✅ {d}")
            with col_m:
                st.success(f"**MOMENTUM**\nSkor: %{skor_kart['mom']['skor']:.0f}")
                st.progress(int(skor_kart['mom']['skor']))
                for d in skor_kart['mom']['detay']: st.write(f"✅ {d}")

        with tab2:
            if not secilen_favoriler: st.info("İndikatör seçiniz.")
            for ind in secilen_favoriler:
                st.subheader(f"{ind}")
                fig_ind = go.Figure()
                if ind == "RSI":
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'))
                    fig_ind.add_hline(y=70, line_color="red", line_dash="dash"); fig_ind.add_hline(y=30, line_color="green", line_dash="dash")
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

        with tab3:
            st.dataframe(df.style.highlight_max(axis=0), use_container_width=True)

        with tab4:
            st.markdown(f"### {sembol_giris} Temel Veriler (İş Yatırım)")
            if ".IS" in sembol_giris:
                is_veri = is_yatirim_verileri(sembol_giris)
                if is_veri:
                    c1, c2 = st.columns(2)
                    with c1: 
                        st.subheader("Temettüler")
                        if is_veri["temettu"] is not None: st.dataframe(is_veri["temettu"], use_container_width=True)
                        else: st.info("Yok")
                    with c2:
                        st.subheader("Sermaye Artırımları")
                        if is_veri["sermaye"] is not None: st.dataframe(is_veri["sermaye"], use_container_width=True)
                        else: st.info("Yok")
                    st.subheader("Finansal Oranlar")
                    if is_veri["oranlar"] is not None: st.dataframe(is_veri["oranlar"], use_container_width=True)
                else: st.error("Veri çekilemedi.")
            else: st.warning("Sadece BIST hisseleri içindir.")
