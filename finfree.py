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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Uyarıları sustur
warnings.filterwarnings("ignore")

# --- AYARLAR (Sidebar Kapalı Başlıyor) ---
st.set_page_config(
    page_title="PROFESYONEL BORSA ANALİZİ",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS İLE MODERN GÖRÜNÜM (Tasarım Ayarları) ---
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;} /* Sidebarı tamamen gizle */
    .stTextInput > div > div > input {text-align: center; font-size: 1.2rem;}
    .big-font {font-size:20px !important; font-weight: bold;}
    .main-header {text-align: center; font-size: 3rem; font-weight: 800; color: #1E3A8A;}
    .sub-header {text-align: center; font-size: 1.2rem; color: #64748B; margin-bottom: 2rem;}
    div.stButton > button:first-child {
        height: 3em;
        width: 100%; 
        font-weight: bold;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- SABİTLER ---
FAVORI_DOSYASI = "favoriler_v3.json"

# Endeks İçerikleri (Otomatik Tarama İçin)
ENDEKSLER = {
    "BIST 30": ["AKBNK.IS", "ARCLK.IS", "ASELS.IS", "BIMAS.IS", "EKGYO.IS", "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KOZAL.IS", "KRDMD.IS", "PETKM.IS", "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TUPRS.IS", "VAKBN.IS", "VESTL.IS", "YKBNK.IS"],
    "BIST 10 (BANKA)": ["AKBNK.IS", "GARAN.IS", "ISCTR.IS", "VAKBN.IS", "YKBNK.IS", "HALKB.IS", "TSKB.IS", "ALBRK.IS", "SKBNK.IS"],
    "TEKNOLOJİ": ["ASELS.IS", "LOGO.IS", "KFEIN.IS", "NETAS.IS", "ALCTL.IS", "LINK.IS", "ARENA.IS", "ESCOM.IS", "MIATK.IS", "VBTYZ.IS"],
    "ENERJİ": ["ENJSA.IS", "ZOREN.IS", "AKSEN.IS", "AYDEM.IS", "GWIND.IS", "ODAS.IS", "NATEN.IS", "CANTE.IS", "EUPWR.IS", "ASTOR.IS"]
}

INDIKATOR_LISTESI = [
    "RSI", "MACD", "FISHER", "BOLLINGER", "SMA", "EMA", "STOCH", "CCI", "MFI", "ATR",
    "ADX", "WILLIAMS", "ROC", "MOM", "OBV", "ULTIMATE", "CHAIKIN", "PARABOLIC", "ICHIMOKU", "TRIX"
]

# --- YARDIMCI FONKSİYONLAR (AYNEN KORUNDU) ---
def favorileri_yukle():
    varsayilan = {"indikatorler": ["RSI", "MACD", "SMA"], "hisseler": ["THYAO.IS", "ASELS.IS", "GARAN.IS"]}
    if os.path.exists(FAVORI_DOSYASI):
        try:
            with open(FAVORI_DOSYASI, 'r') as f: return json.load(f)
        except: return varsayilan
    return varsayilan

def favorileri_kaydet(veri):
    with open(FAVORI_DOSYASI, 'w') as f: json.dump(veri, f)

# --- İŞ YATIRIM SCRAPER (ZIRHLI VE HİBRİT) ---
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    saf_sembol = sembol.replace(".IS", "").replace(".is", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    veriler = {"temettu": None, "sermaye": None, "oranlar": None, "fon_matrisi": None, "ozet": {}}
    
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    
    try:
        tk = yf.Ticker(sembol)
        info = tk.info if tk.info else {}
        
        # Özet Veri (Tarama Tablosu İçin)
        veriler["ozet"] = {
            "F/K": info.get('forwardPE', 0),
            "PD/DD": info.get('priceToBook', 0),
            "ROE": info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            "Beta": info.get('beta', 0)
        }

        # Fon Matrisi
        matris_data = {
            "Kategori": ["Temel", "Temel", "Temel", "Risk", "Risk", "Yönetim", "Yönetim", "Likidite", "Likidite"],
            "Unsur": ["Kârlılık (ROE)", "Borç", "F/K", "Beta", "Volatilite", "Yönetim", "Temettü", "Hacim", "Float"],
            "Değer": [
                f"%{info.get('returnOnEquity', 0)*100:.2f}" if info.get('returnOnEquity') else "N/A",
                info.get('debtToEquity', 'N/A'),
                f"{info.get('forwardPE', 0):.2f}" if info.get('forwardPE') else "N/A",
                f"{info.get('beta', 0):.2f}" if info.get('beta') else "N/A",
                f"%{info.get('52WeekChange', 0)*100:.2f}" if info.get('52WeekChange') else "N/A",
                "Kurumsal",
                f"%{info.get('dividendYield', 0)*100:.2f}" if info.get('dividendYield') else "N/A",
                f"{info.get('averageVolume', 0):,}",
                "N/A"
            ]
        }
        veriler["fon_matrisi"] = pd.DataFrame(matris_data)

        resp = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
        if resp.status_code == 200:
            tbls = pd.read_html(resp.text, decimal=",", thousands=".")
            for df in tbls:
                cols = [str(c).lower() for c in df.columns]
                if any("temettü" in c for c in cols): veriler["temettu"] = df
                elif any("sermaye" in c for c in cols): veriler["sermaye"] = df
                elif any("f/k" in c for c in cols): veriler["oranlar"] = df
        return veriler
    except: return veriler

# --- VERİ HAZIRLAMA MOTORU ---
@st.cache_data(ttl=600)
def verileri_getir(sembol, periyot="1y", secilen_favoriler=None):
    if secilen_favoriler is None: secilen_favoriler = ["RSI", "MACD", "SMA", "EMA"]
    aralik = "1d"
    df = None
    for _ in range(3):
        try:
            df = yf.download(sembol, period=periyot, interval=aralik, progress=False, timeout=15)
            if df is not None and not df.empty: break
            time.sleep(1)
        except: continue

    if df is None or df.empty: return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        close = df['Close']; high = df['High']; low = df['Low']
        
        # Temel İndikatörler (Hızlı Tarama İçin)
        df['RSI'] = ta.rsi(close, length=14)
        macd = ta.macd(close)
        df['MACD'] = macd['MACD_12_26_9']; df['MACD_SIG'] = macd['MACDs_12_26_9']
        df['SMA_20'] = ta.sma(close, length=20)
        df['EMA_50'] = ta.ema(close, length=50)
        df['CCI'] = ta.cci(high, low, close)
        
        # Detaylı Analiz İçin Diğerleri
        for ind in secilen_favoriler:
            if ind not in df.columns and hasattr(df.ta, ind.lower()):
                try: getattr(df.ta, ind.lower())(append=True)
                except: pass

        return df.dropna()
    except: return None

# --- RENKLENDİRME FONKSİYONLARI ---
def renk_belirle(val, tur):
    try: val = float(val)
    except: return ""
    if tur == "RSI": return 'background-color: #d4edda; color: green' if val < 30 else ('background-color: #f8d7da; color: red' if val > 70 else '')
    return ''

def matris_renklendir(val, unsur):
    try:
        clean_val = str(val).replace('%', '').replace(',', '.')
        num_val = float(clean_val)
    except: return '' 
    if "F/K" in unsur: return 'background-color: #d4edda; color: green' if 0 < num_val < 10 else ('background-color: #f8d7da; color: red' if num_val > 25 else '')
    elif "ROE" in unsur: return 'background-color: #d4edda; color: green' if num_val > 20 else ''
    elif "Beta" in unsur: return 'color: red' if num_val > 1.5 else 'color: green'
    return ''

def tablo_renklendir(val, col_name):
    # Tarama Tablosu Renklendirmesi
    try:
        v = float(str(val).replace('%',''))
        if col_name == "Sinyal Puanı":
            return 'background-color: #28a745; color: white' if v >= 70 else ('background-color: #dc3545; color: white' if v <= 30 else '')
        elif col_name == "RSI":
            return 'color: green' if v < 30 else ('color: red' if v > 70 else '')
        elif col_name == "F/K":
            return 'color: green' if 0 < v < 10 else ('color: red' if v > 20 else '')
        elif col_name == "PD/DD":
             return 'color: green' if v < 1.5 else ''
        elif col_name == "ROE (%)":
             return 'color: green' if v > 20 else ''
    except: return ''
    return ''

def detayli_yorum_getir(df, ind):
    last = df.iloc[-1]
    if ind == "RSI": return f"Değer: {last['RSI']:.2f}"
    return "Hesaplandı"

# -----------------------------------------------------------------------------
# YENİ ARAYÜZ MİMARİSİ (SIDEBARSIZ, MERKEZİ)
# -----------------------------------------------------------------------------

# Üst Başlık
col_nav1, col_nav2, col_nav3 = st.columns([1, 6, 1])
with col_nav2:
    st.markdown('<div class="main-header">BORSA İSTANBUL RADARI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Yapay Zeka Destekli Fon Yöneticisi Paneli</div>', unsafe_allow_html=True)

st.divider()

# Session State (Sayfa Geçişleri İçin)
if 'sayfa' not in st.session_state: st.session_state.sayfa = 'ana_sayfa'
if 'secili_hisse' not in st.session_state: st.session_state.secili_hisse = ''
if 'secili_endeks' not in st.session_state: st.session_state.secili_endeks = ''

def git(sayfa, veri=None):
    st.session_state.sayfa = sayfa
    if sayfa == 'hisse_detay': st.session_state.secili_hisse = veri
    if sayfa == 'endeks_detay': st.session_state.secili_endeks = veri

# --- 1. ANA SAYFA (VİTRİN) ---
if st.session_state.sayfa == 'ana_sayfa':
    # Arama Çubuğu
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        arama = st.text_input("🔍 HİSSE ARA (Örn: THYAO, ASELS)", placeholder="Sembol girin ve Enter'a basın...").upper()
        if arama:
            if ".IS" not in arama: arama += ".IS"
            st.button(f"🚀 {arama} Analizine Git", on_click=git, args=('hisse_detay', arama), type="primary", use_container_width=True)

    st.write("")
    
    # Endeks Butonları
    st.subheader("📊 Hızlı Piyasa Taraması")
    row1 = st.columns(len(ENDEKSLER))
    for i, (isim, hisseler) in enumerate(ENDEKSLER.items()):
        with row1[i]:
            if st.button(f"{isim}\n({len(hisseler)} Şirket)", key=f"btn_{i}"):
                git('endeks_detay', isim)
    
    st.info("ℹ️ Bir endekse tıkladığınızda, o endeksteki tüm şirketler 'Fon Yöneticisi Kriterlerine' göre taranır, puanlanır ve sıralanır.")

# --- 2. ENDEKS TARAMA SONUÇLARI (TABLO) ---
elif st.session_state.sayfa == 'endeks_detay':
    st.button("⬅️ Ana Sayfaya Dön", on_click=git, args=('ana_sayfa',))
    st.title(f"🔍 {st.session_state.secili_endeks} ANALİZ RAPORU")
    
    hisse_listesi = ENDEKSLER[st.session_state.secili_endeks]
    sonuclar = []
    
    bar = st.progress(0)
    durum = st.empty()
    
    # Tarama Motoru
    for i, hisse in enumerate(hisse_listesi):
        durum.text(f"Analiz ediliyor: {hisse} ({i+1}/{len(hisse_listesi)})")
        
        # Teknik
        df = verileri_getir(hisse, "6m") # Hızlı olsun diye 6 ay
        # Temel
        temel = is_yatirim_verileri(hisse).get("ozet", {})
        
        if df is not None:
            last = df.iloc[-1]
            
            # --- PUANLAMA ALGORİTMASI ---
            puan = 50
            # Teknik Puanlar
            if last['RSI'] < 30: puan += 15
            elif last['RSI'] > 70: puan -= 15
            if last['Close'] > last['SMA_20']: puan += 10
            if last['MACD'] > last['MACD_SIG']: puan += 10
            # Temel Puanlar
            fk = temel.get('F/K', 0)
            if fk and 0 < fk < 10: puan += 15
            elif fk and fk > 25: puan -= 10
            roe = temel.get('ROE', 0)
            if roe > 25: puan += 10
            
            sonuclar.append({
                "Sembol": hisse.replace(".IS", ""),
                "Fiyat": last['Close'],
                "Sinyal Puanı": puan,
                "RSI": last['RSI'],
                "Trend": "Yükseliş" if last['Close'] > last['SMA_20'] else "Düşüş",
                "F/K": fk if fk else 0,
                "PD/DD": temel.get('PD/DD', 0),
                "ROE (%)": roe
            })
        bar.progress((i+1)/len(hisse_listesi))
        
    bar.empty()
    durum.empty()
    
    if sonuclar:
        df_res = pd.DataFrame(sonuclar)
        df_res = df_res.sort_values(by="Sinyal Puanı", ascending=False) # En iyiler üstte
        
        # Tabloyu Renklendir ve Göster
        styler = df_res.style.apply(lambda x: [tablo_renklendir(v, col) for col, v in zip(x.index, x)], axis=1)
        styler = styler.format({"Fiyat": "{:.2f}", "Sinyal Puanı": "{:.0f}", "RSI": "{:.2f}", "F/K": "{:.2f}", "PD/DD": "{:.2f}", "ROE (%)": "{:.2f}"})
        
        st.dataframe(styler, use_container_width=True, height=600)
        st.success("✅ Tarama tamamlandı. Tablo en yüksek 'Al' sinyaline göre sıralanmıştır.")
    else:
        st.error("Veri alınamadı.")

# --- 3. HİSSE DETAY SAYFASI (ESKİ ANALİZİN YENİ YÜZÜ) ---
elif st.session_state.sayfa == 'hisse_detay':
    sembol = st.session_state.secili_hisse
    st.button("⬅️ Geri Dön", on_click=git, args=('ana_sayfa',))
    
    # Başlık ve Analiz
    st.title(f"📈 {sembol} PROFESYONEL ANALİZ KARTI")
    
    # 2 Kolonlu Düzen: Sol Grafik, Sağ Temel
    c_main1, c_main2 = st.columns([2, 1])
    
    with c_main1:
        st.subheader("Teknik Görünüm")
        with st.spinner('Grafik Çiziliyor...'):
            df = verileri_getir(sembol, "1y", INDIKATOR_LISTESI)
            if df is not None:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Fiyat'))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'))
                fig.update_layout(height=450, xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                # Alt İndikatörler (Tablar Halinde)
                t1, t2, t3 = st.tabs(["RSI & MACD", "Trend", "Osilatörler"])
                last = df.iloc[-1]
                with t1:
                    col_i1, col_i2 = st.columns(2)
                    col_i1.metric("RSI (14)", f"{last['RSI']:.2f}", delta="Aşırı Alım" if last['RSI']>70 else "Aşırı Satım" if last['RSI']<30 else "Nötr")
                    col_i2.metric("MACD Sinyal", "AL" if last['MACD'] > last['MACD_SIG'] else "SAT")
    
    with c_main2:
        st.subheader("Fon Yöneticisi Analiz Matrisi")
        is_veri = is_yatirim_verileri(sembol)
        
        if is_veri["fon_matrisi"] is not None:
            # Matrisi Renklendirerek Bas
            matris_df = is_veri["fon_matrisi"]
            styler_mat = matris_df.style.apply(lambda x: [matris_renklendir(x['Değer'], x['Unsur']) if col == 'Değer' else '' for col in x.index], axis=1)
            st.dataframe(styler_mat, use_container_width=True, hide_index=True)
        else:
            st.warning("Temel veri yükleniyor...")
            
        st.divider()
        if is_veri["oranlar"] is not None:
            st.write("📌 Finansal Oranlar")
            st.dataframe(is_veri["oranlar"].head(5), use_container_width=True, hide_index=True)

    # Alt Kısım: Detaylı Tablo
    st.divider()
    st.subheader("📋 Geçmiş Fiyat Verileri")
    if df is not None:
        st.dataframe(df.tail(100).style.highlight_max(axis=0), use_container_width=True)
