import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
import os
import json
import requests
import warnings

# Uyarıları sustur
warnings.filterwarnings("ignore")

# --- AYARLAR ---
st.set_page_config(page_title="PROFESYONEL BORSA ANALİZİ", layout="wide", initial_sidebar_state="expanded")

# --- SABİTLER ---
FAVORI_DOSYASI = "favoriler_v2.json"

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
    varsayilan = {"indikatorler": ["RSI", "MACD", "SMA"], "hisseler": ["THYAO", "ASELS", "GARAN"]}
    if os.path.exists(FAVORI_DOSYASI):
        try:
            with open(FAVORI_DOSYASI, 'r') as f:
                data = json.load(f)
                if isinstance(data, list): return {"indikatorler": data, "hisseler": varsayilan["hisseler"]}
                return data
        except: return varsayilan
    return varsayilan

def favorileri_kaydet(veri):
    with open(FAVORI_DOSYASI, 'w') as f: json.dump(veri, f)

# -----------------------------------------------------------------------------
# İŞ YATIRIM SCRAPER (DÜZELTİLEN KISIM BURASI)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    saf_sembol = sembol.replace(".IS", "").replace(".is", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    veriler = {"temettu": None, "sermaye": None, "oranlar": None, "fon_matrisi": None}
    
    # Session kullanarak bağlantıyı daha insansı yapalım
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    
    try:
        # Önce Yahoo verilerini hazırla (Yedek plan)
        tk = yf.Ticker(sembol)
        ticker_info = tk.info if tk.info else {}
        
        # Fon Matrisi (Yahoo'dan gelenlerle doldur)
        matris_data = {
            "Kategori": [
                "1. Temel Analiz ve Finansal Sağlık", "1. Temel Analiz ve Finansal Sağlık", "1. Temel Analiz ve Finansal Sağlık",
                "2. Sektör ve Makroekonomi Analizi", "2. Sektör ve Makroekonomi Analizi",
                "3. Yönetim Kalitesi ve Kurumsal Yönetim", "3. Yönetim Kalitesi ve Kurumsal Yönetim",
                "4. Likidite ve İşlem Hacmi", "4. Likidite ve İşlem Hacmi",
                "5. Risk ve Portföy Uyumu", "5. Risk ve Portföy Uyumu"
            ],
            "Unsur": [
                "Kârlılık ve Büyüme (ROE)", "Borç Yapısı (Borç/Özkaynak)", "Piyasa Çarpanları (F/K)",
                "Sektörel Trendler", "Makro Göstergeler (Beta)",
                "Yönetim Performansı", "Temettü Politikası (Yield)",
                "Günlük Ortalama Hacim", "Hisseden Çıkış Kolaylığı (Float)",
                "Beta Katsayısı", "Volatilite (52H Değişim)"
            ],
            "Değer": [
                f"%{ticker_info.get('returnOnEquity', 0)*100:.2f}" if ticker_info.get('returnOnEquity') else "Veri Yok",
                ticker_info.get('debtToEquity', 'N/A'),
                ticker_info.get('forwardPE', 'N/A'),
                ticker_info.get('sector', 'N/A'),
                ticker_info.get('beta', 'N/A'),
                "Kurumsal Analiz Gerekli",
                f"%{ticker_info.get('dividendYield', 0)*100:.2f}" if ticker_info.get('dividendYield') else "Yok/Düşük",
                f"{ticker_info.get('averageVolume', 0):,}",
                f"%{ticker_info.get('floatShares', 0)/ticker_info.get('sharesOutstanding', 1)*100:.2f}" if ticker_info.get('floatShares') and ticker_info.get('sharesOutstanding') else "N/A",
                ticker_info.get('beta', 'N/A'),
                f"%{ticker_info.get('52WeekChange', 0)*100:.2f}" if ticker_info.get('52WeekChange') else "N/A"
            ]
        }
        veriler["fon_matrisi"] = pd.DataFrame(matris_data)

        # Şimdi İş Yatırım'dan tabloları zorla alalım
        response = session.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            tablolar = pd.read_html(response.text, decimal=",", thousands=".")
            for df in tablolar:
                cols = [str(c).lower() for c in df.columns]
                if any("temettü" in c for c in cols): veriler["temettu"] = df
                elif any("sermaye" in c for c in cols): veriler["sermaye"] = df
                elif any("f/k" in c for c in cols): veriler["oranlar"] = df
        
        return veriler
    except Exception as e:
        # İş Yatırım patlasa bile en azından matrisi döndür
        return veriler if veriler["fon_matrisi"] is not None else None

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

# --- RENKLENDİRME ---
def renk_belirle(val, tur):
    try: val = float(val)
    except: return ""
    if tur == "RSI":
        if val < 30: return 'background-color: #d4edda; color: green'
        elif val > 70: return 'background-color: #f8d7da; color: red'
    elif tur == "CCI":
        if val < -100: return 'background-color: #d4edda; color: green'
        elif val > 100: return 'background-color: #f8d7da; color: red'
    elif tur in ["WILLR", "STOCH_K"]:
        if val < 20 or val < -80: return 'background-color: #d4edda; color: green'
        elif val > 80 or val > -20: return 'background-color: #f8d7da; color: red'
    elif tur in ["ROC", "MOM"]:
        if val > 0: return 'background-color: #d4edda; color: green'
        elif val < 0: return 'background-color: #f8d7da; color: red'
    return ''

def detayli_yorum_getir(df, ind):
    last = df.iloc[-1]; close = last['Close']
    yorum = ""
    
    if ind == "RSI":
        val = last['RSI']
        if val < 30: yorum = f"**AŞIRI SATIM (AL FIRSATI)**. Değer: {val:.2f}"
        elif val > 70: yorum = f"**AŞIRI ALIM (SAT SİNYALİ)**. Değer: {val:.2f}"
        else: yorum = f"**NÖTR/TREND**. Değer: {val:.2f}"
    elif ind == "MACD":
        if last['MACD'] > last['MACD_SIG']: yorum = "**AL SİNYALİ**. MACD sinyali yukarı kesti."
        else: yorum = "**SAT SİNYALİ**. MACD sinyali aşağı kesti."
    elif ind == "FISHER":
        if last['FISHER'] > last['FISHER_SIG']:
            durum = "**GÜÇLÜ AL** (Dip Dönüşü)" if last['FISHER'] < -1.5 else "**AL**"
            yorum = f"{durum}. Fisher pozitif kesişimde."
        else:
            durum = "**GÜÇLÜ SAT** (Tepe Dönüşü)" if last['FISHER'] > 1.5 else "**SAT**"
            yorum = f"{durum}. Fisher negatif kesişimde."
    elif ind in ["SMA", "EMA"]:
        col = 'SMA_20' if ind == "SMA" else 'EMA_50'
        if close > last[col]: yorum = f"**POZİTİF**. Fiyat ortalamanın ({last[col]:.2f}) üzerinde."
        else: yorum = f"**NEGATİF**. Fiyat ortalamanın ({last[col]:.2f}) altında."
    elif ind == "BOLLINGER":
        if close < last['BB_LOW']: yorum = "**GÜÇLÜ AL**. Fiyat alt bandı deldi (Ucuz)."
        elif close > last['BB_UP']: yorum = "**GÜÇLÜ SAT**. Fiyat üst bandı deldi (Pahalı)."
        else: yorum = "**NÖTR**. Bant içi hareket."
    else:
        target_cols = [c for c in df.columns if c.startswith(ind)]
        if target_cols:
            vals = [f"{c}: {last[c]:.2f}" for c in target_cols]
            yorum = f"**{ind} Güncel Değerler:** " + ", ".join(vals)
        elif ind in df.columns:
            yorum = f"**{ind} Değeri:** {last[ind]:.2f}"
        else:
            yorum = "Veri hesaplanamadı."
    return yorum

# -----------------------------------------------------------------------------
# ARAYÜZ
# -----------------------------------------------------------------------------
st.sidebar.title("KONTROL PANELİ")
secilen_mod = st.sidebar.radio("Mod Seçiniz:", ["Tek Hisse Analizi", "Radar (Karşılaştırma)", "Ayarlar & Favoriler"])

# --- MOD 3: AYARLAR VE FAVORİLER ---
if secilen_mod == "Ayarlar & Favoriler":
    st.header("⚙️ Ayarlar ve Favori Yönetimi")
    kayitli_veri = favorileri_yukle()
    mevcut_ind = kayitli_veri.get("indikatorler", [])
    mevcut_his = kayitli_veri.get("hisseler", [])
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Favori Hisseler")
        yeni_hisse = st.text_input("Hisse Kodu Ekle (Örn: ASELS):").upper()
        if st.button("Hisse Ekle"):
            if yeni_hisse:
                if ".IS" not in yeni_hisse and "USD" not in yeni_hisse: yeni_hisse += ".IS"
                if yeni_hisse not in mevcut_his:
                    mevcut_his.append(yeni_hisse)
                    kayitli_veri["hisseler"] = mevcut_his
                    favorileri_kaydet(kayitli_veri)
                    st.success(f"{yeni_hisse} eklendi.")
                    st.rerun()
        st.write("📋 **Mevcut Liste:**")
        silinecek_hisse = st.multiselect("Silmek istediklerinizi seçin:", mevcut_his)
        if silinecek_hisse and st.button("Seçili Hisseleri Sil"):
            for h in silinecek_hisse: mevcut_his.remove(h)
            kayitli_veri["hisseler"] = mevcut_his
            favorileri_kaydet(kayitli_veri)
            st.rerun()

    with col2:
        st.subheader("2. Favori İndikatörler")
        yeni_secimler = st.multiselect("İndikatör Listesi:", INDIKATOR_LISTESI, default=mevcut_ind)
        if st.button("İndikatörleri Kaydet"):
            kayitli_veri["indikatorler"] = yeni_secimler
            favorileri_kaydet(kayitli_veri)
            st.success("İndikatör listesi güncellendi!")

# --- MOD 2: RADAR (KARŞILAŞTIRMA) ---
elif secilen_mod == "Radar (Karşılaştırma)":
    st.header("📡 Piyasa Radarı (Karşılaştırmalı Analiz)")
    kayitli_veri = favorileri_yukle()
    fav_hisseler = kayitli_veri.get("hisseler", [])
    fav_indler = kayitli_veri.get("indikatorler", [])
    
    if not fav_hisseler or not fav_indler:
        st.warning("Favori hisse veya indikatör listeniz boş. Ayarlar sekmesinden ekleme yapınız.")
    else:
        st.write(f"**Takip Listesi:** {', '.join(fav_hisseler)}")
        if st.button("TARAMAYI BAŞLAT", type="primary"):
            veriler = []
            ilerleme = st.progress(0)
            for i, hisse in enumerate(fav_hisseler):
                df = verileri_getir(hisse, "1y", fav_indler)
                if df is not None and not df.empty:
                    last = df.iloc[-1]
                    satir = {"Sembol": hisse, "Fiyat": f"{last['Close']:.2f}"}
                    for ind in fav_indler:
                        val = None
                        if ind in df.columns: val = last[ind]
                        else:
                            for c in df.columns:
                                if c.startswith(ind): val = last[c]; break
                        if val is not None: satir[ind] = f"{val:.2f}"
                        else: satir[ind] = "-"
                    veriler.append(satir)
                ilerleme.progress((i + 1) / len(fav_hisseler))
            ilerleme.empty()
            
            radar_df = pd.DataFrame(veriler)
            if not radar_df.empty:
                st.subheader("Radar Sonuçları")
                styler = radar_df.style
                if "RSI" in radar_df.columns: styler = styler.applymap(lambda x: renk_belirle(x, "RSI"), subset=["RSI"])
                if "CCI" in radar_df.columns: styler = styler.applymap(lambda x: renk_belirle(x, "CCI"), subset=["CCI"])
                st.dataframe(styler, use_container_width=True, height=500)
                st.info("🟢 Yeşil: Al Sinyali / Ucuz | 🔴 Kırmızı: Sat Sinyali / Pahalı")
            else: st.error("Veri alınamadı.")

# --- MOD 1: TEK HİSSE ANALİZİ (KLASİK) ---
else:
    sembol_giris = st.sidebar.text_input("Hisse Sembolü:", "THYAO").upper()
    if ".IS" not in sembol_giris and "USD" not in sembol_giris: sembol_giris += ".IS"
    periyot_secimi = st.sidebar.select_slider("Analiz Süresi", options=["6m", "1y", "2y", "3y", "5y", "max"], value="1y")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("İndikatör Ekle")
    hizli_indikatorler = st.sidebar.multiselect("İndikatör Seç:", INDIKATOR_LISTESI)
    st.sidebar.markdown("---")
    
    if st.sidebar.button("ANALİZİ BAŞLAT", type="primary"): st.session_state['run_analiz'] = True
    
    st.title(f"📊 {sembol_giris} ANALİZ PLATFORMU")

    if st.session_state.get('run_analiz'):
        kayitli = favorileri_yukle()
        fav_ind = kayitli.get("indikatorler", [])
        tum_gosterilecekler = list(set(fav_ind + hizli_indikatorler))
        
        with st.spinner('Veriler İşleniyor...'):
            df = verileri_getir(sembol_giris, periyot_secimi, tum_gosterilecekler)

        if df is None: st.error("Veri alınamadı.")
        else:
            def puanlama_yap_local(df):
                if df is None or df.empty: return None
                last = df.iloc[-1]; close = last['Close']
                t_p = 0; t_m = 0
                t_m+=3; t_p+=3 if close>last['SMA_20'] else 0
                t_m+=3; t_p+=3 if close>last['EMA_50'] else 0
                o_p=0; o_m=0
                o_m+=2; o_p+=2 if last['RSI']<30 else (1 if 50<last['RSI']<70 else 0)
                o_m+=2; o_p+=2 if last['MACD']>last['MACD_SIG'] else 0
                o_m+=2; o_p+=2 if last['FISHER']>last['FISHER_SIG'] else 0
                m_p=0; m_m=0
                m_m+=1; m_p+=1 if last['STOCH_K']<20 and last['STOCH_K']>last['STOCH_D'] else 0
                genel = ((t_p+o_p+m_p)/(t_m+o_m+m_m))*100
                return {"genel": genel, "trend": (t_p/t_m)*100, "osc": (o_p/o_m)*100, "mom": (m_p/m_m)*100}

            skor = puanlama_yap_local(df)
            last = df.iloc[-1]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fiyat", f"{last['Close']:.2f}")
            c2.metric("RSI", f"{last.get('RSI', 50):.2f}")
            durum = "GÜÇLÜ AL" if skor["genel"] >= 70 else ("AL" if skor["genel"] >= 50 else "NÖTR")
            c3.metric("TEKNİK SKOR", f"{skor['genel']:.0f}/100", delta=durum)
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'))
            fig.update_layout(height=500, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            tab1, tab2, tab3, tab4 = st.tabs(["SKOR RAPORU", "İNDİKATÖRLER", "VERİLER", "ŞİRKET KARTI"])

            with tab1:
                c_t, c_o, c_m = st.columns(3)
                c_t.info(f"TREND: %{skor['trend']:.0f}"); c_t.progress(int(skor['trend']))
                c_o.warning(f"OSİLATÖR: %{skor['osc']:.0f}"); c_o.progress(int(skor['osc']))
                c_m.success(f"MOMENTUM: %{skor['mom']:.0f}"); c_m.progress(int(skor['mom']))

            with tab2:
                for ind in tum_gosterilecekler:
                    st.subheader(f"📌 {ind} Analizi")
                    yorum = detayli_yorum_getir(df, ind)
                    st.info(f"**Durum:** {yorum}")
                    
                    fig_ind = go.Figure()
                    if ind in df.columns: fig_ind.add_trace(go.Scatter(x=df.index, y=df[ind], name=ind))
                    else:
                        for col in df.columns:
                            if col.startswith(ind): fig_ind.add_trace(go.Scatter(x=df.index, y=df[col], name=col))
                    
                    if ind=="RSI": 
                        fig_ind.add_hline(y=70, line_color="red", line_dash="dash")
                        fig_ind.add_hline(y=30, line_color="green", line_dash="dash")
                    
                    fig_ind.update_layout(height=300, margin=dict(t=0,b=0,l=0,r=0))
                    st.plotly_chart(fig_ind, use_container_width=True, key=f"c_{ind}")
                    st.divider()

            with tab3: st.dataframe(df.style.highlight_max(axis=0), use_container_width=True)

            with tab4:
                if ".IS" in sembol_giris:
                    is_veri = is_yatirim_verileri(sembol_giris)
                    if is_veri:
                        # --- FON YÖNETİCİSİ ANALİZ MATRİSİ (EKLEME BURADA) ---
                        st.subheader("🏛️ Fon Yöneticisi Analiz Matrisi")
                        if is_veri["fon_matrisi"] is not None:
                            arama_matris = st.text_input("Matris İçinde Unsur Ara (Örn: F/K, Beta, Borç):", key="search_mat")
                            filtre_df = is_veri["fon_matrisi"][is_veri["fon_matrisi"]['Unsur'].str.contains(arama_matris, case=False)] if arama_matris else is_veri["fon_matrisi"]
                            st.table(filtre_df)
                        
                        st.divider()
                        
                        c1, c2 = st.columns(2)
                        if is_veri["temettu"] is not None: 
                            st.subheader("💰 Temettü Geçmişi")
                            c1.dataframe(is_veri["temettu"])
                        if is_veri["sermaye"] is not None: 
                            st.subheader("📈 Sermaye Artırımları")
                            c2.dataframe(is_veri["sermaye"])
                        if is_veri["oranlar"] is not None: 
                            st.subheader("📊 Finansal Oranlar")
                            st.dataframe(is_veri["oranlar"])
                    else: st.error("İş Yatırım verileri çekilemedi.")
                else: st.warning("Şirket kartı verileri sadece BIST hisseleri için mevcuttur.")
