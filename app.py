import streamlit as st
import pandas as pd
from google import genai
import datetime

# 2. Interfaz y Visualización - Configuración inicial
st.set_page_config(page_title="Dashboard Marketing Digital", layout="wide")

@st.cache_data
def load_data():
    # 1. Datos - Lectura del CSV adjunto
    # Se saltan las dos primeras filas por el formato del reporte de Google Ads
    df = pd.read_csv("test-informe-paid.csv", sep="\t", skiprows=2, thousands=".", decimal=",", encoding="utf-16")
    
    # Limpieza: Rellenar NAs numéricos con 0
    numeric_cols = df.select_dtypes(include=['number']).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)
    
    # Limpiar columnas monetarias/numéricas que puedan venir como texto
    for col in ['Coste', 'Valor de conv.', 'Conversiones', 'CPC medio']:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('"', '').str.replace('.', '').str.replace(',', '.').apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # Filtrar el dataset para eliminar regiones agregadas (mantén solo filas donde iso_code NO sea nulo)
    if 'iso_code' in df.columns:
        df = df[df['iso_code'].notna()]
        
    # Convertir fecha a datetime
    if 'Semana' in df.columns:
        df['Semana'] = pd.to_datetime(df['Semana'], errors='coerce')
        
    # Generar columnas de marca y hotel en caso de no venir explícitas (basado en 'Campaña')
    if 'hotel' not in df.columns and 'Campaña' in df.columns:
        df['hotel'] = df['Campaña']  # Placeholder: asume la campaña como identificador de hotel si no existe
    if 'marca' not in df.columns and 'Campaña' in df.columns:
        df['marca'] = df['Campaña'].apply(lambda x: str(x).split('_')[0] if pd.notna(x) else 'Desconocida')
        
    return df

df = load_data()

# 2. Sidebar y Filtros
with st.sidebar:
    st.title("Filtros de Campaña")
    
    # Filtro de Semana
    semanas_disponibles = sorted(df['Semana'].dt.date.dropna().unique(), reverse=True) if 'Semana' in df.columns else []
    semana_sel = st.selectbox("Semana", options=semanas_disponibles)
    
    # Comparativa
    comparar_anterior = st.checkbox("Comparar con periodo anterior")
    
    # Filtro Marca
    marcas = ["Todos"] + list(df['marca'].unique()) if 'marca' in df.columns else ["Todos"]
    marca_sel = st.selectbox("Marca", options=marcas)
    
    # Filtro Hotel
    hoteles = ["Todos"] + list(df['hotel'].unique()) if 'hotel' in df.columns else ["Todos"]
    hotel_sel = st.selectbox("Hotel", options=hoteles, index=0)
    
    st.divider()
    
    # 3. Integración de IA - Seguridad y Setup
    st.header("Analista IA (Gemini)")
    api_key = st.text_input("Ingresa tu API Key de Google GenAI", type="password")

# Aplicar filtros
df_filtered = df.copy()
if marca_sel != "Todos" and 'marca' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['marca'] == marca_sel]
    
if hotel_sel != "Todos" and 'hotel' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['hotel'] == hotel_sel]

# Lógica de periodo para KPIs
df_current = df_filtered[df_filtered['Semana'].dt.date == semana_sel] if 'Semana' in df_filtered.columns and semana_sel else df_filtered

# 2. KPIs
st.title("📊 Dashboard de Paid Media (Google Ads)")

col1, col2 = st.columns(2)
conv_actual = df_current['Conversiones'].sum() if 'Conversiones' in df_current.columns else 0
ingresos_actual = df_current['Valor de conv.'].sum() if 'Valor de conv.' in df_current.columns else 0

delta_conv, delta_ingresos = None, None

if comparar_anterior and semana_sel:
    # Obtener la semana inmediatamente anterior a la seleccionada
    semana_ant = semana_sel - datetime.timedelta(days=7)
    df_prev = df_filtered[df_filtered['Semana'].dt.date == semana_ant]
    
    conv_prev = df_prev['Conversiones'].sum() if 'Conversiones' in df_prev.columns else 0
    ingresos_prev = df_prev['Valor de conv.'].sum() if 'Valor de conv.' in df_prev.columns else 0
    
    delta_conv = conv_actual - conv_prev
    delta_ingresos = ingresos_actual - ingresos_prev

with col1:
    st.metric("Conversiones", f"{conv_actual:,.2f}", delta=f"{delta_conv:,.2f}" if delta_conv is not None else None)
with col2:
    st.metric("Ingresos (Valor de conv.)", f"€ {ingresos_actual:,.2f}", delta=f"€ {delta_ingresos:,.2f}" if delta_ingresos is not None else None)

st.divider()

# Gráficos de Tendencia (width="stretch")
st.subheader(f"Evolución de Ingresos y Conversiones - {hotel_sel}")
if 'Semana' in df_filtered.columns and 'Valor de conv.' in df_filtered.columns:
    df_chart = df_filtered.groupby('Semana')[['Valor de conv.', 'Conversiones']].sum().reset_index()
    df_chart = df_chart.set_index('Semana')
    
    # Usando width="stretch" en vez de use_container_width según las instrucciones
    st.line_chart(df_chart['Valor de conv.'], width="stretch")
    st.bar_chart(df_chart['Conversiones'], width="stretch")

st.divider()

# 3. Chatbot con IA
st.subheader("💬 Chatea con tus Datos")

if api_key:
    # Inicializar el cliente del SDK moderno solo si hay API Key
    client = genai.Client(api_key=api_key)
    
    user_q = st.chat_input("Pregunta algo sobre el rendimiento de este hotel/marca...")
    
    if user_q:
        # Contexto: Últimas 10 filas del hotel y fecha seleccionados
        context_df = df_filtered.sort_values(by='Semana', ascending=False).head(10)
        context_csv = context_df.to_csv(index=False)
        
        prompt = f"""
        Eres un experto en Marketing Digital y Paid Media (Google Ads).
        Basándote en las siguientes 10 últimas filas de datos de contexto del hotel/marca seleccionado:
        
        {context_csv}
        
        Responde a la siguiente pregunta del usuario de forma analítica y concisa:
        Pregunta: {user_q}
        """
        
        st.chat_message("user").write(user_q)
        
        with st.chat_message("assistant"):
            # UX: Status y Streaming
            with st.status("Analizando...", expanded=True) as status:
                try:
                    # Modelo gemini-2.5-flash
                    response = client.models.generate_content_stream(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )
                    
                    def stream_generator():
                        for chunk in response:
                            yield chunk.text
                            
                    # Efecto máquina de escribir
                    st.write_stream(stream_generator())
                    status.update(label="Análisis completado", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="Error en el análisis", state="error", expanded=False)
                    st.error(f"Error de conexión con Gemini: {e}")
else:
    st.info("💡 Por favor, introduce tu API Key de Google en la barra lateral para habilitar el Analista de IA.")
