import streamlit as st
import gspread
from datetime import datetime
import pandas as pd
import utils 
import time

st.set_page_config(page_title="Inserimento Operazioni", layout="centered")
st.title("Inserimento Nuove Operazioni")

# --- SEQUENZA TICKER PER SESSIONE GUIDATA ---
SEQUENZA_TICKER = ['BIT:MEUD', 'BIT:VHVE', 'AMS:EMIM', 'BIT:XDEM', 'BIT:XDEQ', 'LON:WSML']

# --- INIZIALIZZAZIONE DELLO STATO DELLA SESSIONE (invariata) ---
if 'modalita_inserimento' not in st.session_state:
    st.session_state.modalita_inserimento = 'menu'
if 'ticker_corrente_index' not in st.session_state:
    st.session_state.ticker_corrente_index = 0
if 'data_sessione' not in st.session_state:
    st.session_state.data_sessione = datetime.now().date()
if 'operazioni_sessione' not in st.session_state:
    st.session_state.operazioni_sessione = []
if 'saveback_pending' not in st.session_state:
    st.session_state.saveback_pending = False

# --- FUNZIONI DI UTILITÀ PER LA PAGINA (invariate) ---
def reset_sessione():
    st.session_state.modalita_inserimento = 'menu'
    st.session_state.ticker_corrente_index = 0
    st.session_state.operazioni_sessione = []
    st.session_state.saveback_pending = False

def salva_operazione(username: str, data_to_write: dict):
    progress_bar = st.progress(0, text="Operazione in corso...")
    try:
        user_config = st.secrets.database.users[username]
        user_creds = st.secrets.google_credentials[username]
        google_sheet_name = user_config.sheet_name
        progress_bar.progress(25, text="Connessione al Google Foglio...")
        client = utils.get_gspread_client_for_user(user_creds)
        if client is None: raise Exception("Impossibile connettersi a Google Sheets.")
        sheet = client.open(google_sheet_name).worksheet("Holding")
        header_row_index = 3
        headers = sheet.row_values(header_row_index)
        header_map = {header: i + 1 for i, header in enumerate(headers)}
        reference_header = 'Data Acquisto'
        reference_col_index = header_map.get(reference_header)
        if not reference_col_index: raise ValueError(f"La colonna di riferimento '{reference_header}' non è stata trovata.")
        reference_col_values = sheet.col_values(reference_col_index)
        data_values_in_col = reference_col_values[header_row_index:]
        num_data_rows = len([val for val in data_values_in_col if val])
        next_empty_row = num_data_rows + header_row_index + 1
        cells_to_update = [gspread.Cell(row=next_empty_row, col=header_map[h], value=v) for h, v in data_to_write.items() if h in header_map]
        progress_bar.progress(50, text="Salvataggio dati nel foglio...")
        if cells_to_update:
            sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        progress_bar.progress(75, text="Aggiornamento dati nell'app...")
        st.cache_data.clear()
        st.session_state.df = utils.load_and_clean_data(username)
        time.sleep(1)
        progress_bar.progress(100, text="Completato!")
        st.success("Operazione aggiunta e dati aggiornati con successo!")
        time.sleep(1)
        return True
    except KeyError:
        progress_bar.empty(); st.error(f"Configurazione non trovata per l'utente '{username}' in st.secrets."); return False
    except Exception as e:
        progress_bar.empty(); st.error(f"Errore durante il salvataggio: {e}"); return False

# --- CONTROLLO DATI CARICATI E RECUPERO UTENTE (invariato) ---
utils.check_data_loaded()
df_original = st.session_state.df
username = st.session_state.get('current_user') 
if not username:
    st.error("Utente non riconosciuto. Esegui nuovamente il login dalla pagina principale."); st.stop()
ticker_list = sorted(df_original['Ticker'].unique())
df_unique_names = df_original.drop_duplicates(subset=['Ticker'])
ticker_to_name = pd.Series(df_unique_names['Nome Titolo'].values, index=df_unique_names['Ticker']).to_dict()

# ==============================================================================
# --- VISTA MENU PRINCIPALE (invariata) ---
# ==============================================================================
if st.session_state.modalita_inserimento == 'menu':
    st.markdown("---")
    if not df_original.empty:
        ultima_data = df_original['Data Acquisto'].max()
        st.markdown(f"<h3 style='text-align: center; color: #FFBF00;'>Ultima Operazione Registrata: {ultima_data.strftime('%d/%m/%Y')}</h3>", unsafe_allow_html=True)
    else:
        st.markdown("<h3 style='text-align: center; color: #FFBF00;'>Nessuna operazione ancora registrata.</h3>", unsafe_allow_html=True)
    st.markdown("---")
    st.header("Scegli la modalità di inserimento")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Sessione Guidata"); st.write("Inserisci le operazioni ricorrenti.")
            if st.button("Avvia Sessione Guidata", use_container_width=True, type="primary"):
                st.session_state.modalita_inserimento = 'guidata_setup'; st.rerun()
    with col2:
        with st.container(border=True):
            st.subheader("Operazione Singola"); st.write("Inserisci una singola operazione.")
            if st.button("Inserisci Operazione Singola", use_container_width=True):
                st.session_state.modalita_inserimento = 'singola'; st.rerun()

# ==============================================================================
# --- VISTA INSERIMENTO SINGOLO (Ripristinata come l'originale) ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'singola':
    with st.form("single_transaction_form"):
        st.header("Inserimento Operazione Singola")
        c1, c2, c3 = st.columns(3)
        data_acquisto = c1.date_input("Data Acquisto", datetime.now().date())
        ticker = c1.selectbox("Ticker", ticker_list, format_func=lambda t: f"{t} - {ticker_to_name.get(t, '')}")
        categoria = c2.selectbox("Categoria", ['Stocks', 'Azione', 'Bond', 'Saveback', 'Round-up', 'Altro'])
        n_share_str = c2.text_input("Numero di Quote", "0,0")
        market_value_acquisto_str = c3.text_input("Prezzo per Quota in €", "0,0")
        commissioni_str = c3.text_input("Commissioni in €", "0,0")
        submitted_single = st.form_submit_button("Aggiungi Operazione", use_container_width=True)
        
    if st.button("Torna al Menu", type="secondary"): reset_sessione(); st.rerun()
        
    if submitted_single:
        n_share_val = utils.valida_e_converti_numero(n_share_str)
        price_val = utils.valida_e_converti_numero(market_value_acquisto_str)
        if n_share_val and price_val is not None:
            commissioni = utils.valida_e_converti_numero(commissioni_str) or 0.0
            data_to_write = {
                'Stock / ETF Ticker Symbol': ticker, 'Investment Category': categoria,
                'n. share': str(n_share_str).replace('.', ','),
                'Market Value ACQUISTO': str(market_value_acquisto_str).replace('.', ','),
                'Data Acquisto': data_acquisto.strftime('%d/%m/%Y'),
                'Trading Fees': str(commissioni_str).replace('.', ',')
            }
            if salva_operazione(username, data_to_write): reset_sessione(); st.rerun()
        else:
            st.error("I campi 'Numero di Quote' e 'Prezzo' devono essere validi e maggiori di zero.")
            
# ==============================================================================
# --- VISTA SETUP SESSIONE GUIDATA (MODIFICATA per mostrare lo storico corretto) ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'guidata_setup':
    st.header("Setup Sessione Guidata")
    data_scelta = st.date_input("Seleziona la data per tutte le operazioni di questa sessione", datetime.now().date())
    
    # --- MODIFICA CHIAVE: Storico mostrato qui, con il filtro corretto ---
    st.subheader("Storico Ultime Sessioni Guidate")
    # Filtra solo per categoria 'Stocks', non per data
    storico_df = df_original[df_original['Categoria'] == 'Stocks']
    if not storico_df.empty:
        # Trova le ultime date uniche, inclusa quella di oggi se presente
        ultime_date_uniche = sorted(storico_df['Data Acquisto'].dt.date.unique(), reverse=True)
        
        # Mostra le ultime 2 o 3 sessioni, a seconda di quante ce ne sono
        if ultime_date_uniche:
            for data in ultime_date_uniche[:3]: # Mostra fino a 3 sessioni recenti
                with st.expander(f"Operazioni del {data.strftime('%d/%m/%Y')}"):
                    ops_giorno = storico_df[storico_df['Data Acquisto'].dt.date == data]
                    st.dataframe(ops_giorno[['Ticker', 'n. share', 'Market Value ACQUISTO']], hide_index=True, use_container_width=True)
        else:
            st.info("Nessuna sessione guidata precedente trovata.")
    else:
        st.info("Nessuna sessione guidata precedente trovata.")
    st.markdown("---")
    # --- FINE MODIFICA ---

    c1, c2 = st.columns(2)
    if c2.button("Inizia Sessione", use_container_width=True, type="primary"):
        st.session_state.data_sessione = data_scelta
        st.session_state.modalita_inserimento = 'guidata_inserimento'
        st.rerun()
    if c1.button("Annulla", use_container_width=True, type="secondary"):
        reset_sessione(); st.rerun()

# ==============================================================================
# --- VISTA INSERIMENTO SAVEBACK (Ripristinata) ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'saveback':
    with st.form("saveback_form"):
        st.header("Aggiungi Operazione Saveback")
        st.info(f"Data di acquisto: {st.session_state.data_sessione.strftime('%d/%m/%Y')}")
        c1, c2 = st.columns(2)
        ticker_saveback = c1.selectbox("Ticker per il Saveback", ticker_list, format_func=lambda t: f"{t} - {ticker_to_name.get(t, 'N/A')}")
        n_share_saveback_str = c1.text_input("Numero di Quote", "0,0")
        market_value_saveback_str = c2.text_input("Prezzo per Quota in €", "0,0")
        submitted_saveback = st.form_submit_button("Aggiungi Saveback e Continua Sessione", use_container_width=True)
        
    if submitted_saveback:
        n_share_sb_val = utils.valida_e_converti_numero(n_share_saveback_str)
        price_sb_val = utils.valida_e_converti_numero(market_value_saveback_str)
        if n_share_sb_val and price_sb_val is not None:
            total_cost_sb = n_share_sb_val * price_sb_val
            data_to_write = {
                'Stock / ETF Ticker Symbol': ticker_saveback, 'Investment Category': 'Saveback',
                'n. share': str(n_share_saveback_str).replace('.', ','),
                'Market Value ACQUISTO': str(market_value_saveback_str).replace('.', ','),
                'Data Acquisto': st.session_state.data_sessione.strftime('%d/%m/%Y'), 'Trading Fees': '0,00',
                'Costo Operazione': total_cost_sb # Aggiunto per il riepilogo
            }
            if salva_operazione(username, data_to_write):
                st.session_state.operazioni_sessione.append(data_to_write)
                st.session_state.modalita_inserimento = 'guidata_inserimento'; st.rerun()
        else:
            st.error("I campi numerici non sono validi o sono uguali a zero.")

# ==============================================================================
# --- VISTA INSERIMENTO GUIDATO (Ripristinata) ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'guidata_inserimento':
    idx = st.session_state.ticker_corrente_index
    
    # NOTA: Lo storico ora è mostrato in guidata_setup, quindi non serve più qui.
    
    if idx < len(SEQUENZA_TICKER):
        ticker_corrente = SEQUENZA_TICKER[idx]
        nome_titolo = ticker_to_name.get(ticker_corrente, "Nome non trovato")
        st.header(f"Passo {idx + 1}/{len(SEQUENZA_TICKER)}: `{ticker_corrente}`")
        st.caption(nome_titolo)
        st.info(f"Data Acquisto: {st.session_state.data_sessione.strftime('%d/%m/%Y')}")
        
        with st.form(f"form_{ticker_corrente}_{idx}"):
            c1, c2 = st.columns(2)
            n_share_str = c1.text_input("Numero di Quote", "0,0", key=f"share_{idx}")
            market_value_acquisto_str = c2.text_input("Prezzo per Quota in €", "0,0", key=f"price_{idx}")
            saveback_checkbox = st.checkbox("Aggiungi operazione Saveback dopo questa", key=f"sb_{idx}")
            submitted_guided = st.form_submit_button("Aggiungi e Prosegui", use_container_width=True, type="primary")
            sub_c1, sub_c2 = st.columns(2)
            skipped = sub_c1.form_submit_button("Salta Ticker", use_container_width=True, type="secondary")
            stopped = sub_c2.form_submit_button("Interrompi Sessione", use_container_width=True, type="secondary")
            
        if submitted_guided:
            n_share_val_g = utils.valida_e_converti_numero(n_share_str)
            price_val_g = utils.valida_e_converti_numero(market_value_acquisto_str)
            if n_share_val_g and price_val_g is not None:
                total_cost_g = n_share_val_g * price_val_g
                data_to_write = {
                    'Stock / ETF Ticker Symbol': ticker_corrente, 'Investment Category': 'Stocks',
                    'n. share': str(n_share_str).replace('.', ','),
                    'Market Value ACQUISTO': str(market_value_acquisto_str).replace('.', ','),
                    'Data Acquisto': st.session_state.data_sessione.strftime('%d/%m/%Y'), 'Trading Fees': '0,00',
                    'Costo Operazione': total_cost_g # Aggiunto per il riepilogo
                }
                if salva_operazione(username, data_to_write):
                    st.session_state.operazioni_sessione.append(data_to_write)
                    st.session_state.ticker_corrente_index += 1
                    if saveback_checkbox:
                        st.session_state.modalita_inserimento = 'saveback'
                    st.rerun()
            else:
                st.warning("Numero di quote e prezzo devono essere validi e maggiori di zero.")
        if skipped: st.session_state.ticker_corrente_index += 1; st.rerun()
        if stopped: st.info("Sessione interrotta."); time.sleep(1); reset_sessione(); st.rerun()
    else:
        st.header("Sessione Guidata Completata!"); st.balloons()
        st.success("Tutte le operazioni della sequenza sono state processate.")
        st.subheader("Menu Azioni Successive")
        c1, c2, c3 = st.columns(3)
        if c1.button("Nuova Sessione Guidata", use_container_width=True):
            reset_sessione(); st.session_state.modalita_inserimento = 'guidata_setup'; st.rerun()
        if c2.button("Inserisci Op. Singola", use_container_width=True):
            reset_sessione(); st.session_state.modalita_inserimento = 'singola'; st.rerun()
        if c3.button("Menu Principale", use_container_width=True, type="secondary"):
            reset_sessione(); st.rerun()

# ==============================================================================
# --- RIEPILOGO SESSIONE (invariato) ---
# ==============================================================================
if st.session_state.operazioni_sessione:
    st.subheader("Riepilogo Operazioni di Questa Sessione")
    df_recap = pd.DataFrame(st.session_state.operazioni_sessione)
    df_recap_display = df_recap.rename(columns={
        'Stock / ETF Ticker Symbol': 'Ticker', 'Investment Category': 'Categoria',
        'n. share': 'Quote', 'Market Value ACQUISTO': 'Prezzo Unit.',
        'Data Acquisto': 'Data', 'Trading Fees': 'Commissioni'
    })
    
    if 'Costo Operazione' in df_recap_display.columns:
        df_recap_display['Costo Operazione'] = df_recap_display['Costo Operazione'].apply(lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        colonne_da_mostrare = ['Data', 'Ticker', 'Categoria', 'Quote', 'Prezzo Unit.', 'Costo Operazione']
    else:
        colonne_da_mostrare = ['Data', 'Ticker', 'Categoria', 'Quote', 'Prezzo Unit.']

    st.dataframe(df_recap_display[colonne_da_mostrare], use_container_width=True, hide_index=True)