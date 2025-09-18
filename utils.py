# utils.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import json
import yfinance as yf

# NOTA: Rimuoviamo tutte le funzioni legate a sqlite3 perché ora usiamo st.secrets

@st.cache_data(ttl=600)
def load_and_clean_data(username: str):
    """
    Carica e pulisce i dati per l'utente specificato, leggendo la configurazione da st.secrets.
    """
    try:
        # --- SEZIONE 1: RECUPERO CONFIGURAZIONE UTENTE DA st.secrets ---
        # Accede alla configurazione dell'utente basandosi sul suo username
        user_config = st.secrets.database.users[username]
        user_creds = st.secrets.google_credentials[username]
        
        google_sheet_name = user_config.sheet_name
        
        # --- SEZIONE 2: CONNESSIONE A GOOGLE SHEETS ---
        # Crea il client gspread usando le credenziali specifiche dell'utente
        scope = [
            "https://spreadsheets.google.com/feeds", 
            'https://www.googleapis.com/auth/spreadsheets',
            "https://www.googleapis.com/auth/drive.file", 
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(user_creds), scope)
        client = gspread.authorize(creds)
        sheet = client.open(google_sheet_name).worksheet("Holding")
        
        # --- SEZIONE 3: LETTURA E COSTRUZIONE DEL DATAFRAME ---
        all_values = sheet.get_all_values()
        if len(all_values) < 4: return pd.DataFrame()
        headers = all_values[2]
        data_rows = all_values[3:]
        df = pd.DataFrame(data_rows, columns=headers)
        df = df.loc[:, df.columns.notna() & (df.columns != '')]
        df = df.loc[:, ~df.columns.duplicated(keep='first')]

    except KeyError:
        st.error(f"Configurazione non trovata per l'utente '{username}' in st.secrets. Controlla il file secrets.toml.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati da Google Fogli: {e}")
        return pd.DataFrame()

    # --- SEZIONE 4: PULIZIA E TRASFORMAZIONE DATI (INVARIATA) ---
    essential_cols = ['Stock / ETF Ticker Symbol', 'Data Acquisto', 'Investment Category']
    for col in essential_cols:
        if col not in df.columns:
            st.error(f"Errore: colonna essenziale '{col}' non trovata. Verificare il foglio Google.")
            return pd.DataFrame()

    df = df[df['Stock / ETF Ticker Symbol'].notna() & (df['Stock / ETF Ticker Symbol'] != '')]

    cols_to_numeric = ['n. share', 'Market Value ACQUISTO', 'Actual Market Value (google)', 'Valore Titoli Real', 'Guadagno Oggi', '% variazione', 'Cost Base', 'Trading Fees']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('€', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['Data Acquisto'] = pd.to_datetime(df['Data Acquisto'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['Data Acquisto'], inplace=True)
    
    df.rename(columns={
        'Stock / ETF Ticker Symbol': 'Ticker', 
        'Actual Market Value (google)': 'Prezzo Attuale',
        'Investment Category': 'Categoria',
        'Nome titolo': 'Nome Titolo'
    }, inplace=True)
    
    if 'Categoria' in df.columns:
        conditions = [
            df['Categoria'].str.contains('Saveback', case=False, na=False),
            df['Categoria'].str.contains('Round-up', case=False, na=False),
            df['Categoria'].str.contains('Azione', case=False, na=False),
            df['Categoria'].str.contains('Bond', case=False, na=False),
            df['Categoria'].str.contains('Stocks', case=False, na=False)
        ]
        choices = ['Saveback', 'RoundUp', 'Azione', 'Bond', 'ETF']
        df['Tipo Transazione'] = np.select(conditions, choices, default='Altro')
    else:
        df['Tipo Transazione'] = 'N/A'

    df['Cost Base Originale'] = df['Cost Base']
    df.loc[df['Tipo Transazione'].isin(['Saveback', 'RoundUp']), 'Cost Base'] = df['n. share'] * df['Market Value ACQUISTO']
    
    return df

# Le funzioni qui sotto sono ancora utili per le altre pagine
def check_data_loaded():
    if 'df' not in st.session_state or st.session_state.df.empty:
        st.warning("I dati non sono stati caricati. Effettua il login dalla Dashboard Generale.")
        st.stop()

def clean_ticker_for_yf(ticker_series: pd.Series) -> pd.Series:
    exchange_map = { 'BIT': '.MI', 'ETR': '.DE', 'LSE': '.L', 'AMS': '.AS' }
    def convert_ticker(ticker):
        if ':' in ticker:
            prefix, symbol = ticker.split(':', 1)
            suffix = exchange_map.get(prefix.upper())
            if suffix: return f"{symbol}{suffix}"
        return ticker
    return ticker_series.apply(convert_ticker)

# --- NUOVA FUNZIONE CENTRALIZZATA PER IL CALCOLO STORICO DEL VALORE ---
@st.cache_data(ttl=3600)
def calculate_historical_portfolio_value(transactions_df: pd.DataFrame):
    """
    Calcola il valore storico giornaliero di un portafoglio di transazioni.
    Usa yfinance per scaricare i prezzi storici.
    Restituisce una Serie pandas con date come indice e valore come dato.
    """
    if transactions_df.empty:
        return pd.Series()

    df_copy = transactions_df.copy()
    df_copy['yf_ticker'] = clean_ticker_for_yf(df_copy['Ticker'])
    
    yf_tickers = df_copy['yf_ticker'].unique().tolist()
    start_date = df_copy['Data Acquisto'].min()
    
    try:
        # Scarica i dati dei prezzi di chiusura
        prices_df = yf.download(yf_tickers, start=start_date, progress=False)['Close']
        if prices_df.empty:
            return pd.Series()
        # Se c'è un solo ticker, yf.download restituisce una Series, la trasformiamo in DataFrame
        if isinstance(prices_df, pd.Series):
            prices_df = prices_df.to_frame(name=yf_tickers[0])
    except Exception:
        return pd.Series()

    # Gestisce i dati mancanti riempiendo con l'ultimo valore valido
    prices_df.ffill(inplace=True)
    
    # Crea un DataFrame per le quote possedute giorno per giorno
    holdings_df = pd.DataFrame(0.0, index=prices_df.index, columns=prices_df.columns)
    
    for _, row in df_copy.iterrows():
        # Per ogni transazione, incrementa il numero di quote dal giorno dell'acquisto in poi
        if row['yf_ticker'] in holdings_df.columns:
            holdings_df.loc[row['Data Acquisto']:, row['yf_ticker']] += row['n. share']
    
    # Calcola il valore giornaliero del portafoglio (quote * prezzo)
    portfolio_daily_value = (holdings_df * prices_df).sum(axis=1)
    
    # Rimuovi i giorni iniziali in cui il valore era zero
    return portfolio_daily_value[portfolio_daily_value > 0]