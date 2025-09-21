# 5_Dashboard_Cash_Flow.py

import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import utils 
import time
import plotly.express as px

st.set_page_config(page_title="Dashboard Cash Flow", layout="wide")
st.title("Dashboard Cash Flow")

# --- LOGICA DI CARICAMENTO DATI ---
utils.check_data_loaded()
username = st.session_state.get('current_user')

# Carica tutte le fonti di dati
config, df_config = utils.carica_configurazione_da_foglio(username)
cash_flow_data_raw, _ = utils.load_cash_flow_data(username, config)
totals_entrate_storico_raw, totals_uscite_storico_raw = utils.load_historical_totals(username)

if not config or not cash_flow_data_raw:
    st.warning("Errore nel caricamento dei dati o della configurazione."); st.stop()

# --- LOGICA DI ALLINEAMENTO DATI ---
# 1. Trova l'orizzonte temporale completo
mesi_da_dettaglio = cash_flow_data_raw.get('total_entrate', pd.Series(dtype=float)).index
mesi_da_storico = totals_entrate_storico_raw.index
tutti_i_mesi_unici = sorted(list(set(mesi_da_dettaglio) | set(mesi_da_storico)))

MAPPA_MESI_ITA_NUM = {'GEN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAG': 5, 'GIU': 6, 'LUG': 7, 'AGO': 8, 'SET': 9, 'OTT': 10, 'NOV': 11, 'DIC': 12}
tutti_i_mesi_disponibili = sorted(
    [m for m in tutti_i_mesi_unici if isinstance(m, str) and '/' in m],
    key=lambda m: (int(m.split('/')[1]), MAPPA_MESI_ITA_NUM.get(m.split('/')[0].strip(), 0))
)
available_years = sorted(list({int(m.split('/')[1]) for m in tutti_i_mesi_disponibili}), reverse=True)

# 2. Allinea tutti i dati a questo orizzonte temporale
cash_flow_data = {
    key: data.reindex(tutti_i_mesi_disponibili, fill_value=0)
    for key, data in cash_flow_data_raw.items()
}
totals_entrate_storico = totals_entrate_storico_raw.reindex(tutti_i_mesi_disponibili, fill_value=0)
totals_uscite_storico = totals_uscite_storico_raw.reindex(tutti_i_mesi_disponibili, fill_value=0)

# ==============================================================================
# SEZIONE FILTRI (SPOSTATA NELLA SIDEBAR)
# ==============================================================================
st.sidebar.header("Filtri di Visualizzazione")
mesi_da_dettaglio = cash_flow_data.get('total_entrate', pd.Series(dtype=float)).index
mesi_da_storico = totals_entrate_storico.index
tutti_i_mesi_unici = sorted(list(set(mesi_da_dettaglio) | set(mesi_da_storico)))


MAPPA_MESI_ITA_NUM = {'GEN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAG': 5, 'GIU': 6, 'LUG': 7, 'AGO': 8, 'SET': 9, 'OTT': 10, 'NOV': 11, 'DIC': 12}
tutti_i_mesi_disponibili = sorted(
    [m for m in tutti_i_mesi_unici if isinstance(m, str) and '/' in m],
    key=lambda m: (int(m.split('/')[1]), MAPPA_MESI_ITA_NUM.get(m.split('/')[0].strip(), 0)))
available_years = sorted(list({int(m.split('/')[1]) for m in tutti_i_mesi_disponibili}), reverse=True)


if not tutti_i_mesi_disponibili:
    st.info("Nessun dato mensile trovato per generare l'analisi.")
    st.stop()
else:
    # --- Logica di gestione dello stato per i filtri (invariata) ---
    if 'mesi_selezionati' not in st.session_state:
        st.session_state.mesi_selezionati = tutti_i_mesi_disponibili

    # --- Widget Vista Rapida ---
    opzioni_vista_rapida = ["Selezione Personalizzata", "Seleziona Tutto", "Mese Corrente", "Ultimi 3 Mesi", "Ultimi 6 Mesi", "Ultimi 12 Mesi"]
    
    # Usiamo st.sidebar.selectbox
    vista_selezionata = st.sidebar.selectbox("Vista Rapida", opzioni_vista_rapida, key="vista_selector")

    # --- Logica di aggiornamento (invariata) ---
    if vista_selezionata != "Selezione Personalizzata":
        new_selection = []
        today = datetime.now()
        if vista_selezionata == "Seleziona Tutto":
            new_selection = tutti_i_mesi_disponibili
        elif vista_selezionata == "Mese Corrente":
            mese_corrente_nome = list(MAPPA_MESI_ITA_NUM.keys())[today.month - 1]
            mese_corrente_str = f"{mese_corrente_nome}/{today.year}"
            if mese_corrente_str in tutti_i_mesi_disponibili: new_selection = [mese_corrente_str]
        elif "Ultimi" in vista_selezionata:
            num_mesi = int(vista_selezionata.split(' ')[1])
            try:
                mese_corrente_nome = list(MAPPA_MESI_ITA_NUM.keys())[today.month - 1]
                mese_corrente_str = f"{mese_corrente_nome}/{today.year}"
                end_index = tutti_i_mesi_disponibili.index(mese_corrente_str)
            except ValueError:
                end_index = len(tutti_i_mesi_disponibili) - 1
            start_index = max(0, end_index - num_mesi + 1)
            new_selection = tutti_i_mesi_disponibili[start_index : end_index + 1]
        
        st.session_state.mesi_selezionati = new_selection

    # --- Griglia di selezione manuale nella sidebar ---
    with st.sidebar.expander("Modifica selezione mesi manualmente"):
        for year in sorted(available_years, reverse=True):
            st.write(f"**{year}**")
            mesi_dell_anno = [m for m in tutti_i_mesi_disponibili if str(year) in m]
            tutti_selezionati_anno = all(m in st.session_state.mesi_selezionati for m in mesi_dell_anno)
            
            if st.checkbox(f"Seleziona tutto il {year}", value=tutti_selezionati_anno, key=f"select_all_{year}"):
                for mese in mesi_dell_anno:
                    if mese not in st.session_state.mesi_selezionati: st.session_state.mesi_selezionati.append(mese)
            else:
                if tutti_selezionati_anno:
                    st.session_state.mesi_selezionati = [m for m in st.session_state.mesi_selezionati if str(year) not in m]

            num_colonne = 2 # Meno colonne per adattarsi alla larghezza della sidebar
            colonne_griglia = st.columns(num_colonne)
            for j, mese in enumerate(mesi_dell_anno):
                col = colonne_griglia[j % num_colonne]
                is_selected = mese in st.session_state.mesi_selezionati
                if col.toggle(mese, value=is_selected, key=f"toggle_{mese}") != is_selected:
                    st.session_state.vista_selector = "Selezione Personalizzata"
                    st.rerun()

    colonne_da_usare = st.session_state.mesi_selezionati

# ==============================================================================
# SEZIONE 1: INTERFACCIA UTENTE
# ==============================================================================
st.title("Dashboard Cash Flow")

with st.expander("Inserisci una nuova operazione"):
    # ... (il codice dell'expander con i form rimane identico) ...
    tab_uscita, tab_entrata = st.tabs(["Registra Uscita", "Registra Entrata"])
    with tab_uscita:
        with st.form("form_uscita", clear_on_submit=True):
            st.subheader("Nuova Uscita")
            c1, c2 = st.columns(2)
            with c1:
                data_uscita = st.date_input("Data", datetime.now(), key="d_uscita")
                conto_uscita = st.selectbox("Conto", config["Conto"], index=config["Conto"].index("TradeRepublic") if "TradeRepublic" in config["Conto"] else 0, key="c_uscita")
                tipo_uscita = st.selectbox("Tipo", config["Tipo"], index=config["Tipo"].index("Elettronici") if "Elettronici" in config["Tipo"] else 0, key="t_uscita")
            with c2:
                voce_uscita = st.text_input("Voce (descrizione)", placeholder="Es. Spesa settimanale", key="v_uscita")
                importo_uscita_str = st.text_input("Importo", "0,00", key="i_uscita")
                macro_uscita = st.selectbox("Macro", config["Macro USCITE"], key="ma_uscita")
                micro_uscita = st.selectbox("Micro", config["Micro USCITE"], key="mi_uscita")
                submitted_uscita = st.form_submit_button("Aggiungi Uscita", use_container_width=True, type="primary")
            
            if submitted_uscita:
                importo = utils.valida_e_converti_numero(importo_uscita_str)
                if importo and importo > 0:
                    dati = {"Conto": conto_uscita, "Tipo": tipo_uscita, "Voce": voce_uscita, "Importo": f"€ {importo_uscita_str}", "Data": data_uscita.strftime('%d/%m/%Y'), "Macro": macro_uscita, "Micro": micro_uscita}
                    mese_str = data_uscita.strftime("%b").upper()
                    with st.spinner("Salvataggio..."):
                        success = utils.salva_operazione_cash_flow(username, mese_str, dati, "USCITE")
                    if success: st.success("Uscita salvata!"); time.sleep(1); st.rerun()
                    else: st.error("Salvataggio fallito.")
                else: st.error("Importo non valido.")
    with tab_entrata:
        with st.form("form_entrata", clear_on_submit=True):
            st.subheader("Nuova Entrata")
            c1, c2 = st.columns(2)
            with c1:
                data_entrata = st.date_input("Data", datetime.now(), key="d_entrata")
                conto_entrata = st.selectbox("Conto", config["Conto"], key="c_entrata")
                tipo_entrata = st.selectbox("Tipo", config["Tipo"], index=config["Tipo"].index("Elettronici") if "Elettronici" in config["Tipo"] else 0, key="t_entrata")
            with c2:
                voce_entrata = st.text_input("Voce", placeholder="Es. Stipendio", key="v_entrata")
                importo_entrata_str = st.text_input("Importo", "0,00", key="i_entrata")
                macro_entrata = st.selectbox("Macro", config["Macro ENTRATE"], key="ma_entrata")
                micro_entrata = st.selectbox("Micro", config["Micro ENTRATE"], key="mi_entrata")
                submitted_entrata = st.form_submit_button("Aggiungi Entrata", use_container_width=True, type="primary")
            
            if submitted_entrata:
                importo = utils.valida_e_converti_numero(importo_entrata_str)
                if importo and importo > 0:
                    dati = {"Conto": conto_entrata, "Tipo": "N/A", "Voce": voce_entrata, "Importo": f"€ {importo_entrata_str}", "Data": data_entrata.strftime('%d/%m/%Y'), "Macro": macro_entrata, "Micro": micro_entrata}
                    mese_str = data_entrata.strftime("%b").upper()
                    with st.spinner("Salvataggio..."):
                        success = utils.salva_operazione_cash_flow(username, mese_str, dati, "ENTRATE")
                    if success: st.success("Entrata salvata!"); time.sleep(1); st.rerun()
                    else: st.error("Salvataggio fallito.")
                else: st.error("Importo non valido.")

# ==============================================================================
# SEZIONE 2 E 3: KPI E GRAFICI (CON SINTASSI CORRETTA)
# ==============================================================================
st.markdown("---")
st.header("Analisi Finanziaria")

if not colonne_da_usare:
    st.warning("Seleziona almeno un mese dalla sidebar per visualizzare i dati.")
else:
    # --- LOGICA DI CONFRONTO E KPI (ORA ROBUSTA) ---
    total_entrate_dettaglio = cash_flow_data['total_entrate'][colonne_da_usare].sum()
    total_uscite_dettaglio = cash_flow_data['total_uscite'][colonne_da_usare].sum()
    
    total_entrate_storico = totals_entrate_storico[colonne_da_usare].sum()
    total_uscite_storico = totals_uscite_storico[colonne_da_usare].sum()
    
    total_entrate_finale = max(total_entrate_dettaglio, total_entrate_storico)
    total_uscite_finale = max(total_uscite_dettaglio, total_uscite_storico)
    
    # Warning
    diff_uscite = total_uscite_storico - total_uscite_dettaglio
    if diff_uscite > 0.01:
        st.warning(f"Attenzione: € {diff_uscite:,.2f} di uscite non sono categorizzate. I grafici mostrano solo la parte categorizzata.")
    
    # Calcolo e Visualizzazione KPI
    risparmio_netto = total_entrate_finale - total_uscite_finale
    tasso_risparmio = (risparmio_netto / total_entrate_finale * 100) if total_entrate_finale > 0 else 0
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Entrate Totali", f"€ {total_entrate_finale:,.2f}")
    kpi2.metric("Uscite Totali", f"€ {total_uscite_finale:,.2f}")
    kpi3.metric("Risparmio Netto", f"€ {risparmio_netto:,.2f}")
    kpi4.metric("Tasso di Risparmio", f"{tasso_risparmio:.1f}%")

    # --- VISUALIZZAZIONI GRAFICHE ---
    st.markdown("---")
    st.header("Dettaglio Categorie del Periodo")
    
    df_macro_uscite = cash_flow_data.get('macro_uscite', pd.DataFrame())
    df_micro_uscite = cash_flow_data.get('micro_uscite', pd.DataFrame())
    df_micro_entrate = cash_flow_data.get('micro_entrate', pd.DataFrame())

    # --- FINESTRA DI DEBUG ---
    with st.expander("🔍 Debug: Dati allineati usati per i calcoli"):
        st.write("**`colonne_da_usare` (mesi selezionati):**", colonne_da_usare)
        st.write("**Dati `total_uscite_dettaglio` (allineati):**")
        st.dataframe(cash_flow_data['total_uscite'])
        st.write("**Dati `totals_uscite_storico` (allineati):**")
        st.dataframe(totals_uscite_storico)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Analisi Uscite")
        somma_macro_uscite = df_macro_uscite[colonne_da_usare].sum(axis=1)
        somma_macro_uscite = somma_macro_uscite[somma_macro_uscite > 0]
        if not somma_macro_uscite.empty:
            fig_pie_macro = px.pie(
                values=somma_macro_uscite.values, names=somma_macro_uscite.index,
                title='Composizione Uscite (Macro)', hole=0.4
            )
            st.plotly_chart(fig_pie_macro, use_container_width=True)
        else:
            st.info("Nessuna uscita categorizzata nel periodo selezionato.")
    
    with col2:
        st.subheader("Analisi Entrate")
        somma_micro_entrate = df_micro_entrate[colonne_da_usare].sum(axis=1)
        somma_micro_entrate = somma_micro_entrate[somma_micro_entrate > 0]
        if not somma_micro_entrate.empty:
            fig_bar_entrate = px.bar(
                somma_micro_entrate.sort_values(ascending=True),
                orientation='h', title='Composizione Entrate (Micro)',
                color_discrete_sequence=['#28a745']
            )
            st.plotly_chart(fig_bar_entrate, use_container_width=True)
        else:
            st.info("Nessuna entrata categorizzata nel periodo selezionato.")