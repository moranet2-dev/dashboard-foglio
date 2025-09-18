# 1_Dashboard_Generale.py
import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import utils
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Dashboard Portafoglio", layout="wide")

# --- SEZIONE 1: CONFIGURAZIONE AUTENTICAZIONE DA st.secrets (MODIFICATA) ---
try:
    # La lettura da st.secrets ora è più diretta
    users_config = st.secrets["database"]["users"]
    
    credentials = {
        "usernames": {
            # Iteriamo sulla configurazione degli utenti
            username: {
                "name": user_details["name"],
                "password": user_details["password_hash"]
            } for username, user_details in users_config.items()
        }
    }

    if not credentials["usernames"]:
         raise ValueError("Nessun utente trovato nella configurazione dei secrets.")

except (AttributeError, KeyError, ValueError) as e:
    st.error(f"Configurazione degli utenti non trovata o malformata in st.secrets: {e}")
    st.info("Assicurati di aver configurato correttamente i Secrets in Streamlit Cloud.")
    st.stop()

# Inizializza l'oggetto authenticator
authenticator = stauth.Authenticate(
    credentials,
    "portfolio_cookie",
    "a_random_secret_key_change_it", # IMPORTANTE: cambia questa chiave con una stringa casuale
    cookie_expiry_days=30
)

# Renderizza il widget di login
name, authentication_status, username = authenticator.login()

# --- SEZIONE 2: LOGICA DELL'APP DOPO IL LOGIN ---
if authentication_status:
    # --- Interfaccia utente post-login ---
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.title(f"Benvenuto {name}")

    # --- Caricamento dati specifico per l'utente loggato ---
    if 'df' not in st.session_state or st.session_state.get('current_user') != username:
        st.session_state.current_user = username
        with st.spinner(f"Caricamento dati per {name}..."):
            st.session_state.df = utils.load_and_clean_data(username=username)

    df_original = st.session_state.df
    if df_original.empty:
        st.error("Impossibile caricare i dati. Controlla la configurazione del tuo foglio Google.")
        st.stop()

    # invariato
        st.title("Dashboard Generale del Portafoglio")

        st.sidebar.header("Filtri Transazioni")
        tutti_i_tipi = sorted(df_original['Tipo Transazione'].unique())
        tipi_selezionati = st.sidebar.multiselect("Seleziona Tipo Transazione", options=tutti_i_tipi, default=tutti_i_tipi)
        df_filtrato_tipo = df_original[df_original['Tipo Transazione'].isin(tipi_selezionati)].copy()

        st.sidebar.header("Filtri Temporali")
        min_date = df_original['Data Acquisto'].min().date()
        max_date_data = df_original['Data Acquisto'].max().date()
        start_date = st.sidebar.date_input("Da", min_date, min_value=min_date, max_value=max_date_data)
        end_date = st.sidebar.date_input("A", max_date_data, min_value=min_date, max_value=max_date_data)

        df_filtrato = df_filtrato_tipo[(df_filtrato_tipo['Data Acquisto'].dt.date >= start_date) & (df_filtrato_tipo['Data Acquisto'].dt.date <= end_date)].copy()

        if df_filtrato.empty:
            st.warning("Nessuna transazione trovata per i filtri selezionati.")
            st.stop()
        else:
            st.info(f"Visualizzazione per: {', '.join(tipi_selezionati)} | Periodo: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")

        total_cost = df_filtrato['Cost Base'].sum()
        total_current_value = df_filtrato['Valore Titoli Real'].sum()
        total_gain = total_current_value - total_cost
        total_gain_perc = (total_gain / total_cost) * 100 if total_cost > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Valore Attuale", f"€ {total_current_value:,.2f}")
        col2.metric("Costo Totale", f"€ {total_cost:,.2f}")
        col3.metric("Guadagno/Perdita", f"€ {total_gain:,.2f}", f"{total_gain_perc:.2f}%")

        st.header("Visualizzazioni di Allocazione")
        alloc_df = df_filtrato.groupby('Ticker')['Valore Titoli Real'].sum().reset_index()
        tab1, tab2, tab3 = st.tabs(["Treemap", "Grafico a Torta", "Grafico a Barre"])
        with tab1:
            fig_treemap = px.treemap(alloc_df, path=['Ticker'], values='Valore Titoli Real', title='Allocazione Portafoglio per Ticker', color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_treemap.update_traces(textinfo='label+percent root')
            st.plotly_chart(fig_treemap, use_container_width=True)
        with tab2:
            fig_pie = px.pie(alloc_df, values='Valore Titoli Real', names='Ticker', title='Allocazione per Ticker')
            st.plotly_chart(fig_pie, use_container_width=True)
        with tab3:
            alloc_df_sorted = alloc_df.sort_values('Valore Titoli Real', ascending=True)
            fig_bar = px.bar(alloc_df_sorted, x='Valore Titoli Real', y='Ticker', orientation='h', title='Valore per Ticker')
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.header("Andamento Cumulativo del Portafoglio Filtrato")
        if not df_filtrato_tipo.empty:
            df_cumulative_base = df_filtrato_tipo[df_filtrato_tipo['Data Acquisto'].dt.date <= end_date].sort_values('Data Acquisto')
            df_cumulative_base['Costo Cumulativo Totale'] = df_cumulative_base['Cost Base'].cumsum()
            df_cumulative_base['Valore Cumulativo Approssimato'] = df_cumulative_base['Valore Titoli Real'].cumsum()
            fig_cumulative = go.Figure()
            fig_cumulative.add_trace(go.Scatter(x=df_cumulative_base['Data Acquisto'], y=df_cumulative_base['Costo Cumulativo Totale'], mode='lines', name='Costo Totale Cumulativo', line=dict(color='red', dash='dot', shape='spline')))
            fig_cumulative.add_trace(go.Scatter(x=df_cumulative_base['Data Acquisto'], y=df_cumulative_base['Valore Cumulativo Approssimato'], mode='lines', name='Valore Totale Cumulativo (Approssimato)', line=dict(color='green', shape='spline'), fill='tonexty', fillcolor='rgba(0,255,0,0.2)'))
            fig_cumulative.update_layout(title="Andamento del Costo vs. Valore Attuale", yaxis_title="Valore (€)", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
            fig_cumulative.update_xaxes(range=[start_date, end_date])
            st.plotly_chart(fig_cumulative, use_container_width=True)

# --- SEZIONE 3: GESTIONE STATI DI LOGIN NON RIUSCITI ---
elif authentication_status == False:
    st.error('Username o password non corretti')
elif authentication_status == None:
    st.warning('Per favore, inserisci username e password per continuare')