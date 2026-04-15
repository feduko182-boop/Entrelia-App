import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
import google.generativeai as genai
from PIL import Image

# Configuración de la IA con tu clave
genai.configure(api_key="AIzaSyCoXpxaDzy1zybVUqHhKcwgVVasytaqbQU")

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
        st.title(f"Hola, {st.session_state.get('usuario_actual', 'Usuario')} 👋")
        
        menu = st.selectbox(
            "Módulo de Gestión", 
            [
                "📊 Salud Financiera", 
                "📝 Registro Contable", 
                "🛒 Comparador de Precios", 
                "🚫 Anular Movimiento", 
                "⏱️ Gestión de Talento", 
                "📂 Obra y Documentos", 
                "⚙️ Configuración"
            ]
        )
        
        st.markdown("---")

        if st.button("🚪 Cerrar Sesión"):
            if "password_correct" in st.session_state:
                del st.session_state["password_correct"]
            if "usuario_actual" in st.session_state:
                del st.session_state["usuario_actual"]
            st.rerun()
        
        st.markdown("---")
        
        # --- AQUÍ ESTÁ LA SOLUCIÓN AL ERROR ---
        # Definimos df_filtrado ANTES de usarlo en los módulos
        if not df_master.empty:
            proyectos_existentes = sorted(df_master['Obra'].unique().tolist())
            obra_sel_global = st.selectbox("🎯 Filtrar por Obra", ["Todas las Obras"] + proyectos_existentes)
            
            # Creamos la variable que te falta
            if obra_sel_global == "Todas las Obras":
                df_filtrado = df_master.copy()
            else:
                df_filtrado = df_master[df_master['Obra'] == obra_sel_global].copy()
        else:
            obra_sel_global = "Sin datos"
            df_filtrado = pd.DataFrame() # DataFrame vacío para que no marque error
            
        st.caption("Federico | Coach & Developer")

    
    # --- 5. LÓGICA DE MÓDULOS ---

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

    # --- MÓDULO REGISTRO CONTABLE CON IA ---
    elif menu == "📝 Registro Contable":
        st.header("📸 Escáner Inteligente de Tickets")
        
        # 1. Cargador de archivos (Fuera del form)
        archivo_ticket = st.file_uploader("Capturar Ticket / Factura", type=["jpg", "png", "jpeg"])
        
        # Inicializamos las variables para que NADA marque error
        datos_ia = {"monto": 0.0, "detalle": "", "ferreteria": "", "fecha": datetime.now()}
        
        if archivo_ticket:
            with st.spinner("🕵️ IA Analizando..."):
                # Aquí irá la conexión real con Gemini después
                datos_ia = {"monto": 0.0, "detalle": "", "ferreteria": "", "fecha": datetime.now()}
                st.info("✅ Foto cargada. Rellena los datos faltantes o verifica los extraídos.")

        # 2. El Formulario (Aquí corregimos los nombres de las imágenes)
        with st.form("form_registro_v3", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                fecha = st.date_input("Fecha", datos_ia['fecha'])
                proyectos_list = sorted(df_master['Obra'].unique().tolist()) if not df_master.empty else []
                obra_opcion = st.selectbox("Seleccionar Obra", ["+ Nueva Obra"] + proyectos_list)
                # FIX imagen cf156c: Definimos la variable siempre
                nueva_obra_input = st.text_input("Nombre de la nueva obra") if obra_opcion == "+ Nueva Obra" else ""
            
            with col2:
                # FIX imagen cf1cea: Usamos 'tipo_movimiento' para que coincida con tus IFs de abajo
                monto_input = st.number_input("Monto total ($)", value=datos_ia['monto'], step=0.01)
                tipo_movimiento = st.selectbox("Categoría", ["Ingreso (Honorarios)", "Gasto (Materiales)", "Gasto (Sueldos)", "Gasto (Admin)"])
                metodo_pago = st.selectbox("Caja / Banco", ["Efectivo", "Transferencia", "Tarjeta"])

            st.divider()
            
            # Campos dinámicos (FIX imágenes cf19e6, cf1c95, cf1d28)
            nombre_material = st.text_input("Material / Concepto (ej. Cemento)", value=datos_ia['detalle'])
            nombre_ferreteria = st.text_input("Ferretería / Proveedor", value=datos_ia['ferreteria'])
            detalle_mov = st.text_area("Notas adicionales")
            
            enviar_btn = st.form_submit_button("🔨 Guardar en Registro")
            
            if enviar_btn:
                nombre_obra_final = nueva_obra_input if obra_opcion == "+ Nueva Obra" else obra_opcion
                
                if nombre_obra_final and monto_input > 0:
                    # Guardado en Master
                    nuevo_reg = pd.DataFrame([{
                        "Fecha": str(fecha), "Obra": nombre_obra_final, "Monto": monto_input, 
                        "Tipo": tipo_movimiento, "Detalle": nombre_material, "Metodo": metodo_pago, "Estado": "Activo"
                    }])
                    df_actualizado = pd.concat([df_master, nuevo_reg], ignore_index=True)
                    conn.update(data=df_actualizado)
                    
                    # Guardado en IA Espía (Si es material)
                    if tipo_movimiento == "Gasto (Materiales)" and nombre_material:
                        try:
                            df_cat = conn.read(worksheet="Catalogo_Precios", ttl=0)
                            nuevo_p = pd.DataFrame([{
                                "Material": nombre_material.upper(), "Ferreteria": nombre_ferreteria.upper(), 
                                "Precio_Unitario": monto_input, "Fecha_Actualizacion": str(fecha), "Obra_Origen": nombre_obra_final
                            }])
                            conn.update(worksheet="Catalogo_Precios", data=pd.concat([df_cat, nuevo_p], ignore_index=True))
                        except: pass
                    
                    st.success("✅ Registro completado")
                    st.rerun()

    # --- MÓDULO: COMPARADOR DE PRECIOS ---
    elif menu == "🛒 Comparador de Precios":
        st.header("🕵️ Radar de Costos e Inteligencia de Mercado")
        
        # --- FICHA DE CONTACTO RÁPIDO ---
        with st.expander("🏗️ Proveedor Estrella: MATERIALES CONSTRUMAR", expanded=True):
            col_wa, col_mail = st.columns(2)
            
            with col_wa:
                # Configuramos el link de WhatsApp
                num_wa = "529861005818"
                msg_wa = "Hola Construmar, te contacto de Proyecto ENTRELIA. Me gustaría cotizar material."
                link_wa = f"https://wa.me/{num_wa}?text={msg_wa.replace(' ', '%20')}"
                st.link_button("📲 Cotizar por WhatsApp", link_wa, use_container_width=True)
            
            with col_mail:
                # Configuramos el link de Correo
                correo = "cuyoconstrumar@gmail.com"
                asunto = "Solicitud de Cotización / Factura - ENTRELIA"
                link_mail = f"mailto:{correo}?subject={asunto.replace(' ', '%20')}"
                st.link_button("📧 Enviar Correo / Factura", link_mail, use_container_width=True)
            
            st.caption("📍 El Cuyo | Facturación Disponible | Contacto Directo")

        # --- LÓGICA DE BÚSQUEDA DE PRECIOS ---
        try:
            # 1. Leemos la pestaña de precios
            df_p = conn.read(worksheet="Catalogo_Precios", ttl=0)
            df_p.columns = df_p.columns.str.strip() # Limpiamos espacios en los títulos
            
            if not df_p.empty:
                st.subheader("🔍 Buscar el mejor precio")
                
                # 2. Lista de materiales para el buscador
                mat_list = sorted(df_p['Material'].unique().tolist())
                busqueda = st.selectbox("¿Qué material buscas?", ["Seleccionar..."] + mat_list)
                
                if busqueda != "Seleccionar...":
                    # 3. Filtramos por el material seleccionado
                    df_res = df_p[df_p['Material'] == busqueda].copy()
                    
                    # Aseguramos que el precio sea un número para poder ordenar
                    df_res['Precio_Unitario'] = pd.to_numeric(df_res['Precio_Unitario'], errors='coerce')
                    df_res = df_res.sort_values(by="Precio_Unitario", ascending=True)
                    
                    # 4. Mostramos el cuadro de éxito con el más barato
                    mejor_precio = df_res.iloc[0]
                    st.success(f"🏆 El mejor precio para **{busqueda}** es de **${mejor_precio['Precio_Unitario']:,.2f}** en **{mejor_precio['Ferreteria']}**")
                    
                    # 5. Mostramos la tabla completa del historial
                    st.write("### Historial de Precios Registrados")
                    st.dataframe(df_res[['Ferreteria', 'Precio_Unitario', 'Fecha_Actualizacion', 'Obra_Origen']], use_container_width=True)
                
                st.divider()
                # Gráfica para ver cómo varían los precios
                fig_p = px.box(df_p, x='Material', y='Precio_Unitario', color='Material', title="Dispersión de Precios en el Mercado")
                st.plotly_chart(fig_p, use_container_width=True)
                
            else:
                st.info("💡 El catálogo está vacío. Registra un gasto de materiales para activarlo.")

        except Exception as e:
            st.error(f"⚠️ Error al leer catálogo: {e}")

    # --- MÓDULO: ANULACIÓN ---
    elif menu == "🚫 Anular Movimiento":
        st.header("🚫 Anulación de Movimientos")
        
        if not df_master.empty:
            df_anula = df_master.copy()
            # Filtramos solo los que están activos para poder anularlos
            movs_activos = df_anula[df_anula['Estado'] != 'Anulado'].copy()
            
            if not movs_activos.empty:
                # Creamos una lista para que el usuario identifique el movimiento
                movs_activos['Display'] = movs_activos['Fecha'].astype(str) + " | " + movs_activos['Obra'] + " | $" + movs_activos['Monto'].astype(str)
                sel = st.selectbox("Selecciona el movimiento a anular:", movs_activos['Display'])
                motivo = st.text_input("Motivo de la anulación:")
                
                if st.button("Confirmar Anulación") and motivo:
                    # Buscamos el índice correcto
                    idx = movs_activos[movs_activos['Display'] == sel].index
                    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    # Capturamos el usuario de la sesión
                    usuario_actual = st.session_state.get('usuario_actual', 'Desconocido')
                    
                    # --- LIMPIEZA CUÁNTICA (Evita el None) ---
                    detalle_previo = df_anula.loc[idx, 'Detalle'].values[0]
                    if pd.isna(detalle_previo) or detalle_previo is None or str(detalle_previo).lower() == 'none':
                        detalle_limpio = ""
                    else:
                        detalle_limpio = str(detalle_previo)

                    # Creamos la etiqueta de anulación para el detalle
                    registro_anulacion = f" | 🚫 ANULADO: {ahora} | Motivo: {motivo}"
                    
                    # --- ACTUALIZACIÓN DE COLUMNAS (MANTENIENDO TU LÓGICA) ---
                    df_anula.loc[idx, 'Estado'] = 'Anulado'
                    df_anula.loc[idx, 'Detalle'] = detalle_limpio + registro_anulacion
                    
                    # NUEVAS LÍNEAS: Registro en columnas H e I del Sheet
                    df_anula.loc[idx, 'Fecha_Anulacion'] = ahora
                    df_anula.loc[idx, 'Usuario_Anulacion'] = usuario_actual
                    
                    # Guardamos en Google Sheets
                    conn.update(data=df_anula)
                    st.success(f"✅ Movimiento anulado por {usuario_actual} y registrado en el historial.")
                    st.rerun()
            else:
                st.info("No hay movimientos activos para anular.")

            st.divider()
            
            # --- HISTORIAL DE ANULACIONES (Información Inteligente) ---
            st.subheader("📜 Historial de Movimientos Anulados")
            df_historial = df_anula[df_anula['Estado'] == 'Anulado'].copy()
            
            if not df_historial.empty:
                # Seleccionamos y renombramos columnas para que se vea profesional
                hist_table = df_historial[['Fecha', 'Obra', 'Monto', 'Tipo', 'Detalle']].copy()
                hist_table.columns = ['Fecha Origen', 'Obra', 'Monto Anulado', 'Categoría', 'Detalle y Motivo de Anulación']
                
                st.dataframe(hist_table, use_container_width=True)
                
                # Resumen de dinero anulado
                total_anulado = hist_table['Monto Anulado'].sum()
                st.warning(f"⚠️ Total de flujo anulado en este periodo: ${total_anulado:,.2f} MXN")
            else:
                st.write("Aún no hay registros en el historial de anulaciones.")
        else:
            st.warning("El registro maestro está vacío.")

    elif menu == "⏱️ Gestión de Talento":
        st.header(f"⏱️ Control de Horas y Rendimiento: {obra_sel_global}")
        
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
                nueva_fila_t = pd.DataFrame([{
                    "Fecha": str(fecha_talento),
                    "Obra": obra_sel_global,
                    "Empleado": colaborador,
                    "Horas": horas_laboradas,
                    "Actividad": tarea_realizada
                }])
                
                df_t_final = pd.concat([df_talento, nueva_fila_t], ignore_index=True)
                conn.update(worksheet="Talento", data=df_t_final)
                st.success(f"✅ Horas de {colaborador} registradas en {obra_sel_global}")
                st.rerun()
        
        if not df_talento.empty:
            # Gráfico de distribución de tiempo para el dueño del despacho
            df_t_filtro = df_talento if obra_sel_global == "Todas las Obras" else df_talento[df_talento['Obra'] == obra_sel_global]
            if not df_t_filtro.empty:
                st.plotly_chart(px.pie(df_t_filtro, values='Horas', names='Actividad', hole=0.4, title="Distribución de Esfuerzo"))
    elif menu == "📂 Obra y Documentos":
        st.header("📂 Expediente Digital de Obra")
        
        tab_docs, tab_planos = st.tabs(["📄 Presupuestos OPUS", "🏗️ Planos y Licencias"])
        
        with tab_docs:
            st.write("### Vinculación de Presupuesto Base")
            st.info("Sube tu Excel de prueba. Asegúrate que la Obra esté en la celda A2 y el monto en la B2.")
            
            archivo_subido = st.file_uploader("Seleccionar archivo (.xlsx)", type=["xlsx"])
            
            if archivo_subido:
                try:
                    df_nuevo_pres = pd.read_excel(archivo_subido)
                    
                    if st.button("🚀 Vincular a Salud Financiera"):
                        # Leemos los datos del Excel que subiste
                        obra_nombre = str(df_nuevo_pres.iloc[0, 0]) # Celda A2
                        monto_total_p = pd.to_numeric(df_nuevo_pres.iloc[0, 1], errors='coerce') # Celda B2
                        
                        datos_vinculo = pd.DataFrame([{
                            "Obra": obra_nombre,
                            "Monto_Presupuestado": monto_total_p,
                            "Fecha_Carga": datetime.now().strftime("%d/%m/%Y"),
                            "Cargado_Por": st.session_state.get('usuario_actual', 'Admin')
                        }])
                        
                        # INTENTO DE GUARDADO ROBUSTO
                        try:
                            df_existente = conn.read(worksheet="Presupuestos_Opus", ttl=0)
                            df_v_final = pd.concat([df_existente, datos_vinculo], ignore_index=True)
                        except:
                            # Si la hoja no existe en Google Sheets, empezamos de cero
                            df_v_final = datos_vinculo
                        
                        conn.update(worksheet="Presupuestos_Opus", data=df_v_final)
                        st.success(f"✅ Presupuesto de {obra_nombre} vinculado con éxito.")
                        st.balloons()
                except Exception as e:
                    st.error(f"❌ Error técnico: {e}")
            
            st.divider()
            st.subheader("Historial de Presupuestos")
            try:
                df_view_p = conn.read(worksheet="Presupuestos_Opus", ttl=0)
                st.table(df_view_p)
            except:
                st.info("Aún no hay presupuestos vinculados en el Google Sheets.")

        with tab_planos:
            st.write("### Planos y Documentación")
            st.info("Copia aquí el enlace de la carpeta compartida de Google Drive.")
            enlace_drive = st.text_input("URL de Carpeta Drive:", "https://drive.google.com/...")
            if st.button("Guardar Enlace"):
                st.success("Enlace guardado.")

    elif menu == "⚙️ Configuración":
        st.header("⚙️ Administración")
        with st.form("crear_usuario_form", clear_on_submit=True):
            nuevo_u = st.text_input("Usuario")
            nueva_p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("🔨 Crear Usuario"):
                if nuevo_u and nueva_p:
                    df_users = consultar_datos("Usuarios")
                    nuevo_u_df = pd.DataFrame([{"USUARIO": nuevo_u, "PASSWORD": nueva_p, "ROL": "admin", "NOMBRE": nuevo_u}])
                    conn.update(worksheet="Usuarios", data=pd.concat([df_users, nuevo_u_df], ignore_index=True))
                    st.success(f"✅ Usuario {nuevo_u} creado.")
    elif menu == "🛒 Comparador de Precios":
        st.header("🕵️ Radar de Costos e Inteligencia de Mercado")
        
        try:
            # Leemos la base de datos de precios que la IA va alimentando
            df_precios = conn.read(worksheet="Catalogo_Precios", ttl=0)
            
            if not df_precios.empty:
                materiales_disponibles = sorted(df_precios['Material'].unique().tolist())
                material_buscar = st.selectbox("🔍 ¿Qué material quieres cotizar hoy?", materiales_disponibles)
                
                # Filtramos y ordenamos por el precio más bajo
                df_resumen = df_precios[df_precios['Material'] == material_buscar].sort_values(by='Precio_Unitario')
                
                # --- MÉTRICAS DE INTELIGENCIA ---
                mejor_p = df_resumen.iloc[0]['Precio_Unitario']
                ferreteria_gto = df_resumen.iloc[0]['Ferreteria']
                
                c1, c2 = st.columns(2)
                c1.metric("Mejor Precio Histórico", f"${mejor_p:,.2f}", help="Precio más bajo detectado por la IA")
                c2.metric("Proveedor Recomendado", ferreteria_gto)

                # --- BOTÓN DE COTIZACIÓN EN TIEMPO REAL ---
                st.subheader("📲 Cotización Flash vía WhatsApp")
                st.write(f"La IA preparó un mensaje para validar si el precio de **{material_buscar}** sigue vigente:")
                
                # Aquí puedes crear un diccionario de teléfonos en el futuro
                tel_contacto = "529990000000" # <--- Cambia por el número de tu ferretería principal
                msg = f"Hola! Soy el Arq. Hugo de Proyecto ENTRELIA. Me podrias dar precio de hoy para: {material_buscar}? Quedo atento, gracias!"
                link_wa = f"https://wa.me/{tel_contacto}?text={msg.replace(' ', '%20')}"
                
                st.markdown(f'''
                    <a href="{link_wa}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#25D366;color:white;padding:10px 20px;border-radius:10px;text-align:center;font-weight:bold;">
                            📩 Preguntar Precio Actual a {ferreteria_gto}
                        </div>
                    </a>
                ''', unsafe_allow_html=True)

                st.divider()
                
                # --- GRÁFICA COMPARATIVA ---
                fig_comp = px.bar(df_resumen, x='Ferreteria', y='Precio_Unitario', 
                                 title=f"Comparativa de Costos: {material_buscar}",
                                 color='Precio_Unitario', color_continuous_scale='RdYlGn_r')
                st.plotly_chart(fig_comp, use_container_width=True)
                
            else:
                st.warning("🕵️ La IA aún no tiene datos. Registra compras de materiales para activar el radar.")
        except:
            st.error("⚠️ Error: Asegúrate de que la pestaña 'Catalogo_Precios' exista en tu Sheets.")
# --- FIN DEL SISTEMA ---