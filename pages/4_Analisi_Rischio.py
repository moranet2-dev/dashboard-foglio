# pages/4_Analisi_Rischio.py

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import utils # Importa il file di utilità

st.set_page_config(page_title="Analisi Rischio", layout="wide")
st.title("Analisi del Rischio del Portafoglio")

# La funzione check_data_loaded garantisce che l'utente sia loggato
# e che i dati siano stati caricati in session_state.
utils.check_data_loaded()
df_original = st.session_state.df

# --- LA FUNZIONE LOCALE È STATA RIMOSSA, ORA USIAMO QUELLA IN UTILS.PY ---

with st.spinner("Calcolo della serie storica del portafoglio..."):
    # --- MODIFICA CHIAVE: Chiamiamo la funzione centralizzata ---
    portfolio_value = utils.calculate_historical_portfolio_value(df_original)

if portfolio_value is None or portfolio_value.empty:
    st.error("Impossibile calcolare l'analisi del rischio. Controlla i ticker nel tuo foglio o la connessione a yfinance.")
    st.stop()

# Calcoliamo i ritorni giornalieri dalla serie storica del valore
daily_returns = portfolio_value.pct_change().dropna()

# --- SEZIONE 1: VOLATILITÀ ---
st.header("Volatilità")
st.markdown("Misura le fluttuazioni del valore del portafoglio. Più è alta, più è rischioso.")

if not daily_returns.empty:
    annualized_volatility = daily_returns.std() * np.sqrt(252)
    st.metric("Volatilità Annualizzata del Portafoglio", f"{annualized_volatility:.2%}")

    rolling_volatility = daily_returns.rolling(window=30).std() * np.sqrt(252)
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(x=rolling_volatility.index, y=rolling_volatility, mode='lines', name='Volatilità Mobile (30 giorni)', fill='tozeroy', line_color='purple'))
    fig_vol.update_layout(title="Andamento della Volatilità nel Tempo", yaxis_title="Volatilità Annualizzata", yaxis_tickformat=".0%")
    st.plotly_chart(fig_vol, use_container_width=True)
else:
    st.warning("Non ci sono abbastanza dati per calcolare la volatilità.")


# --- SEZIONE 2: DRAWDOWN ---
st.header("Drawdown")
st.markdown("Misura la perdita percentuale dal punto più alto (picco) raggiunto.")

# Il drawdown si calcola sulla serie storica del valore del portafoglio
cumulative_max = portfolio_value.cummax()
drawdown = (portfolio_value - cumulative_max) / cumulative_max

if not drawdown.empty:
    st.metric("Massimo Drawdown Storico", f"{drawdown.min():.2%}", help="La massima perdita percentuale subita da un picco.")

    fig_drawdown_area = go.Figure()
    fig_drawdown_area.add_trace(go.Scatter(x=drawdown.index, y=drawdown, mode='lines', name='Drawdown', fill='tozeroy', line_color='red'))
    
    # Aggiunge un'annotazione per il massimo drawdown
    max_drawdown_date = drawdown.idxmin()
    max_drawdown_value = drawdown.min()
    fig_drawdown_area.add_annotation(
        x=max_drawdown_date, 
        y=max_drawdown_value,
        text=f"Max Drawdown: {max_drawdown_value:.2%}<br>on {max_drawdown_date.strftime('%d-%m-%Y')}",
        showarrow=True, arrowhead=1, ax=0, ay=-60, bgcolor="rgba(255, 255, 255, 0.7)"
    )
    
    fig_drawdown_area.update_layout(title="Periodi di Drawdown del Portafoglio", yaxis_title="Perdita dal Picco", yaxis_tickformat=".1%")
    st.plotly_chart(fig_drawdown_area, use_container_width=True)
else:
    st.warning("Non ci sono abbastanza dati per calcolare il drawdown.")