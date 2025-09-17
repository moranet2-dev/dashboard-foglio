# pages/3_Inserimento_Operazioni.py

import streamlit as st
import gspread
from datetime import datetime, timedelta
import pandas as pd
import utils 
import time

st.set_page_config(page_title="Inserimento Operazioni", layout="centered")
st.title("Inserimento Nuove Operazioni")

# --- SEQUENZA TICKER PER SESSIONE GUIDATA ---
SEQUENZA_TICKER = ['BIT:MEUD', 'BIT:VHVE', 'AMS:EMIM', 'BIT:XDEM', 'BIT:XDEQ', 'LON:WSML']

# --- INIZIALIZZAZIONE DELLO STATO DELLA SESSIONE ---
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

# --- FUNZIONI DI UTILITÀ PER LA PAGINA ---
def reset_sessione():
    st.session_state.modalita_inserimento = 'menu'
    st.session_state.ticker_corrente_index = 0
    st.session_state.operazioni_sessione = []
    st.session_state.saveback_pending = False

def salva_operazione(data_to_write):
    # ... (invariata)
    progress_bar = st.progress(0, text="Operazione in corso...")
    try:
        progress_bar.progress(25, text="Connessione al Google Foglio...")
        client = utils.get_gspread_client()
        sheet = client.open("Conto_2025_3.0 - P").worksheet("Holding")
        header_row_index = 3
        headers = sheet.row_values(header_row_index)
        header_map = {header: i + 1 for i, header in enumerate(headers)}
        reference_header = 'Data Acquisto'
        reference_col_index = header_map.get(reference_header)
        if not reference_col_index:
            raise ValueError(f"La colonna di riferimento '{reference_header}' non è stata trovata.")
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
        st.session_state.df = utils.load_and_clean_data()
        time.sleep(1)
        progress_bar.progress(100, text="Completato!")
        st.success("Operazione aggiunta e dati aggiornati con successo!")
        time.sleep(1)
        return True
    except Exception as e:
        progress_bar.empty()
        st.error(f"Errore durante il salvataggio: {e}")
        return False

def valida_e_converti_numero(testo_numero):
    # ... (invariata)
    if not isinstance(testo_numero, str) or not testo_numero.strip():
        return None
    try:
        valore_float = float(testo_numero.strip().replace(',', '.'))
        return valore_float
    except ValueError:
        return None

# --- CONTROLLO DATI CARICATI ---
utils.check_data_loaded()
df_original = st.session_state.df
ticker_list = sorted(df_original['Ticker'].unique())
ticker_to_name = pd.Series(df_original['Nome Titolo'].values, index=df_original['Ticker']).to_dict()


# ==============================================================================
# --- VISTA MENU PRINCIPALE ---
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
    with st.container(border=True):
        st.subheader("Sessione Guidata")
        st.write("Inserisci rapidamente le operazioni ricorrenti seguendo una sequenza predefinita.")
        if st.button("Avvia Sessione Guidata", use_container_width=True, type="primary"):
            st.session_state.modalita_inserimento = 'guidata_setup'
            st.rerun()
    st.write("")
    with st.container(border=True):
        st.subheader("Operazione Singola")
        st.write("Inserisci manualmente una singola operazione con tutti i campi personalizzabili.")
        if st.button("Inserisci Operazione Singola", use_container_width=True):
            st.session_state.modalita_inserimento = 'singola'
            st.rerun()

# ==============================================================================
# --- VISTA INSERIMENTO SINGOLO ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'singola':
    with st.form("single_transaction_form"):
        # ... (codice invariato)
        st.header("Inserimento Operazione Singola")
        c1, c2, c3 = st.columns(3)
        data_acquisto = c1.date_input("Data Acquisto", datetime.now().date())
        ticker = c1.selectbox("Ticker", ticker_list)
        categoria = c2.selectbox("Categoria", ['Stocks', 'Azione', 'Bond', 'Saveback', 'Round-up', 'Altro'])
        n_share_str = c2.text_input("Numero di Quote", "0,0")
        market_value_acquisto_str = c3.text_input("Prezzo per Quota in €", "0,0")
        commissioni_str = c3.text_input("Commissioni in €", "0,0")
        submitted_single = st.form_submit_button("Aggiungi Operazione", use_container_width=True)
    if st.button("Torna al Menu", type="secondary"):
        reset_sessione()
        st.rerun()
    if submitted_single:
        # ... (codice invariato)
        n_share = valida_e_converti_numero(n_share_str)
        market_value_acquisto = valida_e_converti_numero(market_value_acquisto_str)
        commissioni = valida_e_converti_numero(commissioni_str)
        if n_share is not None and market_value_acquisto is not None and commissioni is not None and n_share > 0 and market_value_acquisto > 0:
            data_to_write = {
                'Stock / ETF Ticker Symbol': ticker, 'Investment Category': categoria,
                'n. share': str(n_share_str).replace('.', ','),
                'Market Value ACQUISTO': str(market_value_acquisto_str).replace('.', ','),
                'Data Acquisto': data_acquisto.strftime('%d/%m/%Y'),
                'Trading Fees': str(commissioni_str).replace('.', ',')
            }
            if salva_operazione(data_to_write):
                reset_sessione()
                st.rerun()
        else:
            st.error("I campi numerici non sono validi o sono uguali a zero.")
            
# ==============================================================================
# --- VISTA SETUP SESSIONE GUIDATA (MODIFICATA) ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'guidata_setup':
    st.header("Setup Sessione Guidata")
    data_scelta = st.date_input("Seleziona la data per tutte le operazioni di questa sessione", datetime.now().date())
    
    # --- MODIFICA: Inversione dei pulsanti ---
    c1, c2 = st.columns(2)
    if c2.button("Inizia Sessione", use_container_width=True, type="primary"):
        st.session_state.data_sessione = data_scelta
        st.session_state.modalita_inserimento = 'guidata_inserimento'
        st.rerun()
    if c1.button("Annulla", use_container_width=True, type="secondary"):
        reset_sessione()
        st.rerun()

# ==============================================================================
# --- VISTA INSERIMENTO SAVEBACK ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'saveback':
    with st.form("saveback_form"):
        # ... (codice invariato)
        st.header("Aggiungi Operazione Saveback")
        st.info(f"La data di acquisto è impostata al {st.session_state.data_sessione.strftime('%d/%m/%Y')}")
        c1, c2 = st.columns(2)
        ticker_saveback = c1.selectbox("Seleziona il Ticker per il Saveback", ticker_list, format_func=lambda t: f"{t} - {ticker_to_name.get(t, 'N/A')}")
        n_share_saveback_str = c1.text_input("Numero di Quote", "0,0")
        market_value_saveback_str = c2.text_input("Prezzo per Quota in €", "0,0")
        submitted_saveback = st.form_submit_button("Aggiungi Saveback e Continua Sessione", use_container_width=True)
    if submitted_saveback:
        # ... (codice invariato)
        n_share_saveback = valida_e_converti_numero(n_share_saveback_str)
        market_value_saveback = valida_e_converti_numero(market_value_saveback_str)
        if n_share_saveback is not None and market_value_saveback is not None and n_share_saveback > 0 and market_value_saveback > 0:
            data_to_write = {
                'Stock / ETF Ticker Symbol': ticker_saveback, 'Investment Category': 'Saveback',
                'n. share': str(n_share_saveback_str).replace('.', ','),
                'Market Value ACQUISTO': str(market_value_saveback_str).replace('.', ','),
                'Data Acquisto': st.session_state.data_sessione.strftime('%d/%m/%Y'),
                'Trading Fees': '0,00'
            }
            if salva_operazione(data_to_write):
                st.session_state.operazioni_sessione.append(data_to_write)
                st.session_state.modalita_inserimento = 'guidata_inserimento'
                st.rerun()
        else:
            st.error("I campi numerici non sono validi o sono uguali a zero.")

# ==============================================================================
# --- VISTA INSERIMENTO GUIDATO (MODIFICATA) ---
# ==============================================================================
elif st.session_state.modalita_inserimento == 'guidata_inserimento':
    idx = st.session_state.ticker_corrente_index
    
    # --- NUOVO: Mostra storico sessioni precedenti solo la prima volta ---
    if idx == 0 and not st.session_state.operazioni_sessione:
        st.subheader("Storico Ultime Sessioni Guidate")
        # Filtra per operazioni di tipo 'Stocks' che non siano nella data della sessione corrente
        storico_df = df_original[(df_original['Categoria'] == 'Stocks') & (df_original['Data Acquisto'].dt.date != st.session_state.data_sessione)]
        if not storico_df.empty:
            # Trova le ultime due date uniche
            ultime_date = storico_df['Data Acquisto'].dt.date.unique()
            ultime_due_date = sorted(ultime_date, reverse=True)[:2]
            
            if ultime_due_date:
                for data in ultime_due_date:
                    with st.expander(f"Operazioni del {data.strftime('%d/%m/%Y')}"):
                        ops_giorno = storico_df[storico_df['Data Acquisto'].dt.date == data]
                        st.dataframe(ops_giorno[['Ticker', 'n. share', 'Market Value ACQUISTO']], hide_index=True, use_container_width=True)
            else:
                st.info("Nessuna sessione guidata precedente trovata.")
        else:
            st.info("Nessuna sessione guidata precedente trovata.")
        st.markdown("---")


    if idx < len(SEQUENZA_TICKER):
        # ... (codice form invariato)
        ticker_corrente = SEQUENZA_TICKER[idx]
        nome_titolo = ticker_to_name.get(ticker_corrente, "Nome non trovato")
        st.header(f"Passo {idx + 1}/{len(SEQUENZA_TICKER)}")
        st.subheader(f"Inserimento per: `{ticker_corrente}`")
        st.caption(nome_titolo)
        st.info(f"Data Acquisto: {st.session_state.data_sessione.strftime('%d/%m/%Y')} | Categoria: Stocks | Commissioni: 0.00 €")
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
            # ... (codice logica sottomissione invariato)
            n_share = valida_e_converti_numero(n_share_str)
            market_value_acquisto = valida_e_converti_numero(market_value_acquisto_str)
            if n_share is not None and market_value_acquisto is not None and n_share > 0 and market_value_acquisto > 0:
                data_to_write = {
                    'Stock / ETF Ticker Symbol': ticker_corrente, 'Investment Category': 'Stocks',
                    'n. share': str(n_share_str).replace('.', ','),
                    'Market Value ACQUISTO': str(market_value_acquisto_str).replace('.', ','),
                    'Data Acquisto': st.session_state.data_sessione.strftime('%d/%m/%Y'),
                    'Trading Fees': '0,00'
                }
                if salva_operazione(data_to_write):
                    st.session_state.operazioni_sessione.append(data_to_write)
                    st.session_state.ticker_corrente_index += 1
                    if saveback_checkbox:
                        st.session_state.modalita_inserimento = 'saveback'
                    st.rerun()
            else:
                st.warning("Numero di quote e prezzo devono essere validi e maggiori di zero.")
        if skipped:
            st.session_state.ticker_corrente_index += 1
            st.rerun()
        if stopped:
            st.info("Sessione interrotta.")
            time.sleep(1)
            reset_sessione()
            st.rerun()

    else: # --- MODIFICA: Fine della sessione con menu completo ---
        st.header("Sessione Guidata Completata!")
        st.balloons()
        st.success("Tutte le operazioni della sequenza sono state processate.")

        st.subheader("Menu Azioni Successive")
        c1, c2, c3 = st.columns(3)
        if c1.button("Inizia Nuova Sessione Guidata", use_container_width=True, type="primary"):
            reset_sessione()
            st.session_state.modalita_inserimento = 'guidata_setup' # Vai direttamente al setup
            st.rerun()
        if c2.button("Inserisci Operazione Singola", use_container_width=True):
            reset_sessione()
            st.session_state.modalita_inserimento = 'singola'
            st.rerun()
        if c3.button("Torna al Menu Principale", use_container_width=True, type="secondary"):
            reset_sessione()
            st.rerun()

    # Riepilogo sessione corrente (mostrato durante e alla fine)
    if st.session_state.operazioni_sessione:
        st.subheader("Riepilogo Operazioni di Questa Sessione")
        df_recap = pd.DataFrame(st.session_state.operazioni_sessione)
        df_recap_display = df_recap.rename(columns={
            'Stock / ETF Ticker Symbol': 'Ticker', 'Investment Category': 'Categoria',
            'n. share': 'Quote', 'Market Value ACQUISTO': 'Prezzo',
            'Data Acquisto': 'Data', 'Trading Fees': 'Commissioni'
        })
        st.dataframe(df_recap_display[['Data', 'Ticker', 'Categoria', 'Quote', 'Prezzo', 'Commissioni']], use_container_width=True, hide_index=True)