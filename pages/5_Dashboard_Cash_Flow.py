# 5_Dashboard_Cash_Flow.py

import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import utils 
import time
import plotly.express as px


st.set_page_config(page_title="Dashboard Cash Flow", layout="wide")

# --- LOGICA DI CARICAMENTO DATI ---
utils.check_data_loaded()
username = st.session_state.get('current_user')

# Carica sia la configurazione che i dati del cash flow
config, df_config = utils.carica_configurazione_da_foglio(username)
cash_flow_data, available_years = utils.load_cash_flow_data(username, config)

if not config or not cash_flow_data or not available_years:
    st.warning("Errore nel caricamento dei dati o della configurazione.")
    st.stop()

# ==============================================================================
# SEZIONE FILTRI (SPOSTATA NELLA SIDEBAR)
# ==============================================================================
st.sidebar.header("Filtri di Visualizzazione")

s_total_entrate = cash_flow_data.get('total_entrate', pd.Series(dtype=float))
MAPPA_MESI_ITA_NUM = {'GEN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAG': 5, 'GIU': 6, 'LUG': 7, 'AGO': 8, 'SET': 9, 'OTT': 10, 'NOV': 11, 'DIC': 12}
tutti_i_mesi_disponibili = sorted(
    [col for col in s_total_entrate.index if isinstance(col, str) and '/' in col],
    key=lambda m: (int(m.split('/')[1]), MAPPA_MESI_ITA_NUM.get(m.split('/')[0].strip(), 0))
)

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
# SEZIONE 2: FILTRO AVANZATO CON LOGICA DIPENDENTE
# ==============================================================================

if not colonne_da_usare:
    st.warning("Seleziona almeno un mese dalla sidebar per visualizzare i dati.")
else:
    # --- MODIFICA CHIAVE: CREAZIONE DEL TITOLO DINAMICO ---
    periodo_selezionato_str = vista_selezionata
    if vista_selezionata == "Selezione Personalizzata":
        # Se la selezione è personalizzata, mostra il range di date
        colonne_ordinate = sorted(colonne_da_usare, key=lambda m: (int(m.split('/')[1]), MAPPA_MESI_ITA_NUM.get(m.split('/')[0].strip(), 0)))
        if len(colonne_ordinate) > 1:
            periodo_selezionato_str = f"da {colonne_ordinate[0]} a {colonne_ordinate[-1]}"
        elif len(colonne_ordinate) == 1:
            periodo_selezionato_str = colonne_ordinate[0]
        else:
            periodo_selezionato_str = "Nessun periodo"
    
    st.success(f"Dati visualizzati per: **{periodo_selezionato_str}**")
    
    # Calcolo KPI
    s_total_uscite = cash_flow_data.get('total_uscite', pd.Series(dtype=float))
    total_entrate = s_total_entrate.get(colonne_da_usare, 0).sum()
    total_uscite = s_total_uscite.get(colonne_da_usare, 0).sum()
    risparmio_netto = total_entrate - total_uscite
    tasso_risparmio = (risparmio_netto / total_entrate * 100) if total_entrate > 0 else 0
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(label="Entrate Totali", value=f"€ {total_entrate:,.2f}")
    kpi2.metric(label="Uscite Totali", value=f"€ {total_uscite:,.2f}")
    kpi3.metric(label="Risparmio Netto", value=f"€ {risparmio_netto:,.2f}")
    kpi4.metric(label="Tasso di Risparmio", value=f"{tasso_risparmio:.1f}%")

#==============================================================================
# SEZIONE 3: VISUALIZZAZIONI GRAFICHE (CON AGGIUNTA MICRO)
# ==============================================================================
st.markdown("---")
st.header("Analisi Uscite ({periodo_selezionato_str})")

df_macro_uscite_raw = cash_flow_data.get('macro_uscite', pd.DataFrame())
df_micro_uscite_raw = cash_flow_data.get('micro_uscite', pd.DataFrame())

df_macro_uscite = df_macro_uscite_raw.loc[(df_macro_uscite_raw.sum(axis=1) != 0)]
df_micro_uscite = df_micro_uscite_raw.loc[(df_micro_uscite_raw.sum(axis=1) != 0)]

if 'colonne_da_usare' in locals() and colonne_da_usare:
    
    # --- ANALISI USCITE ---
    st.subheader("Analisi Uscite del Periodo")
    
    df_macro_uscite = cash_flow_data.get('macro_uscite', pd.DataFrame()).loc[lambda df: df.sum(axis=1) != 0]
    df_micro_uscite = cash_flow_data.get('micro_uscite', pd.DataFrame()).loc[lambda df: df.sum(axis=1) != 0]

    if df_macro_uscite.empty:
        st.info("Nessuna uscita registrata nel periodo selezionato.")
    else:
        somma_macro_uscite = df_macro_uscite[colonne_da_usare].sum(axis=1).sort_values(ascending=False)
        somma_micro_uscite = df_micro_uscite[colonne_da_usare].sum(axis=1).sort_values(ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie_macro = px.pie(
                values=somma_macro_uscite.values,
                names=somma_macro_uscite.index,
                title='Composizione Uscite (Macro)',
                hole=0.4
            )
            st.plotly_chart(fig_pie_macro, use_container_width=True)

        with col2:
            fig_bar_micro = px.bar(
                somma_micro_uscite.sort_values(ascending=True),
                x=somma_micro_uscite.sort_values(ascending=True).values,
                y=somma_micro_uscite.sort_values(ascending=True).index,
                orientation='h',
                title='Top Voci di Spesa (Micro)'
            )
            st.plotly_chart(fig_bar_micro, use_container_width=True)

    st.markdown("---")
    
    # --- ANALISI ENTRATE ---
    st.subheader("Analisi Entrate del Periodo")
    
    # Nota: Per le entrate non abbiamo la distinzione Macro/Micro, usiamo le categorie disponibili
    df_micro_entrate = cash_flow_data.get('micro_entrate', pd.DataFrame()).loc[lambda df: df.sum(axis=1) != 0]

    if df_micro_entrate.empty:
        st.info("Nessuna entrata registrata nel periodo selezionato.")
    else:
        somma_micro_entrate = df_micro_entrate[colonne_da_usare].sum(axis=1).sort_values(ascending=False)
        
        # Per le entrate, usiamo un unico grafico a barre orizzontali
        st.write("**Dettaglio Entrate per Categoria**")
        fig_bar_entrate = px.bar(
            somma_micro_entrate.sort_values(ascending=True),
            x=somma_micro_entrate.sort_values(ascending=True).values,
            y=somma_micro_entrate.sort_values(ascending=True).index,
            orientation='h',
            title='Composizione Entrate',
            color_discrete_sequence=['#28a745'] # Colore verde
        )
        st.plotly_chart(fig_bar_entrate, use_container_width=True)

else:
    st.info("Seleziona un periodo per visualizzare le analisi.")