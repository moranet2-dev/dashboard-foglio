# pages/4_Analisi_Rischio.py

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import utils # Importa il nuovo file di utilità

st.set_page_config(page_title="Analisi Rischio", layout="wide")
st.title("Analisi del Rischio del Portafoglio")

# Proposta 1.2: Usa la funzione centralizzata per il controllo
utils.check_data_loaded()
df_original = st.session_state.df

@st.cache_data(ttl=3600)
def calculate_portfolio_timeseries(df_transactions):
    df_copy = df_transactions.copy()
    
    # Usa la funzione di utilità centralizzata per pulire i ticker
    df_copy['yf_ticker'] = utils.clean_ticker_for_yf(df_copy['Ticker'])
    
    yf_tickers = df_copy['yf_ticker'].unique().tolist()
    start_date = df_copy['Data Acquisto'].min()
    
    try:
        prices_df = yf.download(yf_tickers, start=start_date, progress=False)['Close']
        if isinstance(prices_df, pd.Series):
            prices_df = prices_df.to_frame(name=yf_tickers[0])
    except Exception as e:
        st.error(f"Errore durante il download dei dati di mercato: {e}")
        return None, None

    prices_df.ffill(inplace=True)
    holdings_df = pd.DataFrame(0.0, index=prices_df.index, columns=yf_tickers)
    
    for _, row in df_copy.iterrows():
        holdings_df.loc[row['Data Acquisto']:, row['yf_ticker']] += row['n. share']
        
    portfolio_daily_value = (holdings_df * prices_df).sum(axis=1)
    portfolio_daily_value = portfolio_daily_value[portfolio_daily_value > 0]
    
    if portfolio_daily_value.empty:
        return None, None
        
    daily_returns = portfolio_daily_value.pct_change().dropna()
    
    return portfolio_daily_value, daily_returns

with st.spinner("Calcolo della serie storica del portafoglio..."):
    portfolio_value, daily_returns = calculate_portfolio_timeseries(df_original)

if portfolio_value is None or portfolio_value.empty:
    st.error("Impossibile calcolare l'analisi del rischio. Controlla i ticker nel tuo foglio o la connessione a yfinance.")
    st.stop()

# --- SEZIONE 1: VOLATILITÀ ---
st.header("Volatilità")
st.markdown("Misura le fluttuazioni del valore del portafoglio. Più è alta, più è rischioso.")
annualized_volatility = daily_returns.std() * np.sqrt(252)
st.metric("Volatilità Annualizzata del Portafoglio", f"{annualized_volatility:.2%}")

rolling_volatility = daily_returns.rolling(window=30).std() * np.sqrt(252)
fig_vol = go.Figure()
fig_vol.add_trace(go.Scatter(x=rolling_volatility.index, y=rolling_volatility, mode='lines', name='Volatilità Mobile (30 giorni)', fill='tozeroy', line_color='purple'))
fig_vol.update_layout(title="Andamento della Volatilità nel Tempo", yaxis_title="Volatilità Annualizzata", yaxis_tickformat=".0%")
st.plotly_chart(fig_vol, use_container_width=True)

# --- SEZIONE 2: DRAWDOWN ---
st.header("Drawdown")
st.markdown("Misura la perdita percentuale dal punto più alto (picco) raggiunto.")
cumulative_max = portfolio_value.cummax()
drawdown = (portfolio_value - cumulative_max) / cumulative_max

st.metric("Massimo Drawdown Storico", f"{drawdown.min():.2%}", help="La massima perdita percentuale subita da un picco.")

fig_drawdown_area = go.Figure()
fig_drawdown_area.add_trace(go.Scatter(x=drawdown.index, y=drawdown, mode='lines', name='Drawdown', fill='tozeroy', line_color='red'))
fig_drawdown_area.update_layout(title="Periodi di Drawdown del Portafoglio", yaxis_title="Perdita dal Picco", yaxis_tickformat=".1%")

# Proposta 2.4: Aggiunge un'annotazione per il massimo drawdown
if not drawdown.empty:
    max_drawdown_date = drawdown.idxmin()
    max_drawdown_value = drawdown.min()
    fig_drawdown_area.add_annotation(
        x=max_drawdown_date, 
        y=max_drawdown_value,
        text=f"Max Drawdown: {max_drawdown_value:.2%}<br>on {max_drawdown_date.strftime('%d-%m-%Y')}",
        showarrow=True, 
        arrowhead=1,
        ax=0, 
        ay=-60, # Sposta l'annotazione più in basso per leggibilità
        bgcolor="rgba(255, 255, 255, 0.7)"
    )

st.plotly_chart(fig_drawdown_area, use_container_width=True)