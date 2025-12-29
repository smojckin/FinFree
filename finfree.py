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
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -----------------------------------------------------------------------------
# 1. AYARLAR VE YAPILANDIRMA
# -----------------------------------------------------------------------------
# Uyarıları susturuyoruz, ekran kirlenmesin
warnings.filterwarnings("ignore")

# Sayfa ayarları: Geniş mod ve sidebar kapalı başlangıç
st.set_page_config(
    page_title="BORSA İSTANBUL RADARI",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="📈"
)

# -----------------------------------------------------------------------------
# 2. CSS İLE MODERN GÖRÜNÜM (TAM LİSTE)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* Yan menüyü (Sidebar) tamamen yok ediyoruz */
    [data-testid="stSidebar"] {
        display: none;
    }
    section[data-testid="stSidebar"] {
        display: none;
    }
    
    /* Üst Başlık Stilleri */
    .main-header {
        text-align: center; 
        font-size: 2.5rem; 
        font-weight: 800; 
        color: #1E3A8A; 
        margin-top: -50px;
    }
    
    .sub-header {
        text-align: center; 
        font-size: 1.1rem; 
        color: #64748B; 
        margin-bottom: 20px;
    }

    /* Butonları Güzelleştirme */
    div.stButton > button:first-child {
        height: 3.5em;
        width: 100%; 
        font-weight: bold;
        border-radius: 8px;
        border: 1px solid #d1d5db;
        transition: all 0.3s ease;
    }
    
    div.stButton > button:hover {
        border-color: #1E3A8A;
        color: #1E3A8A;
        background-color: #f3f4f6;
    }

    /* Input Alanlarını Ortalama */
    .stTextInput > div > div > input {
        text-align: center; 
        font-size: 1.1rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. SABİTLER VE VERİ LİSTELERİ
# -----------------------------------------------------------------------------
FAVORI_DOSYASI = "favoriler_v5.json"

# Endeks listelerini olduğu gibi bırakıyoruz
ENDEKSLER = {
    "BIST 30 (DEVLER)": [
        "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "BIMAS.IS", "EKGYO.IS", 
        "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", 
        "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KOZAL.IS", "KRDMD.IS", 
        "PETKM.IS", "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", 
        "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", 
        "TTKOM.IS", "TUPRS.IS", "VAKBN.IS", "VESTL.IS", "YKBNK.IS"
    ],
    "BANKA (XBNK)": [
        "AKBNK.IS", "GARAN.IS", "ISCTR.IS", "VAKBN.IS", "YKBNK.IS", 
        "HALKB.IS", "TSKB.IS", "ALBRK.IS", "SKBNK.IS"
    ],
    "TEKNOLOJİ (XUTEK)": [
        "ASELS.IS", "LOGO.IS", "KFEIN.IS", "NETAS.IS", "ALCTL.IS", 
        "LINK.IS", "ARENA.IS", "ESCOM.IS", "MIATK.IS", "VBTYZ.IS", 
        "FONET.IS", "ARDYZ.IS"
    ],
    "ENERJİ (XELKT)": [
        "ENJSA.IS", "ZOREN.IS", "AKSEN.IS", "AYDEM.IS", "GWIND.IS", 
        "ODAS.IS", "NATEN.IS", "CANTE.IS", "EUPWR.IS", "ASTOR.IS", 
        "ALFAS.IS", "SMRTG.IS"
    ]
}

# TradingView benzeri genişletilmiş havuz
TUM_INDIKATORLER = [
    "RSI", "MACD", "FISHER", "BOLLINGER", "SMA", "EMA", "WMA", "HMA",
    "STOCH", "STOCHRSI", "CCI", "MOM", "WILLR", "ADX", "OBV", "ATR",
    "SUPERTREND", "ICHIMOKU", "KC", "DC", "TRIX", "UO"
]

# Maskeleme İçin User-Agent Listesi
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
]

# -----------------------------------------------------------------------------
# 4. YARDIMCI FONKSİYONLAR
# -----------------------------------------------------------------------------
def favorileri_yukle():
    varsayilan = {"indikatorler": ["RSI", "MACD", "SMA"], "hisseler": ["THYAO.IS", "ASELS.IS"]}
    if os.path.exists(FAVORI_DOSYASI):
        try:
            with open(FAVORI_DOSYASI, 'r') as f: return json.load(f)
        except: pass
    return varsayilan

def favorileri_kaydet(veri):
    with open(FAVORI_DOSYASI, 'w') as f: json.dump(veri, f)

# -----------------------------------------------------------------------------
# 5. İŞ YATIRIM VERİ KAZIMA (SCRAPER) - MASKELEME VE GÜVENLİ
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    # Ban yememek için rastgele kısa bekleme
    time.sleep(random.uniform(0.5, 1.2))
    
    saf_sembol = sembol.replace(".IS", "").replace(".is", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    veriler = {"temettu": None, "sermaye": None, "oranlar": None, "fon_matrisi": None, "ozet": {}}
    
    session = requests.Session()
    retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    
    # Gerçek kullanıcı maskelemesi
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.isyatirim.com.tr/"
    }
    
    try:
        tk = yf.Ticker(sembol)
        ticker_info = tk.info if tk.info else {}
        veriler["ozet"] = {
            "F/K": ticker_info.get('forwardPE', 0),
            "PD/DD": ticker_info.get('priceToBook', 0),
            "ROE": ticker_info.get('returnOnEquity', 0) * 100 if ticker_info.get('returnOnEquity') else 0,
            "Beta": ticker_info.get('beta', 0)
        }

        matris_data = {
            "Kategori": ["Temel Analiz", "Temel Analiz", "Temel Analiz", "Risk Analizi", "Risk Analizi", "Yönetim", "Yönetim", "Likidite", "Likidite"],
            "Unsur": ["Kârlılık (ROE)", "Borç Yapısı", "F/K Oranı", "Beta Katsayısı", "Volatilite", "Kurumsal Yönetim", "Temettü Verimi", "İşlem Hacmi", "Halka Açıklık"],
            "Değer": [
                f"%{ticker_info.get('returnOnEquity', 0)*100:.2f}" if ticker_info.get('returnOnEquity') else "N/A",
                ticker_info.get('debtToEquity', 'N/A'),
                f"{ticker_info.get('forwardPE', 0):.2f}" if ticker_info.get('forwardPE') else "N/A",
                f"{ticker_info.get('beta', 0):.2f}" if ticker_info.get('beta') else "N/A",
                f"%{ticker_info.get('52WeekChange', 0)*100:.2f}" if ticker_info.get('52WeekChange') else "N/A",
                "İncelenmeli",
                f"%{ticker_info.get('dividendYield', 0)*100:.2f}" if ticker_info.get('dividendYield') else "N/A",
                f"{ticker_info.get('averageVolume', 0):,}", "N/A"
            ]
        }
        veriler["fon_matrisi"] = pd.DataFrame(matris_data)

        response = session.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            tablolar = pd.read_html(response.text, match=".", decimal=",", thousands=".")
            for df in tablolar:
                cols = [str(c).lower() for c in df.columns]
                if any("temettü" in c for c in cols): veriler["temettu"] = df
                elif any("bedelli" in c for c in cols): veriler["sermaye"] = df
                elif any("f/k" in c for c in cols): veriler["oranlar"] = df
        return veriler
    except:
        return veriler

# -----------------------------------------------------------------------------
# 6. TEKNİK VERİ MOTORU (ELLE YAZILANLAR + KÜTÜPHANE)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def verileri_getir(sembol, periyot, secilen_favoriler=None):
    if secilen_favoriler is None: secilen_favoriler = ["RSI", "MACD", "SMA", "EMA"]
    download_period = "5y" if periyot == "3y" else periyot
    
    df = None
    for _ in range(3):
        try:
            df = yf.download(sembol, period=download_period, interval="1d", progress=False, timeout=15)
            if df is not None and not df.empty: break
            time.sleep(random.uniform(1, 2))
        except: continue

    if df is None or df.empty: return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        if periyot == "3y":
            start_date = df.index[-1] - pd.DateOffset(years=3)
            df = df[df.index >= start_date]
            
        close, high, low = df['Close'], df['High'], df['Low']
        
        # --- ELLE YAZDIĞIN ÖZEL İNDİKATÖRLER (KORUNDU) ---
        df['RSI'] = ta.rsi(close, length=14)
        macd_calc = ta.macd(close)
        df['MACD'] = macd_calc['MACD_12_26_9']
        df['MACD_SIG'] = macd_calc['MACDs_12_26_9']
        df['SMA_20'] = ta.sma(close, length=20)
        df['EMA_50'] = ta.ema(close, length=50)
        df['CCI'] = ta.cci(high, low, close)
        
        # --- KÜTÜPHANEDEN DİNAMİK GELENLER (YENİ) ---
        for ind in secilen_favoriler:
            ind_low = ind.lower()
            if ind_low not in [c.lower() for c in df.columns]:
                try:
                    if hasattr(df.ta, ind_low):
                        getattr(df.ta, ind_low)(append=True)
                    else:
                        if ind == "BOLLINGER": df.ta.bbands(append=True)
                        elif ind == "SUPERTREND": df.ta.supertrend(append=True)
                        elif ind == "ICHIMOKU": df.ta.ichimoku(append=True)
                except: pass
        
        return df.dropna()
    except: return None

# -----------------------------------------------------------------------------
# 7. RENKLENDİRME VE STİL (KORUNDU)
# -----------------------------------------------------------------------------
def matris_renklendir(val, unsur):
    try:
        clean_v = str(val).replace('%', '').replace(',', '.')
        num = float(clean_v)
        if "F/K" in unsur: return 'background-color: #d4edda; color: green' if 0 < num < 10 else ('background-color: #f8d7da; color: red' if num > 25 else '')
        if "ROE" in unsur: return 'background-color: #d4edda; color: green' if num > 20 else ('background-color: #f8d7da; color: red' if num < 5 else '')
        if "Beta" in unsur: return 'color: red' if num > 1.5 else ('color: green' if num < 1.0 else '')
    except: pass
    return ''

def tablo_renklendir(val, col_name):
    try:
        v = float(str(val).replace('%',''))
        if col_name == "Sinyal Puanı": return 'background-color: #28a745; color: white' if v >= 70 else ('background-color: #dc3545; color: white' if v <= 30 else '')
        elif col_name == "RSI": return 'color: green; font-weight: bold' if v < 30 else ('color: red; font-weight: bold' if v > 70 else '')
        elif col_name == "F/K": return 'color: green; font-weight: bold' if 0 < v < 10 else ('color: red; font-weight: bold' if v > 20 else '')
    except: return ''
    return ''

def detayli_yorum_getir(df, ind):
    last = df.iloc[-1]
    if "RSI" in ind:
        val = last[ind]
        if val < 30: return f"AŞIRI SATIM (AL FIRSATI) - {val:.2f}"
        elif val > 70: return f"AŞIRI ALIM (SAT SİNYALİ) - {val:.2f}"
        return f"NÖTR BÖLGE - {val:.2f}"
    elif "MACD" in ind: return "AL SİNYALİ" if last['MACD'] > last['MACD_SIG'] else "SAT SİNYALİ"
    return "Analiz Yapıldı"

# -----------------------------------------------------------------------------
# 8. ANA ARAYÜZ (TAM YAPI)
# -----------------------------------------------------------------------------


if 'sayfa' not in st.session_state: st.session_state.sayfa = 'ana_sayfa'
if 'secili_hisse' not in st.session_state: st.session_state.secili_hisse = ''
if 'secili_endeks' not in st.session_state: st.session_state.secili_endeks = ''
if 'zaman_araligi' not in st.session_state: st.session_state.zaman_araligi = '1y'

def git(sayfa, veri=None):
    st.session_state.sayfa = sayfa
    if sayfa == 'hisse_detay': st.session_state.secili_hisse = veri
    if sayfa == 'endeks_detay': st.session_state.secili_endeks = veri

c_logo, c_arama, c_zaman = st.columns([1, 4, 1])
with c_logo:
    if st.button("🏠 ANA SAYFA", use_container_width=True): st.session_state.sayfa = 'ana_sayfa'

with c_arama:
    arama_girdisi = st.text_input("Hisse Ara:", placeholder="THYAO, ASELS...", label_visibility="collapsed").upper()
    if arama_girdisi:
        if ".IS" not in arama_girdisi: arama_girdisi += ".IS"
        git('hisse_detay', arama_girdisi)

with c_zaman:
    st.session_state.zaman_araligi = st.selectbox("Süre", ["1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "max"], index=3, label_visibility="collapsed")

with st.expander("🛠️ ANALİZ AYARLARI & FAVORİLER"):
    kayitli_ayarlar = favorileri_yukle()
    c_set1, c_set2 = st.columns(2)
    with c_set1:
        st.subheader("İndikatör Havuzu")
        secili_indikatortler = st.multiselect("Grafiklere Eklenecekler:", TUM_INDIKATORLER, default=kayitli_ayarlar.get("indikatorler", ["RSI", "MACD"]))
        if st.button("Ayarları Kaydet"):
            kayitli_ayarlar["indikatorler"] = secili_indikatortler
            favorileri_kaydet(kayitli_ayarlar)
            st.success("Kaydedildi!")
    with c_set2:
        st.subheader("Favori Hisselerim")
        yeni_f = st.text_input("Ekle:").upper()
        if st.button("Listeye Ekle") and yeni_f:
            if ".IS" not in yeni_f: yeni_f += ".IS"
            m = kayitli_ayarlar.get("hisseler", [])
            if yeni_f not in m:
                m.append(yeni_f); kayitli_ayarlar["hisseler"] = m; favorileri_kaydet(kayitli_ayarlar); st.rerun()

st.divider()

# -----------------------------------------------------------------------------
# 9. SAYFA İÇERİKLERİ
# -----------------------------------------------------------------------------
if st.session_state.sayfa == 'ana_sayfa':
    st.markdown("<h1 class='main-header'>BORSA İSTANBUL RADARI</h1>", unsafe_allow_html=True)
    cols = st.columns(len(ENDEKSLER))
    for i, (isim, liste) in enumerate(ENDEKSLER.items()):
        with cols[i]:
            if st.button(f"📈 {isim}\n({len(liste)} Hisse)", key=f"m_btn_{i}"): git('endeks_detay', isim)
    
    favs = favorileri_yukle().get("hisseler", [])
    if favs:
        st.subheader("⭐ Favori Listeniz")
        f_cols = st.columns(6)
        for i, fh in enumerate(favs):
            if f_cols[i % 6].button(fh, key=f"f_{fh}"): git('hisse_detay', fh)

elif st.session_state.sayfa == 'endeks_detay':
    st.button("⬅️ Ana Sayfa", on_click=git, args=('ana_sayfa',))
    st.markdown(f"## 🔍 {st.session_state.secili_endeks} TARAMA RAPORU")
    h_list = ENDEKSLER[st.session_state.secili_endeks]
    t_veriler = []
    bar = st.progress(0)
    for i, h in enumerate(h_list):
        df = verileri_getir(h, "6mo", [])
        raw_f = is_yatirim_verileri(h)
        temel = raw_f.get("ozet", {}) if raw_f else {}
        if df is not None:
            l = df.iloc[-1]
            p = 50 + (20 if l['RSI'] < 30 else (-20 if l['RSI'] > 70 else 0))
            t_veriler.append({
                "Sembol": h.replace(".IS",""), "Fiyat": l['Close'], "Sinyal Puanı": p, 
                "RSI": l['RSI'], "F/K": temel.get('F/K', 0), "ROE (%)": temel.get('ROE', 0)
            })
        bar.progress((i+1)/len(h_list))
    if t_veriler:
        res_df = pd.DataFrame(t_veriler).sort_values("Sinyal Puanı", ascending=False)
        st.dataframe(res_df.style.apply(lambda x: [tablo_renklendir(v, col) for col, v in zip(x.index, x)], axis=1), use_container_width=True, height=700)

elif st.session_state.sayfa == 'hisse_detay':
    s = st.session_state.secili_hisse
    st.button("⬅️ Geri", on_click=git, args=('ana_sayfa',))
    df = verileri_getir(s, st.session_state.zaman_araligi, favorileri_yukle().get("indikatorler"))
    
    if df is not None:
        tab1, tab2, tab3, tab4 = st.tabs(["GENEL BAKIŞ", "DETAYLI İNDİKATÖRLER", "FONCU MATRİSİ", "FİNANSALLAR"])
        with tab1:
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='blue', width=1)))
            st.plotly_chart(fig, use_container_width=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Son Fiyat", f"{df.iloc[-1]['Close']:.2f}")
            c2.metric("RSI", f"{df.iloc[-1]['RSI']:.2f}")
            c3.metric("Trend", "YÜKSELİŞ" if df.iloc[-1]['Close'] > df.iloc[-1]['SMA_20'] else "DÜŞÜŞ")
            c4.metric("MACD", "AL" if df.iloc[-1]['MACD'] > df.iloc[-1]['MACD_SIG'] else "SAT")
        
        with tab2:
            # Hem senin elle yazdıkların hem de kütüphaneden gelenlerin hepsi burada çizilir
            for ind in df.columns:
                if ind not in ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']:
                    st.write(f"### {ind} Grafiği")
                    st.info(detayli_yorum_getir(df, ind))
                    f_ind = go.Figure(go.Scatter(x=df.index, y=df[ind], name=ind))
                    st.plotly_chart(f_ind, use_container_width=True, key=f"c_{ind}_{s}")

        with tab3:
            f_data = is_yatirim_verileri(s)
            if f_data and f_data.get("fon_matrisi") is not None:
                st.dataframe(f_data["fon_matrisi"].style.apply(lambda x: [matris_renklendir(x['Değer'], x['Unsur']) if col == 'Değer' else '' for col in x.index], axis=1), use_container_width=True)
            else: st.warning("Veri çekilemedi.")

        with tab4:
            f_data = is_yatirim_verileri(s)
            if f_data:
                if f_data.get("oranlar") is not None: st.write("#### Finansal Oranlar"); st.dataframe(f_data["oranlar"])
                if f_data.get("temettu") is not None: st.write("#### Temettü"); st.dataframe(f_data["temettu"])
                if f_data.get("sermaye") is not None: st.write("#### Sermaye"); st.dataframe(f_data["sermaye"])
