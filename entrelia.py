import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px

# --- 1. CONFIGURACION DE LA PAGINA ---
st.set_page_config(page_title="ENTRELIA PRO", page_icon="🏗️", layout="wide")

# --- 2. FUNCIONES DE DATOS E INFLACIÓN ---
def consultar_datos(sheet_name="Movimientos"):
    try:
        ID_EXCEL = "1fpTC_6y9fndidwnr4xaZf2ISDRGNKHEFYW-OLwxMzt0"
        url = f"https://docs.google.com/spreadsheets/d/{ID_EXCEL}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        return df.dropna(how="all")
    except: return pd.DataFrame()

def obtener_inflacion_reciente(): return 4.42 

def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🏗️ ENTRELIA PRO</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.button("Ingresar"):
                df_u = consultar_datos("Usuarios")
                if not df_u.empty:
                    valido = df_u[(df_u['USUARIO'] == u) & (df_u['PASSWORD'] == p)]
                    if not valido.empty:
                        st.session_state["password_correct"] = True
                        st.session_state["usuario_actual"] = valido.iloc[0]['NOMBRE']
                        st.rerun()
                    else: st.error("❌ Acceso denegado")
        return False
    return True

# --- 3. INICIO DE LA APP ---
if check_password():
    df_master = consultar_datos("Movimientos")
    conn = st.connection("gsheets", type=GSheetsConnection)

    with st.sidebar:
        st.title(f"Hola, {st.session_state.get('usuario_actual', 'Usuario')} 👋")
        menu = st.selectbox("Gestión", ["📊 Salud Financiera", "📝 Registro Contable", "🚫 Anular Movimiento", "⏱️ Gestión de Talento", "📂 Obra y Documentos", "⚙️ Configuración"])
        if not df_master.empty:
            proyectos = sorted(df_master['Obra'].unique().tolist())
            obra_sel_global = st.selectbox("🎯 Obra", ["Todas las Obras"] + proyectos)
            df_filtrado = df_master if obra_sel_global == "Todas las Obras" else df_master[df_master['Obra'] == obra_sel_global]
        else:
            df_filtrado = df_master
            obra_sel_global = "Sin datos"
        if st.button("🚪 Salir"):
            del st.session_state["password_correct"]
            st.rerun()

    if menu == "📊 Salud Financiera":
        st.header(f"📊 Análisis Estratégico: {obra_sel_global}")
        
        # 1. CONEXIÓN Y DATOS DE INFLACIÓN
        inflacion_anual = obtener_inflacion_reciente() # Retorna 4.42%
        
        try:
            df_opus = conn.read(worksheet="Presupuesto_Opus", ttl=0)
            df_opus.columns = df_opus.columns.str.strip()
            cols_m = [c for c in df_opus.columns if 'monto' in c.lower()]
            col_dinero = cols_m[0] if cols_m else None

            if col_dinero and obra_sel_global != "Todas las Obras":
                df_obra_p = df_opus[df_opus['Obra'].astype(str).str.upper() == obra_sel_global.upper()]
                pres_original = pd.to_numeric(df_obra_p[col_dinero], errors='coerce').sum()
            else:
                pres_original = 0
        except:
            pres_original = 0

        # 2. LÓGICA DE FLUJO DE CAJA (GASTOS E INGRESOS)
        if not df_filtrado.empty:
            df_c = df_filtrado.copy()
            if 'Estado' in df_c.columns:
                df_c = df_c[df_c['Estado'] != 'Anulado']
            
            df_c['Monto'] = pd.to_numeric(df_c['Monto'], errors='coerce').fillna(0)
            ingresos = df_c[df_c['Tipo'].str.contains("Ingreso", na=False)]['Monto'].sum()
            gastos_reales = df_c[df_c['Tipo'].str.contains("Gasto", na=False)]['Monto'].sum()
            
            # --- CÁLCULOS DE IMPACTO FINANCIERO ---
            utilidad_nominal = ingresos - gastos_reales
            # El "costo de oportunidad" o pérdida por inflación (estimación mensual simple)
            perdida_inflacionaria = gastos_reales * (inflacion_anual / 100)
            utilidad_real = utilidad_nominal - perdida_inflacionaria

            # Métrica de Inflación Arriba
            st.info(f"📅 **Tasa de Inflación Aplicada (INPC):** {inflacion_anual}%")

            c1, c2, c3 = st.columns(3)
            c1.metric("Ingresos Totales", f"${ingresos:,.2f}")
            c2.metric("Gastos Reales", f"${gastos_reales:,.2f}", delta_color="inverse")
            c3.metric("Utilidad Nominal", f"${utilidad_nominal:,.2f}")

            st.divider()

            # --- SECCIÓN DE IMPACTO EN UTILIDAD ---
            st.subheader("📉 Impacto de la Inflación en tu Ganancia")
            u1, u2 = st.columns(2)
            
            with u1:
                st.write("### Utilidad Real Ajustada")
                st.write(f"Considerando que el costo de vida y materiales subió un **{inflacion_anual}%**, tu utilidad se ve afectada:")
                st.metric("Utilidad Real", f"${utilidad_real:,.2f}", 
                          delta=f"-${perdida_inflacionaria:,.2f} por inflación", 
                          delta_color="inverse")
            
            with u2:
                # Gráfica de comparación
                data_utilidad = pd.DataFrame({
                    'Tipo': ['Nominal (En papel)', 'Real (Ajustada)'],
                    'Monto': [utilidad_nominal, utilidad_real]
                })
                fig_u = px.bar(data_utilidad, x='Tipo', y='Monto', color='Tipo',
                               color_discrete_map={'Nominal (En papel)': '#3498db', 'Real (Ajustada)': '#e67e22'},
                               title="Pérdida de Poder Adquisitivo")
                st.plotly_chart(fig_u, use_container_width=True)

            st.divider()
            
            # --- CONTROL PRESUPUESTAL ---
            st.subheader("🎯 Comparativo vs Presupuesto Original (OPUS)")
            pres_ajustado = pres_original * (1 + (inflacion_anual / 100))
            margen = pres_ajustado - gastos_reales
            
            o1, o2, o3 = st.columns(3)
            o1.metric("Presupuesto Original", f"${pres_original:,.2f}")
            o2.metric("Presupuesto Ajustado", f"${pres_ajustado:,.2f}", delta=f"+{inflacion_anual}%")
            o3.metric("Margen Disponible", f"${margen:,.2f}", 
                      delta="SANO" if margen > 0 else "SOBREGIRO",
                      delta_color="normal" if margen > 0 else "inverse")
            
            if pres_original > 0:
                st.warning(f"⚠️ Para mantener la misma utilidad proyectada, la obra debería costar máximo ${pres_ajustado:,.2f}.")

        else:
            st.warning("⚠️ No hay movimientos registrados para realizar el análisis.")
            # --- MODULO: REGISTRO CONTABLE ---
    elif menu == "📝 Registro Contable":
        st.header("📝 Entrada de Datos")
        with st.form("form_reg", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                f_m = st.date_input("Fecha", datetime.now())
                proys = df_master['Obra'].unique().tolist() if not df_master.empty else []
                o_s = st.selectbox("Obra", ["+ Nueva"] + proys)
                n_o = st.text_input("Nombre nueva obra") if o_s == "+ Nueva" else ""
            with col2:
                mon = st.number_input("Monto", min_value=0.0)
                tip = st.selectbox("Tipo", ["Ingreso (Honorarios)", "Gasto (Materiales)", "Gasto (Sueldos)", "Gasto (Admin)"])
                met = st.selectbox("Método", ["Efectivo", "Transferencia"])
            det = st.text_area("Detalle")
            if st.form_submit_button("🔨 Guardar"):
                o_f = n_o if o_s == "+ Nueva" else o_s
                if o_f and mon > 0:
                    nuevo = pd.DataFrame([{"Fecha": str(f_m), "Obra": o_f, "Monto": mon, "Tipo": tip, "Detalle": det, "Metodo": met}])
                    conn.update(data=pd.concat([df_master, nuevo], ignore_index=True))
                    st.success("✅ Guardado"); st.rerun()

    # --- MODULO: ANULAR MOVIMIENTO (CON HISTORIAL) ---
    elif menu == "🚫 Anular Movimiento":
        st.header("🚫 Módulo de Anulación")
        df_m = conn.read(worksheet="Hoja 1", ttl=0)
        df_m.columns = df_m.columns.str.strip()
        for c in ['Estado', 'Fecha_Anulacion', 'Usuario_Anulacion']:
            if c not in df_m.columns: df_m[c] = ""
            df_m[c] = df_m[c].astype(object)
        
        act = df_m[df_m['Estado'] != 'Anulado'].copy()
        if not act.empty:
            act['Visual'] = act['Fecha'].astype(str) + " | " + act['Obra'] + " | $" + act['Monto'].astype(str)
            sel = st.selectbox("Seleccionar:", act['Visual'].tolist())
            mot = st.text_input("Motivo:")
            if st.button("Anular Ahora"):
                if mot:
                    idx = df_m[ (df_m['Fecha'].astype(str) + " | " + df_m['Obra'] + " | $" + df_m['Monto'].astype(str)) == sel].index
                    df_m.loc[idx, 'Estado'] = 'Anulado'
                    df_m.loc[idx, 'Fecha_Anulacion'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    df_m.loc[idx, 'Usuario_Anulacion'] = st.session_state.usuario_actual
                    conn.update(worksheet="Hoja 1", data=df_m); st.success("Anulado"); st.rerun()

        st.divider(); st.subheader("📜 Historial de Anulaciones")
        df_h = df_m[df_m['Estado'] == 'Anulado']
        if not df_h.empty:
            if obra_sel_global != "Todas las Obras": df_h = df_h[df_h['Obra'] == obra_sel_global]
            df_h['Monto'] = pd.to_numeric(df_h['Monto'], errors='coerce').fillna(0)
            st.warning(f"💰 Total Anulado: ${df_h['Monto'].sum():,.2f}")
            st.dataframe(df_h[['Fecha', 'Obra', 'Monto', 'Detalle', 'Usuario_Anulacion', 'Fecha_Anulacion']], use_container_width=True)

    # --- MODULO: TALENTO ---
    elif menu == "⏱️ Gestión de Talento":
        st.header("⏱️ Control de Horas")
        df_t = consultar_datos("Talento")
        with st.form("f_t"):
            e = st.selectbox("Personal", ["Federico", "Hugo", "Capataz"])
            h = st.number_input("Horas", min_value=0.5, step=0.5)
            a = st.selectbox("Actividad", ["Diseño", "Supervisión", "Admin"])
            if st.form_submit_button("Registrar"):
                n = pd.DataFrame([{"Fecha": str(datetime.now().date()), "Obra": obra_sel_global, "Empleado": e, "Horas": h, "Actividad": a}])
                conn.update(worksheet="Talento", data=pd.concat([df_t, n], ignore_index=True)); st.rerun()
        if not df_t.empty:
            st.plotly_chart(px.pie(df_t.groupby("Actividad")["Horas"].sum().reset_index(), values='Horas', names='Actividad', hole=0.4))

    # --- MODULO: DOCUMENTOS ---
    elif menu == "📂 Obra y Documentos":
        st.header("📂 Expediente")
        tab1, tab2 = st.tabs(["📄 Documentos", "🏗️ Planos"])
        with tab1:
            arc = st.file_uploader("Subir Opus", type=["xlsx"])
            if arc:
                df_n = pd.read_excel(arc)
                if st.button("Vincular"):
                    dat = pd.DataFrame([{"Obra": df_n.iloc[0,0], "Monto_Presupuestado": df_n.iloc[:,1].sum(), "Fecha_Carga": str(datetime.now().date())}])
                    conn.update(worksheet="Presupuestos_Opus", data=pd.concat([consultar_datos("Presupuestos_Opus"), dat], ignore_index=True))
                    st.success("🎯 Vinculado")
            st.table(consultar_datos("Presupuestos_Opus"))
        with tab2: st.info("🔗 [Carpeta Drive]")

    # --- CONFIGURACIÓN ---
    elif menu == "⚙️ Configuración":
        with st.form("c_u"):
            u = st.text_input("Usuario"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Crear"):
                conn.update(worksheet="Usuarios", data=pd.concat([consultar_datos("Usuarios"), pd.DataFrame([{"USUARIO":u,"PASSWORD":p,"NOMBRE":u}])], ignore_index=True))
                st.success("✅ Usuario Creado")