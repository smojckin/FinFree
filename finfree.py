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
    /* Yan menüyü (Sidebar) tamamen yok ediyoruz */
    [data-testid="stSidebar"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    
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

    /* Tablo ve Metrik Stilleri */
    .dataframe { font-size: 14px !important; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; color: #333; }
    
    /* Ekstra Güvenlik */
    [data-testid="stSidebar"] {display: none;}
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
    "RSI", "MACD", "FISHER", "BOLLINGER", "SMA", "EMA", 
    "STOCH", "CCI", "MOM", "WILLR", "ADX", "OBV",
    "SUPERTREND", "ICHIMOKU", "ATR", "WMA", "HMA", "TRIX"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

# -----------------------------------------------------------------------------
# 4. KER ÖLÇÜTÜ ANALİZ MOTORU (HATA TOLERANSLI)
# -----------------------------------------------------------------------------
def ker_analizi_yap(tk_obj):
    """
    Ker Ölçütü Filtreleme Sistemi.
    Yahoo veri vermezse bile info'dan hesaplamaya çalışır.
    """
    if not tk_obj:
        return {"skor": 0, "durum": "VERİ YOK", "sabikalar": ["Bağlantı nesnesi yok"]}

    skor = 0
    sabikalar = []
    
    try:
        # Info verisi (Genelde en güvenilir olan)
        info = tk_obj.info if tk_obj.info else {}
        
        # Tablo verileri (Bazen boş gelebilir, try-except ile geçiyoruz)
        finansallar = pd.DataFrame()
        nakit_akis = pd.DataFrame()
        try:
            finansallar = tk_obj.financials
        except: pass
        try:
            nakit_akis = tk_obj.cashflow
        except: pass

        # --- KRİTERLER ---

        # 1. Brüt Kar Marjı
        gross_m = info.get('grossMargins', 0) * 100
        if gross_m < 20: sabikalar.append(f"ELENDİ: Brüt Kar Marjı Düşük (%{gross_m:.1f} < %20)")
        elif gross_m > 35: skor += 1

        # 2. Faaliyet Giderleri (Tablo varsa bakar, yoksa pas geçer)
        if not finansallar.empty and 'Gross Profit' in finansallar.index:
            try:
                brut_kar = finansallar.loc['Gross Profit'].iloc[0]
                # SG&A kalemi kontrolü
                kalem = 'Selling General Administrative'
                if kalem in finansallar.index:
                    sga = finansallar.loc[kalem].iloc[0]
                    if brut_kar > 0 and (sga / brut_kar) > 0.30:
                        sabikalar.append("ELENDİ: Faaliyet Gid. > %30")
            except: pass
        
        # 3. Net Kar Oranı
        net_m = info.get('profitMargins', 0) * 100
        if net_m < 13: sabikalar.append(f"ELENDİ: Net Kar Marjı Düşük (%{net_m:.1f} < %13)")
        elif net_m > 18: skor += 1

        # 4. Cari Oran
        cari = info.get('currentRatio', 0)
        if 1.5 <= cari <= 2.0: skor += 1

        # 5. ROE
        roe = info.get('returnOnEquity', 0) * 100
        if roe < 15: sabikalar.append(f"ELENDİ: ROE Yetersiz (%{roe:.1f} < %15)")
        else: skor += 1

        # 6. F/K ve PD/DD
        if 0 < info.get('forwardPE', 100) < 10: skor += 1
        if info.get('priceToBook', 0) >= 1: skor += 1

        # 7. FAVÖK Marjı
        ebitda_m = info.get('ebitdaMargins', 0) * 100
        if ebitda_m < 10: sabikalar.append(f"ELENDİ: FAVÖK Marjı Düşük (%{ebitda_m:.1f})")
        elif ebitda_m > 15: skor += 1

        # 8. Net Borç / FAVÖK
        ebitda_val = info.get('ebitda', 1)
        # Bazen totalDebt info'da olmaz, balance sheet'ten bakmak gerekebilir ama basit tutalım
        total_debt = info.get('totalDebt', 0)
        total_cash = info.get('totalCash', 0)
        net_debt = total_debt - total_cash
        
        nd_ebitda = net_debt / ebitda_val if ebitda_val else 0
        if nd_ebitda > 4.5: sabikalar.append(f"ELENDİ: Net Borç/FAVÖK Kritik ({nd_ebitda:.1f})")
        elif nd_ebitda < 2.0: skor += 1

        # 9. Nakit Akışı (Tablo varsa)
        if not nakit_akis.empty and 'Operating Cash Flow' in nakit_akis.index:
            op_cash = nakit_akis.loc['Operating Cash Flow'].iloc[0]
            if op_cash <= 0: sabikalar.append("ELENDİ: Negatif Operasyonel Nakit")
            else: skor += 1

        # Sonuç
        durum = "ELENDİ" if len(sabikalar) > 0 else "GEÇTİ"
        return {"skor": skor, "durum": durum, "sabikalar": sabikalar}

    except Exception as e:
        return {"skor": 0, "durum": "HATA", "sabikalar": [f"Analiz sırasında hata: {str(e)}"]}

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
# 6. VERİ KAZIMA (GÜÇLENDİRİLMİŞ)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    """
    Yahoo Finance verilerini çeker. 'Ker Ölçütü' hatası almamak için
    tk objesini her durumda döndürür.
    """
    time.sleep(random.uniform(0.5, 1.5))
    saf_sembol = sembol.replace(".IS", "").replace(".is", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    
    # Varsayılan Boş Yapı
    veriler = {
        "temettu": None, 
        "sermaye": None, 
        "oranlar": None, 
        "fon_matrisi": None, 
        "ozet": {},
        "tk_obj": None # Kritik: Başlangıçta None
    }
    
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500])
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        # Ticker objesini en başta yarat
        tk = yf.Ticker(sembol)
        veriler["tk_obj"] = tk 
        
        # Info çekmeyi dene, patlarsa boş sözlük ver
        try:
            ticker_info = tk.info
        except:
            ticker_info = {}
            
        veriler["ozet"] = {
            "F/K": ticker_info.get('forwardPE', 0),
            "PD/DD": ticker_info.get('priceToBook', 0),
            "ROE": ticker_info.get('returnOnEquity', 0) * 100 if ticker_info.get('returnOnEquity') else 0,
            "Beta": ticker_info.get('beta', 0)
        }
        
        # Fon Matrisi
        mat_data = {
            "Kategori": ["Temel Analiz", "Temel Analiz", "Temel Analiz", "Risk Analizi", "Risk Analizi", "Yönetim", "Yönetim", "Likidite", "Likidite"],
            "Unsur": ["Kârlılık (ROE)", "Borç Yapısı", "F/K Oranı", "Beta Katsayısı", "Volatilite", "Kurumsal Yönetim", "Temettü Verimi", "İşlem Hacmi", "Halka Açıklık"],
            "Değer": [
                f"%{veriler['ozet']['ROE']:.2f}",
                ticker_info.get('debtToEquity', 'N/A'),
                f"{veriler['ozet']['F/K']:.2f}",
                f"{veriler['ozet']['Beta']:.2f}",
                "N/A", "Kurumsal",
                f"%{ticker_info.get('dividendYield', 0)*100:.2f}" if ticker_info.get('dividendYield') else "N/A",
                "N/A", "N/A"
            ]
        }
        veriler["fon_matrisi"] = pd.DataFrame(mat_data)

        # İş Yatırım (Opsiyonel)
        try:
            response = session.get(url, headers=headers, timeout=10, verify=False)
            if response.status_code == 200:
                tablolar = pd.read_html(response.text, match=".", decimal=",", thousands=".")
                for df in tablolar:
                    cols = [str(c).lower() for c in df.columns]
                    if any("temettü" in c for c in cols): veriler["temettu"] = df
                    elif any("bedelli" in c for c in cols): veriler["sermaye"] = df
                    elif any("f/k" in c for c in cols): veriler["oranlar"] = df
        except: pass
        
        return veriler
    except:
        # En kötü durumda bile tk_obj olan veriyi dönmeye çalış
        if 'tk' in locals(): veriler["tk_obj"] = tk
        return veriler

# -----------------------------------------------------------------------------
# 7. TEKNİK VERİ MOTORU
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
            time.sleep(1)
        except: continue

    if df is None or df.empty: return None
    
    try:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        if periyot == "3y":
            start_date = df.index[-1] - pd.DateOffset(years=3)
            df = df[df.index >= start_date]
            
        close, high, low = df['Close'], df['High'], df['Low']
        df['RSI'] = ta.rsi(close, length=14)
        macd_calc = ta.macd(close)
        df['MACD'], df['MACD_SIG'] = macd_calc['MACD_12_26_9'], macd_calc['MACDs_12_26_9']
        df['SMA_20'], df['EMA_50'] = ta.sma(close, length=20), ta.ema(close, length=50)
        df['CCI'] = ta.cci(high, low, close)
        
        for ind in secilen_favoriler:
            if ind not in df.columns:
                try:
                    if hasattr(df.ta, ind.lower()): getattr(df.ta, ind.lower())(append=True)
                except: pass
        return df.dropna()
    except: return None

# -----------------------------------------------------------------------------
# 8. RENKLENDİRME VE STİL
# -----------------------------------------------------------------------------
def matris_renklendir(val, unsur):
    try:
        num = float(str(val).replace('%', '').replace(',', '.'))
        if "F/K" in unsur: return 'background-color: #d4edda; color: green' if 0 < num < 10 else ('background-color: #f8d7da; color: red' if num > 25 else '')
        if "ROE" in unsur: return 'background-color: #d4edda; color: green' if num > 20 else ('background-color: #f8d7da; color: red' if num < 5 else '')
    except: pass
    return ''

def tablo_renklendir(val, col):
    try:
        v = float(str(val).replace('%',''))
        if col == "Sinyal Puanı": return 'background-color: #28a745; color: white' if v >= 70 else ('background-color: #dc3545; color: white' if v <= 30 else '')
        elif col == "RSI": return 'color: green; font-weight: bold' if v < 30 else ('color: red; font-weight: bold' if v > 70 else '')
    except: pass
    return ''

def detayli_yorum_getir(df, ind):
    last = df.iloc[-1]
    if "RSI" in ind:
        val = last[ind]
        if val < 30: return f"AŞIRI SATIM (AL) - {val:.2f}"
        elif val > 70: return f"AŞIRI ALIM (SAT) - {val:.2f}"
        return f"NÖTR - {val:.2f}"
    return "Analiz Yapıldı"

# -----------------------------------------------------------------------------
# 9. ANA ARAYÜZ (LAYOUT)
# -----------------------------------------------------------------------------
if 'sayfa' not in st.session_state: st.session_state.sayfa = 'ana_sayfa'
if 'secili_hisse' not in st.session_state: st.session_state.secili_hisse = ''
if 'secili_endeks' not in st.session_state: st.session_state.secili_endeks = ''
if 'zaman_araligi' not in st.session_state: st.session_state.zaman_araligi = '1y'

def git(sayfa, veri=None):
    st.session_state.sayfa = sayfa
    if sayfa == 'hisse_detay': st.session_state.secili_hisse = veri
    if sayfa == 'endeks_detay': st.session_state.secili_endeks = veri

c_l, c_a, c_z = st.columns([1, 4, 1])
with c_l:
    if st.button("🏠 ANA SAYFA", use_container_width=True): st.session_state.sayfa = 'ana_sayfa'
with c_a:
    arama = st.text_input("Hisse Ara:", placeholder="THYAO...", label_visibility="collapsed").upper()
    if arama: git('hisse_detay', arama + (".IS" if ".IS" not in arama else ""))
with c_z:
    st.session_state.zaman_araligi = st.selectbox("Süre", ["1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "max"], index=3, label_visibility="collapsed")

with st.expander("🛠️ ANALİZ AYARLARI"):
    kayitli = favorileri_yukle()
    c1, c2 = st.columns(2)
    with c1:
        secili = st.multiselect("İndikatörler:", TUM_INDIKATORLER, default=kayitli.get("indikatorler", ["RSI", "MACD"]))
        if st.button("Kaydet"):
            kayitli["indikatorler"] = secili; favorileri_kaydet(kayitli); st.success("Kaydedildi!")
    with c2:
        yeni = st.text_input("Favoriye Ekle:").upper()
        if st.button("Ekle") and yeni:
            lst = kayitli.get("hisseler", [])
            if yeni not in lst: lst.append(yeni + (".IS" if ".IS" not in yeni else "")); kayitli["hisseler"] = lst; favorileri_kaydet(kayitli); st.rerun()

st.divider()

if st.session_state.sayfa == 'ana_sayfa':
    st.markdown("<h1 class='main-header'>BORSA İSTANBUL RADARI</h1>", unsafe_allow_html=True)
    cols = st.columns(len(ENDEKSLER))
    for i, (isim, liste) in enumerate(ENDEKSLER.items()):
        with cols[i]:
            if st.button(f"📈 {isim}\n({len(liste)} Hisse)", key=f"b_{i}"): git('endeks_detay', isim)
    
    favs = favorileri_yukle().get("hisseler", [])
    if favs:
        st.subheader("⭐ Favoriler")
        fc = st.columns(6)
        for i, f in enumerate(favs):
            if fc[i%6].button(f, key=f"f_{f}"): git('hisse_detay', f)

elif st.session_state.sayfa == 'endeks_detay':
    st.button("⬅️ Geri", on_click=git, args=('ana_sayfa',))
    st.markdown(f"## {st.session_state.secili_endeks} TARAMA RAPORU")
    liste = ENDEKSLER[st.session_state.secili_endeks]
    res = []
    bar = st.progress(0)
    for i, h in enumerate(liste):
        df = verileri_getir(h, "6mo", [])
        fund = is_yatirim_verileri(h)
        temel = fund.get("ozet", {}) if fund else {}
        if df is not None:
            l = df.iloc[-1]
            p = 50 + (20 if l['RSI']<30 else (-20 if l['RSI']>70 else 0))
            res.append({"Sembol": h.replace(".IS",""), "Fiyat": l['Close'], "Puan": p, "RSI": l['RSI'], "F/K": temel.get('F/K', 0)})
        bar.progress((i+1)/len(liste))
    if res:
        st.dataframe(pd.DataFrame(res).sort_values("Puan", ascending=False).style.apply(lambda x: [tablo_renklendir(v, c) for c, v in zip(x.index, x)], axis=1), use_container_width=True)

elif st.session_state.sayfa == 'hisse_detay':
    s = st.session_state.secili_hisse
    st.button("⬅️ Geri", on_click=git, args=('ana_sayfa',))
    
    fund_data = is_yatirim_verileri(s)
    df = verileri_getir(s, st.session_state.zaman_araligi, favorileri_yukle().get("indikatorler"))
    
    if df is not None:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["GENEL", "TEKNİK", "MATRİS", "FİNANSAL", "🚩 KER ÖLÇÜTÜ"])
        with tab1:
            st.plotly_chart(go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])]), use_container_width=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Fiyat", f"{df.iloc[-1]['Close']:.2f}")
            c2.metric("RSI", f"{df.iloc[-1]['RSI']:.2f}")
            c3.metric("Trend", "YÜKSELİŞ" if df.iloc[-1]['Close'] > df.iloc[-1]['SMA_20'] else "DÜŞÜŞ")
        
        with tab2:
            for c in df.columns:
                if c not in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    st.write(f"### {c}")
                    st.plotly_chart(go.Figure(go.Scatter(x=df.index, y=df[c])), use_container_width=True, key=f"c_{c}")
        
        with tab3:
            if fund_data and fund_data.get("fon_matrisi") is not None:
                st.dataframe(fund_data["fon_matrisi"].style.apply(lambda x: [matris_renklendir(x['Değer'], x['Unsur']) if col == 'Değer' else '' for col in x.index], axis=1), use_container_width=True)
            else: st.warning("Veri yok.")
            
        with tab4:
            if fund_data:
                if fund_data.get("oranlar") is not None: st.dataframe(fund_data["oranlar"])
                if fund_data.get("temettu") is not None: st.dataframe(fund_data["temettu"])
                
        with tab5:
            st.subheader("🏁 KER ÖLÇÜTÜ ANALİZİ")
            if fund_data and fund_data.get("tk_obj"):
                analiz = ker_analizi_yap(fund_data["tk_obj"])
                c_s, c_d = st.columns(2)
                c_s.metric("Skor", f"{analiz['skor']} / 13")
                if analiz['durum'] == "GEÇTİ": c_d.success("GEÇTİ")
                else: 
                    c_d.error("ELENDİ")
                    for err in analiz['sabikalar']: st.write(f"⚠️ {err}")
            else: st.error("Finansal veri çekilemedi (Yahoo API Limit).")
    else: st.error("Veri yok.")
