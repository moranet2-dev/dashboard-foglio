# utils.py
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import json
import yfinance as yf

# --- FUNZIONI DI CONNESSIONE E DI UTILITÀ GENERICA ---
def get_gspread_client_for_user(user_creds):
    """
    Crea un client gspread usando le credenziali specifiche di un utente (passate come dizionario).
    """
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    try:
        if not isinstance(user_creds, dict): 
            user_creds = dict(user_creds)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(user_creds, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Errore nella validazione delle credenziali Google: {e}")
        return None

def check_data_loaded():
    """Controlla se i dati principali sono stati caricati in session_state."""
    if 'df' not in st.session_state or st.session_state.df.empty:
        st.warning("Dati non caricati. Effettua il login dalla Dashboard Generale.")
        st.stop()

def clean_ticker_for_yf(ticker_series: pd.Series) -> pd.Series:
    """Converte i ticker dal formato 'BIT:...' a quello di yfinance '....MI'."""
    exchange_map = {'BIT': '.MI', 'ETR': '.DE', 'LSE': '.L', 'AMS': '.AS'}
    def convert_ticker(ticker):
        if ':' in ticker:
            prefix, symbol = ticker.split(':', 1)
            suffix = exchange_map.get(prefix.upper())
            if suffix: return f"{symbol}{suffix}"
        return ticker
    return ticker_series.apply(convert_ticker)

def valida_e_converti_numero(testo_numero):
    """Converte in sicurezza una stringa (con virgola o punto) in un numero float."""
    if not isinstance(testo_numero, str) or not testo_numero.strip(): return None
    try:
        return float(testo_numero.strip().replace(',', '.'))
    except (ValueError, TypeError):
        return None

# --- FUNZIONI PER IL CARICAMENTO DATI DEL PORTAFOGLIO ('Holding') ---
@st.cache_data(ttl=600)
def load_and_clean_data(username: str):
    """Carica e pulisce i dati del portafoglio dal foglio 'Holding'."""
    try:
        user_config = st.secrets.database.users[username]
        user_creds = st.secrets.google_credentials[username]
        google_sheet_name = user_config.sheet_name
        client = get_gspread_client_for_user(user_creds)
        if client is None: return pd.DataFrame()

        sheet = client.open(google_sheet_name).worksheet("Holding")
        all_values = sheet.get_all_values()
        if len(all_values) < 4: return pd.DataFrame()
        headers = all_values[2]
        data_rows = all_values[3:]
        df = pd.DataFrame(data_rows, columns=headers)
        df = df.loc[:, df.columns.notna() & (df.columns != '')]
        df = df.loc[:, ~df.columns.duplicated(keep='first')]

    except KeyError:
        st.error(f"Configurazione non trovata per l'utente '{username}' in st.secrets.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati da Google Fogli: {e}")
        return pd.DataFrame()

    essential_cols = ['Stock / ETF Ticker Symbol', 'Data Acquisto', 'Investment Category']
    for col in essential_cols:
        if col not in df.columns:
            st.error(f"Errore: colonna essenziale '{col}' non trovata nel foglio 'Holding'.")
            return pd.DataFrame()

    df = df[df['Stock / ETF Ticker Symbol'].notna() & (df['Stock / ETF Ticker Symbol'] != '')]
    cols_to_numeric = ['n. share', 'Market Value ACQUISTO', 'Actual Market Value (google)', 'Valore Titoli Real', 'Guadagno Oggi', '% variazione', 'Cost Base', 'Trading Fees']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('€', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.replace('%', '', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['Data Acquisto'] = pd.to_datetime(df['Data Acquisto'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['Data Acquisto'], inplace=True)
    df.rename(columns={'Stock / ETF Ticker Symbol': 'Ticker', 'Actual Market Value (google)': 'Prezzo Attuale', 'Investment Category': 'Categoria', 'Nome titolo': 'Nome Titolo'}, inplace=True)
    
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

@st.cache_data(ttl=3600)
def calculate_historical_portfolio_value(transactions_df: pd.DataFrame):
    """Calcola il valore storico giornaliero di un portafoglio di transazioni."""
    if transactions_df.empty: return pd.Series()
    df_copy = transactions_df.copy()
    df_copy['yf_ticker'] = clean_ticker_for_yf(df_copy['Ticker'])
    yf_tickers = df_copy['yf_ticker'].unique().tolist()
    start_date = df_copy['Data Acquisto'].min()
    try:
        prices_df = yf.download(yf_tickers, start=start_date, progress=False)['Close']
        if prices_df.empty: return pd.Series()
        if isinstance(prices_df, pd.Series):
            prices_df = prices_df.to_frame(name=yf_tickers[0])
    except Exception:
        return pd.Series()
    prices_df.ffill(inplace=True)
    holdings_df = pd.DataFrame(0.0, index=prices_df.index, columns=prices_df.columns)
    for _, row in df_copy.iterrows():
        if row['yf_ticker'] in holdings_df.columns:
            holdings_df.loc[row['Data Acquisto']:, row['yf_ticker']] += row['n. share']
    portfolio_daily_value = (holdings_df * prices_df).sum(axis=1)
    return portfolio_daily_value[portfolio_daily_value > 0]

# --- FUNZIONI SPECIFICHE PER IL CASH FLOW ---

@st.cache_data(ttl=600)
def carica_configurazione_da_foglio(username: str):
    """Legge SOLO il foglio 'appconfig' e restituisce config e df_config."""
    try:
        user_config = st.secrets.database.users[username]
        user_creds = st.secrets.google_credentials[username]
        google_sheet_name = user_config.sheet_name
        client = get_gspread_client_for_user(dict(user_creds))
        if client is None: raise Exception("Impossibile creare il client GSpread.")
        
        config_sheet = client.open(google_sheet_name).worksheet("appconfig")
        df_config = pd.DataFrame(config_sheet.get_all_records())
        
        micro_uscite_cols = [col for col in df_config.columns if 'Micro USCITE' in col]
        micro_uscite_list = df_config[micro_uscite_cols].unstack().dropna().unique().tolist()
        
        config = {
            "Conto": df_config["Conto"].dropna().tolist(), "Tipo": df_config["Tipo"].dropna().tolist(),
            "Macro ENTRATE": df_config["Macro ENTRATE"].dropna().tolist(), "Micro ENTRATE": sorted(df_config["Micro ENTRATE"].dropna().unique().tolist()),
            "Macro USCITE": df_config["Macro USCITE"].dropna().tolist(), "Micro USCITE": sorted(micro_uscite_list)
        }
        return config, df_config
    except Exception as e:
        st.error(f"Errore caricamento da 'appconfig': {e}"); return None, None

@st.cache_data(ttl=600)
def load_cash_flow_data(username: str, config: dict):
    """
    Carica i dati dal foglio 'IN/OUT' con stampe di debug dettagliate.
    """
    with st.expander("🔍 Debug: Caricamento Dati da Foglio 'IN/OUT'"):
        try:
            st.write("--- **Inizio `load_cash_flow_data`** ---")
            if not config:
                st.error("Configurazione non fornita. Arresto.")
                return {}, []

            # 1. CARICAMENTO GREZZO E CONFIGURAZIONE
            user_config = st.secrets.database.users[username]
            user_creds = st.secrets.google_credentials[username]
            google_sheet_name = user_config.sheet_name
            
            client = get_gspread_client_for_user(user_creds)
            if client is None: 
                st.error("Connessione a Google fallita.")
                return {}, []

            st.write(f"✅ Connesso a Google. Apro il foglio: **{google_sheet_name}**")
            
            sheet_in_out = client.open(google_sheet_name).worksheet("IN/OUT")
            all_values = sheet_in_out.get_all_values()
            df_raw = pd.DataFrame(all_values)

            st.write("✅ Foglio 'IN/OUT' letto. **DataFrame grezzo (prime 25 righe):**")
            st.dataframe(df_raw.head(25))

            # 2. RICERCA DINAMICA DELL'HEADER MASTER
            st.write("Cerco 'Macro ENTRATE' nella colonna B (indice 1)...")
            colonna_b_raw = df_raw.iloc[:, 1]
            header_row_matches = colonna_b_raw[colonna_b_raw.str.strip() == 'Macro ENTRATE']
            
            st.write(f"Risultati trovati per 'Macro ENTRATE': `{len(header_row_matches)}`")

            if header_row_matches.empty:
                st.error("ERRORE CRITICO: Non sono riuscito a trovare la riga con l'intestazione 'Macro ENTRATE' nella colonna B. Controlla che sia scritta esattamente così nel foglio 'IN/OUT'.")
                return {}, []
            
            header_row_index = header_row_matches.index[0]
            st.write(f"✅ Trovata intestazione master alla riga con indice: `{header_row_index}`")
            
            # ... (il resto della funzione rimane invariato ma è dentro il try/except per sicurezza)
            header_row_values = df_raw.iloc[header_row_index].tolist()
            master_headers_mesi = [h for h in header_row_values if isinstance(h, str) and '/' in h]
            header_to_col_index = {h: i for i, h in enumerate(header_row_values) if h in master_headers_mesi}
            
            tables = {}
        

        except IndexError:
             st.error("ERRORE: `single positional indexer is out-of-bounds`. Questo di solito significa che una riga chiave (come 'Macro ENTRATE') non è stata trovata, quindi il DataFrame dei risultati è vuoto.")
             st.info("Controlla lo screenshot del DataFrame grezzo qui sopra e verifica che le etichette nella colonna B siano identiche a quelle del foglio di configurazione e al foglio originale.")
             st.dataframe(colonna_b_raw.to_frame(name="Colonna B Analizzata"))
             return {}, []
        except Exception as e:
            st.error(f"Errore grave durante il caricamento da 'IN/OUT': {e}")
            st.exception(e)
            return {}, []
    
    # Questo return è fuori dal blocco `with`, ma dentro la funzione
    return tables, available_years # Assumendo che tables e available_years siano definite prima dell'except
        

def trova_prossima_riga_vuota_cash_flow(sheet, tipo_sezione):
    # ...
    pass
def salva_operazione_cash_flow(username, mese, data_to_write, tipo_sezione):
    # ...
    pass