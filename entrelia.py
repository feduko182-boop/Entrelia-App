import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACION DE LA PAGINA ---
st.set_page_config(
    page_title="ENTRELIA PRO - Gestión Integral", 
    page_icon="🏗️", 
    layout="wide"
)

# --- 2. SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🏗️ ENTRELIA PRO</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Introduzca la clave de acceso para continuar</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            pwd = st.text_input("Contraseña", type="password")
            if st.button("Ingresar al Sistema"):
                if pwd == "ENTRELIA2026": # CAMBIA TU CLAVE AQUÍ
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta")
        return False
    return True

if not check_password():
    st.stop()

# --- 3. ESTILOS Y CONEXIÓN ---
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

def consultar_datos(sheet_name="Movimientos"):
    try:
        # ID de tu Excel compartido
        ID_EXCEL = "1fpTC_6y9fndidwnr4xaZf2ISDRGNKHEFYW-OLwxMzt0"
        url = f"https://docs.google.com/spreadsheets/d/{ID_EXCEL}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        return df.dropna(how="all")
    except:
        return pd.DataFrame()

# --- 4. MENÚ LATERAL EVOLUCIONADO ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4342/4342728.png", width=80)
    st.title("ENTRELIA PRO")
    menu = st.sidebar.selectbox(
        "Módulo de Gestión",
        ["📊 Salud Financiera", 
         "📝 Registro Contable", 
         "⏱️ Gestión de Talento", 
         "📂 Obra y Documentos", 
         "⚙️ Configuración"]
    )
    st.markdown("---")
    st.caption("Federico | Coach & Developer")

# Carga de datos global
df_master = consultar_datos("Movimientos")

# --- 5. LÓGICA DE MÓDULOS ---

# MODULO 1: SALUD FINANCIERA (Responde al punto 4 del diagnóstico)
if menu == "📊 Salud Financiera":
    st.header("📊 Análisis de Salud Financiera")
    
    if df_master is not None and not df_master.empty:
        # 1. Limpieza de datos
        df_master['Monto'] = pd.to_numeric(df_master['Monto'], errors='coerce').fillna(0)
        
        # 2. Cálculos de métricas
        ingresos = df_master[df_master['Tipo'].str.contains("Ingreso", na=False)]['Monto'].sum()
        gastos = df_master[df_master['Tipo'].str.contains("Gasto", na=False)]['Monto'].sum()
        liquidez = ingresos - gastos
        
        # 3. Visualización de métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos Totales", f"${ingresos:,.2f}")
        c2.metric("Gastos Totales", f"${gastos:,.2f}", delta_color="inverse")
        c3.metric("Liquidez Actual", f"${liquidez:,.2f}")

        st.markdown("---")
        st.subheader("📈 Rentabilidad por Proyecto")
        
        # 4. Gráfico de Rentabilidad
        fig = px.bar(
            df_master, 
            x="Obra", 
            y="Monto", 
            color="Tipo", 
            barmode="group", 
            title="Comparativa: Ingresos vs Gastos",
            color_discrete_map={"Ingreso (Honorarios)": "#2ecc71", "Gasto (Material/Sueldo)": "#e74c3c"}
        )
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning("⚠️ No se encontraron datos. Registra un movimiento para ver el análisis.")

# MODULO 2: REGISTRO CONTABLE (Responde al 'One Click' de tu diagrama)
elif menu == "📝 Registro Contable":
    st.header("📝 Diario Contable - Entrada de Datos")
    
    with st.form("form_registro_pro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", datetime.now())
            proyectos = df_master['Obra'].unique().tolist() if not df_master.empty else []
            obra_sel = st.selectbox("Proyecto / Cliente", ["+ Nueva Obra"] + proyectos)
            nueva_obra = st.text_input("Nombre de nueva obra") if obra_sel == "+ Nueva Obra" else ""
        
        with col2:
            monto = st.number_input("Monto ($)", min_value=0.0)
            tipo_mov = st.selectbox("Tipo de Movimiento", [
                "Ingreso (Honorarios)", 
                "Ingreso (Adelanto)", 
                "Gasto (Materiales)", 
                "Gasto (Sueldos/Contratados)", 
                "Gasto (Administrativo)"
            ])
            metodo = st.selectbox("Caja / Banco", ["Efectivo", "Transferencia", "Billetera Virtual"])

        detalle = st.text_area("Detalle / Proveedor")
        
        if st.form_submit_button("🔨 Guardar Movimiento"):
            obra_final = nueva_obra if obra_sel == "+ Nueva Obra" else obra_sel
            if obra_final and monto > 0:
                # 1. Creamos la fila con los datos actuales
                nuevo_dato = pd.DataFrame([{
                    "Fecha": str(fecha),
                    "Obra": obra_final,
                    "Monto": monto,
                    "Tipo": tipo_mov,
                    "Detalle": detalle,
                    "Metodo": metodo
                }])
                
                try:
                    # 2. Intentamos la conexión real a la nube
                    # Combinamos lo nuevo con lo que ya existe en el Excel
                    df_actualizado = pd.concat([df_master, nuevo_dato], ignore_index=True)
                    conn.update(data=df_actualizado)
                    
                    st.success(f"✅ ¡Movimiento en '{obra_final}' guardado con éxito en la nube!")
                    st.balloons()
                    st.rerun() # Esto actualiza las gráficas de Salud Financiera al instante
                except Exception as e:
                    # Si falla, aquí nos dirá si es culpa de la llave o de los permisos
                    st.error(f"❌ Error de conexión: {e}")
            else:
                st.error("⚠️ Por favor completa los campos de Obra y Monto.")

# MODULO 3: GESTIÓN DE TALENTO (Tiempo vs Honorarios)
elif menu == "⏱️ Gestión de Talento":
    st.header("⏱️ Control de Tiempo y Eficiencia")
    st.write("¿Tus honorarios cubren el tiempo real invertido?")
    
    col_a, col_b = st.columns(2)
    with col_a:
        with st.form("form_horas"):
            st.subheader("🕒 Registrar Horas")
            st.selectbox("Colaborador", ["Federico", "Equipo", "Admin"])
            st.number_input("Horas dedicadas", min_value=0.5, step=0.5)
            st.selectbox("Tarea", ["Diseño", "Dirección Obra", "Administración"])
            st.form_submit_button("Cargar Tiempo")
            
    with col_b:
        st.subheader("📊 Distribución del Día")
        # Simulación basada en tu diagnóstico
        df_t = pd.DataFrame({"Cat": ["Diseño", "Obra", "Admin"], "Hrs": [45, 25, 30]})
        fig_t = px.pie(df_t, values='Hrs', names='Cat', hole=0.4)
        st.plotly_chart(fig_t, use_container_width=True)
        st.warning("⚠️ El 30% del tiempo es administrativo. Meta: reducirlo.")

# MODULO 4: OBRA Y DOCUMENTOS (Búsqueda rápida)
elif menu == "📂 Obra y Documentos":
    st.header("📂 Gestión de Documentación")
    
    t1, t2 = st.tabs(["📄 Actas y Visitas", "🏗️ Planos Actualizados"])
    with t1:
        st.write("Actas de los últimos 6 meses:")
        st.table(pd.DataFrame({
            "Fecha": ["2026-03-01", "2026-04-10"],
            "Obra": ["Proyecto El Cuyo", "Anakin's Coffee"],
            "Estado": ["Finalizado", "En proceso"]
        }))
        st.file_uploader("Subir Acta en PDF", type="pdf")
    with t2:
        st.error("⚠️ Versión Actual Maestra: V.3.1 - Abril 2026")
        st.button("🔗 Abrir Carpeta Maestra en Drive")

# MODULO 5: CONFIGURACIÓN
elif menu == "⚙️ Configuración":
    st.header("⚙️ Configuración del Sistema")
    st.write(f"**Usuario Actual:** Federico | Rol: Administrador")
    st.divider()
    if st.button("➕ Gestionar Usuarios del Equipo"):
        st.info("Aquí podrás añadir a tu padre y otros colaboradores pronto.")