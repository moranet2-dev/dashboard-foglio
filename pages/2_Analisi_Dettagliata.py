# pages/2_Analisi_Dettagliata.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime
import utils

st.set_page_config(page_title="Analisi Dettagliata", layout="wide")
st.title("Analisi Dettagliata per Titolo")

utils.check_data_loaded()
df_original = st.session_state.df

@st.cache_data
def prepare_ticker_data(df_ticker):
    # ... (funzione invariata)
    df_sorted = df_ticker.sort_values('Data Acquisto').reset_index(drop=True)
    df_sorted['Costo Cumulativo'] = df_sorted['Cost Base'].cumsum()
    df_sorted['Quote Cumulative'] = df_sorted['n. share'].cumsum()
    df_sorted['PMC Evoluzione'] = df_sorted.apply(
        lambda row: row['Costo Cumulativo'] / row['Quote Cumulative'] if row['Quote Cumulative'] > 0 else 0,
        axis=1
    )
    current_price = df_sorted['Prezzo Attuale'].iloc[-1] if not df_sorted.empty else 0
    df_sorted['Valore Reale Cumulativo'] = df_sorted['Quote Cumulative'] * current_price
    return df_sorted

@st.cache_data(ttl=3600)
def get_comparison_data(tickers, start_date, end_date):
    # ... (funzione invariata)
    try:
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)['Close']
        if data.empty: return pd.DataFrame()
        if isinstance(data, pd.Series):
             data = data.to_frame(name=tickers[0])
        return (data / data.iloc[0] * 100).dropna(axis=0, how='all')
    except Exception as e:
        st.error(f"Errore durante il download dei dati di mercato: {e}")
        return pd.DataFrame()

# --- INTERFACCIA E LOGICA PRINCIPALE ---

trans_df = df_original[df_original['Tipo Transazione'].isin(['ETF', 'Azione', 'Bond'])].copy()

if trans_df.empty:
    st.warning("Nessuna transazione di tipo 'ETF', 'Azione' o 'Bond' trovata nei dati.")
    st.stop()

# --- MODIFICA 1: Creazione della mappa Ticker -> Nome ---
# Creiamo un dizionario per associare ogni ticker al suo nome, prendendo solo valori unici.
df_unique_names = trans_df.drop_duplicates(subset=['Ticker'])
ticker_to_name = pd.Series(df_unique_names['Nome Titolo'].values, index=df_unique_names['Ticker']).to_dict()

ticker_list = sorted(trans_df['Ticker'].unique())

# --- MODIFICA 2: Aggiunta di format_func al selettore ---
# Usiamo format_func per mostrare sia il ticker che il nome nel menu a tendina.
selected_ticker = st.sidebar.selectbox(
    "Seleziona un Ticker", 
    ticker_list,
    format_func=lambda t: f"{t} - {ticker_to_name.get(t, 'Nome non disponibile')}"
)

df_ticker = trans_df[trans_df['Ticker'] == selected_ticker].copy()
df_ticker_analysis_full = prepare_ticker_data(df_ticker)

# Recupera il nome completo del titolo selezionato
selected_ticker_name = ticker_to_name.get(selected_ticker, "")

st.sidebar.header("Filtro Temporale per Titolo")
min_date_ticker = df_ticker['Data Acquisto'].min().date()
max_date_ticker = df_ticker['Data Acquisto'].max().date()
start_date_ticker = st.sidebar.date_input("Dal", min_date_ticker, min_value=min_date_ticker, max_value=max_date_ticker, key=f"start_{selected_ticker}")
end_date_ticker = st.sidebar.date_input("Al", max_date_ticker, min_value=min_date_ticker, max_value=max_date_ticker, key=f"end_{selected_ticker}")

df_display = df_ticker_analysis_full[
    (df_ticker_analysis_full['Data Acquisto'].dt.date >= start_date_ticker) &
    (df_ticker_analysis_full['Data Acquisto'].dt.date <= end_date_ticker)
].copy()

if df_display.empty:
    st.warning("Nessuna transazione trovata per questo titolo nel periodo selezionato.")
    st.stop()

st.info(f"Visualizzazione per {selected_ticker} | Periodo: {start_date_ticker.strftime('%d/%m/%Y')} - {end_date_ticker.strftime('%d/%m/%Y')}")

# --- GRAFICI ---

# --- MODIFICA 3: Aggiunta del nome del fondo all'intestazione ---
st.header(f"Valore vs. Costo Cumulativo per {selected_ticker}")
if selected_ticker_name:
    st.subheader(f"*{selected_ticker_name}*") # Aggiunge il nome in corsivo sotto l'header

fig_val_cost = go.Figure()
fig_val_cost.add_trace(go.Scatter(x=df_display['Data Acquisto'], y=df_display['Costo Cumulativo'], mode='lines', name='Costo Base Totale', line=dict(color='red', dash='dot')))
fig_val_cost.add_trace(go.Scatter(x=df_display['Data Acquisto'], y=df_display['Valore Reale Cumulativo'], mode='lines', name='Valore Reale Totale', line=dict(color='green')))
fig_val_cost.update_layout(title="Andamento del Valore dell'Investimento vs. Costo Sostenuto", yaxis_title="Valore (€)", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
st.plotly_chart(fig_val_cost, use_container_width=True)

st.header("Evoluzione del Prezzo Medio di Carico (PMC)")
fig_pmc = go.Figure()
fig_pmc.add_trace(go.Scatter(x=df_display['Data Acquisto'], y=df_display['PMC Evoluzione'], mode='lines', name='PMC nel Tempo', line=dict(shape='hv')))
fig_pmc.update_layout(title="Andamento del PMC dopo ogni acquisto", xaxis_title="Data Acquisto", yaxis_title="Prezzo Medio di Carico (€)")
st.plotly_chart(fig_pmc, use_container_width=True)

# --- SEZIONE DI CONFRONTO CON BENCHMARK ---
st.header(f"Confronto Performance di {selected_ticker}")
if selected_ticker_name:
    st.subheader(f"*{selected_ticker_name}*")

BENCHMARKS = {
    # ... (codice invariato)
    "S&P 500 (Indice USA)": "^GSPC", "Nasdaq 100 (Indice USA Tech)": "^NDX",
    "MSCI World (ETF Globale, USD)": "URTH", "FTSE All-World (ETF Globale, EUR)": "VWCE.DE",
    "MSCI Emerging Markets (ETF Emergenti, USD)": "EEM", "Euro Stoxx 50 (Indice Europa)": "^STOXX50E",
    "Oro (Future)": "GC=F", "Bitcoin (USD)": "BTC-USD"
}
with st.expander("Mostra suggerimenti per i ticker di benchmark"):
    # ... (codice invariato)
    table_header = "| Nome Descrittivo | Ticker per Yahoo Finance |\n|---|---|\n"
    table_rows = ""
    for name, ticker in BENCHMARKS.items():
        table_rows += f"| {name} | `{ticker}` |\n"
    st.markdown(table_header + table_rows)

yf_selected_ticker_series = pd.Series([selected_ticker])
yf_selected_ticker = utils.clean_ticker_for_yf(yf_selected_ticker_series).iloc[0]
benchmark_ticker_input = st.text_input("Inserisci un Ticker di Benchmark", value="^GSPC")

if benchmark_ticker_input:
    yf_benchmark_ticker = utils.clean_ticker_for_yf(pd.Series([benchmark_ticker_input])).iloc[0]
    st.write(f"Richiesta dati per i ticker: **{yf_selected_ticker}** e **{yf_benchmark_ticker}**")
    comparison_df = get_comparison_data([yf_selected_ticker, yf_benchmark_ticker], start_date_ticker, end_date_ticker)
    if not comparison_df.empty:
        fig_comp = px.line(comparison_df, title=f'Performance Normalizzata: {selected_ticker} vs {benchmark_ticker_input}')
        fig_comp.update_layout(yaxis_title="Performance (Base 100)", legend_title="Ticker")
        st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.warning("Impossibile caricare i dati per il confronto. Verificare che entrambi i ticker siano corretti e disponibili su Yahoo Finance per il periodo selezionato.")

# --- TABELLA STORICO OPERAZIONI ---
st.header("Storico Operazioni")
if selected_ticker_name:
    st.subheader(f"*{selected_ticker_name}*")
    
df_ticker_filtered_table = df_ticker[
    (df_ticker['Data Acquisto'].dt.date >= start_date_ticker) &
    (df_ticker['Data Acquisto'].dt.date <= end_date_ticker)
]
cols_to_display = ['Data Acquisto', 'Tipo Transazione', 'n. share', 'Market Value ACQUISTO', 'Cost Base', 'Guadagno Oggi']
existing_cols = [col for col in cols_to_display if col in df_ticker_filtered_table.columns]
st.data_editor(
    df_ticker_filtered_table[existing_cols].sort_values('Data Acquisto', ascending=False),
    use_container_width=True, hide_index=True, num_rows="dynamic"
)