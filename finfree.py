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
# 2. CSS İLE MODERN GÖRÜNÜM (SIDEBAR GİZLEME VE STİL)
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

# Endeks listelerini uzun uzun yazıyorum ki satır sayısı artsın ve okuması kolay olsun
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

# İndikatör listesi (Dropdown için)
TUM_INDIKATORLER = [
    "RSI", "MACD", "FISHER", "BOLLINGER", "SMA", "EMA", 
    "STOCH", "CCI", "MOM", "WILLR", "ADX", "OBV"
]

# -----------------------------------------------------------------------------
# 4. YARDIMCI FONKSİYONLAR (VERİ SAKLAMA/YÜKLEME)
# -----------------------------------------------------------------------------
def favorileri_yukle():
    """Favori ayarları JSON dosyasından çeker."""
    varsayilan = {
        "indikatorler": ["RSI", "MACD", "SMA"], 
        "hisseler": ["THYAO.IS", "ASELS.IS"]
    }
    if os.path.exists(FAVORI_DOSYASI):
        try:
            with open(FAVORI_DOSYASI, 'r') as f:
                return json.load(f)
        except:
            pass
    return varsayilan

def favorileri_kaydet(veri):
    """Ayarları JSON dosyasına yazar."""
    with open(FAVORI_DOSYASI, 'w') as f:
        json.dump(veri, f)

# -----------------------------------------------------------------------------
# 5. İŞ YATIRIM VERİ KAZIMA (SCRAPER) - HİBRİT MOTOR
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def is_yatirim_verileri(sembol):
    """
    İş Yatırım sitesinden ve Yahoo Finance'den temel verileri çeker.
    Hibrit çalışır: İş Yatırım yanıt vermezse Yahoo verilerini döndürür.
    """
    saf_sembol = sembol.replace(".IS", "").replace(".is", "")
    url = f"https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse={saf_sembol}"
    
    # Boş veri şablonu
    veriler = {
        "temettu": None, 
        "sermaye": None, 
        "oranlar": None, 
        "fon_matrisi": None, 
        "ozet": {}
    }
    
    # Bağlantı ayarları (Zırhlı)
    session = requests.Session()
    retry_strategy = Retry(
        total=3, 
        backoff_factor=1, 
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        # 1. Adım: Yahoo Finance verilerini çek (Garanti Veri)
        tk = yf.Ticker(sembol)
        ticker_info = tk.info if tk.info else {}
        
        # Özet veri sözlüğü (Hızlı erişim için)
        veriler["ozet"] = {
            "F/K": ticker_info.get('forwardPE', 0),
            "PD/DD": ticker_info.get('priceToBook', 0),
            "ROE": ticker_info.get('returnOnEquity', 0) * 100 if ticker_info.get('returnOnEquity') else 0,
            "Beta": ticker_info.get('beta', 0)
        }

        # 2. Adım: Fon Yöneticisi Analiz Matrisi Oluşturma
        matris_data = {
            "Kategori": [
                "Temel Analiz", "Temel Analiz", "Temel Analiz", 
                "Risk Analizi", "Risk Analizi", 
                "Yönetim", "Yönetim", 
                "Likidite", "Likidite"
            ],
            "Unsur": [
                "Kârlılık (ROE)", "Borç Yapısı", "F/K Oranı", 
                "Beta Katsayısı", "Volatilite", 
                "Kurumsal Yönetim", "Temettü Verimi", 
                "İşlem Hacmi", "Halka Açıklık"
            ],
            "Değer": [
                f"%{ticker_info.get('returnOnEquity', 0)*100:.2f}" if ticker_info.get('returnOnEquity') else "N/A",
                ticker_info.get('debtToEquity', 'N/A'),
                f"{ticker_info.get('forwardPE', 0):.2f}" if ticker_info.get('forwardPE') else "N/A",
                f"{ticker_info.get('beta', 0):.2f}" if ticker_info.get('beta') else "N/A",
                f"%{ticker_info.get('52WeekChange', 0)*100:.2f}" if ticker_info.get('52WeekChange') else "N/A",
                "İncelenmeli",
                f"%{ticker_info.get('dividendYield', 0)*100:.2f}" if ticker_info.get('dividendYield') else "N/A",
                f"{ticker_info.get('averageVolume', 0):,}",
                "N/A"
            ]
        }
        veriler["fon_matrisi"] = pd.DataFrame(matris_data)

        # 3. Adım: İş Yatırım'dan Tabloları Çekmeye Çalış
        response = session.get(url, headers=headers, timeout=15, verify=False)
        
        if response.status_code == 200:
            tablolar = pd.read_html(response.text, match=".", decimal=",", thousands=".")
            for df in tablolar:
                # Kolon isimlerini küçültüp kontrol et
                cols = [str(c).lower() for c in df.columns]
                
                if any("temettü" in c for c in cols) or any("dağıtma" in c for c in cols): 
                    veriler["temettu"] = df
                elif any("bedelli" in c for c in cols) or any("bedelsiz" in c for c in cols): 
                    veriler["sermaye"] = df
                elif any("f/k" in c for c in cols) or any("pd/dd" in c for c in cols): 
                    veriler["oranlar"] = df
                    
        return veriler
        
    except Exception as e:
        # Hata durumunda elimizdeki Yahoo verisiyle dönüyoruz
        return veriler if veriler["fon_matrisi"] is not None else None

# -----------------------------------------------------------------------------
# 6. TEKNİK VERİ MOTORU (YFINANCE)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def verileri_getir(sembol, periyot, secilen_favoriler=None):
    """
    Hisse senedi fiyat verilerini çeker ve teknik indikatörleri hesaplar.
    """
    if secilen_favoriler is None: 
        secilen_favoriler = ["RSI", "MACD", "SMA", "EMA"]
    
    # 3Y seçeneği eklendiği için download mantığını kontrol edelim
    # Yahoo Finance "3y" periyodunu desteklemeyebilir, manuel tarih gerekebilir ama
    # yfinance kütüphanesi genelde "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max" destekler.
    # "3y" standart listede yoksa "5y" çekip kesmek gerekebilir ama biz doğrudan paslayalım, kütüphane hallederse ne ala.
    # Eğer hata verirse "5y" çekip filtreleyeceğiz.
    
    download_period = periyot
    if periyot == "3y":
        download_period = "5y" # 5 yıllık çekip son 3 yılı alırız
        
    interval = "1d" # Günlük veri
    
    df = None
    # 3 kez deneme döngüsü
    for _ in range(3):
        try:
            df = yf.download(
                sembol, 
                period=download_period, 
                interval=interval, 
                progress=False, 
                timeout=15
            )
            if df is not None and not df.empty: 
                break
            time.sleep(1)
        except: 
            continue

    if df is None or df.empty: 
        return None
    
    try:
        # MultiIndex sütun temizliği
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.droplevel(1)
            
        # 3Y filtresi (Eğer 5Y çektiysek)
        if periyot == "3y":
            start_date = df.index[-1] - pd.DateOffset(years=3)
            df = df[df.index >= start_date]
            
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # --- Temel İndikatör Hesaplamaları (Her zaman hesaplanır) ---
        # RSI
        df['RSI'] = ta.rsi(close, length=14)
        
        # MACD
        macd = ta.macd(close)
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_SIG'] = macd['MACDs_12_26_9']
        
        # Hareketli Ortalamalar
        df['SMA_20'] = ta.sma(close, length=20)
        df['EMA_50'] = ta.ema(close, length=50)
        
        # CCI
        df['CCI'] = ta.cci(high, low, close)
        
        # --- İsteğe Bağlı İndikatörler ---
        for ind in secilen_favoriler:
            if ind not in df.columns:
                try:
                    # Pandas TA kütüphanesinden dinamik çağırma
                    if hasattr(df.ta, ind.lower()):
                        getattr(df.ta, ind.lower())(append=True)
                    else:
                        # Manuel eklemeler
                        if ind == "SUPERTREND": df.ta.supertrend(append=True)
                        elif ind == "ICHIMOKU": df.ta.ichimoku(append=True)
                        elif ind == "BOLLINGER": df.ta.bbands(append=True)
                except: 
                    pass

        return df.dropna()
        
    except Exception as e: 
        return None

# -----------------------------------------------------------------------------
# 7. RENKLENDİRME VE STİL FONKSİYONLARI
# -----------------------------------------------------------------------------
def matris_renklendir(val, unsur):
    """Fon matrisi tablosunu renklendirir."""
    try:
        # Değeri temizle ve sayıya çevir
        clean_val = str(val).replace('%', '').replace(',', '.')
        num_val = float(clean_val)
        
        # Kriterlere göre renk ata
        if "F/K" in unsur: 
            return 'background-color: #d4edda; color: green' if 0 < num_val < 10 else ('background-color: #f8d7da; color: red' if num_val > 25 else '')
        if "ROE" in unsur: 
            return 'background-color: #d4edda; color: green' if num_val > 20 else ('background-color: #f8d7da; color: red' if num_val < 5 else '')
        if "Beta" in unsur: 
            return 'color: red' if num_val > 1.5 else ('color: green' if num_val < 1.0 else '')
        if "Borç" in unsur:
             return 'background-color: #d4edda; color: green' if num_val < 0.5 else ('background-color: #f8d7da; color: red' if num_val > 2.0 else '')
             
    except: 
        pass
    return ''

def tablo_renklendir(val, col_name):
    """Tarama sonuç tablosunu renklendirir."""
    try:
        v = float(str(val).replace('%',''))
        
        if col_name == "Sinyal Puanı":
            return 'background-color: #28a745; color: white' if v >= 70 else ('background-color: #dc3545; color: white' if v <= 30 else '')
        elif col_name == "RSI":
            return 'color: green; font-weight: bold' if v < 30 else ('color: red; font-weight: bold' if v > 70 else '')
        elif col_name == "F/K":
            return 'color: green; font-weight: bold' if 0 < v < 10 else ('color: red; font-weight: bold' if v > 20 else '')
        elif col_name == "PD/DD":
             return 'color: green' if v < 1.5 else ''
        elif col_name == "ROE (%)":
             return 'color: green' if v > 20 else ''
             
    except: 
        return ''
    return ''

def detayli_yorum_getir(df, ind):
    """İndikatör için basit bir durum yorumu döndürür."""
    last = df.iloc[-1]
    close = last['Close']
    
    if ind == "RSI":
        val = last['RSI']
        if val < 30: return f"AŞIRI SATIM (AL FIRSATI) - {val:.2f}"
        elif val > 70: return f"AŞIRI ALIM (SAT SİNYALİ) - {val:.2f}"
        return f"NÖTR BÖLGE - {val:.2f}"
    elif ind == "MACD":
        if last['MACD'] > last['MACD_SIG']: return "AL SİNYALİ (MACD > Sinyal)"
        return "SAT SİNYALİ (MACD < Sinyal)"
    elif ind == "SMA":
        if close > last['SMA_20']: return f"TREND POZİTİF (Fiyat > SMA20)"
        return "TREND NEGATİF (Fiyat < SMA20)"
        
    return "Analiz Yapıldı"

# -----------------------------------------------------------------------------
# 8. ANA ARAYÜZ (LAYOUT)
# -----------------------------------------------------------------------------

# SESSION STATE (Sayfa Durumları)
if 'sayfa' not in st.session_state: st.session_state.sayfa = 'ana_sayfa'
if 'secili_hisse' not in st.session_state: st.session_state.secili_hisse = ''
if 'secili_endeks' not in st.session_state: st.session_state.secili_endeks = ''
if 'zaman_araligi' not in st.session_state: st.session_state.zaman_araligi = '1y'

# Sayfa Değiştirme Fonksiyonu
def git(sayfa, veri=None):
    st.session_state.sayfa = sayfa
    if sayfa == 'hisse_detay': 
        st.session_state.secili_hisse = veri
    if sayfa == 'endeks_detay': 
        st.session_state.secili_endeks = veri

# --- YATAY ÜST KONTROL PANELİ ---
c_logo, c_arama, c_zaman = st.columns([1, 4, 1])

with c_logo:
    # Ana sayfaya dönüş butonu
    if st.button("🏠 ANA SAYFA", use_container_width=True):
        st.session_state.sayfa = 'ana_sayfa'

with c_arama:
    # Merkezi Arama Kutusu
    arama_girdisi = st.text_input(
        "Hisse Ara:", 
        placeholder="THYAO, ASELS, GARAN...", 
        label_visibility="collapsed"
    ).upper()
    
    if arama_girdisi:
        if ".IS" not in arama_girdisi: 
            arama_girdisi += ".IS"
        st.session_state.secili_hisse = arama_girdisi
        st.session_state.sayfa = 'hisse_detay'

with c_zaman:
    # Zaman Aralığı Seçici (3Y EKLENDİ)
    # Burada kullanıcı grafiğin süresini seçer.
    yeni_zaman = st.selectbox(
        "Süre", 
        ["1mo", "3mo", "6mo", "1y", "2y", "3y", "5y", "max"], 
        index=3, 
        label_visibility="collapsed"
    )
    st.session_state.zaman_araligi = yeni_zaman

# --- AYARLAR VE FAVORİLER (GİZLENEBİLİR YATAY PANEL) ---
with st.expander("🛠️ ANALİZ AYARLARI & FAVORİLER (Tıkla Aç/Kapa)"):
    # Ayarları yükle
    kayitli_ayarlar = favorileri_yukle()
    
    col_set1, col_set2 = st.columns(2)
    
    with col_set1:
        st.subheader("İndikatör Havuzu")
        st.info("Hisse detay sayfasında görüntülenecek ekstra indikatörleri seçiniz.")
        secili_indikatortler = st.multiselect(
            "Grafiklerde Görünecek İndikatörler:", 
            TUM_INDIKATORLER, 
            default=kayitli_ayarlar.get("indikatorler", ["RSI", "MACD"])
        )
        if st.button("Ayarları Kaydet"):
            kayitli_ayarlar["indikatorler"] = secili_indikatortler
            favorileri_kaydet(kayitli_ayarlar)
            st.success("İndikatör tercihleri kaydedildi!")
            
    with col_set2:
        st.subheader("Favori Hisselerim")
        st.info("Hızlı erişim listenizi düzenleyin.")
        yeni_favori_hisse = st.text_input("Favoriye Ekle (Sembol):").upper()
        
        if st.button("Listeye Ekle") and yeni_favori_hisse:
            if ".IS" not in yeni_favori_hisse: 
                yeni_favori_hisse += ".IS"
                
            mevcut_liste = kayitli_ayarlar.get("hisseler", [])
            if yeni_favori_hisse not in mevcut_liste:
                mevcut_liste.append(yeni_favori_hisse)
                kayitli_ayarlar["hisseler"] = mevcut_liste
                favorileri_kaydet(kayitli_ayarlar)
                st.rerun()
                
        # Silme işlemi
        silinecekler = st.multiselect("Listeden Sil:", kayitli_ayarlar.get("hisseler", []))
        if silinecekler and st.button("Seçilenleri Sil"):
            mevcut_liste = kayitli_ayarlar.get("hisseler", [])
            for s in silinecekler: 
                if s in mevcut_liste:
                    mevcut_liste.remove(s)
            kayitli_ayarlar["hisseler"] = mevcut_liste
            favorileri_kaydet(kayitli_ayarlar)
            st.rerun()

st.divider()

# -----------------------------------------------------------------------------
# 9. SAYFA İÇERİKLERİ
# -----------------------------------------------------------------------------

# --- SAYFA 1: ANA SAYFA (DASHBOARD) ---
if st.session_state.sayfa == 'ana_sayfa':
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>BORSA İSTANBUL RADARI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Yapay Zeka Destekli Teknik ve Temel Analiz Platformu</p>", unsafe_allow_html=True)
    st.write("")
    st.write("")
    
    # Endeks Kartları (Butonlar)
    st.subheader("📊 Hızlı Piyasa Taraması (Sektörel & Endeks)")
    
    # Butonları dinamik olarak oluştur
    cols = st.columns(len(ENDEKSLER))
    for i, (isim, liste) in enumerate(ENDEKSLER.items()):
        with cols[i]:
            # Her butona benzersiz key veriyoruz
            if st.button(f"📈 {isim}\n({len(liste)} Hisse)", key=f"main_btn_{i}", use_container_width=True):
                git('endeks_detay', isim)
    
    st.info("💡 BİLGİ: Bir endekse tıkladığınızda, sistem o endeksteki TÜM şirketleri güncel verilerle tarar, RSI, MACD, F/K ve PD/DD gibi kriterlere göre puanlar ve sıralar.")
    
    # Favoriler Kısa Yolu
    st.subheader("⭐ Favori Listeniz")
    fav_hisseler = favorileri_yukle().get("hisseler", [])
    if fav_hisseler:
        f_cols = st.columns(min(len(fav_hisseler), 6)) # En fazla 6 sütun
        for i, fh in enumerate(fav_hisseler):
            with f_cols[i % 6]: # Modulo ile sütunları döndür
                if st.button(fh, key=f"fav_{fh}"):
                    st.session_state.secili_hisse = fh
                    st.session_state.sayfa = 'hisse_detay'
                    st.rerun()
    else:
        st.write("Henüz favori hisse eklemediniz. Yukarıdaki 'Ayarlar' panelini kullanın.")

# --- SAYFA 2: ENDEKS TARAMA RAPORU (SCANNER) ---
elif st.session_state.sayfa == 'endeks_detay':
    st.button("⬅️ Ana Sayfaya Dön", on_click=git, args=('ana_sayfa',))
    st.markdown(f"## 🔍 {st.session_state.secili_endeks} DETAYLI TARAMA RAPORU")
    
    hisse_listesi = ENDEKSLER[st.session_state.secili_endeks]
    taranan_veriler = []
    
    # İlerleme Çubuğu
    bar_text = st.empty()
    bar = st.progress(0)
    
    # Döngü ile her hisseyi analiz et
    for i, hisse in enumerate(hisse_listesi):
        bar_text.text(f"Analiz ediliyor: {hisse} ({i+1}/{len(hisse_listesi)})")
        
        # Veri Çek (Hız için 6 aylık veri yeterli)
        df = verileri_getir(hisse, "6mo", [])
        
        # Temel verileri çek
        temel_veri = is_yatirim_verileri(hisse).get("ozet", {})
        
        if df is not None:
            last_row = df.iloc[-1]
            
            # --- BASİT PUANLAMA ALGORİTMASI ---
            puan = 50 # Başlangıç puanı
            
            # Teknik Kriterler
            rsi_val = last_row['RSI']
            if rsi_val < 30: puan += 20     # Aşırı satım (Al fırsatı)
            elif rsi_val > 70: puan -= 20   # Aşırı alım (Sat sinyali)
            
            if last_row['Close'] > last_row['SMA_20']: puan += 10 # Trend pozitif
            if last_row['MACD'] > last_row['MACD_SIG']: puan += 10 # Momentum pozitif
            
            # Temel Kriterler
            fk = temel_veri.get('F/K', 0)
            if fk and 0 < fk < 8: puan += 20 # Ucuz hisse
            elif fk and fk > 25: puan -= 10  # Pahalı hisse
            
            roe = temel_veri.get('ROE', 0)
            if roe and roe > 30: puan += 10 # Yüksek karlılık
            
            taranan_veriler.append({
                "Sembol": hisse.replace(".IS", ""),
                "Fiyat": last_row['Close'],
                "Sinyal Puanı": puan,
                "RSI": rsi_val,
                "Trend": "Yükseliş" if last_row['Close'] > last_row['SMA_20'] else "Düşüş",
                "F/K": fk if fk else 0,
                "PD/DD": temel_veri.get('PD/DD', 0),
                "ROE (%)": roe if roe else 0
            })
            
        # İlerlemeyi güncelle
        bar.progress((i+1)/len(hisse_listesi))
        
    bar.empty()
    bar_text.empty()
    
    if taranan_veriler:
        # Sonuçları DataFrame'e çevir ve sırala
        df_res = pd.DataFrame(taranan_veriler)
        df_res = df_res.sort_values(by="Sinyal Puanı", ascending=False)
        
        # Renklendirme ve Formatlama
        styler = df_res.style.apply(lambda x: [tablo_renklendir(v, col) for col, v in zip(x.index, x)], axis=1)
        styler = styler.format({
            "Fiyat": "{:.2f}", 
            "Sinyal Puanı": "{:.0f}", 
            "RSI": "{:.2f}", 
            "F/K": "{:.2f}", 
            "PD/DD": "{:.2f}", 
            "ROE (%)": "{:.2f}"
        })
        
        st.dataframe(styler, use_container_width=True, height=700)
        st.success(f"✅ {len(taranan_veriler)} hisse tarandı ve puana göre sıralandı.")
    else:
        st.error("Veri alınamadı veya bağlantı hatası oluştu.")

# --- SAYFA 3: HİSSE DETAY KARTI (TEKİL ANALİZ) ---
elif st.session_state.sayfa == 'hisse_detay':
    sembol = st.session_state.secili_hisse
    st.button("⬅️ Geri Dön", on_click=git, args=('ana_sayfa',))
    
    # Kullanıcı ayarlarını çek
    ayarlar = favorileri_yukle()
    secili_ind = ayarlar.get("indikatorler", ["RSI", "MACD"])
    
    st.markdown(f"## 📈 {sembol} PROFESYONEL ANALİZ RAPORU")
    st.caption(f"Seçilen Zaman Aralığı: {st.session_state.zaman_araligi.upper()}")
    
    # Sekmeli Yapı
    tab1, tab2, tab3, tab4 = st.tabs([
        "GENEL BAKIŞ", 
        "DETAYLI İNDİKATÖRLER", 
        "FONCU MATRİSİ", 
        "FİNANSALLAR"
    ])
    
    # Verileri Çek
    df = verileri_getir(sembol, st.session_state.zaman_araligi, secili_ind)
    
    if df is not None:
        last = df.iloc[-1]
        
        # TAB 1: GENEL BAKIŞ (Fiyat Grafiği ve Özet)
        with tab1:
            # Mum Grafiği
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, 
                open=df['Open'], 
                high=df['High'], 
                low=df['Low'], 
                close=df['Close'], 
                name='Fiyat'
            ))
            # Ortalamalar
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA 20'))
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], line=dict(color='orange', width=1), name='EMA 50'))
            
            fig.update_layout(
                height=500, 
                xaxis_rangeslider_visible=False, 
                margin=dict(l=0,r=0,t=0,b=0),
                title=f"{sembol} Fiyat Hareketi"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Hızlı Durum Kartları
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Son Fiyat", f"{last['Close']:.2f}")
            
            rsi_durum = "Aşırı Alım" if last['RSI']>70 else ("Aşırı Satım" if last['RSI']<30 else None)
            c2.metric("RSI (14)", f"{last['RSI']:.2f}", delta=rsi_durum, delta_color="inverse")
            
            macd_sinyal = "AL" if last['MACD'] > last['MACD_SIG'] else "SAT"
            c3.metric("MACD", macd_sinyal, delta="Pozitif" if macd_sinyal=="AL" else "Negatif")
            
            trend_durum = "YÜKSELİŞ" if last['Close'] > last['SMA_20'] else "DÜŞÜŞ"
            c4.metric("Kısa Vade Trend", trend_durum, delta="Boğa" if trend_durum=="YÜKSELİŞ" else "Ayı")

        # TAB 2: DETAYLI İNDİKATÖRLER (Grafikler)
        with tab2:
            st.subheader("Teknik İndikatör Paneli")
            
            for ind in secili_ind:
                st.markdown(f"### {ind} Analizi")
                st.info(detayli_yorum_getir(df, ind))
                
                fig_ind = go.Figure()
                # İlgili sütunları bul (Örn: MACD, MACD_SIG)
                cols = [c for c in df.columns if c.startswith(ind)]
                
                for c in cols:
                    fig_ind.add_trace(go.Scatter(x=df.index, y=df[c], name=c))
                
                # Referans çizgileri (RSI için)
                if ind == "RSI":
                    fig_ind.add_hline(y=70, line_color="red", line_dash="dash", annotation_text="Aşırı Alım")
                    fig_ind.add_hline(y=30, line_color="green", line_dash="dash", annotation_text="Aşırı Satım")
                
                # Referans çizgileri (CCI için)
                if ind == "CCI":
                    fig_ind.add_hline(y=100, line_color="red", line_dash="dash")
                    fig_ind.add_hline(y=-100, line_color="green", line_dash="dash")

                fig_ind.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0))
                st.plotly_chart(fig_ind, use_container_width=True, key=f"chart_{ind}")
                st.divider()

        # TAB 3: FONCU MATRİSİ (Temel Analiz)
        with tab3:
            st.subheader("🏛️ Fon Yöneticisi Karar Destek Matrisi")
            st.write("Aşağıdaki veriler, kurumsal yatırımcıların baktığı temel kriterlere göre renklendirilmiştir.")
            
# Yeni hali bu, her ihtimali hesaba kat:
fund_data = is_yatirim_verileri(sembol)

# 1. fund_data var mı? 2. İçinde "fon_matrisi" anahtarı var mı? 3. O anahtarın içi dolu mu?
if fund_data and isinstance(fund_data, dict) and fund_data.get("fon_matrisi") is not None:
    matris_df = fund_data["fon_matrisi"]
    # Buradan sonra matris_df ile ne halt yiyeceksen yiyebilirsin.
else:
    # Veri gelmediğinde programın patlamaması için bir uyarı çak:
    st.warning(f"{sembol} kodlu arkadaşın verisi çekilemedi. Ya sembol yanlış ya da İş Yatırım'ın keyfi yerinde değil.")
    matris_df = None # Boş bırak ki aşağıda başka yerler de patlamasın
    
                # Renklendirme fonksiyonunu uygula
                styler_mat = matris_df.style.apply(
                    lambda x: [matris_renklendir(x['Değer'], x['Unsur']) if col == 'Değer' else '' for col in x.index], 
                    axis=1
                )
                st.dataframe(styler_mat, use_container_width=True, hide_index=True)
            else:
                st.warning("Temel finansal veriler şu anda çekilemiyor.")

        # TAB 4: DETAYLI FİNANSALLAR
        with tab4:
            fund_data = is_yatirim_verileri(sembol)
            
            c_fin1, c_fin2 = st.columns(2)
            
            with c_fin1:
                if fund_data["oranlar"] is not None:
                    st.write("#### Finansal Oranlar")
                    st.dataframe(fund_data["oranlar"], use_container_width=True)
                else:
                    st.info("Oran verisi yok.")
                    
            with c_fin2:
                if fund_data["temettu"] is not None:
                    st.write("#### Temettü Geçmişi")
                    st.dataframe(fund_data["temettu"], use_container_width=True)
                else:
                    st.info("Temettü verisi yok.")
            
            if fund_data["sermaye"] is not None:
                st.write("#### Sermaye Artırımları")
                st.dataframe(fund_data["sermaye"], use_container_width=True)

    else:
        st.error(f"⚠️ {sembol} için veri çekilemedi. Lütfen sembolü kontrol edin veya daha sonra tekrar deneyin.")
