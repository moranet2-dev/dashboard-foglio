# pages/3_Inserimento_Operazioni.py

import streamlit as st
import gspread
from datetime import datetime
import pandas as pd
import utils 
import time

st.set_page_config(page_title="Inserimento Operazioni", layout="centered")
st.title("Inserimento Nuove Operazioni")

# --- INIZIALIZZAZIONE DELLO STATO DELLA SESSIONE ---
if 'modalita_inserimento' not in st.session_state:
    st.session_state.modalita_inserimento = 'menu'
if 'ticker_corrente_index' not in st.session_state:
    st.session_state.ticker_corrente_index = 0
if 'data_sessione' not in st.session_state:
    st.session_state.data_sessione = datetime.now().date()
if 'operazioni_sessione' not in st.session_state:
    st.session_state.operazioni_sessione = []

# --- FUNZIONI DI UTILITÀ PER LA PAGINA ---
def reset_sessione():
    st.session_state.modalita_inserimento = 'menu'
    st.session_state.ticker_corrente_index = 0
    st.session_state.operazioni_sessione = []

def salva_operazione(username: str, data_to_write: dict):
    with st.spinner("Salvataggio in corso..."):
        try:
            user_config = st.secrets.database.users[username]
            user_creds = st.secrets.google_credentials[username]
            google_sheet_name = user_config.sheet_name
            client = utils.get_gspread_client_for_user(user_creds)
            if client is None: raise Exception("Impossibile connettersi a Google Sheets.")
            sheet = client.open(google_sheet_name).worksheet("Holding")
            header_row_index = 3
            headers = sheet.row_values(header_row_index)
            header_map = {header: i + 1 for i, header in enumerate(headers)}
            reference_header = 'Data Acquisto'
            reference_col_index = header_map.get(reference_header)
            if not reference_col_index: raise ValueError(f"Colonna '{reference_header}' non trovata.")
            reference_col_values = sheet.col_values(reference_col_index)
            num_data_rows = len([val for val in reference_col_values[header_row_index:] if val])
            next_empty_row = num_data_rows + header_row_index + 1
            cells_to_update = [gspread.Cell(row=next_empty_row, col=header_map[h], value=v) for h, v in data_to_write.items() if h in header_map]
            if cells_to_update:
                sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.session_state.df = utils.load_and_clean_data(username)
                st.success("Operazione aggiunta!")
                time.sleep(1)
                return True
            return False
        except Exception as e:
            st.error(f"Errore durante il salvataggio: {e}"); return False

def mostra_riepilogo_corrente(titolo="Riepilogo Sessione Corrente"):
    if st.session_state.operazioni_sessione:
        st.subheader(titolo) # Usa il titolo passato come argomento
        df_recap = pd.DataFrame(st.session_state.operazioni_sessione)
        df_recap_display = df_recap.rename(columns={
            'Stock / ETF Ticker Symbol': 'Ticker', 'Investment Category': 'Categoria',
            'n. share': 'Quote', 'Market Value ACQUISTO': 'Prezzo'
        })
        st.dataframe(df_recap_display[['Ticker', 'Categoria', 'Quote', 'Prezzo']], use_container_width=True, hide_index=True)

def mostra_storico_sessioni(df_principale):
    """Mostra lo storico delle ultime 3 sessioni guidate."""
    st.subheader("Storico Ultime 3 Sessioni Guidate")
    
    # Rimuoviamo l'expander esterno
    storico_df = df_principale[df_principale['Categoria'].isin(['Stocks', 'Azione', 'Bond'])]
    if not storico_df.empty:
        ultime_date_uniche = sorted(storico_df['Data Acquisto'].dt.date.unique(), reverse=True)[:3]
        if ultime_date_uniche:
            # Per ogni data, crea un expander separato (questo è permesso)
            for data in ultime_date_uniche:
                with st.expander(f"Dettaglio operazioni del {data.strftime('%d/%m/%Y')}"):
                    ops_giorno = storico_df[storico_df['Data Acquisto'].dt.date == data]
                    st.dataframe(
                        ops_giorno[['Ticker', 'n. share', 'Cost Base']], 
                        hide_index=True, 
                        use_container_width=True
                    )
        else:
            st.info("Nessuna sessione guidata precedente trovata.")
    else:
        st.info("Nessuna sessione guidata precedente trovata.")


# --- LOGICA DI CONTROLLO E CARICAMENTO ---
utils.check_data_loaded()
username = st.session_state.get('current_user')
df_original = st.session_state.df
ticker_list = sorted(df_original['Ticker'].unique())
ticker_to_name = pd.Series(df_original.drop_duplicates('Ticker').set_index('Ticker')['Nome Titolo']).to_dict()

config, _ = utils.carica_configurazione_da_foglio(username)
sequenza_guidata = config.get("Sequenza Guidata", []) if config else []

# ==============================================================================
# VISTA MENU PRINCIPALE
# ==============================================================================
if st.session_state.modalita_inserimento == 'menu':
    st.markdown("---")
    if not df_original.empty:
        ultima_data = df_original['Data Acquisto'].max()
        st.markdown(f"<h3 style='text-align: center; color: #FFBF00;'>Ultima Operazione Registrata: {ultima_data.strftime('%d/%m/%Y')}</h3>", unsafe_allow_html=True)
    st.markdown("---") 
    st.header("Scegli la modalità di inserimento")
    c1, c2 = st.columns(2)
    if c1.button("Avvia Sessione Guidata", use_container_width=True, type="primary", disabled=(not sequenza_guidata)):
        st.session_state.modalita_inserimento = 'guidata_setup'; st.rerun()
    if c2.button("Inserisci Operazione Singola", use_container_width=True):
        st.session_state.modalita_inserimento = 'singola'; st.rerun()
    if not sequenza_guidata:
        st.warning("Modalità 'Sessione Guidata' disabilitata. Aggiungi ticker in 'Sequenza Guidata' nel foglio 'appconfig'.")
    st.markdown("---")
    mostra_storico_sessioni(df_original)

# ==============================================================================
# VISTA INSERIMENTO SINGOLO
# ==============================================================================
elif st.session_state.modalita_inserimento == 'singola':
    st.header("Inserimento Operazione Singola")
    
    with st.form("single_transaction_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            data_acquisto = st.date_input("Data Acquisto", datetime.now().date())
            ticker = st.selectbox("Ticker", ticker_list, format_func=lambda t: f"{t} - {ticker_to_name.get(t, '')}")
        with c2:
            categoria = st.selectbox("Categoria", ['Stocks', 'Azione', 'Bond', 'Saveback', 'RoundUp', 'Altro'])
            n_share_str = st.text_input("Numero di Quote", "0,0")
        with c3:
            market_value_acquisto_str = st.text_input("Prezzo per Quota in €", "0,0")
            commissioni_str = st.text_input("Commissioni in €", "0,0")
        
        submitted_single = st.form_submit_button("Aggiungi Operazione", use_container_width=True)

    # --- LOGICA DI SOTTOMISSIONE CORRETTA E UNIFICATA ---
    if submitted_single:
        # 1. Validazione
        n_share_val = utils.valida_e_converti_numero(n_share_str)
        price_val = utils.valida_e_converti_numero(market_value_acquisto_str)
        
        if n_share_val and price_val and n_share_val > 0 and price_val > 0:
            # 2. Creazione del dizionario dati
            data_to_write = {
                'Stock / ETF Ticker Symbol': ticker, 
                'Investment Category': categoria,
                'n. share': n_share_str.replace('.', ','), 
                'Market Value ACQUISTO': market_value_acquisto_str.replace('.', ','),
                'Data Acquisto': data_acquisto.strftime('%d/%m/%Y'), 
                'Trading Fees': commissioni_str.replace('.', ',')
            }
            # 3. Salvataggio e aggiornamento stato
            if salva_operazione(username, data_to_write):
                st.session_state.operazioni_sessione.append(data_to_write)
                st.rerun() # Ricarica per aggiornare la tabella e pulire il form implicito
        else:
            st.error("I campi 'Numero di Quote' e 'Prezzo' devono essere validi e maggiori di zero.")

    st.markdown("---")
    mostra_riepilogo_corrente()
    
    if st.button("Torna al Menu", type="secondary"):
        reset_sessione()
        st.rerun()
        
#==================================================================
# VISTA SETUP SESSIONE GUIDATA
# ==============================================================================
elif st.session_state.modalita_inserimento == 'guidata_setup':
    st.header("Setup Sessione Guidata")
    data_scelta = st.date_input("Seleziona la data per la sessione", datetime.now().date())
    mostra_storico_sessioni(df_original) # Lo storico va qui
    c1, c2 = st.columns(2)
    if c2.button("Inizia Sessione", use_container_width=True, type="primary"):
        st.session_state.data_sessione = data_scelta
        st.session_state.modalita_inserimento = 'guidata_inserimento'; st.rerun()
    if c1.button("Annulla", use_container_width=True, type="secondary"):
        reset_sessione(); st.rerun()

# ==============================================================================
# VISTE SAVEBACK E ROUND-UP
# ==============================================================================
elif st.session_state.modalita_inserimento in ['saveback', 'roundup']:
    tipo_op = st.session_state.modalita_inserimento.title()
    
    with st.form(f"form_{tipo_op.lower()}", clear_on_submit=True):
        st.header(f"Aggiungi Operazione {tipo_op}")
        c1, c2 = st.columns(2)
        ticker_op = c1.selectbox(f"Ticker per {tipo_op}", ticker_list, format_func=lambda t: f"{t} - {ticker_to_name.get(t, '')}")
        n_share_str = c1.text_input("Numero di Quote", "0,0")
        market_value_str = c2.text_input("Prezzo per Quota in €", "0,0")
        submitted = st.form_submit_button(f"Aggiungi {tipo_op} e Continua")
        
    if submitted:
        n_share_val = utils.valida_e_converti_numero(n_share_str)
        price_val = utils.valida_e_converti_numero(market_value_str)
        if n_share_val and price_val:
            if tipo_op == 'roundup':
                categoria_da_salvare = 'RoundUp'
            else:
                categoria_da_salvare = 'Saveback' # Manteniamo 
            
            # Crea il dizionario qui
            data_to_write = {
                'Stock / ETF Ticker Symbol': ticker_op, 'Investment Category': tipo_op,
                'n. share': n_share_str.replace('.', ','), 
                'Market Value ACQUISTO': market_value_str.replace('.', ','),
                'Data Acquisto': st.session_state.data_sessione.strftime('%d/%m/%Y'), 
                'Trading Fees': '0,00'
            }
            # E poi salva
            if salva_operazione(username, data_to_write):
                st.session_state.operazioni_sessione.append(data_to_write)
                st.session_state.modalita_inserimento = 'guidata_inserimento'
                st.rerun()
        else: 
            st.error("I campi numerici devono essere validi e maggiori di zero.")

# ==============================================================================
# VISTA INSERIMENTO GUIDATO
# ==============================================================================
elif st.session_state.modalita_inserimento == 'guidata_inserimento':
    idx = st.session_state.ticker_corrente_index
    
    mostra_storico_sessioni(df_original)
    st.markdown("---")
    
    if idx < len(sequenza_guidata):
        ticker_corrente = sequenza_guidata[idx]
        nome_titolo = ticker_to_name.get(ticker_corrente, "")
        st.header(f"Passo {idx + 1}/{len(sequenza_guidata)}: `{ticker_corrente}`")
        st.caption(nome_titolo)
        st.info(f"Data Acquisto: {st.session_state.data_sessione.strftime('%d/%m/%Y')}")
        
        with st.form(f"form_{ticker_corrente}_{idx}"):
            c1, c2 = st.columns(2)
            n_share_str = c1.text_input("Numero di Quote", "0,0", key=f"share_{idx}")
            market_value_str = c2.text_input("Prezzo per Quota in €", "0,0", key=f"price_{idx}")
            check_c1, check_c2 = st.columns(2)
            saveback_check = check_c1.checkbox("Aggiungi Saveback", key=f"sb_{idx}")
            roundup_check = check_c2.checkbox("Aggiungi RoundUp", key=f"ru_{idx}")
            submitted_guided = st.form_submit_button("Aggiungi e Prosegui", use_container_width=True, type="primary")
            sub_c1, sub_c2 = st.columns(2)
            skipped = sub_c1.form_submit_button("Salta Ticker", use_container_width=True, type="secondary")
            stopped = sub_c2.form_submit_button("Interrompi Sessione", use_container_width=True, type="secondary")

        if submitted_guided:
            n_share_val = utils.valida_e_converti_numero(n_share_str)
            price_val = utils.valida_e_converti_numero(market_value_str)
            if n_share_val and price_val:
                # Crea il dizionario qui
                data_to_write = {
                    'Stock / ETF Ticker Symbol': ticker_corrente, 'Investment Category': 'Stocks',
                    'n. share': n_share_str.replace('.', ','), 
                    'Market Value ACQUISTO': market_value_str.replace('.', ','),
                    'Data Acquisto': st.session_state.data_sessione.strftime('%d/%m/%Y'), 
                    'Trading Fees': '0,00'
                }
                # E poi salva
                if salva_operazione(username, data_to_write):
                    st.session_state.operazioni_sessione.append(data_to_write)
                    st.session_state.ticker_corrente_index += 1
                    if saveback_check: st.session_state.modalita_inserimento = 'saveback'
                    elif roundup_check: st.session_state.modalita_inserimento = 'roundup'
                    st.rerun()
            else: 
                st.warning("Quote e Prezzo devono essere validi e maggiori di zero.")
        
        if skipped: st.session_state.ticker_corrente_index += 1; st.rerun()
        if stopped: reset_sessione(); st.rerun()
    else:
        st.header("Sessione Guidata Completata!"); st.balloons()
        mostra_riepilogo_corrente("Riepilogo Finale Sessione")
        st.subheader("Menu Azioni Successive")
        c1, c2, c3 = st.columns(3)
        if c1.button("Nuova Sessione Guidata", use_container_width=True):
            reset_sessione(); st.session_state.modalita_inserimento = 'guidata_setup'; st.rerun()
        if c2.button("Inserisci Op. Singola", use_container_width=True):
            reset_sessione(); st.session_state.modalita_inserimento = 'singola'; st.rerun()
        if c3.button("Menu Principale", use_container_width=True, type="secondary"):
            reset_sessione(); st.rerun()