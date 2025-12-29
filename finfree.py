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
warnings.filterwarnings("ignore")

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
    [data-testid="stSidebar"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    .main-header { text-align: center; font-size: 2.5rem; font-weight: 800; color: #1E3A8A; margin-top: -50px; }
    .sub-header { text-align: center; font-size: 1.1rem; color: #64748B; margin-bottom: 20px; }
    div.stButton > button:first-child { height: 3.5em; width: 100%; font-weight: bold; border-radius: 8px; border: 1px solid #d1d5db; transition: all 0.3s ease; }
    div.stButton > button:hover { border-color: #1E3A8A; color: #1E3A8A; background-color: #f3f4f6; }
    .stTextInput > div > div > input { text-align: center; font-size: 1.1rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. SABİTLER VE VERİ LİSTELERİ
# -----------------------------------------------------------------------------
FAVORI_DOSYASI = "favoriler_v5.json"

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

TUM_INDIKATORLER = [
    "RSI", "MACD", "FISHER", "BOLLINGER", "SMA", "EMA", "WMA", "HMA",
    "STOCH", "STOCHRSI", "CCI", "MOM", "WILLR", "ADX", "OBV", "ATR",
    "SUPERTREND", "ICHIMOKU", "KC", "DC", "TRIX", "UO"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
]

# -----------------------------------------------------------------------------
# 4. KER ÖLÇÜTÜ ANALİZ MOTORU (YENİ EKLEME - SİSTEMİN KALBİ)
# -----------------------------------------------------------------------------
def ker_olcuyu_hesapla(tk_info):
    """Kullanıcının özel yatırım kriterlerine göre puanlama yapar."""
    skor = 0
    durum = "GEÇTİ"
    sabikalar = []
    
    # 1. Brüt Kar Marjı
    gross_margin = tk_info.get('grossMargins', 0) * 100
    if gross_margin < 20:
        durum = "ELENDİ"; sabikalar.append("Brüt Kar Marjı < %20")
    elif gross_margin > 35: skor += 1
    
    # 2. Net Kar Oranı
    net_margin = tk_info.get('profitMargins', 0) * 100
    if net_margin < 13:
        durum = "ELENDİ"; sabikalar.append("Net Kar Oranı < %13")
    elif net_margin > 18: skor += 1
    
    # 3. Cari Oran
    curr_ratio = tk_info.get('currentRatio', 0)
    if 1.5 <= curr_ratio <= 2.0: skor += 1
    
    # 4. Özkaynak Karlılığı (ROE)
    roe = tk_info.get('returnOnEquity', 0) * 100
    if roe < 15:
        durum = "ELENDİ"; sabikalar.append("ROE < %15")
    else: skor += 1 # "Öz Sermaye Karlılığı varsa +1"
    
    # 5. F/K (Fiyat / Kazanç)
    fk = tk_info.get('forwardPE', 100)
    if fk < 10: skor += 1
    
    # 6. PD/DD (Piyasa Defter Değeri)
    pddd = tk_info.get('priceToBook', 0)
    if pddd >= 1: skor += 1
    
    # 7. FAVÖK (EBITDA) Marjı
    ebitda_margin = tk_info.get('ebitdaMargins', 0) * 100
    if ebitda_margin < 10:
        durum = "ELENDİ"; sabikalar.append("FAVÖK Marjı < %10")
    elif ebitda_margin > 15: skor += 1
    
    # 8. Net Borç / FAVÖK
    ebitda = tk_info.get('ebitda', 1)
    net_borc = tk_info.get('totalDebt', 0) - tk_info.get('totalCash', 0)
    borc_favok = net_borc / ebitda if ebitda != 0 else 5
    if borc_favok < 2.0: skor += 1
    elif borc_favok > 4.5:
        durum = "ELENDİ"; sabikalar.append("Borç/FAVÖK > 4.5")
    
    # 9. Satış Artışı ve Diğerleri (Bilgi varsa +1)
    if tk_info.get('revenueGrowth', 0) > 0: skor += 1
    
    return {"skor": skor, "durum": durum, "sabikalar": sabikalar}

# -----------------------------------------------------------------------------
# 5. YARDIMCI FONKSİYONLAR
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
# 6. İŞ YATIRIM VERİ KAZIMA (SCRAPER)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    time.sleep(random.uniform(0.5, 1.2))
    saf_sembol = sembol.replace(".IS", "").replace(".is", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    veriler = {"temettu": None, "sermaye": None, "oranlar": None, "fon_matrisi": None, "ozet": {}, "tk_info": {}}
    
    session = requests.Session()
    retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"}
    
    try:
        tk = yf.Ticker(sembol)
        ticker_info = tk.info if tk.info else {}
        veriler["tk_info"] = ticker_info
        veriler["ozet"] = {
            "F/K": ticker_info.get('forwardPE', 0),
            "PD/DD": ticker_info.get('priceToBook', 0),
            "ROE": ticker_info.get('returnOnEquity', 0) * 100 if ticker_info.get('returnOnEquity') else 0,
            "Beta": ticker_info.get('beta', 0)
        }
        
        # Fon Matrisi ve Tablolar (Orijinal Kod Korundu)
        matris_data = {
            "Kategori": ["Temel Analiz", "Temel Analiz", "Temel Analiz", "Risk Analizi", "Risk Analizi", "Yönetim", "Yönetim", "Likidite", "Likidite"],
            "Unsur": ["Kârlılık (ROE)", "Borç Yapısı", "F/K Oranı", "Beta Katsayısı", "Volatilite", "Kurumsal Yönetim", "Temettü Verimi", "İşlem Hacmi", "Halka Açıklık"],
            "Değer": [f"%{veriler['ozet']['ROE']:.2f}", ticker_info.get('debtToEquity', 'N/A'), f"{veriler['ozet']['F/K']:.2f}", f"{veriler['ozet']['Beta']:.2f}", "N/A", "N/A", "N/A", "N/A", "N/A"]
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
    except: return veriler

# -----------------------------------------------------------------------------
# 7. TEKNİK VERİ MOTORU
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def verileri_getir(sembol, periyot, secilen_favoriler=None):
    if secilen_favoriler is None: secilen_favoriler = ["RSI", "MACD"]
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
        close, high, low = df['Close'], df['High'], df['Low']
        df['RSI'] = ta.rsi(close, length=14)
        macd_calc = ta.macd(close)
        df['MACD'] = macd_calc['MACD_12_26_9']
        df['MACD_SIG'] = macd_calc['MACDs_12_26_9']
        df['SMA_20'] = ta.sma(close, length=20)
        df['EMA_50'] = ta.ema(close, length=50)
        df['CCI'] = ta.cci(high, low, close)
        for ind in secilen_favoriler:
            ind_low = ind.lower()
            if ind_low not in [c.lower() for c in df.columns]:
                try:
                    if hasattr(df.ta, ind_low): getattr(df.ta, ind_low)(append=True)
                except: pass
        return df.dropna()
    except: return None

# -----------------------------------------------------------------------------
# 8. ANA ARAYÜZ (LAYOUT)
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
            t_veriler.append({"Sembol": h.replace(".IS",""), "Fiyat": l['Close'], "Sinyal Puanı": p, "RSI": l['RSI'], "F/K": temel.get('F/K', 0)})
        bar.progress((i+1)/len(h_list))
    if t_veriler:
        st.dataframe(pd.DataFrame(t_veriler).sort_values("Sinyal Puanı", ascending=False), use_container_width=True)

elif st.session_state.sayfa == 'hisse_detay':
    s = st.session_state.secili_hisse
    st.button("⬅️ Geri", on_click=git, args=('ana_sayfa',))
    
    f_data = is_yatirim_verileri(s)
    df = verileri_getir(s, st.session_state.zaman_araligi, favorileri_yukle().get("indikatorler"))
    
    if df is not None:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["GENEL BAKIŞ", "DETAYLI İNDİKATÖRLER", "FONCU MATRİSİ", "FİNANSALLAR", "🚩 KER ÖLÇÜTÜ"])
        
        with tab1:
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
            st.plotly_chart(fig, use_container_width=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Son Fiyat", f"{df.iloc[-1]['Close']:.2f}")
            c2.metric("RSI", f"{df.iloc[-1]['RSI']:.2f}")
            c3.metric("Trend", "YÜKSELİŞ" if df.iloc[-1]['Close'] > df.iloc[-1]['SMA_20'] else "DÜŞÜŞ")
        
        with tab2:
            for ind in df.columns:
                if ind not in ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']:
                    st.write(f"### {ind} Grafiği")
                    f_ind = go.Figure(go.Scatter(x=df.index, y=df[ind], name=ind))
                    st.plotly_chart(f_ind, use_container_width=True, key=f"c_{ind}_{s}")

        with tab3:
            if f_data.get("fon_matrisi") is not None: st.dataframe(f_data["fon_matrisi"])
        
        with tab4:
            if f_data.get("oranlar") is not None: st.write("#### Oranlar"); st.dataframe(f_data["oranlar"])
            if f_data.get("temettu") is not None: st.write("#### Temettü"); st.dataframe(f_data["temettu"])

        with tab5:
            st.subheader("🏁 KER ÖLÇÜTÜ DERİN ANALİZ RAPORU")
            
            if f_data.get("tk_info"):
                analiz = ker_olcuyu_hesapla(f_data["tk_info"])
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Toplam Ker Puanı", f"{analiz['skor']} / 13")
                    if analiz['durum'] == "GEÇTİ":
                        st.success("✅ ŞİRKET KER ÖLÇÜTÜNDEN GEÇTİ")
                    else:
                        st.error("❌ ŞİRKET KER ÖLÇÜTÜNDEN ELENDİ")
                
                with col_b:
                    if analiz['sabikalar']:
                        st.write("#### ⚠️ Elenme Nedenleri (Sabıkalar):")
                        for s in analiz['sabikalar']:
                            st.write(f"- {s}")
                    else:
                        st.write("#### 💎 Şirket Tüm Filtrelerden Temiz Çıktı")
            else:
                st.warning("Bu raporu oluşturmak için gerekli finansal veriler Yahoo API'den çekilemedi.")
    else: st.error("Veri çekilemedi.")
