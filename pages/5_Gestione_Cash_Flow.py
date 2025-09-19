# pages/5_Gestione_Cash_Flow.py

import streamlit as st
import pandas as pd
from datetime import datetime
import utils 
import time
import gspread # Import necessario per gspread.Cell

st.set_page_config(page_title="Gestione Cash Flow", layout="wide")
st.title("Inserimento Entrate e Uscite Mensili")

# --- CSS DEFINITIVO PER IL PULSANTE VERDE ---
# Questo selettore si aggancia al nome del form, che è un identificatore stabile,
# per garantire che lo stile venga applicato solo al pulsante corretto.
st.markdown("""
<style>
    /* Seleziona il form con l'etichetta specifica 'form_entrata' e applica lo stile al suo pulsante primario */
    form[aria-label="form_entrata"] .stButton button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        border-color: #28a745 !important;
    }
    form[aria-label="form_entrata"] .stButton button[kind="primary"]:hover {
        background-color: #218838 !important;
        border-color: #1e7e34 !important;
        color: white !important;
    }
    form[aria-label="form_entrata"] .stButton button[kind="primary"]:focus {
        box-shadow: 0 0 0 0.2rem rgba(40, 167, 69, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)
# --- FINE CSS ---

if 'entrate_sessione' not in st.session_state:
    st.session_state.entrate_sessione = []
if 'uscite_sessione' not in st.session_state:
    st.session_state.uscite_sessione = []
@st.cache_data(ttl=600)
def carica_configurazione_da_foglio(username):
    """
    Legge il foglio 'appconfig' e restituisce un dizionario con le opzioni per i menu.
    """
    try:
        user_config = st.secrets.database.users[username]
        user_creds = st.secrets.google_credentials[username]
        google_sheet_name = user_config.sheet_name
        
        client = utils.get_gspread_client_for_user(dict(user_creds))
        if client is None:
            raise Exception("Impossibile creare il client per Google Sheets.")
        
        config_sheet = client.open(google_sheet_name).worksheet("appconfig")
        df_config = pd.DataFrame(config_sheet.get_all_records())

        micro_uscite_cols = [col for col in df_config.columns if 'Micro USCITE' in col]
        micro_uscite_list = df_config[micro_uscite_cols].unstack().dropna().unique().tolist()

        config = {
            "Conto": df_config["Conto"].dropna().tolist(),
            "Tipo": df_config["Tipo"].dropna().tolist(),
            "Macro ENTRATE": df_config["Macro ENTRATE"].dropna().tolist(),
            "Micro ENTRATE": sorted(df_config["Micro ENTRATE"].dropna().unique().tolist()),
            "Macro USCITE": df_config["Macro USCITE"].dropna().tolist(),
            "Micro USCITE": sorted(micro_uscite_list)
        }
        return config
    except Exception as e:
        st.error(f"Errore durante il caricamento della configurazione da 'appconfig': {e}")
        return None

def trova_prossima_riga_vuota(sheet, tipo_sezione):
    """
    Trova la prima riga vuota nella sezione 'ENTRATE' o 'USCITE'.
    """
    colonna_voce_valori = sheet.col_values(4) # Colonna D = Voce
    
    if tipo_sezione == "ENTRATE":
        start_row = 7; end_row = 23
        sezione_valori = colonna_voce_valori[start_row-1:end_row]
        for i, cell in enumerate(sezione_valori):
            if not cell.strip(): return start_row + i
        return end_row + 1
        
    elif tipo_sezione == "USCITE":
        start_row = 25
        sezione_valori = colonna_voce_valori[start_row-1:]
        for i, cell in enumerate(sezione_valori):
            if not cell.strip(): return start_row + i
        return len(colonna_voce_valori) + 1
    return None

def salva_operazione_cash_flow(username, mese, data_to_write, tipo_sezione):
    """ Salva i dati nel foglio mensile corretto. """
    try:
        user_config = st.secrets.database.users[username]
        user_creds = st.secrets.google_credentials[username]
        google_sheet_name = user_config.sheet_name
        
        client = utils.get_gspread_client_for_user(dict(user_creds))
        if client is None: return False
        
        sheet = client.open(google_sheet_name).worksheet(mese)
        riga_da_scrivere = trova_prossima_riga_vuota(sheet, tipo_sezione)
        if not riga_da_scrivere:
            st.error("Impossibile trovare una riga libera per l'inserimento.")
            return False

        col_map = {'Conto': 2, 'Tipo': 3, 'Voce': 4, 'Importo': 5, 'Data': 6, 'Macro': 7, 'Micro': 8, 'Flag': 9, 'Note': 10}
        cells_to_update = [gspread.Cell(row=riga_da_scrivere, col=col_map[key], value=value) for key, value in data_to_write.items() if key in col_map]
        
        if cells_to_update:
            sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
            # MODIFICA: Aggiunge alla lista di session_state corretta
            if tipo_sezione == "USCITE":
                st.session_state.uscite_sessione.append(data_to_write)
            else:
                st.session_state.entrate_sessione.append(data_to_write)
            return True
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Errore: il foglio per il mese '{mese}' non è stato trovato. Assicurati che esista.")
        return False
    except Exception as e:
        st.error(f"Errore durante il salvataggio nel foglio '{mese}': {e}")
        return False
    
# --- LOGICA PRINCIPALE DELLA PAGINA ---
utils.check_data_loaded()
username = st.session_state.get('current_user')
config = carica_configurazione_da_foglio(username)

if not config:
    st.warning("Impossibile caricare la configurazione. Verifica che il foglio 'appconfig' esista e sia strutturato correttamente.")
    st.stop()

mesi_anno = ["GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"]
mese_corrente_index = datetime.now().month - 1
mese_selezionato = st.selectbox("Seleziona il mese di riferimento per l'inserimento", mesi_anno, index=mese_corrente_index)
st.markdown("---")

tab_uscite, tab_entrate = st.tabs(["**Registra Uscita**", "**Registra Entrata**"])

with tab_uscite:
    st.subheader("Nuova Uscita")
    with st.form("form_uscita", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            data_uscita = st.date_input("Data", datetime.now(), key="data_uscita")
            conto_uscita = st.selectbox("Conto", config["Conto"], index=config["Conto"].index("TradeRepublic") if "TradeRepublic" in config["Conto"] else 0, key="conto_uscita")
            tipo_uscita = st.selectbox("Tipo", config["Tipo"], index=config["Tipo"].index("Elettronici") if "Elettronici" in config["Tipo"] else 0, key="tipo_uscita")
        with c2:
            voce_uscita = st.text_input("Voce (descrizione)", placeholder="Es. Spesa settimanale")
            importo_uscita_str = st.text_input("Importo", "0,00")
            sub_c1, sub_c2 = st.columns(2)
            macro_uscita = sub_c1.selectbox("Macro", config["Macro USCITE"], key="macro_uscita")
            micro_uscita = sub_c2.selectbox("Micro", config["Micro USCITE"], key="micro_uscita")
        note_uscita = st.text_area("Note")
        st.write("**Flag:**")
        flag_c1, flag_c2, flag_c3 = st.columns(3)
        flag_ricorrenti = flag_c1.checkbox("Ricorrenti", key="flag_r_uscita")
        flag_detraibili = flag_c2.checkbox("Detraibili", key="flag_d_uscita")
        flag_famiglia = flag_c3.checkbox("Famiglia", key="flag_fam_uscita")
        st.write("")
        submitted_uscita = st.form_submit_button("Aggiungi Uscita", use_container_width=True, type="primary")

    if submitted_uscita:
        importo_uscita = utils.valida_e_converti_numero(importo_uscita_str)
        if importo_uscita and importo_uscita > 0:
            flag_list = []
            if flag_ricorrenti: flag_list.append("R")
            if flag_detraibili: flag_list.append("D")
            if flag_famiglia: flag_list.append("FAM")
            dati_da_salvare = {"Conto": conto_uscita, "Tipo": tipo_uscita, "Voce": voce_uscita, "Importo": f"€ {importo_uscita_str}", "Data": data_uscita.strftime('%d/%m/%Y'), "Macro": macro_uscita, "Micro": micro_uscita, "Flag": ", ".join(flag_list), "Note": note_uscita}
            with st.spinner("Salvataggio in corso..."):
                if salva_operazione_cash_flow(username, mese_selezionato, dati_da_salvare, "USCITE"):
                    st.success(f"Uscita '{voce_uscita}' salvata con successo!")
                    time.sleep(2)
                    st.rerun()
        else:
            st.error("L'importo inserito non è valido o è uguale a zero.")

with tab_entrate:
    st.subheader("Nuova Entrata")
    
    # --- MODIFICA: Avvolgiamo il form nel div con la classe personalizzata ---
    st.markdown('<div class="green-button-container">', unsafe_allow_html=True)
    with st.form("form_entrata", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            data_entrata = c1.date_input("Data", datetime.now(), key="data_entrata")
            conto_entrata = c1.selectbox("Conto", config["Conto"], key="conto_entrata")
            tipo_entrata = c1.selectbox("Tipo", config["Tipo"], key="tipo_entrata")
        with c2:
            voce_entrata = c2.text_input("Voce (descrizione)", placeholder="Es. Stipendio")
            importo_entrata_str = c2.text_input("Importo", "0,00")
            sub_c1, sub_c2 = st.columns(2)
            macro_entrata = sub_c1.selectbox("Macro", config["Macro ENTRATE"], key="macro_entrata")
            micro_entrata = sub_c2.selectbox("Micro", config["Micro ENTRATE"], key="micro_entrata")
        note_entrata = st.text_area("Note")
        st.write("")
        submitted_entrata = st.form_submit_button("Aggiungi Entrata", use_container_width=True, type="primary")
    st.markdown('</div>', unsafe_allow_html=True)

    if submitted_entrata:
        importo_entrata = utils.valida_e_converti_numero(importo_entrata_str)
        if importo_entrata and importo_entrata > 0:
            dati_da_salvare = {"Conto": conto_entrata, "Tipo": tipo_entrata, "Voce": voce_entrata, "Importo": f"€ {importo_entrata_str}", "Data": data_entrata.strftime('%d/%m/%Y'), "Macro": macro_entrata, "Micro": micro_entrata, "Note": note_entrata}
            with st.spinner("Salvataggio in corso..."):
                if salva_operazione_cash_flow(username, mese_selezionato, dati_da_salvare, "ENTRATE"):
                    st.success(f"Entrata '{voce_entrata}' salvata con successo!")
                    time.sleep(2)
                    st.rerun()
        else:
            st.error("L'importo inserito non è valido o è uguale a zero.")

# --- TABELLE RIEPILOGATIVE SEPARATE ---
st.markdown("---")
st.header("Operazioni Inserite in Questa Sessione")

# Mostra la tabella delle uscite solo se non è vuota
if st.session_state.uscite_sessione:
    st.subheader("Uscite Registrate")
    df_recap_uscite = pd.DataFrame(st.session_state.uscite_sessione).rename(columns={"Voce": "Descrizione"})
    st.dataframe(df_recap_uscite, use_container_width=True, hide_index=True)

# Mostra la tabella delle entrate solo se non è vuota
if st.session_state.entrate_sessione:
    st.subheader("Entrate Registrate")
    df_recap_entrate = pd.DataFrame(st.session_state.entrate_sessione).rename(columns={"Voce": "Descrizione"})
    st.dataframe(df_recap_entrate, use_container_width=True, hide_index=True)

# Messaggio se entrambe sono vuote
if not st.session_state.uscite_sessione and not st.session_state.entrate_sessione:
    st.info("Nessuna operazione ancora inserita in questa sessione.")