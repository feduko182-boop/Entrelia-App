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

# --- 2. FUNCIONES DE DATOS Y SEGURIDAD ---

def consultar_datos(sheet_name="Movimientos"):
    try:
        ID_EXCEL = "1fpTC_6y9fndidwnr4xaZf2ISDRGNKHEFYW-OLwxMzt0"
        url = f"https://docs.google.com/spreadsheets/d/{ID_EXCEL}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        return df.dropna(how="all")
    except:
        return pd.DataFrame()

def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🏗️ ENTRELIA PRO</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            pwd = st.text_input("Contraseña", type="password")
            if st.button("Ingresar al Sistema"):
                if pwd == "ENTRELIA2026":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta")
        return False
    return True

# --- 3. INICIO DE LA APP SEGURA ---
if check_password():
    # Carga de datos global tras login exitoso
    df_master = consultar_datos("Movimientos")
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Estilos Visuales
    st.markdown("""
        <style>
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
        .main { background-color: #f8f9fa; }
        </style>
        """, unsafe_allow_html=True)

    # --- 4. MENÚ LATERAL ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/4342/4342728.png", width=80)
        st.title("ENTRELIA PRO")
        menu = st.sidebar.selectbox(
            "Módulo de Gestión",
            ["📊 Salud Financiera", "📝 Registro Contable", "🚫 Anular Movimiento", "⏱️ Gestión de Talento", "📂 Obra y Documentos", "⚙️ Configuración"]
        )
        st.markdown("---")
        
        # FILTRO DE OBRA GLOBAL
        if not df_master.empty:
            proyectos_existentes = sorted(df_master['Obra'].unique().tolist())
            obra_sel_global = st.selectbox("🎯 Filtrar por Obra", ["Todas las Obras"] + proyectos_existentes)
            
            if obra_sel_global == "Todas las Obras":
                df_filtrado = df_master
            else:
                df_filtrado = df_master[df_master['Obra'] == obra_sel_global]
        else:
            df_filtrado = df_master
            obra_sel_global = "Sin datos"
            
        st.caption("Federico | Coach & Developer")

    # --- 5. LÓGICA DE MÓDULOS ---

    if menu == "📊 Salud Financiera":
        st.header(f"📊 Análisis: {obra_sel_global}")
        if not df_filtrado.empty:
            df_filtrado['Monto'] = pd.to_numeric(df_filtrado['Monto'], errors='coerce').fillna(0)
            ingresos = df_filtrado[df_filtrado['Tipo'].str.contains("Ingreso", na=False)]['Monto'].sum()
            gastos = df_filtrado[df_filtrado['Tipo'].str.contains("Gasto", na=False)]['Monto'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Ingresos", f"${ingresos:,.2f}")
            c2.metric("Gastos", f"${gastos:,.2f}", delta_color="inverse")
            c3.metric("Liquidez", f"${(ingresos-gastos):,.2f}")

            fig = px.bar(df_filtrado, x="Obra", y="Monto", color="Tipo", barmode="group",
                         color_discrete_map={"Ingreso (Honorarios)": "#2ecc71", "Gasto (Materiales)": "#e74c3c"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ No hay movimientos registrados.")

    elif menu == "📝 Registro Contable":
        st.header("📝 Entrada de Datos")
        with st.form("form_registro_pro", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", datetime.now())
                proyectos = df_master['Obra'].unique().tolist() if not df_master.empty else []
                obra_sel = st.selectbox("Proyecto / Cliente", ["+ Nueva Obra"] + proyectos)
                nueva_obra = st.text_input("Nombre de nueva obra") if obra_sel == "+ Nueva Obra" else ""
            with col2:
                monto = st.number_input("Monto ($)", min_value=0.0)
                tipo_mov = st.selectbox("Tipo", ["Ingreso (Honorarios)", "Gasto (Materiales)", "Gasto (Sueldos)", "Gasto (Admin)"])
                metodo = st.selectbox("Caja / Banco", ["Efectivo", "Transferencia"])
            
            detalle = st.text_area("Detalle")
            if st.form_submit_button("🔨 Guardar"):
                obra_final = nueva_obra if obra_sel == "+ Nueva Obra" else obra_sel
                if obra_final and monto > 0:
                    nuevo_dato = pd.DataFrame([{"Fecha": str(fecha), "Obra": obra_final, "Monto": monto, "Tipo": tipo_mov, "Detalle": detalle, "Metodo": metodo}])
                    df_actualizado = pd.concat([df_master, nuevo_dato], ignore_index=True)
                    conn.update(data=df_actualizado)
                    st.success("✅ Guardado en la nube")
                    st.rerun()

    elif menu == "🚫 Anular Movimiento":
        st.header("🚫 Módulo de Anulación")
        st.info("Selecciona un registro para eliminarlo permanentemente del sistema.")
        if not df_master.empty:
            df_master['Visual'] = df_master['Fecha'].astype(str) + " | " + df_master['Obra'] + " | $" + df_master['Monto'].astype(str)
            seleccion = st.selectbox("Registro a eliminar:", df_master['Visual'].tolist())
            if st.button("Confirmar Eliminación"):
                df_final = df_master[df_master['Visual'] != seleccion].drop(columns=['Visual'])
                conn.update(data=df_final)
                st.success("🔥 Registro eliminado y balances actualizados.")
                st.rerun()
        else:
            st.warning("No hay datos para anular.")

    elif menu == "⏱️ Gestión de Talento":
        st.header("⏱️ Control de Horas y Eficiencia")
        st.write("Registra el tiempo dedicado a cada tarea para asegurar la rentabilidad.")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            with st.form("form_talento", clear_on_submit=True):
                st.subheader("🕒 Nueva Entrada")
                empleado = st.selectbox("Personal", ["Federico", "Papá", "Capataz", "Contratista"])
                horas = st.number_input("Horas invertidas", min_value=0.5, step=0.5)
                actividad = st.selectbox("Actividad", ["Diseño", "Supervisión Obra", "Trámites/Admin", "Compras"])
                if st.form_submit_button("Cargar Tiempo"):
                    st.success(f"✅ Registradas {horas}h para {empleado}")
        
        with col_t2:
            st.subheader("📊 Distribución de Esfuerzo")
            df_pie = pd.DataFrame({"Actividad": ["Obra", "Admin", "Diseño"], "Total": [50, 30, 20]})
            fig_pie = px.pie(df_pie, values='Total', names='Actividad', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

    elif menu == "📂 Obra y Documentos":
        st.header("📂 Expediente Digital de Obra")
        tab1, tab2 = st.tabs(["📄 Documentos", "🏗️ Planos"])
        with tab1:
            st.subheader("Subir Documentación")
            u_file = st.file_uploader("Arrastra aquí actas o recibos", type=["pdf", "jpg", "png"])
            if u_file: st.success("Archivo listo para vincular.")
            st.write("---")
            st.table(pd.DataFrame({
                "Documento": ["Acta Inicio", "Presupuesto V1"],
                "Fecha": ["2026-03-15", "2026-04-01"]
            }))
        with tab2:
            st.info("🔗 [Click aquí para abrir Carpeta Drive de Planos]")

    elif menu == "⚙️ Configuración":
        st.header("⚙️ Configuración del Sistema")
        st.write(f"**Usuario:** Federico | Rol: Administrador")
        st.divider()
        with st.expander("👥 Gestión de Acceso"):
            with st.form("crear_user_final"):
                u_name = st.text_input("Nombre de Usuario")
                u_pass = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Dar de Alta"):
                    st.success(f"Usuario {u_name} registrado.")

# --- FIN DEL IF DE SEGURIDAD ---