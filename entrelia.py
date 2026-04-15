import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
import google.generativeai as genai
from PIL import Image

# --- CONFIGURACIÓN SEGURA DE IA ---
# Lee la llave desde los secrets de Streamlit (funciona en local y en la nube)
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except:
    st.error("⚠️ Falta la configuración de GEMINI_API_KEY en los secretos.")

# --- 1. CONFIGURACION DE LA PAGINA ---
st.set_page_config(
    page_title="ENTRELIA PRO - Gestión Integral",
    page_icon="🏗️",
    layout="wide"
)

# --- 2. FUNCIONES DE DATOS, SEGURIDAD E INFLACIÓN ---

def consultar_datos(sheet_name="Movimientos"):
    try:
        ID_EXCEL = "1fpTC_6y9fndidwnr4xaZf2ISDRGNKHEFYW-OLwxMzt0"
        # Agregamos headers para asegurar que Google no bloquee la petición
        url = f"https://docs.google.com/spreadsheets/d/{ID_EXCEL}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()

def obtener_inflacion_reciente():
    """Retorna la tasa de inflación actual para cálculos de utilidad real."""
    return 4.42

def check_password():
    # 1. Si ya estás logueado en esta sesión, entramos directo
    if st.session_state.get("password_correct"):
        return True

    # 2. Si refrescaste la página, revisamos si la sesión sigue viva en la URL
    if "session_active" in st.query_params and st.query_params["session_active"] == "true":
        st.session_state["password_correct"] = True
        st.session_state["usuario_actual"] = st.query_params.get("user", "Usuario")
        return True

    # --- TU LÓGICA DE LOGIN ORIGINAL ---
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🏗️ ENTRELIA PRO</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Acceso al Sistema de Gestión</p>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            user_input = st.text_input("Usuario")
            pwd_input = st.text_input("Contraseña", type="password")

            if st.button("Ingresar al Sistema"):
                df_u = consultar_datos("Usuarios")
                if not df_u.empty:
                    # Filtramos ignorando espacios (tu lógica original)
                    valido = df_u[(df_u['USUARIO'].astype(str).str.strip() == user_input) & 
                                  (df_u['PASSWORD'].astype(str).str.strip() == pwd_input)]
                    
                    if not valido.empty:
                        nombre_final = valido.iloc[0]['NOMBRE']
                        st.session_state["password_correct"] = True
                        st.session_state["usuario_actual"] = nombre_final
                        
                        # NUEVO: Guardamos en la URL para que no se cierre al refrescar
                        st.query_params["session_active"] = "true"
                        st.query_params["user"] = nombre_final
                        
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.error("⚠️ No se pudo conectar con la base de datos de usuarios.")
        return False
    return True

# --- 3. INICIO DE LA APP SEGURA ---
if check_password():
    try:
        # CONEXIÓN ESTÁNDAR: Streamlit leerá los Secrets que acabas de arreglar
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # CONSULTA DE DATOS
        df_master = conn.read(worksheet="Movimientos", ttl=0)

    except Exception as e:
        # Si sale un error aquí, lo imprimirá para que sepamos qué es
        st.error(f"❌ Error de conexión: {e}")
        st.stop()

    # --- 4. INICIALIZACIÓN DE VARIABLES GLOBALES ---
    # Tu lógica sigue intacta aquí
    obra_sel_global = "Todas las Obras"
    df_filtrado = df_master.copy() if not df_master.empty else pd.DataFrame()
    pres_original = 0


    # --- 4. INICIALIZACIÓN DE VARIABLES GLOBALES ---
    obra_sel_global = "Todas las Obras"
    df_filtrado = df_master.copy() if not df_master.empty else pd.DataFrame()
    pres_original = 0
    
    # 3. Inicializar variables globales para evitar errores de "not defined"
    obra_sel_global = "Todas las Obras"
    df_filtrado = df_master.copy() if not df_master.empty else pd.DataFrame()
    pres_original = 0

    # --- [MEMORIA OPERATIVA Y SMART ANALYTICS] ---
    if "session_data" not in st.session_state:
        st.session_state.session_data = {"last_obra": "", "last_monto": 0.0, "ia_ready": False}

    # Cálculo preventivo para el Semáforo Visual
    if not df_master.empty:
        df_activos = df_master[df_master['Estado'] != 'Anulado'].copy()
        df_activos['Monto'] = pd.to_numeric(df_activos['Monto'], errors='coerce').fillna(0)
        
        # Guardar última obra usada para One-Click UX
        st.session_state.session_data["last_obra"] = df_master.iloc[-1]['Obra'] if not df_master.empty else ""
    
    
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
        
        # --- [MODO PRODUCTO: SWITCH GLOBAL] ---
        st.markdown("---")
        modo_producto = st.toggle("🚀 MODO PRODUCTO (Simple)", value=True, help="Activa una interfaz simplificada para el día a día en obra.")
        
        if modo_producto:
            st.info("💡 **ENTRELIA** te dice en 1 click si tu obra es rentable.")
        
        st.markdown("---")
        st.title(f"Hola, {st.session_state.get('usuario_actual', 'Usuario')} 👋")

        # --- [ADAPTACIÓN DE MENÚ SEGÚN MODO] ---
        if modo_producto:
            opciones_menu = ["🟢 Dashboard", "🟡 Operativa", "🔴 Análisis"]
            label_menu = "Menú Principal"
        else:
            opciones_menu = [
                "📊 Salud Financiera", 
                "📝 Registro Contable", 
                "🛒 Comparador de Precios", 
                "🚫 Anular Movimiento", 
                "⏱️ Gestión de Talento", 
                "📂 Obra y Documentos", 
                "⚙️ Configuración"
            ]
            label_menu = "Módulo de Gestión"

        menu = st.selectbox(label_menu, opciones_menu)
        
        st.markdown("---")

        if st.button("🚪 Cerrar Sesión"):
            if "password_correct" in st.session_state:
                del st.session_state["password_correct"]
            if "usuario_actual" in st.session_state:
                del st.session_state["usuario_actual"]
            st.query_params.clear()
            st.rerun()
        
        st.markdown("---")
        
        # --- DEFINICIÓN DE VARIABLES Y FILTROS ---
        if not df_master.empty:
            proyectos_existentes = sorted(df_master['Obra'].unique().tolist())
            obra_sel_global = st.selectbox("🎯 Filtrar por Obra", ["Todas las Obras"] + proyectos_existentes)
            
            if obra_sel_global == "Todas las Obras":
                df_filtrado = df_master.copy()
            else:
                df_filtrado = df_master[df_master['Obra'] == obra_sel_global].copy()
        else:
            obra_sel_global = "Sin datos"
            df_filtrado = pd.DataFrame() 

        # --- [INDICADOR TIPO SEMÁFORO - VERSIÓN PROTEGIDA] ---
        if obra_sel_global != "Todas las Obras" and not df_filtrado.empty:
            st.markdown("---")
            df_s = df_filtrado.copy()
            df_s['Monto'] = pd.to_numeric(df_s['Monto'], errors='coerce').fillna(0)
            ingresos_s = df_s[df_s['Tipo'].str.contains("Ingreso", na=False)]['Monto'].sum()
            gastos_s = df_s[df_s['Tipo'].str.contains("Gasto", na=False)]['Monto'].sum()
            margen_s = ingresos_s - gastos_s
            
            if margen_s > 0:
                st.success(f"🟢 Saludable: ${margen_s:,.0f}")
                if modo_producto: st.caption("✅ Esta obra es rentable")
            elif margen_s < 0:
                st.error(f"🔴 Riesgo: ${margen_s:,.0f}")
                if modo_producto: st.caption("⚠️ Estás perdiendo dinero aquí")
            else:
                st.warning("🟡 Punto de Equilibrio")
            
        st.caption("Federico | Coach & Developer")

    
    # --- 5. LÓGICA DE NAVEGACIÓN Y MÓDULOS ---
    
    # Esta condición separa la interfaz técnica de la interfaz simplificada
    if not modo_producto:
        
        # ==========================================
        # VISTA PROFESIONAL (SISTEMA ORIGINAL ÍNTEGRO)
        # ==========================================

        if menu == "📊 Salud Financiera":
            st.header(f"📊 Análisis Estratégico: {obra_sel_global}")
            
            # --- 1. CONEXIÓN Y DATOS DE INFLACIÓN ---
            inflacion_anual = obtener_inflacion_reciente() 
            
            try:
                df_opus = conn.read(worksheet="Presupuestos_Opus", ttl=0)
                df_opus.columns = df_opus.columns.str.strip()
                col_monto_fija = "Monto_Presupuestado"
                
                if col_monto_fija in df_opus.columns and obra_sel_global != "Todas las Obras":
                    df_obra_p = df_opus[df_opus['Obra'].astype(str).str.upper() == obra_sel_global.upper()]
                    pres_original = pd.to_numeric(df_obra_p[col_monto_fija], errors='coerce').sum()
                else:
                    pres_original = 0
            except Exception:
                pres_original = 0

            # --- 2. LÓGICA DE FLUJO DE CAJA ---
            if not df_filtrado.empty:
                df_c = df_filtrado.copy()
                if 'Estado' in df_c.columns:
                    df_c = df_c[df_c['Estado'] != 'Anulado']
                
                df_c['Monto'] = pd.to_numeric(df_c['Monto'], errors='coerce').fillna(0)
                ingresos = df_c[df_c['Tipo'].fillna("").str.contains("Ingreso", na=False)]['Monto'].sum()
                gastos_reales = df_c[df_c['Tipo'].fillna("").str.contains("Gasto", na=False)]['Monto'].sum()
                
                utilidad_nominal = ingresos - gastos_reales
                perdida_inflacionaria = gastos_reales * (inflacion_anual / 100)
                utilidad_real = utilidad_nominal - perdida_inflacionaria

                st.info(f"📅 **Tasa de Inflación Aplicada (INPC):** {inflacion_anual}%")
                c1, c2, c3 = st.columns(3)
                c1.metric("Ingresos Totales", f"${ingresos:,.2f}")
                c2.metric("Gastos Reales", f"${gastos_reales:,.2f}", delta_color="inverse")
                c3.metric("Utilidad Nominal", f"${utilidad_nominal:,.2f}")
                st.divider()

                # --- 3. IMPACTO DE LA INFLACIÓN ---
                st.subheader("📉 Impacto de la Inflación en tu Ganancia")
                u1, u2 = st.columns(2)
                with u1:
                    st.write("### Utilidad Real Ajustada")
                    st.metric("Utilidad Real", f"${utilidad_real:,.2f}", 
                              delta=f"-${perdida_inflacionaria:,.2f} Poder Adquisitivo", delta_color="inverse")
                with u2:
                    data_utilidad = pd.DataFrame({'Tipo': ['Nominal', 'Real'], 'Monto': [utilidad_nominal, utilidad_real]})
                    fig_u = px.bar(data_utilidad, x='Tipo', y='Monto', color='Tipo',
                                   color_discrete_map={'Nominal': '#3498db', 'Real': '#e67e22'})
                    st.plotly_chart(fig_u, use_container_width=True)
                st.divider()

                # --- [EVALUACIÓN RÁPIDA Y ALERTAS] ---
                if pres_original > 0:
                    porcentaje_gastado = (gastos_reales / pres_original) * 100
                    if porcentaje_gastado > 90:
                        st.error(f"⚠️ ALERTA DE SOBRECOSTO: Has consumido el {porcentaje_gastado:.1f}% del presupuesto.")
                    
                    if st.button("🤖 Evaluar Rentabilidad Actual"):
                        if utilidad_real > (pres_original * 0.10):
                            st.balloons(); st.success("🚀 Obra altamente rentable.")
                        else:
                            st.warning("⚠️ Margen estrecho. Revisar costos de materiales.")

                # --- 4. PROYECCIÓN DE CIERRE (FORECASTING) ---
                st.subheader("🔮 Proyección de Cierre (Forecasting)")
                if pres_original > 0:
                    p1, p2 = st.columns(2)
                    with p1:
                        costo_final_proyectado = gastos_reales + (pres_original - gastos_reales) * (1 + (inflacion_anual / 100))
                        desviacion = costo_final_proyectado - pres_original
                        st.metric("Costo Final Proyectado", f"${costo_final_proyectado:,.2f}", 
                                  delta=f"${desviacion:,.2f} Desvío Estimado", delta_color="inverse")
                    with p2:
                        por_gastar = max(0, pres_original - gastos_reales)
                        fig_p = px.pie(values=[gastos_reales, por_gastar], names=['Consumido', 'Disponible'], hole=.5,
                                       color_discrete_sequence=['#e74c3c', '#2ecc71'])
                        st.plotly_chart(fig_p, use_container_width=True)
                st.divider()

                # --- 5. COMPARATIVO VS OPUS ---
                st.subheader("🎯 Comparativo vs Presupuesto Original (OPUS)")
                pres_ajustado = pres_original * (1 + (inflacion_anual / 100))
                margen_pres = pres_ajustado - gastos_reales
                o1, o2, o3 = st.columns(3)
                o1.metric("Presupuesto Original", f"${pres_original:,.2f}")
                o2.metric("Ajustado (INPC)", f"${pres_ajustado:,.2f}", delta=f"+{inflacion_anual}%")
                o3.metric("Margen Disponible", f"${margen_pres:,.2f}", 
                          delta="SANO" if margen_pres > 0 else "SOBREGIRO",
                          delta_color="normal" if margen_pres > 0 else "inverse")
            else:
                st.warning("⚠️ No hay movimientos registrados para realizar el análisis estratégico.")

        elif menu == "📝 Registro Contable":
            st.header("📸 Escáner Inteligente de Tickets")
            # --- [REGISTRO RÁPIDO ONE-CLICK] ---
            with st.expander("⚡ Acciones Rápidas", expanded=False):
                col_q1, col_q2 = st.columns(2)
                if col_q1.button("🛒 Gasto Rápido Material ($1,000)"):
                    nueva_q = pd.DataFrame([{"Fecha": str(datetime.now().date()), "Obra": obra_sel_global if obra_sel_global != "Todas las Obras" else st.session_state.session_data["last_obra"], "Monto": 1000, "Tipo": "Gasto (Materiales)", "Detalle": "GASTO RÁPIDO EN OBRA", "Metodo": "Efectivo", "Estado": "Activo"}])
                    conn.update(data=pd.concat([df_master, nueva_q], ignore_index=True))
                    st.toast("✅ Gasto de $1,000 registrado"); st.rerun()
            
            # 1. Cargador de archivos
            archivo_ticket = st.file_uploader("Capturar Ticket / Factura", type=["jpg", "png", "jpeg"])
            
            if archivo_ticket:
                img_ia = Image.open(archivo_ticket)
                st.image(img_ia, width=250)
                if st.button("🕵️ Escanear con IA"):
                    with st.spinner("IA Analizando Ticket..."):
                        model_ia = genai.GenerativeModel('gemini-1.5-flash')
                        prompt_ia = "Extrae de este ticket: monto total (monto), nombre del negocio (ferreteria), y material comprado (detalle). Responde solo en JSON."
                        try:
                            res_ia = model_ia.generate_content([prompt_ia, img_ia])
                            import json
                            datos_res = json.loads(res_ia.text.replace('```json', '').replace('```', ''))
                            st.session_state.session_data.update({"last_monto": float(datos_res['monto']), "last_detalle": datos_res['detalle'], "last_ferreteria": datos_res['ferreteria']})
                            st.success("✅ Datos extraídos. Formulario pre-llenado.")
                        except: st.error("No se pudo extraer datos automáticamente.")

            # 2. Formulario de Registro
            with st.form("form_registro_v3", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    fecha = st.date_input("Fecha", datetime.now())
                    proyectos_list = sorted(df_master['Obra'].unique().tolist()) if not df_master.empty else []
                    obra_opcion = st.selectbox("Seleccionar Obra", ["+ Nueva Obra"] + proyectos_list)
                    nueva_obra_input = st.text_input("Nombre de la nueva obra") if obra_opcion == "+ Nueva Obra" else ""
                
                with col2:
                    monto_input = st.number_input("Monto total ($)", value=st.session_state.session_data.get("last_monto", 0.0), step=0.01)
                    tipo_movimiento = st.selectbox("Categoría", ["Ingreso (Honorarios)", "Gasto (Materiales)", "Gasto (Sueldos)", "Gasto (Admin)"])
                    metodo_pago = st.selectbox("Caja / Banco", ["Efectivo", "Transferencia", "Tarjeta"])

                st.divider()
                nombre_material = st.text_input("Material / Concepto", value=st.session_state.session_data.get("last_detalle", ""))
                nombre_ferreteria = st.text_input("Ferretería / Proveedor", value=st.session_state.session_data.get("last_ferreteria", ""))
                detalle_mov = st.text_area("Notas adicionales")
                
                if st.form_submit_button("🔨 Guardar en Registro"):
                    nombre_obra_final = nueva_obra_input if obra_opcion == "+ Nueva Obra" else obra_opcion
                    if nombre_obra_final and monto_input > 0:
                        nuevo_reg = pd.DataFrame([{
                            "Fecha": str(fecha), "Obra": nombre_obra_final, "Monto": monto_input, 
                            "Tipo": tipo_movimiento, "Detalle": nombre_material, "Metodo": metodo_pago, "Estado": "Activo"
                        }])
                        # Actualización de movimientos
                        df_actualizado = pd.concat([df_master, nuevo_reg], ignore_index=True)
                        conn.update(data=df_actualizado)

                        # Actualización de catálogo de precios inteligente
                        if tipo_movimiento == "Gasto (Materiales)" and nombre_material:
                            try:
                                df_cat = conn.read(worksheet="Catalogo_Precios", ttl=0)
                                nuevo_p = pd.DataFrame([{
                                    "Material": nombre_material.upper(), "Ferreteria": nombre_ferreteria.upper(), 
                                    "Precio_Unitario": monto_input, "Fecha_Actualizacion": str(fecha), "Obra_Origen": nombre_obra_final
                                }])
                                conn.update(worksheet="Catalogo_Precios", data=pd.concat([df_cat, nuevo_p], ignore_index=True))
                            except: pass
                            
                        st.success("✅ Registro completado"); st.rerun()
        elif menu == "🛒 Comparador de Precios":
            st.header("🕵️ Radar de Costos e Inteligencia de Mercado")
            
            # --- FICHA DE CONTACTO RÁPIDO ---
            with st.expander("🏗️ Proveedor Estrella: MATERIALES CONSTRUMAR", expanded=True):
                col_wa, col_mail = st.columns(2)
                with col_wa:
                    num_wa = "529861005818"
                    msg_wa = "Hola Construmar, te contacto de Proyecto ENTRELIA. Me gustaría cotizar material."
                    link_wa = f"https://wa.me/{num_wa}?text={msg_wa.replace(' ', '%20')}"
                    st.link_button("📲 Cotizar por WhatsApp", link_wa, use_container_width=True)
                with col_mail:
                    correo = "cuyoconstrumar@gmail.com"
                    asunto = "Solicitud de Cotización / Factura - ENTRELIA"
                    link_mail = f"mailto:{correo}?subject={asunto.replace(' ', '%20')}"
                    st.link_button("📧 Enviar Correo / Factura", link_mail, use_container_width=True)
                st.caption("📍 El Cuyo | Facturación Disponible | Contacto Directo")

            # --- LÓGICA DE BÚSQUEDA DE PRECIOS ---
            try:
                df_p = conn.read(worksheet="Catalogo_Precios", ttl=0)
                df_p.columns = df_p.columns.str.strip() 
                
                if not df_p.empty:
                    st.subheader("🔍 Buscar el mejor precio")
                    mat_list = sorted(df_p['Material'].unique().tolist())
                    busqueda = st.selectbox("¿Qué material buscas?", ["Seleccionar..."] + mat_list)
                    
                    if busqueda != "Seleccionar...":
                        df_res = df_p[df_p['Material'] == busqueda].copy()
                        df_res['Precio_Unitario'] = pd.to_numeric(df_res['Precio_Unitario'], errors='coerce')
                        df_res = df_res.sort_values(by="Precio_Unitario", ascending=True)
                        
                        mejor_precio = df_res.iloc[0] 
                        st.success(f"🏆 El mejor precio para **{busqueda}** es de **${mejor_precio['Precio_Unitario']:,.2f}** en **{mejor_precio['Ferreteria']}**")

                        # --- [WHATSAPP INTELIGENTE - ONE CLICK UX] ---
                        num_wa = "529861005818" # Construmar
                        msg_wa_ia = f"Hola Construmar, necesito cotizar {busqueda}. Mi último precio registrado fue de ${mejor_precio['Precio_Unitario']:,.2f}. ¿Tienen mejor precio hoy?"
                        link_wa_ia = f"https://wa.me/{num_wa}?text={msg_wa_ia.replace(' ', '%20')}"
                        st.link_button("📲 Negociar Mejor Precio (One-Click)", link_wa_ia, use_container_width=True)
                        
                        st.write("### Historial de Precios Registrados")
                        st.dataframe(df_res[['Ferreteria', 'Precio_Unitario', 'Fecha_Actualizacion', 'Obra_Origen']], use_container_width=True)
                else:
                    st.info("💡 El catálogo está vacío.")
            except Exception as e:
                st.error(f"⚠️ Error al leer catálogo: {e}")

        elif menu == "🚫 Anular Movimiento":
            st.header("🚫 Anulación de Movimientos")
            if not df_master.empty:
                df_anula = df_master.copy()
                movs_activos = df_anula[df_anula['Estado'] != 'Anulado'].copy()
                
                if not movs_activos.empty:
                    movs_activos['Display'] = movs_activos['Fecha'].astype(str) + " | " + movs_activos['Obra'] + " | $" + movs_activos['Monto'].astype(str)
                    sel = st.selectbox("Selecciona el movimiento a anular:", movs_activos['Display'])
                    motivo = st.text_input("Motivo de la anulación:")
                    
                    if st.button("Confirmar Anulación") and motivo:
                        idx = movs_activos[movs_activos['Display'] == sel].index
                        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                        usuario_actual = st.session_state.get('usuario_actual', 'Desconocido')
                        
                        detalle_previo = df_anula.loc[idx, 'Detalle'].values[0]
                        detalle_limpio = str(detalle_previo) if not pd.isna(detalle_previo) else ""

                        df_anula.loc[idx, 'Estado'] = 'Anulado'
                        df_anula.loc[idx, 'Detalle'] = detalle_limpio + f" | 🚫 ANULADO: {ahora} | Motivo: {motivo}"
                        df_anula.loc[idx, 'Fecha_Anulacion'] = ahora
                        df_anula.loc[idx, 'Usuario_Anulacion'] = usuario_actual
                        
                        conn.update(data=df_anula)
                        st.success(f"✅ Movimiento anulado y registrado.")
                        st.rerun()
                else:
                    st.info("No hay movimientos activos para anular.")

        elif menu == "⏱️ Gestión de Talento":
            st.header(f"⏱️ Control de Horas: {obra_sel_global}")
            df_talento = consultar_datos("Talento")
            with st.form("registro_talento_form", clear_on_submit=True):
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    colaborador = st.selectbox("Personal", ["Federico", "Hugo", "Capataz", "Residente"])
                    horas_laboradas = st.number_input("Horas invertidas", min_value=0.5, step=0.5)
                with col_t2:
                    tarea_realizada = st.selectbox("Tipo de Tarea", ["Diseño", "Supervisión", "Gestión Admin", "Trámites"])
                    fecha_talento = st.date_input("Fecha", datetime.now())
                if st.form_submit_button("🔨 Registrar Jornada"):
                    nueva_fila_t = pd.DataFrame([{"Fecha": str(fecha_talento), "Obra": obra_sel_global, "Empleado": colaborador, "Horas": horas_laboradas, "Actividad": tarea_realizada}])
                    df_t_final = pd.concat([df_talento, nueva_fila_t], ignore_index=True)
                    conn.update(worksheet="Talento", data=df_t_final)
                    st.success("✅ Horas registradas"); st.rerun()

        elif menu == "📂 Obra y Documentos":
            st.header("📂 Expediente Digital de Obra")
            tab_docs, tab_planos = st.tabs(["📄 Presupuestos OPUS", "🏗️ Planos y Licencias"])
            with tab_docs:
                st.write("### Vinculación de Presupuesto Base")
                archivo_subido = st.file_uploader("Seleccionar archivo (.xlsx)", type=["xlsx"])
                if archivo_subido:
                    try:
                        df_nuevo_pres = pd.read_excel(archivo_subido)
                        if st.button("🚀 Vincular a Salud Financiera"):
                            obra_nombre = str(df_nuevo_pres.iloc[0, 0])
                            monto_total_p = pd.to_numeric(df_nuevo_pres.iloc[0, 1], errors='coerce')
                            datos_vinculo = pd.DataFrame([{"Obra": obra_nombre, "Monto_Presupuestado": monto_total_p, "Fecha_Carga": datetime.now().strftime("%d/%m/%Y"), "Cargado_Por": st.session_state.get('usuario_actual', 'Admin')}])
                            df_existente = conn.read(worksheet="Presupuestos_Opus", ttl=0)
                            conn.update(worksheet="Presupuestos_Opus", data=pd.concat([df_existente, datos_vinculo], ignore_index=True))
                            st.success(f"✅ Presupuesto vinculado con éxito."); st.balloons()
                    except Exception as e:
                        st.error(f"❌ Error técnico al procesar el archivo: {e}")
            
            with tab_planos:
                st.write("### Planos y Documentación")
                st.info("Copia aquí el enlace de la carpeta compartida de Google Drive.")
                enlace_drive = st.text_input("URL de Carpeta Drive:", "https://drive.google.com/...")
                if st.button("Guardar Enlace"):
                    st.success("Enlace guardado correctamente.")

        elif menu == "⚙️ Configuración":
            st.header("⚙️ Administración")
            with st.form("crear_usuario_form", clear_on_submit=True):
                nuevo_u = st.text_input("Nuevo Usuario")
                nueva_p = st.text_input("Nueva Contraseña", type="password")
                if st.form_submit_button("🔨 Crear Usuario"):
                    if nuevo_u and nueva_p:
                        df_users = consultar_datos("Usuarios")
                        nuevo_u_df = pd.DataFrame([{"USUARIO": nuevo_u, "PASSWORD": nueva_p, "ROL": "admin", "NOMBRE": nuevo_u}])
                        conn.update(worksheet="Usuarios", data=pd.concat([df_users, nuevo_u_df], ignore_index=True))
                        st.success(f"✅ Usuario {nuevo_u} creado con éxito.")

    # ==========================================
    # 6. VISTA MODO PRODUCTO (INTERFAZ SAAS)
    # ==========================================
    else:
        # --- ONBOARDING BÁSICO SI NO HAY DATOS ---
        if df_master.empty:
            st.info("👋 **¡Bienvenido a ENTRELIA!** Tu asistente de rentabilidad.")
            st.markdown("""
            **Sigue estos pasos para tomar el control de tu obra:**
            1. 🏗️ **Configuración:** Crea tu primera obra y usuario.
            2. 🟡 **Operativa:** Registra tu primer gasto rápido.
            3. 🟢 **Dashboard:** Mira cómo se mueve tu utilidad en tiempo real.
            """)

        # PANTALLA: DASHBOARD (¿ESTOY GANANDO DINERO?)
        if menu == "🟢 Dashboard":
            st.title("🏗️ ¿Estás ganando dinero?")
            
            if obra_sel_global != "Todas las Obras" and obra_sel_global != "Sin datos":
                col_d1, col_d2 = st.columns(2)
                
                with col_d1:
                    st.metric("Utilidad Neta Actual", f"${margen_s:,.2f}", help="Ingresos totales menos gastos reales.")
                
                with col_d2:
                    if margen_s > 0:
                        st.success("🟢 **Esta obra es rentable.**")
                    else:
                        st.error("🔴 **Estás perdiendo dinero en esta obra.**")
                
                st.divider()
                st.subheader("💡 Estado del Proyecto")
                
                if pres_original > 0:
                    if gastos_s > pres_original:
                        st.error(f"⚠️ **Atención:** Has gastado ${gastos_s - pres_original:,.2f} más de lo presupuestado.")
                    else:
                        st.info(f"✅ Vas por buen camino. Te quedan ${(pres_original - gastos_s):,.2f} del presupuesto.")
                else:
                    st.info("ℹ️ No hay un presupuesto OPUS vinculado todavía.")
                
                if st.button("🚀 Evaluación Rápida de Obra"):
                    with st.spinner("Analizando..."):
                        if margen_s > 0:
                            st.balloons(); st.success("Proyecto saludable. Flujo de caja positivo.")
                        else:
                            st.warning("Riesgo financiero detectado. Revisa tus gastos de inmediato.")
            else:
                st.warning("🎯 Selecciona una obra en el menú lateral para ver tu rentabilidad.")

        # PANTALLA: OPERATIVA (REGISTRO VELOZ)
        elif menu == "🟡 Operativa":
            st.title("📝 Registra un gasto en 1 click")
            
            col_o1, col_o2 = st.columns(2)
            with col_o1:
                st.write("### Registro Veloz")
                if st.button("⚡ Materiales ($1,000)"):
                    last_obra_safe = st.session_state.session_data.get("last_obra", obra_sel_global)
                    nueva_q = pd.DataFrame([{"Fecha": str(datetime.now().date()), "Obra": last_obra_safe, "Monto": 1000, "Tipo": "Gasto (Materiales)", "Detalle": "GASTO RÁPIDO", "Metodo": "Efectivo", "Estado": "Activo"}])
                    conn.update(data=pd.concat([df_master, nueva_q], ignore_index=True))
                    st.toast("✅ Registrado con éxito"); st.rerun()
            
            with col_o2:
                st.write("### Inteligencia")
                st.info("Para usar funciones avanzadas (IA, Comparador), apaga el **Modo Producto** en el menú lateral.")

            st.divider()
            if not df_filtrado.empty:
                st.write("### Últimos movimientos registrados")
                st.table(df_filtrado[['Fecha', 'Tipo', 'Monto', 'Detalle']].tail(10))

        # PANTALLA: ANÁLISIS (ESTADÍSTICA SIMPLE)
        elif menu == "🔴 Análisis":
            st.title("📊 Análisis de Rentabilidad")
            if pres_original > 0:
                porcentaje = (gastos_s / pres_original) * 100
                st.write(f"Has consumido el **{porcentaje:.1f}%** de lo presupuestado originalmente.")
                st.progress(min(porcentaje/100, 1.0))
                
                c_a1, c_a2 = st.columns(2)
                c_a1.metric("Presupuesto Planeado", f"${pres_original:,.2f}")
                c_a2.metric("Gastos Acumulados", f"${gastos_s:,.2f}", delta=f"{porcentaje:.1f}%")
            else:
                st.info("💡 **Tip:** Vincula un presupuesto OPUS en el modo avanzado para ver la comparativa aquí.")

# --- FIN DEL SISTEMA ENTRELIA PRO ---