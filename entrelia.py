import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
import google.generativeai as genai
from PIL import Image
import json
import re
import os
import io

# Configuración de la IA con tu clave
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 1. CONFIGURACION DE LA PAGINA ---
st.set_page_config(
    page_title="EVO-Q - Gestión de Obras",
    page_icon="🏗️",
    layout="wide"
)

# --- 2. FUNCIONES DE DATOS, SEGURIDAD E INFLACIÓN ---

def consultar_datos(sheet_name="Movimientos"):
    """
    Fuente única de verdad: Google Sheets vía Streamlit Connection API
    (Elimina CSV caching issues)
    """
    try:
        df = conn.read(worksheet=sheet_name, ttl=0)  # 🔥 FIX CRÍTICO: lectura en tiempo real
        
        df = df.dropna(how="all")
        
        # Garantía de consistencia de estados para filtros
        if 'Estado' in df.columns:
            df['Estado'] = df['Estado'].astype(str).str.strip().str.upper()

        # --- AGREGADO: BLINDAJE ANTI-NAN ---
        if not df.empty:
            for col in df.columns:
                # Si la columna es numérica, llenar vacíos con 0
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(0)
                # Si es objeto/texto, llenar vacíos con string vacío
                else:
                    df[col] = df[col].fillna("")
        # -----------------------------------

        return df
    
    except Exception as e:
        return pd.DataFrame()

def obtener_inflacion_reciente():
    """Retorna la tasa de inflación actual para cálculos de utilidad real."""
    return 4.42

def normalizar_texto(valor):
    """Evita errores de comparación por tipos Mixed en DataFrames."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip().upper()

def tiene_permiso(modulo):
    """Capa de seguridad de acceso por rol."""
    rol = st.session_state.get("rol_actual", "campo")
    permisos = {
        "admin": ["🏠 Dashboard", "📊 Salud Financiera", "📝 Registro Contable",
                  "🛒 Comparador de Precios", "🚫 Anular Movimiento",
                  "⏱️ Gestión de Talento", "📂 Obra y Documentos", "⚙️ Configuración"],
        "arquitecto": ["🏠 Dashboard", "📊 Salud Financiera", "🛒 Comparador de Precios",
                       "⏱️ Gestión de Talento", "📂 Obra y Documentos"],
        "campo": ["📝 Registro Contable", "⏱️ Gestión de Talento"]
    }
    return modulo in permisos.get(rol, [])

def check_password():
    # 1. Validación de sesión en estado
    if st.session_state.get("password_correct"):
        return True

    # 2. Persistencia vía URL (Sanitizada)
    if "session_active" in st.query_params and st.query_params["session_active"] == "true":
        st.session_state["password_correct"] = True
        st.session_state["usuario_actual"] = st.query_params.get("user", "Usuario")
        st.session_state["rol_actual"] = str(st.query_params.get("rol", "campo")).lower().strip()
        return True

    # --- LÓGICA DE LOGIN ---
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🏗️ EVO-Q</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Acceso al Sistema de Gestión</p>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            user_input = st.text_input("Usuario")
            pwd_input = st.text_input("Contraseña", type="password")

            if st.button("Ingresar al Sistema"):
                df_u = consultar_datos("Usuarios")
                if not df_u.empty and 'USUARIO' in df_u.columns and 'PASSWORD' in df_u.columns:
                    # Comparación normalizada para evitar errores de espacios en el Sheet
                    valido = df_u[(df_u['USUARIO'].astype(str).str.strip() == user_input) & 
                                  (df_u['PASSWORD'].astype(str).str.strip() == pwd_input)]
                    
                    if not valido.empty:
                        nombre_final = valido.iloc[0]['NOMBRE']
                        rol_final = str(valido.iloc[0]['ROL']).lower().strip() if 'ROL' in valido.columns else 'campo'
                        st.session_state["password_correct"] = True
                        st.session_state["usuario_actual"] = nombre_final
                        st.session_state["rol_actual"] = rol_final
                        
                        st.query_params["session_active"] = "true"
                        st.query_params["user"] = nombre_final
                        st.query_params["rol"] = rol_final
                        
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.error("⚠️ Error de conexión con base de datos de usuarios.")
        return False
    return True

# --- INICIO DE LA APP SEGURA ---
conn = st.connection("gsheets", type=GSheetsConnection)

if check_password():
    df_master = consultar_datos("Movimientos")

    if not df_master.empty:
        df_master['Obra']   = df_master['Obra'].apply(normalizar_texto)
        df_master['Tipo']   = df_master['Tipo'].apply(normalizar_texto)
        df_master['Estado'] = df_master['Estado'].apply(normalizar_texto)

    if "session_data" not in st.session_state:
        st.session_state.session_data = {"last_obra": "", "last_monto": 0.0, "ia_ready": False}

    # ── ONBOARDING EVO Q ─────────────────────────────────────────────────
    # Persistencia del onboarding vía query_params
    # Si el usuario ya vio el onboarding en esta sesión URL, no lo mostramos
    if "onboarding_visto" not in st.session_state:
        # Si la sesión ya estaba activa (refresh), onboarding ya fue visto
        sesion_activa = st.query_params.get("session_active", "false") == "true"
        onboarding_hecho = st.query_params.get("onboarding_done", "false") == "true"
        st.session_state["onboarding_visto"] = sesion_activa or onboarding_hecho
    

    if not st.session_state["onboarding_visto"]:

        st.markdown("""
            <style>
            [data-testid="stSidebar"]        { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }
            .block-container {
                max-width: 680px;
                margin: auto;
                padding-top: 40px;
            }
            </style>
            <script>
            (function() {
                var style = document.createElement('style');
                style.id = 'onboarding-hide';
                style.textContent = '[data-testid="stSidebar"]{display:none!important}[data-testid="collapsedControl"]{display:none!important}';
                document.head.appendChild(style);
            })();
            </script>
        """, unsafe_allow_html=True)

        # ── Header mínimo ─────────────────────────────────────────────────
        st.markdown("""
            <div style="text-align:center; margin-bottom:24px;">
                <span style="font-size:42px;">🏗️</span>
                <h2 style="color:#1a73e8; margin:8px 0 4px 0;">
                    Bienvenido a Evo Q
                </h2>
                <p style="color:#666; font-size:14px; margin:0;">
                    Mirá este video de 15 segundos antes de empezar
                </p>
            </div>
        """, unsafe_allow_html=True)

        VIDEO_PATH = os.path.join(os.path.dirname(__file__), "Bienvenido a Evo-Q.mp4")

        col_vid_l, col_vid, col_vid_r = st.columns([0.5, 9, 0.5])
        with col_vid:
            try:
                st.video(VIDEO_PATH, autoplay=True, muted=True, loop=False)
            except Exception as e:
                st.warning(f"⚠️ No se pudo cargar el video: {str(e)}")

        st.markdown("<br>", unsafe_allow_html=True)

        col_l, col_ok, col_gap, col_skip, col_r = st.columns([2, 3, 1, 2, 2])

        with col_ok:
            if st.button("✅ Continuar", key="onboarding_ok", use_container_width=True):
                st.session_state["onboarding_visto"] = True
                st.query_params["onboarding_done"] = "true"
                st.rerun()

        with col_skip:
            if st.button("⏭️ Omitir", key="onboarding_skip", use_container_width=True):
                st.session_state["onboarding_visto"] = True
                st.query_params["onboarding_done"] = "true"
                st.rerun()

        st.stop()

    # Estilos Visuales
    st.markdown("""
        <style>
        .stMetric { background-color: #ffffff; padding: 15px;
                    border-radius: 10px; border: 1px solid #e0e0e0; }
        .main { background-color: #f8f9fa; }
        footer { display: none !important; }
        #MainMenu { display: none !important; }

        /* Ocultar elementos nativos Streamlit — móvil y desktop */
        [data-testid="stToolbar"]      { display: none !important; visibility: hidden !important; }
        [data-testid="stHeader"]       { height: 0 !important; min-height: 0 !important; padding: 0 !important; overflow: hidden !important; }
        [data-testid="stDecoration"]   { display: none !important; visibility: hidden !important; }
        [data-testid="stStatusWidget"] { display: none !important; visibility: hidden !important; }
        .stDeployButton                { display: none !important; visibility: hidden !important; }
        a[href*="github"]              { display: none !important; visibility: hidden !important; }
        [data-testid="stMainMenu"]     { display: none !important; }
        button[kind="header"]          { display: none !important; }

        /* Botón hamburger — solo visible en móvil */
        div[data-testid="stHorizontalBlock"]:has(#evoq-sidebar-toggle) {
            position: fixed;
            top: 8px;
            left: 8px;
            z-index: 999999;
            width: auto !important;
        }
        @media (min-width: 769px) {
            div[data-testid="stHorizontalBlock"]:has(#evoq-sidebar-toggle) {
                display: none !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # Botón hamburger móvil (nativo Streamlit, sin JavaScript)
    if "sidebar_abierto" not in st.session_state:
        st.session_state["sidebar_abierto"] = True

    col_ham, _ = st.columns([1, 11])
    with col_ham:
        if st.button("☰", key="evoq-sidebar-toggle"):
            st.session_state["sidebar_abierto"] = not st.session_state.get("sidebar_abierto", True)

    # Aplicar estado del sidebar en móvil
    if not st.session_state.get("sidebar_abierto", True):
        st.markdown("""
            <style>
            @media (max-width: 768px) {
                [data-testid="stSidebar"] { transform: translateX(-110%) !important; }
            }
            </style>
        """, unsafe_allow_html=True)

    # --- MENÚ LATERAL ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/4342/4342728.png", width=80)
        st.title(f"Hola, {st.session_state.get('usuario_actual', 'Usuario')} 👋")
        
        rol_display = {
            "admin": "👑 Administrador",
            "arquitecto": "🧑‍💼 Arquitecto",
            "campo": "🏗️ Operario de Campo"
        }
        st.caption(rol_display.get(st.session_state.get("rol_actual"), "Usuario"))
        
        todos_los_modulos = [ 
            "🏠 Dashboard", "📊 Salud Financiera", "📝 Registro Contable", 
            "🛒 Comparador de Precios", "🚫 Anular Movimiento", 
            "⏱️ Gestión de Talento", "📂 Obra y Documentos", "⚙️ Configuración"
        ]
        modulos_visibles = [m for m in todos_los_modulos if tiene_permiso(m)]
        menu_default = st.session_state.pop("menu_override", None)
        menu_index = (
            modulos_visibles.index(menu_default)
            if menu_default and menu_default in modulos_visibles
            else 0
        )

        menu = st.selectbox(
            "Módulo de Gestión",
            modulos_visibles,
            index=menu_index
        )
        
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Filtros con protección contra datos vacíos
        if not df_master.empty:
            proyectos_existentes = sorted(df_master['Obra'].unique().tolist())
            obra_sel_global = st.selectbox("🎯 Filtrar por Obra", ["Todas las Obras"] + proyectos_existentes)
            
            df_filtrado = df_master.copy() if obra_sel_global == "Todas las Obras" else df_master[df_master['Obra'] == obra_sel_global].copy()
        else:
            obra_sel_global = "Sin datos"
            df_filtrado = pd.DataFrame() 

        # Semáforo Sidebar
        if obra_sel_global != "Todas las Obras" and not df_filtrado.empty:
            st.markdown("---")
            df_s = df_filtrado[df_filtrado['Estado'] != 'ANULADO'].copy()
            df_s['Monto'] = pd.to_numeric(df_s['Monto'], errors='coerce').fillna(0)
            
            ingresos_s = df_s[df_s['Tipo'].str.contains("INGRESO", na=False)]['Monto'].sum()
            gastos_s = df_s[df_s['Tipo'].str.contains("GASTO", na=False)]['Monto'].sum()
            margen_s = ingresos_s - gastos_s
            
            if margen_s > 0: st.success(f"🟢 Saludable: ${margen_s:,.0f}")
            elif margen_s < 0: st.error(f"🔴 Riesgo: ${margen_s:,.0f}")
            else: st.warning("🟡 Punto de Equilibrio")
            
        st.caption("Federico | EVO-Q")
        
        # --- AGREGADO: BOTÓN SOPORTE WHATSAPP ---
        st.sidebar.markdown("---")
        numero_whatsapp = "529842106254" # Tu número actual en el código
        texto_soporte = "Hola, necesito ayuda con Evo Q."
        link_soporte = f"https://wa.me/{numero_whatsapp}?text={texto_soporte.replace(' ', '%20')}"
        st.sidebar.markdown(f"""
            <a href="{link_soporte}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #25D366; color: white; padding: 10px; border-radius: 10px; text-align: center; font-weight: bold;">
                    💬 Soporte Evo Q
                </div>
            </a>
        """, unsafe_allow_html=True)

        # --- LÓGICA DE MÓDULOS ---

    if menu == "🏠 Dashboard":
        st.title(f"👋 Bienvenido, {st.session_state.get('usuario_actual', 'Usuario')}")
        st.caption(f"📅 {datetime.now().strftime('%A %d de %B, %Y')}")

        # 🔥 AGREGADO AQUÍ
        st.caption("🛡️ Evo Q protege tu utilidad real contra la inflación en tiempo real.")

        st.divider()
        st.subheader("📋 Estado de Obras Activas")
        if not df_master.empty:
            obras = df_master['Obra'].dropna().unique().tolist()
            for obra in obras:
                df_obra = df_master[(df_master['Obra'] == obra) & (df_master['Estado'] != 'ANULADO')].copy()
                df_obra['Monto'] = pd.to_numeric(df_obra['Monto'], errors='coerce').fillna(0)
                ingresos_o = df_obra[df_obra['Tipo'].str.contains("INGRESO", na=False)]['Monto'].sum()
                gastos_o = df_obra[df_obra['Tipo'].str.contains("GASTO", na=False)]['Monto'].sum()
                if ingresos_o == 0 and gastos_o == 0:
                    col1, col2 = st.columns([2, 3])
                    with col1: st.markdown(f"**🏗️ {obra}**")
                    with col2: st.caption("— Sin actividad registrada")
                    st.divider()
                    continue
                margen_o = ingresos_o - gastos_o
                inflacion = obtener_inflacion_reciente()
                utilidad_real_o = margen_o - (gastos_o * (inflacion / 100))

                # Lectura de presupuestos con try/except para estabilidad
                try:
                    df_opus_d = conn.read(worksheet="Presupuestos_Opus", ttl=0)
                    df_opus_d.columns = df_opus_d.columns.str.strip()
                    df_obra_p_d = df_opus_d[df_opus_d['Obra'].apply(normalizar_texto) == normalizar_texto(obra)]
                    pres_original_d = pd.to_numeric(df_obra_p_d['Monto_Presupuestado'], errors='coerce').sum()
                except:
                    pres_original_d = 0

                pct_consumido = (gastos_o / pres_original_d * 100) if pres_original_d > 0 else 0

                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                with col1: st.markdown(f"**🏗️ {obra}**")
                with col2: st.metric("Utilidad Real", f"${utilidad_real_o:,.0f}")
                with col3: st.metric("Ingresos", f"${ingresos_o:,.0f}")
                with col4: st.metric("% Consumido", f"{pct_consumido:.1f}%")
                with col5:
                    if margen_o < 0 or pct_consumido > 95:
                        st.error("🔴 RIESGO")
                        st.caption("Revisar urgente")
                        st.caption(f"Margen: ${margen_o:,.0f}")
                    elif pct_consumido >= 80:
                        st.warning("🟡 ATENCIÓN")
                        st.caption("Presupuesto ajustado")
                        st.caption(f"Margen: ${margen_o:,.0f}")
                    else: 
                        st.success("🟢 OK")
                        st.caption(f"Margen: ${margen_o:,.0f}")
                st.divider()
        else:
            st.info("⚠️ No hay obras registradas aún.")

        st.subheader("⚡ Acciones Rápidas")
        col_g, col_i, col_nueva = st.columns(3)

        with col_g:
            if st.button("➕ Registrar Gasto Rápido", use_container_width=True):
                st.session_state["accion_rapida"] = "gasto"

        with col_i:
            if st.button("➕ Registrar Ingreso Rápido", use_container_width=True):
                st.session_state["accion_rapida"] = "ingreso"

        with col_nueva:
            if st.button("🏗️ Crear Nueva Obra", use_container_width=True, key="btn_crear_obra"):
                # Toggle: abre o cierra el panel
                st.session_state["ir_a_obra"] = not st.session_state.get("ir_a_obra", False)

        # ── Mini panel crear obra ─────────────────────────────────────────
        if st.session_state.get("ir_a_obra"):
            with st.container():
                st.markdown("""
                    <div style="
                        background-color:#f0f7ff;
                        border-left: 4px solid #1a73e8;
                        border-radius: 8px;
                        padding: 16px 20px;
                        margin: 12px 0;
                    ">
                        <b style="color:#1a73e8;">🏗️ Nueva Obra</b>
                    </div>
                """, unsafe_allow_html=True)

                with st.form("form_nueva_obra", clear_on_submit=True):
                    nombre_obra_nueva = st.text_input(
                        "Nombre de la obra *",
                        placeholder="Ej: Casa Tulum 2024"
                    )

                    presupuesto_tipo = st.radio(
                        "Presupuesto",
                        ["Ingresar monto manualmente", "Subir archivo Excel"],
                        horizontal=True
                    )

                    monto_manual = 0.0
                    archivo_opus = None

                    if presupuesto_tipo == "Ingresar monto manualmente":
                        monto_manual = st.number_input(
                            "Monto presupuestado ($)",
                            min_value=0.0,
                            step=1000.0
                        )
                    else:
                        archivo_opus = st.file_uploader(
                            "Archivo Excel OPUS (.xlsx)",
                            type=["xlsx"]
                        )

                    col_guardar, col_cancelar = st.columns([2, 1])

                    with col_guardar:
                        guardar_obra = st.form_submit_button(
                            "💾 Crear Obra",
                            use_container_width=True
                        )

                    with col_cancelar:
                        cancelar_obra = st.form_submit_button(
                            "✕ Cancelar",
                            use_container_width=True
                        )

                    # ── Cancelar ─────────────────────────────────────────
                    if cancelar_obra:
                        st.session_state["ir_a_obra"] = False
                        st.rerun()

                    # ── Guardar ──────────────────────────────────────────
                    if guardar_obra:
                        if not nombre_obra_nueva.strip():
                            st.warning("⚠️ El nombre de la obra es obligatorio.")
                        else:
                            obra_normalizada = normalizar_texto(nombre_obra_nueva)

                            # Determinar monto final
                            if presupuesto_tipo == "Subir archivo Excel" and archivo_opus:
                                try:
                                    df_excel = pd.read_excel(archivo_opus)
                                    monto_final = pd.to_numeric(
                                        df_excel.iloc[0, 1], errors='coerce'
                                    )
                                    if pd.isna(monto_final):
                                        monto_final = 0.0
                                except Exception:
                                    st.warning("⚠️ No se pudo leer el Excel. Se guardará sin monto.")
                                    monto_final = 0.0
                            else:
                                monto_final = monto_manual

                            # Guardar en Presupuestos_Opus
                            try:
                                df_opus_actual = consultar_datos("Presupuestos_Opus")
                                nuevo_presupuesto = pd.DataFrame([{
                                    "Obra":                obra_normalizada,
                                    "Monto_Presupuestado": monto_final,
                                    "Fecha_Carga":         datetime.now().strftime("%d/%m/%Y"),
                                    "Cargado_Por":         st.session_state.get("usuario_actual", "Admin")
                                }])
                                conn.update(
                                    worksheet="Presupuestos_Opus",
                                    data=pd.concat(
                                        [df_opus_actual, nuevo_presupuesto],
                                        ignore_index=True
                                    )
                                )

                                # --- AGREGADO: Registrar obra en Movimientos para activar filtros globales ---
                                df_fresco_alta = consultar_datos("Movimientos")
                                mov_alta = pd.DataFrame([{
                                    "Fecha": str(datetime.now().date()),
                                    "Obra": obra_normalizada,
                                    "Monto": 0.0,
                                    "Tipo": "ALTA DE OBRA",
                                    "Detalle": "Registro inicial de obra",
                                    "Metodo": "N/A",
                                    "Estado": "Activo",
                                    "Partida": "Sin partida"
                                }])
                                if "Partida" not in df_fresco_alta.columns:
                                    df_fresco_alta["Partida"] = "Sin partida"
                                conn.update(
                                    worksheet="Movimientos",
                                    data=pd.concat([df_fresco_alta, mov_alta], ignore_index=True)
                                )
                                # ---------------------------------------------------------------------------

                                st.session_state["ir_a_obra"] = False
                                st.success(f"✅ Obra **{obra_normalizada}** creada. ¡Ve al menú lateral y selecciónala para comenzar a registrar gastos!")
                                st.rerun()

                            except Exception as e:
                                st.error(f"❌ Error al guardar: {str(e)}")

        # --- NUEVO BLOQUE ACCIONES RÁPIDAS ---
        if st.session_state.get("accion_rapida") == "gasto":
            with st.form("form_gasto_rapido", clear_on_submit=True):
                obras_lista = ["+ Nueva Obra"] + (sorted(df_master['Obra'].dropna().unique().tolist()) if not df_master.empty else [])
                
                obra_sel = st.selectbox("Obra", obras_lista)
                nueva_obra = st.text_input("Nombre de la nueva obra") if obra_sel == "+ Nueva Obra" else ""
                
                monto_r = st.number_input("Monto ($)", min_value=0.01, step=0.01)
                tipo_r = st.selectbox("Categoría", ["GASTO (MATERIALES)", "GASTO (SUELDOS)", "GASTO (ADMIN)"])

                if st.form_submit_button("💾 Guardar"):
                    obra_final = normalizar_texto(nueva_obra if obra_sel == "+ Nueva Obra" else obra_sel)

                    if not obra_final or monto_r <= 0:
                        st.warning("⚠️ Completa obra y monto antes de guardar.")
                    else:
                        nuevo = pd.DataFrame([{
                            "Fecha": str(datetime.now().date()),
                            "Obra": obra_final,
                            "Monto": monto_r,
                            "Tipo": tipo_r,
                            "Detalle": "ONE CLICK",
                            "Metodo": "EFECTIVO",
                            "Estado": "ACTIVO"
                        }])

                        df_fresco = consultar_datos("Movimientos")
                        conn.update(worksheet="Movimientos", data=pd.concat([df_fresco, nuevo], ignore_index=True))

                        st.session_state["accion_rapida"] = ""
                        st.success("✅ Gasto registrado")
                        st.rerun()


    if st.session_state.get("accion_rapida") == "ingreso":
        with st.form("form_ingreso_rapido", clear_on_submit=True):
            obras_lista = ["+ Nueva Obra"] + (sorted(df_master['Obra'].dropna().unique().tolist()) if not df_master.empty else [])
            obra_sel = st.selectbox("Obra", obras_lista)
            nueva_obra = st.text_input("Nombre de la nueva obra") if obra_sel == "+ Nueva Obra" else ""
            monto_r = st.number_input("Monto ($)", min_value=0.01, step=0.01)

            if st.form_submit_button("💾 Guardar"):

                obra_final = normalizar_texto(
                    nueva_obra if obra_sel == "+ Nueva Obra" else obra_sel
                )
                if not obra_sel or monto_r <= 0:
                    st.warning("⚠️ Completa obra y monto antes de guardar.")                
                else:
                    nuevo = pd.DataFrame([{
                        "Fecha": str(datetime.now().date()),
                        "Obra": obra_final,
                        "Monto": monto_r,
                        "Tipo": "INGRESO (HONORARIOS)",
                        "Detalle": "ONE CLICK",
                        "Metodo": "TRANSFERENCIA",
                        "Estado": "ACTIVO"
                    }])

                    df_fresco = consultar_datos("Movimientos")
                    conn.update(worksheet="Movimientos", data=pd.concat([df_fresco, nuevo], ignore_index=True))

                    st.session_state["accion_rapida"] = ""
                    st.success("✅ Ingreso registrado")
                    st.rerun()

            # ── NUEVA SECCIÓN: Vista de Campo ─────────────────────────────────
            st.divider()

            with st.expander("📱 Vista de Campo", expanded=False):

                if df_master.empty:
                    st.info("📋 Sin datos registrados aún.")
                else:
                    # ── KPI 1: % Presupuesto Consumido ────────────────────────
                    # Requiere obra específica seleccionada
                    if obra_sel_global != "Todas las Obras":
                        try:
                            df_opus_campo = conn.read(
                                worksheet="Presupuestos_Opus", ttl=0
                            )
                            df_opus_campo.columns = df_opus_campo.columns.str.strip()
                            df_obra_campo = df_opus_campo[
                                df_opus_campo['Obra'].apply(normalizar_texto)
                                == normalizar_texto(obra_sel_global)
                            ]
                            pres_campo = pd.to_numeric(
                                df_obra_campo['Monto_Presupuestado'],
                                errors='coerce'
                            ).sum()
                        except Exception:
                            pres_campo = 0

                        df_campo = df_master[
                            (df_master['Obra'] == normalizar_texto(obra_sel_global)) &
                            (df_master['Estado'] != 'ANULADO')
                        ].copy()
                        df_campo['Monto'] = pd.to_numeric(
                            df_campo['Monto'], errors='coerce'
                        ).fillna(0)

                        gastos_campo = df_campo[
                            df_campo['Tipo'].str.contains("GASTO", na=False)
                        ]['Monto'].sum()

                        ingresos_campo = df_campo[
                            df_campo['Tipo'].str.contains("INGRESO", na=False)
                        ]['Monto'].sum()

                        # Utilidad real — misma fórmula que Salud Financiera
                        inflacion_campo   = obtener_inflacion_reciente()
                        utilidad_nom_campo = ingresos_campo - gastos_campo
                        utilidad_real_campo = utilidad_nom_campo - (
                            gastos_campo * (inflacion_campo / 100)
                        )

                        # % consumido con fallback seguro
                        pct_campo = (
                            (gastos_campo / pres_campo * 100)
                            if pres_campo > 0 else 0.0
                        )

                        # ── KPI 3: Días desde último registro ─────────────────
                        try:
                            df_campo['Fecha'] = pd.to_datetime(
                                df_campo['Fecha'], errors='coerce'
                            )
                            ultima_fecha = df_campo['Fecha'].dropna().max()
                            dias_ultimo = (
                                pd.Timestamp.now() - ultima_fecha
                            ).days if pd.notna(ultima_fecha) else None
                        except Exception:
                            dias_ultimo = None

                        # ── Render de los 3 KPIs ──────────────────────────────
                        k1, k2, k3 = st.columns(3)

                        k1.metric(
                            "📊 Presupuesto Consumido",
                            f"{pct_campo:.1f}%",
                            delta="⚠️ Alto" if pct_campo > 90 else "OK",
                            delta_color="inverse" if pct_campo > 90 else "normal"
                        )

                        k2.metric(
                            "💰 Utilidad Real",
                            f"${utilidad_real_campo:,.0f}",
                            delta="🔴 Negativa" if utilidad_real_campo < 0 else "🟢 Positiva",
                            delta_color="inverse" if utilidad_real_campo < 0 else "normal"
                        )

                        k3.metric(
                            "📅 Días sin Registro",
                            f"{dias_ultimo} días" if dias_ultimo is not None else "—",
                            delta="⚠️ Revisar" if dias_ultimo and dias_ultimo > 7 else "OK",
                            delta_color="inverse" if dias_ultimo and dias_ultimo > 7 else "normal"
                        )

                    else:
                        st.info(
                            "👆 Selecciona una obra específica en el panel lateral "
                            "para ver la Vista de Campo."
                        )
            # ── FIN VISTA DE CAMPO ────────────────────────────────────────────

    elif menu == "📊 Salud Financiera":
        st.header(f"📊 Análisis Estratégico: {obra_sel_global}")

        # --- 1. INFLACIÓN (INTACTA) ---
        inflacion_anual = obtener_inflacion_reciente()

        try:
            df_opus = conn.read(worksheet="Presupuestos_Opus", ttl=0)
            df_opus.columns = df_opus.columns.str.strip()

            col_monto_fija = "Monto_Presupuestado"

            if col_monto_fija in df_opus.columns and obra_sel_global != "Todas las Obras":
                df_opus["Obra"] = df_opus["Obra"].astype(str).str.strip().str.upper()

                df_obra_p = df_opus[
                    df_opus["Obra"] == normalizar_texto(obra_sel_global)
                ]

                pres_original = pd.to_numeric(
                    df_obra_p[col_monto_fija],
                    errors="coerce"
                ).sum()
            else:
                pres_original = 0

        except Exception:
            pres_original = 0

        # --- 2. FLUJO DE CAJA ---
        if not df_filtrado.empty:
            df_c = df_filtrado.copy()

            if 'Estado' in df_c.columns:
                df_c = df_c[df_c['Estado'] != 'ANULADO']

            df_c['Monto'] = pd.to_numeric(df_c['Monto'], errors='coerce').fillna(0)

            ingresos = df_c[
                df_c['Tipo'].fillna("").str.contains("INGRESO", case=False, na=False)
            ]['Monto'].sum()

            gastos_reales = df_c[
                df_c['Tipo'].fillna("").str.contains("GASTO", case=False, na=False)
            ]['Monto'].sum()

            utilidad_nominal = ingresos - gastos_reales
            perdida_inflacionaria = gastos_reales * (inflacion_anual / 100)
            utilidad_real = utilidad_nominal - perdida_inflacionaria

            # --- MÉTRICAS BASE ---
            st.info(f"📅 **Tasa de Inflación Aplicada (INPC):** {inflacion_anual}%")
            
            # --- AGREGADO: EXPLICACIÓN DE CONCEPTOS ---
            with st.expander("❓ Entender Utilidad Nominal vs Real"):
                st.write("""
                * **Utilidad Nominal:** Es tu ganancia bruta actual (Ingresos - Gastos).
                * **Utilidad Real:** Es lo que realmente ganas después de descontar la pérdida de valor por inflación (INPC). 
                Evo Q ajusta tus gastos para que sepas cuánto dinero tienes disponible hoy con el poder adquisitivo real.
                """)

            c1, c2, c3 = st.columns(3)
            c1.metric("Ingresos Totales", f"${ingresos:,.2f}")
            c2.metric("Gastos Reales", f"${gastos_reales:,.2f}", delta_color="inverse")
            c3.metric("Utilidad Nominal", f"${utilidad_nominal:,.2f}")

            st.divider()

            # --- 3. IMPACTO DE INFLACIÓN (CLAVE DEL SISTEMA) ---
            st.subheader("📉 Impacto de la Inflación en tu Ganancia")

            u1, u2 = st.columns(2)

            with u1:
                st.metric(
                    "Utilidad Real",
                    f"${utilidad_real:,.2f}",
                    delta=f"-${perdida_inflacionaria:,.2f} Poder Adquisitivo",
                    delta_color="inverse"
                )
                
                # --- AGREGADO: SEMÁFORO DE RENTABILIDAD ---
                margen_porcentaje = (utilidad_real / ingresos) if ingresos > 0 else 0
                if margen_porcentaje < 0.10:
                    st.error(f"🔴 Margen Crítico: {margen_porcentaje:.1%}. Revisar costos.")
                elif margen_porcentaje < 0.20:
                    st.warning(f"🟡 Margen Ajustado: {margen_porcentaje:.1%}.")
                else:
                    st.success(f"🟢 Margen Óptimo: {margen_porcentaje:.1%}.")

            with u2:
                fig_u = px.bar(
                    pd.DataFrame({
                        'Tipo': ['Nominal', 'Real'],
                        'Monto': [utilidad_nominal, utilidad_real]
                    }),
                    x='Tipo',
                    y='Monto',
                    color='Tipo',
                    color_discrete_map={
                        'Nominal': '#3498db',
                        'Real': '#e67e22'
                    }
                )
                st.plotly_chart(fig_u, use_container_width=True)

            st.divider()

            if pres_original > 0:
                porcentaje_gastado = (gastos_reales / pres_original) * 100
                if porcentaje_gastado > 90:
                    st.error(f"⚠️ ALERTA DE SOBRECOSTO: Has consumido el {porcentaje_gastado:.1f}% del presupuesto.")
                
                if st.button("🤖 Evaluar Rentabilidad Actual", key="btn_evaluar_rentabilidad"):
                    if utilidad_real > (pres_original * 0.10):
                        st.balloons()
                        st.success("🚀 Obra altamente rentable.")
                    else:
                        st.warning("⚠️ Margen estrecho. Revisar costos de materiales.")

                    st.divider()

            # --- [NUEVO] EFICIENCIA OPERATIVA ────────────────────────────
            st.subheader("⏱️ Eficiencia Operativa")

            # Lectura fresca de talento (misma fuente que el módulo de talento)
            df_talento_ef = consultar_datos("Talento")

            total_horas = 0.0

            if not df_talento_ef.empty:
                df_talento_ef['Horas'] = pd.to_numeric(
                    df_talento_ef['Horas'], errors='coerce'
                ).fillna(0)

                # Filtrar por obra — misma lógica que df_filtrado en este módulo
                if obra_sel_global != "Todas las Obras":
                    df_t_obra = df_talento_ef[
                        df_talento_ef['Obra'].apply(normalizar_texto)
                        == normalizar_texto(obra_sel_global)
                    ]
                else:
                    df_t_obra = df_talento_ef.copy()

                total_horas = df_t_obra['Horas'].sum()

            # Métricas de eficiencia
            ef1, ef2 = st.columns(2)

            with ef1:
                st.metric(
                    "⏱️ Horas Totales Registradas",
                    f"{total_horas:.1f} hrs"
                )

            with ef2:
                if total_horas > 0:
                    rentabilidad_por_hora = utilidad_real / total_horas
                else:
                    rentabilidad_por_hora = 0.0


                with ef1:
                    st.metric(
                        "⏱️ Horas Totales Registradas",
                        f"{total_horas:.1f} hrs"
                    )

                with ef2:
                    if total_horas > 0:
                        st.metric(
                            "💰 Rentabilidad por Hora",
                            f"${rentabilidad_por_hora:,.2f} / hr"
                        )
                    else:
                        st.metric("💰 Rentabilidad por Hora", "— Sin horas registradas")

            # Evaluación visual (thresholds simples de negocio)
            # Threshold "horas altas": más de 100 hrs por obra es carga considerable
            # Threshold "utilidad alta": utilidad_real positiva y > $5,000
            UMBRAL_HORAS_ALTO  = 100   # hrs — ajustable según perfil del despacho
            UMBRAL_UTILIDAD    = 5000  # MXN — ajustable

            # Garantía de que rentabilidad_por_hora siempre existe en scope
            # antes de los if/elif/else de evaluación visual
            if total_horas > 0:
                rentabilidad_por_hora = utilidad_real / total_horas
            else:
                rentabilidad_por_hora = 0.0

            # Evaluación visual (thresholds simples de negocio)
            UMBRAL_HORAS_ALTO = 100
            UMBRAL_UTILIDAD   = 5000

            if total_horas == 0:
                st.info(
                    "📋 No hay horas registradas para esta obra. "
                    "Registra jornadas en **Gestión de Talento** para activar este análisis."
                )
            elif utilidad_real > UMBRAL_UTILIDAD and total_horas <= UMBRAL_HORAS_ALTO:
                st.success(
                    f"🚀 **Alta Eficiencia** — Generando **${utilidad_real:,.0f}** "
                    f"con solo **{total_horas:.0f} hrs** de trabajo. "
                    f"Rentabilidad: **${rentabilidad_por_hora:,.2f}/hr**"
                )
            elif utilidad_real > 0 and total_horas > UMBRAL_HORAS_ALTO:
                st.warning(
                    f"⚠️ **Baja Eficiencia** — Ganancia positiva (${utilidad_real:,.0f}) "
                    f"pero con **{total_horas:.0f} hrs** invertidas. "
                    f"Rentabilidad: **${rentabilidad_por_hora:,.2f}/hr**. "
                    f"Revisar distribución de tareas."
                )
            elif utilidad_real <= 0:
                st.error(
                    f"🔴 **Ineficiencia Crítica** — Utilidad real negativa "
                    f"(${utilidad_real:,.0f}) con {total_horas:.0f} hrs invertidas. "
                    f"Obra en riesgo financiero."
                )
            else:
                st.warning(
                    f"🟡 **Balance Moderado** — Rentabilidad de "
                    f"**${rentabilidad_por_hora:,.2f}/hr** con {total_horas:.0f} hrs. "
                    f"Margen mejorable."
                )
            # --- 4. ALERTA DE PRESUPUESTO ---
            if pres_original > 0:
                porcentaje_gastado = (gastos_reales / pres_original) * 100

                if porcentaje_gastado > 90:
                    st.error(
                        f"⚠️ ALERTA DE SOBRECOSTO: Has consumido el {porcentaje_gastado:.1f}% del presupuesto."
                    )

            # --- 5. FORECASTING (RECUPERADO COMPLETO) ---
            st.subheader("🔮 Proyección de Cierre (Forecasting)")

            if pres_original > 0:
                p1, p2 = st.columns(2)

                with p1:
                    costo_final_proyectado = gastos_reales + (
                        pres_original - gastos_reales
                    ) * (1 + (inflacion_anual / 100))

                    desviacion = costo_final_proyectado - pres_original

                    st.metric(
                        "Costo Final Proyectado",
                        f"${costo_final_proyectado:,.2f}",
                        delta=f"${desviacion:,.2f} Desvío Estimado",
                        delta_color="inverse"
                    )

                with p2:
                    por_gastar = max(0, pres_original - gastos_reales)

                    st.plotly_chart(
                        px.pie(
                            values=[gastos_reales, por_gastar],
                            names=['Consumido', 'Disponible'],
                            hole=.5
                        ),
                        use_container_width=True
                    )

            st.divider()


            # --- 7. COMPARATIVO OPUS (AJUSTADO INFLACIÓN) ---
            st.subheader("🎯 Comparativo vs Presupuesto Original (OPUS)")

            if pres_original > 0:
                pres_ajustado = pres_original * (1 + (inflacion_anual / 100))
                margen_pres = pres_ajustado - gastos_reales

                o1, o2, o3 = st.columns(3)

                o1.metric("Presupuesto Original", f"${pres_original:,.2f}")
                o2.metric(
                    "Ajustado (INPC)",
                    f"${pres_ajustado:,.2f}",
                    delta=f"+{inflacion_anual}%"
                )
                o3.metric(
                    "Margen Disponible",
                    f"${margen_pres:,.2f}",
                    delta="SANO" if margen_pres > 0 else "SOBREGIRO",
                    delta_color="normal" if margen_pres > 0 else "inverse"
                )

                st.divider()

                # ── NUEVO: Desglose por Partida ───────────────────────────────
                st.subheader("🗂️ Control por Partidas Presupuestarias")

                # Solo se activa si la columna Partida existe en los datos
                if "Partida" in df_c.columns:

                    df_partidas = df_c[
                        df_c['Tipo'].fillna("").str.contains("Gasto", case=False)
                    ].copy()

                    df_partidas['Partida'] = df_partidas['Partida'].fillna(
                        "Sin partida"
                    ).replace("", "Sin partida")

                    if not df_partidas.empty:
                        # Agrupación por partida
                        resumen_partidas = (
                            df_partidas.groupby("Partida")["Monto"]
                            .sum()
                            .reset_index()
                            .rename(columns={"Monto": "Gastado"})
                            .sort_values("Gastado", ascending=False)
                        )

                        # Columna de alerta visual
                        def semaforo_partida(gastado, total_gastos):
                            pct = (gastado / total_gastos * 100) if total_gastos > 0 else 0
                            if pct >= 40:
                                return f"🔴 {pct:.1f}%"
                            elif pct >= 20:
                                return f"🟡 {pct:.1f}%"
                            else:
                                return f"🟢 {pct:.1f}%"

                        resumen_partidas["% del Total"] = resumen_partidas["Gastado"].apply(
                            lambda x: semaforo_partida(x, gastos_reales)
                        )
                        resumen_partidas["Gastado $"] = resumen_partidas["Gastado"].apply(
                            lambda x: f"${x:,.2f}"
                        )

                        # Tabla de desglose
                        st.dataframe(
                            resumen_partidas[["Partida", "Gastado $", "% del Total"]],
                            use_container_width=True,
                            hide_index=True
                        )

                        # Gráfico de barras por partida
                        fig_partidas = px.bar(
                            resumen_partidas,
                            x="Partida",
                            y="Gastado",
                            title="Distribución de Gastos por Partida",
                            color="Gastado",
                            color_continuous_scale="RdYlGn_r",
                            labels={"Gastado": "Monto ($)", "Partida": "Partida"}
                        )
                        fig_partidas.update_layout(
                            showlegend=False,
                            coloraxis_showscale=False
                        )
                        st.plotly_chart(fig_partidas, use_container_width=True)

                    else:
                        st.info(
                            "📋 No hay gastos con partida asignada aún. "
                            "Asigna partidas al registrar gastos en Registro Contable."
                        )
                else:
                    st.info(
                        "📋 El control por partidas se activa automáticamente "
                        "cuando registres tu próximo gasto en Registro Contable."
                    )
                # ─────────────────────────────────────────────────────────────

            else:
                st.warning("⚠️ No hay movimientos registrados para realizar el análisis estratégico.")

    elif menu == "📝 Registro Contable":
        if not tiene_permiso("📝 Registro Contable"):
            st.warning("🔒 No tienes permiso para acceder a este módulo.")
            st.stop()

        st.header("📸 Escáner Inteligente de Tickets")

        # --- ACCIÓN RÁPIDA ONE-CLICK ---
        with st.expander("⚡ Acciones Rápidas", expanded=False):
            col_q1, col_q2 = st.columns(2)

            if col_q1.button("🛒 Gasto Rápido Material ($1,000)"):
                obra_rapida = (
                    obra_sel_global
                    if obra_sel_global != "Todas las Obras"
                    else st.session_state.session_data.get("last_obra", "")
                )
                if not obra_rapida:
                    st.warning("⚠️ Selecciona una obra en el panel lateral primero.")
                else:
                    nueva_q = pd.DataFrame([{
                        "Fecha":   str(datetime.now().date()),
                        "Obra":    normalizar_texto(obra_rapida),
                        "Monto":   1000,
                        "Tipo":    "Gasto (Materiales)",
                        "Detalle": "GASTO RÁPIDO EN OBRA",
                        "Metodo":  "Efectivo",
                        "Estado":  "Activo"
                    }])
                    df_fresco = consultar_datos("Movimientos")
                    conn.update(
                        worksheet="Movimientos",
                        data=pd.concat([df_fresco, nueva_q], ignore_index=True)
                    )
                    st.toast("✅ Gasto de $1,000 registrado")
                    st.rerun()

        # --- HELPER: AUTOCATEGORIZACIÓN (disponible para todo el módulo) ---
        def auto_categorizar(concepto):
            c = concepto.lower()
            if any(x in c for x in ["cemento", "varilla", "arena", "bloque", "ladrillo"]):
                return "Gasto (Materiales)"
            if any(x in c for x in ["raya", "sueldo", "pago", "nomina"]):
                return "Gasto (Sueldos)"
            return "Gasto (Admin)"

        # --- IA GEMINI: OPCIONAL, NO BLOQUEA EL FLUJO ---
        # Leemos session_data para prellenar el formulario si la IA ya corrió
        last_monto     = st.session_state.session_data.get("last_monto", 0.0)
        last_detalle   = st.session_state.session_data.get("last_detalle", "")
        last_ferreteria = st.session_state.session_data.get("last_ferreteria", "")

        archivo_ticket = st.file_uploader(
            "Capturar Ticket / Factura (opcional)",
            type=["jpg", "png", "jpeg"]
        )

        if archivo_ticket:
            img_ia = Image.open(archivo_ticket)
            st.image(img_ia, width=250)

            if st.button("🕵️ Escanear con IA"):
                with st.spinner("🤖 Evo Q está leyendo tu ticket..."):
                    try:
                        model_ia = genai.GenerativeModel('gemini-1.5-flash')
                        prompt_ia = (
                            "Extrae de este ticket: monto total (monto), "
                            "nombre del negocio (ferreteria), y material comprado (detalle). "
                            "Responde solo en JSON válido, sin texto adicional ni backticks."
                        )
                        # Convertir PIL.Image a bytes para la API de Gemini
                        buffer = io.BytesIO()
                        img_ia.save(buffer, format="JPEG")
                        img_bytes = buffer.getvalue()
                        img_part = {"mime_type": "image/jpeg", "data": img_bytes}
                        res_ia = model_ia.generate_content([prompt_ia, img_part])
                        texto_ia = res_ia.text.replace('```json', '').replace('```', '').strip()
                        # Extraer solo el bloque JSON si hay texto adicional alrededor
                        match_json = re.search(r'\{.*\}', texto_ia, re.DOTALL)
                        if match_json:
                            datos_res = json.loads(match_json.group())
                        else:
                            raise ValueError("Gemini no devolvió JSON válido")

                        # Guardamos en session_data para prellenar el form
                        st.session_state.session_data.update({
                            "last_monto":      float(datos_res.get('monto', 0.0)),
                            "last_detalle":    str(datos_res.get('detalle', '')),
                            "last_ferreteria": str(datos_res.get('ferreteria', ''))
                        })
                        # Actualizamos variables locales para el form de abajo
                        last_monto      = st.session_state.session_data["last_monto"]
                        last_detalle    = st.session_state.session_data["last_detalle"]
                        last_ferreteria = st.session_state.session_data["last_ferreteria"]

                        st.success("✅ Datos extraídos. Formulario pre-llenado.")
                        st.toast("🤖 Evo Q procesó el ticket automáticamente", icon="🤖")

                    except Exception as e_ia:
                        # Detección específica de error 404 (modelo no disponible)
                        error_str = str(e_ia).lower()
                        if "404" in error_str or "not found" in error_str or "deprecated" in error_str:
                            st.info(
                                "🤖 IA temporalmente no disponible. "
                                "Puedes continuar completando el formulario manualmente — "
                                "funciona igual de bien."
                            )
                        else:
                            st.info(
                                "🤖 No se pudo leer el ticket automáticamente. "
                                "Completa el formulario manualmente y continúa sin problema."
                            )
                        # El formulario manual siempre está disponible debajo
                        # No se lanza ningún error — flujo continúa normalmente

        # --- FORMULARIO PRINCIPAL ---
        with st.form("form_registro_v3", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                fecha = st.date_input("Fecha", datetime.now())
                proyectos_list = (
                    sorted(df_master['Obra'].unique().tolist())
                    if not df_master.empty else []
                )
                obra_opcion = st.selectbox(
                    "Seleccionar Obra",
                    ["+ Nueva Obra"] + proyectos_list
                )
                nueva_obra_input = (
                    st.text_input("Nombre de la nueva obra")
                    if obra_opcion == "+ Nueva Obra"
                    else ""
                )

            with col2:
                monto_input = st.number_input(
                    "Monto total ($)",
                    value=float(last_monto),
                    min_value=0.0,
                    step=0.01
                )
                tipo_movimiento = st.selectbox(
                    "Categoría",
                    ["Ingreso (Honorarios)", "Gasto (Materiales)",
                    "Gasto (Sueldos)", "Gasto (Admin)"]
                )
                metodo_pago = st.selectbox(
                    "Caja / Banco",
                    ["Efectivo", "Transferencia", "Tarjeta"]
                )

                # ── NUEVO: Partida presupuestaria ─────────────────────────────
                # Solo se activa para gastos — los ingresos no tienen partida
                PARTIDAS = [
                    "Sin partida",
                    "Cimentación",
                    "Estructura",
                    "Albañilería",
                    "Instalación Eléctrica",
                    "Instalación Hidráulica",
                    "Acabados",
                    "Carpintería",
                    "Herrería",
                    "Equipamiento",
                    "Honorarios",
                    "Administración"
                ]
                partida_sel = st.selectbox(
                    "Partida Presupuestaria",
                    PARTIDAS,
                    help="Clasifica el gasto por partida para control detallado"
                )

            st.divider()

            # Inputs reales — nunca vacíos ni "GENERAL"
            nombre_material   = st.text_input(
                "Material / Concepto (ej. Cemento Portland)",
                value=last_detalle
            )
            nombre_ferreteria = st.text_input(
                "Ferretería / Proveedor",
                value=last_ferreteria
            )
            detalle_mov = st.text_area("Notas adicionales")

            enviar_btn = st.form_submit_button("🔨 Guardar en Registro")

            if enviar_btn:
                nombre_obra_final = (
                    nueva_obra_input
                    if obra_opcion == "+ Nueva Obra"
                    else obra_opcion
                )

                # --- VALIDACIONES MEJORADAS (ANTI-ERRORES) ---
                if not nombre_obra_final:
                    st.error("⚠️ Debes seleccionar o crear una OBRA.")

                elif monto_input <= 0:
                    st.error("⚠️ El MONTO debe ser mayor a 0.")

                elif not tipo_movimiento:
                    st.error("⚠️ Debes seleccionar una CATEGORÍA.")

                elif tipo_movimiento == "Gasto (Materiales)" and not nombre_material.strip():
                    st.error("⚠️ Debes especificar el MATERIAL.")

                elif tipo_movimiento == "Gasto (Materiales)" and not nombre_ferreteria.strip():
                    st.error("⚠️ Debes especificar la FERRETERÍA.")
                else:
                    # ── 1. GUARDAR EN MOVIMIENTOS ─────────────────────────
                    nuevo_reg = pd.DataFrame([{
                        "Fecha":    str(fecha),
                        "Obra":     normalizar_texto(nombre_obra_final),
                        "Monto":    monto_input,
                        "Tipo":     tipo_movimiento,
                        "Detalle":  nombre_material,
                        "Metodo":   metodo_pago,
                        "Estado":   "Activo",
                        "Partida":  partida_sel   # ← columna nueva
                    }])

                    df_fresco_mov = consultar_datos("Movimientos")

                    # Garantía de compatibilidad: si la hoja aún no tiene
                    # columna Partida, la agregamos vacía antes del concat
                    if "Partida" not in df_fresco_mov.columns:
                        df_fresco_mov["Partida"] = "Sin partida"

                    conn.update(
                        worksheet="Movimientos",
                        data=pd.concat([df_fresco_mov, nuevo_reg], ignore_index=True)
                    )

                    # ── 2. ALIMENTAR CATÁLOGO DE PRECIOS (solo si es material) ──
                    # Requiere material Y ferretería con valores reales
                    if (
                        tipo_movimiento == "Gasto (Materiales)"
                        and nombre_material.strip()
                        and nombre_ferreteria.strip()
                    ):
                        try:
                            df_cat = consultar_datos("Catalogo_Precios")
                            nuevo_precio = pd.DataFrame([{
                                "Material":           nombre_material.strip().upper(),
                                "Ferreteria":         nombre_ferreteria.strip().upper(),
                                "Precio_Unitario":    monto_input,
                                "Fecha_Actualizacion": str(fecha),
                                "Obra_Origen":        normalizar_texto(nombre_obra_final)
                            }])
                            conn.update(
                                worksheet="Catalogo_Precios",
                                data=pd.concat([df_cat, nuevo_precio], ignore_index=True)
                            )
                        except Exception as e_cat:
                            # No bloquea el flujo principal si el catálogo falla
                            st.warning(f"⚠️ Movimiento guardado, pero no se pudo actualizar Catálogo: {str(e_cat)}")

                    # ── 3. LIMPIAR SESSION DATA DE IA ─────────────────────
                    st.session_state.session_data.update({
                        "last_monto": 0.0,
                        "last_detalle": "",
                        "last_ferreteria": ""
                    })

                    st.success("✅ Registro completado")
                    st.rerun()

        # --- MÓDULO: COMPARADOR DE PRECIOS ---
    elif menu == "🛒 Comparador de Precios":
        st.header("🕵️ Radar de Costos e Inteligencia de Mercado")

        # --- FICHA DE CONTACTO RÁPIDO ---
        with st.expander("🏗️ Proveedor Estrella: MATERIALES CONSTRUMAR", expanded=True):
            col_wa, col_mail = st.columns(2)

            with col_wa:
                num_wa = "529861005818"
                msg_wa = "Hola Construmar, te contacto de EVO-Q. Me gustaría cotizar material."
                link_wa = f"https://wa.me/{num_wa}?text={msg_wa.replace(' ', '%20')}"
                st.link_button("📲 Cotizar por WhatsApp", link_wa, use_container_width=True)

            with col_mail:
                correo = "cuyoconstrumar@gmail.com"
                asunto = "Solicitud de Cotización / Factura - EVO-Q"
                link_mail = f"mailto:{correo}?subject={asunto.replace(' ', '%20')}"
                st.link_button("📧 Enviar Correo / Factura", link_mail, use_container_width=True)

            st.caption("📍 El Cuyo | Facturación Disponible | Contacto Directo")

        # --- LÓGICA DE BÚSQUEDA DE PRECIOS ---
        try:
            ID_EXCEL = "1fpTC_6y9fndidwnr4xaZf2ISDRGNKHEFYW-OLwxMzt0"
            url_cat = f"https://docs.google.com/spreadsheets/d/{ID_EXCEL}/gviz/tq?tqx=out:csv&sheet=Catalogo_Precios"

            df_p = pd.read_csv(url_cat)

            # 🔥 FIX: protección de catálogo corrupto o vacío
            if df_p is None or df_p.empty:
                st.info("💡 El catálogo está vacío.")
                st.stop()

            df_p.columns = df_p.columns.str.strip()
            df_p = df_p.fillna("")

            # 🔥 FIX: asegurar columnas críticas
            for col in ["Material", "Ferreteria", "Precio_Unitario"]:
                if col not in df_p.columns:
                    df_p[col] = ""

            st.subheader("🔍 Buscar el mejor precio")

            mat_list = sorted(df_p['Material'].dropna().unique().tolist())
            busqueda = st.selectbox("¿Qué material buscas?", ["Seleccionar..."] + mat_list)

            if busqueda != "Seleccionar...":
                    df_res = df_p[df_p['Material'] == busqueda].copy()
                    df_res['Precio_Unitario'] = pd.to_numeric(
                        df_res['Precio_Unitario'], errors='coerce'
                    )
                    df_res = df_res.sort_values(by="Precio_Unitario", ascending=True)

                    mejor_precio = df_res.iloc[0]

                    st.success(
                        f"🏆 El mejor precio para **{busqueda}** es de "
                        f"**${mejor_precio['Precio_Unitario']:,.2f}** "
                        f"en **{mejor_precio['Ferreteria']}**"
                    )

                    # ── NUEVO: Tabulador de Precio Referencia ─────────────
                    # Se activa SOLO si la columna existe en el catálogo
                    # Si no existe, el flujo original continúa sin cambios
                    if 'Precio_Referencia' in df_res.columns:

                        precio_ref_raw = pd.to_numeric(
                            df_res.iloc[0].get('Precio_Referencia', None),
                            errors='coerce'
                        )

                        if pd.notna(precio_ref_raw) and precio_ref_raw > 0:
                            precio_actual  = mejor_precio['Precio_Unitario']
                            precio_ref     = float(precio_ref_raw)
                            variacion      = ((precio_actual - precio_ref) / precio_ref) * 100

                            if variacion > 0:
                                semaforo  = "🔴"
                                delta_color = "inverse"
                            else:
                                semaforo  = "🟢"
                                delta_color = "normal"

                            st.markdown("#### 📊 Análisis vs Precio de Referencia")

                            t1, t2, t3 = st.columns(3)

                            t1.metric(
                                "📌 Precio Referencia",
                                f"${precio_ref:,.2f}",
                                help="Precio paramétrico interno del despacho"
                            )
                            t2.metric(
                                "🏷️ Mejor Precio Actual",
                                f"${precio_actual:,.2f}"
                            )
                            t3.metric(
                                "📈 Variación",
                                f"{semaforo} {variacion:+.1f}%",
                                delta=f"{'Por encima' if variacion > 0 else 'Por debajo'} del tabulador",
                                delta_color=delta_color
                            )
                    # ── FIN TABULADOR ─────────────────────────────────────

                    num_wa = "529861005818"
                    msg_wa_ia = (
                        f"Hola Construmar, necesito cotizar {busqueda}. "
                        f"Mi último precio registrado fue de "
                        f"${mejor_precio['Precio_Unitario']:,.2f}. "
                        f"¿Tienen mejor precio hoy?"
                    )
                    link_wa_ia = f"https://wa.me/{num_wa}?text={msg_wa_ia.replace(' ', '%20')}"
                    st.link_button(
                        "📲 Negociar Mejor Precio (One-Click)",
                        link_wa_ia,
                        use_container_width=True
                    )

                    st.write("### Historial de Precios Registrados")
                    st.dataframe(
                        df_res[['Ferreteria', 'Precio_Unitario',
                                'Fecha_Actualizacion', 'Obra_Origen']],
                        use_container_width=True
                    )

        except Exception as e:
                    st.error(f"⚠️ Error detallado: {str(e)}")        

    elif menu == "🚫 Anular Movimiento":
        if not tiene_permiso("🚫 Anular Movimiento"):
            st.warning("🔒 No tienes permiso para acceder a este módulo.")
            st.stop()

        st.header("🚫 Anulación de Movimientos")

        # Lectura fresca para evitar operar sobre datos de sesión desactualizados
        df_anula = consultar_datos("Movimientos")

        if df_anula.empty:
            st.warning("⚠️ El registro maestro está vacío.")
            st.stop()

        # ── SECCIÓN 1: ANULAR MOVIMIENTO ─────────────────────────────────────
        movs_activos = df_anula[df_anula['Estado'] != 'ANULADO'].copy()

        if not movs_activos.empty:
            # Etiqueta de display legible para el selector
            movs_activos['Display'] = (
                movs_activos['Fecha'].astype(str) + " | "
                + movs_activos['Obra'].astype(str) + " | $"
                + movs_activos['Monto'].astype(str) + " | "
                + movs_activos['Tipo'].astype(str)
            )

            sel = st.selectbox("Selecciona el movimiento a anular:", movs_activos['Display'])
            motivo = st.text_input("Motivo de la anulación (obligatorio):")

            if st.button("🚫 Confirmar Anulación"):
                # Validación DENTRO del único botón
                if not motivo.strip():
                    st.warning("⚠️ El motivo de anulación es obligatorio.")
                else:
                    idx = movs_activos[movs_activos['Display'] == sel].index

                    if not idx.empty:
                        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                        usuario_actual = st.session_state.get('usuario_actual', 'Desconocido')

                        detalle_previo = df_anula.loc[idx, 'Detalle'].values[0]
                        if pd.isna(detalle_previo) or str(detalle_previo).lower() in ('none', 'nan', ''):
                            detalle_limpio = ""
                        else:
                            detalle_limpio = str(detalle_previo)

                        df_anula.loc[idx, 'Estado']  = 'ANULADO'
                        df_anula.loc[idx, 'Detalle'] = (
                            detalle_limpio
                            + f" | 🚫 ANULADO: {ahora}"
                            + f" | Motivo: {motivo.strip()}"
                            + f" | Por: {usuario_actual}"
                        )

                        if 'Fecha_Anulacion' not in df_anula.columns:
                            df_anula['Fecha_Anulacion'] = ""
                        if 'Usuario_Anulacion' not in df_anula.columns:
                            df_anula['Usuario_Anulacion'] = ""

                        df_anula.loc[idx, 'Fecha_Anulacion']   = ahora
                        df_anula.loc[idx, 'Usuario_Anulacion'] = usuario_actual

                        conn.update(worksheet="Movimientos", data=df_anula)

                        st.success(
                            f"✅ Movimiento anulado por **{usuario_actual}** "
                            f"el {ahora}. Registrado en historial."
                        )
                        st.rerun()

        # ── SECCIÓN 2: HISTORIAL DE ANULACIONES ──────────────────────────────
        st.subheader("📜 Historial de Movimientos Anulados")

        df_historial = df_anula[df_anula['Estado'] == 'ANULADO'].copy()

        if not df_historial.empty:
            # Columnas a mostrar — usamos las que existen para no crashear
            cols_base    = ['Fecha', 'Obra', 'Monto', 'Tipo', 'Detalle']
            cols_auditoria = []
            if 'Fecha_Anulacion'   in df_historial.columns: cols_auditoria.append('Fecha_Anulacion')
            if 'Usuario_Anulacion' in df_historial.columns: cols_auditoria.append('Usuario_Anulacion')

            cols_mostrar = cols_base + cols_auditoria
            hist_table   = df_historial[cols_mostrar].copy()

            # Renombrado solo de las columnas que existen
            rename_map = {
                'Fecha':             'Fecha Origen',
                'Monto':             'Monto Anulado',
                'Tipo':              'Categoría',
                'Detalle':           'Detalle y Motivo',
                'Fecha_Anulacion':   'Fecha Anulación',
                'Usuario_Anulacion': 'Anulado Por'
            }
            hist_table = hist_table.rename(columns=rename_map)

            st.dataframe(hist_table, use_container_width=True)

            # Total anulado (conversión segura)
            total_anulado = pd.to_numeric(
                df_historial['Monto'], errors='coerce'
            ).fillna(0).sum()

            st.warning(
                f"⚠️ Total de flujo anulado en este periodo: "
                f"**${total_anulado:,.2f} MXN**"
            )
        else:
            st.info("📋 Aún no hay registros en el historial de anulaciones.")
        
    elif menu == "⏱️ Gestión de Talento":
        st.header(f"⏱️ Control de Horas y Rendimiento: {obra_sel_global}")
        
        df_talento = consultar_datos("Talento")
        
        # ── SECCIÓN ORIGINAL: Registro de Jornada (INTACTA) ──────────────
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
            df_t_filtro = df_talento if obra_sel_global == "Todas las Obras" else df_talento[df_talento['Obra'] == obra_sel_global]
            if not df_t_filtro.empty:
                st.plotly_chart(px.pie(df_t_filtro, values='Horas', names='Actividad', hole=0.4, title="Distribución de Esfuerzo"))

        # ── NUEVA SECCIÓN: Nómina Quincenal ───────────────────────────────
        st.divider()
        st.subheader("💰 Nómina Quincenal")

        # Tabs: una para registrar, otra para consultar
        tab_registro, tab_resumen = st.tabs([
            "➕ Registrar Nómina",
            "📋 Resumen por Quincena"
        ])

        # ── TAB 1: Registro de nómina ─────────────────────────────────────
        with tab_registro:
            with st.form("form_nomina_quincenal", clear_on_submit=True):
                col_n1, col_n2 = st.columns(2)

                with col_n1:
                    empleado_nom = st.selectbox(
                        "Empleado",
                        ["Federico", "Hugo", "Capataz", "Residente"],
                        key="nom_empleado"
                    )
                    obra_nom = st.selectbox(
                        "Obra",
                        (["Todas las Obras"] +
                         sorted(df_master['Obra'].unique().tolist()))
                        if not df_master.empty else ["Sin obras"],
                        key="nom_obra"
                    )
                    fecha_nom = st.date_input(
                        "Fecha de pago",
                        datetime.now(),
                        key="nom_fecha"
                    )

                with col_n2:
                    periodo_nom = st.selectbox(
                        "Periodo",
                        ["Quincena 1 (1-15)", "Quincena 2 (16-31)"],
                        key="nom_periodo"
                    )
                    sueldo_base = st.number_input(
                        "Sueldo Base ($)",
                        min_value=0.0,
                        step=100.0,
                        key="nom_sueldo"
                    )
                    bono = st.number_input(
                        "Bono ($)",
                        min_value=0.0,
                        step=100.0,
                        value=0.0,
                        key="nom_bono"
                    )

                motivo_bono = st.text_input(
                    "Motivo del Bono (opcional)",
                    placeholder="Ej: Cumplimiento de metas, horas extra, etc.",
                    key="nom_motivo"
                )

                # Preview del total antes de guardar
                total_pagar = sueldo_base + bono
                st.info(f"💵 Total a pagar: **${total_pagar:,.2f}**")

                guardar_nom = st.form_submit_button(
                    "💾 Registrar Pago",
                    use_container_width=True
                )

                if guardar_nom:
                    if sueldo_base <= 0:
                        st.warning("⚠️ El sueldo base debe ser mayor a cero.")
                    else:
                        # Leer hoja Nomina (nueva hoja en Sheets)
                        df_nomina_actual = consultar_datos("Nomina")

                        nuevo_pago = pd.DataFrame([{
                            "Fecha":        str(fecha_nom),
                            "Obra":         normalizar_texto(obra_nom),
                            "Empleado":     empleado_nom,
                            "Periodo":      periodo_nom,
                            "Sueldo_Base":  sueldo_base,
                            "Bono":         bono,
                            "Motivo_Bono":  motivo_bono.strip() if motivo_bono else "",
                            "Total_Pago":   total_pagar,
                            "Registrado_Por": st.session_state.get("usuario_actual", "Admin")
                        }])

                        # Compatibilidad: si la hoja Nomina no existe aún,
                        # consultar_datos retorna DataFrame vacío y
                        # el concat crea la estructura correcta
                        conn.update(
                            worksheet="Nomina",
                            data=pd.concat(
                                [df_nomina_actual, nuevo_pago],
                                ignore_index=True
                            )
                        )
                        st.success(
                            f"✅ Pago de **{empleado_nom}** registrado: "
                            f"**${total_pagar:,.2f}** ({periodo_nom})"
                        )
                        st.rerun()

        # ── TAB 2: Resumen por quincena ───────────────────────────────────
        with tab_resumen:
            df_nomina = consultar_datos("Nomina")

            if df_nomina.empty:
                st.info("📋 Aún no hay pagos registrados. "
                        "Usa la pestaña 'Registrar Nómina' para comenzar.")
            else:
                # Filtro por obra
                if obra_sel_global != "Todas las Obras":
                    df_nom_filtro = df_nomina[
                        df_nomina['Obra'].apply(normalizar_texto)
                        == normalizar_texto(obra_sel_global)
                    ].copy()
                else:
                    df_nom_filtro = df_nomina.copy()

                if df_nom_filtro.empty:
                    st.info("📋 No hay pagos registrados para esta obra.")
                else:
                    # Conversión segura de montos
                    for col_num in ["Sueldo_Base", "Bono", "Total_Pago"]:
                        if col_num in df_nom_filtro.columns:
                            df_nom_filtro[col_num] = pd.to_numeric(
                                df_nom_filtro[col_num], errors='coerce'
                            ).fillna(0)

                    # ── Métricas globales ─────────────────────────────────
                    total_nomina   = df_nom_filtro['Total_Pago'].sum()
                    total_bonos    = df_nom_filtro['Bono'].sum()
                    total_base     = df_nom_filtro['Sueldo_Base'].sum()

                    m1, m2, m3 = st.columns(3)
                    m1.metric("💵 Total Nómina Pagada",  f"${total_nomina:,.2f}")
                    m2.metric("📦 Total Sueldos Base",   f"${total_base:,.2f}")
                    m3.metric("🎯 Total Bonos Pagados",  f"${total_bonos:,.2f}")

                    st.divider()

                    # ── Resumen por empleado y periodo ────────────────────
                    st.markdown("**Detalle por Empleado y Periodo**")

                    resumen_nom = (
                        df_nom_filtro
                        .groupby(["Empleado", "Periodo"])
                        .agg(
                            Sueldo_Base=("Sueldo_Base", "sum"),
                            Bonos=("Bono", "sum"),
                            Total=("Total_Pago", "sum"),
                            Pagos=("Total_Pago", "count")
                        )
                        .reset_index()
                    )

                    resumen_nom["Sueldo_Base"] = resumen_nom["Sueldo_Base"].apply(
                        lambda x: f"${x:,.2f}"
                    )
                    resumen_nom["Bonos"] = resumen_nom["Bonos"].apply(
                        lambda x: f"${x:,.2f}"
                    )
                    resumen_nom["Total"] = resumen_nom["Total"].apply(
                        lambda x: f"${x:,.2f}"
                    )

                    st.dataframe(
                        resumen_nom,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.divider()

                    # ── Detalle completo con motivo de bono ───────────────
                    with st.expander("📄 Ver todos los registros de nómina"):
                        cols_mostrar = [
                            c for c in [
                                "Fecha", "Empleado", "Periodo",
                                "Sueldo_Base", "Bono", "Motivo_Bono",
                                "Total_Pago", "Registrado_Por"
                            ] if c in df_nom_filtro.columns
                        ]
                        st.dataframe(
                            df_nom_filtro[cols_mostrar],
                            use_container_width=True,
                            hide_index=True
                        )

                    # ── Gráfico total por empleado ────────────────────────
                    df_graf_nom = (
                        df_nom_filtro
                        .groupby("Empleado")["Total_Pago"]
                        .sum()
                        .reset_index()
                    )

                    st.plotly_chart(
                        px.bar(
                            df_graf_nom,
                            x="Empleado",
                            y="Total_Pago",
                            title="Total Pagado por Empleado",
                            color="Empleado",
                            labels={"Total_Pago": "Total ($)"}
                        ),
                        use_container_width=True
                    )

    elif menu == "📂 Obra y Documentos":
        st.header("📂 Expediente Digital")
        tab_p, tab_l = st.tabs(["📄 Presupuestos OPUS", "🏗️ Planos"])
        
        with tab_p:
            up = st.file_uploader("Subir Excel OPUS", type=["xlsx"])
            if up:
                try:
                    df_new = pd.read_excel(up)
                    if st.button("🚀 Vincular"):
                        obra_n = normalizar_texto(obra_sel_global)
                        monto_p = pd.to_numeric(df_new.iloc[0, 1], errors='coerce')
                        nuevo_p = pd.DataFrame([{"Obra": obra_n, "Monto_Presupuestado": monto_p, "Fecha_Carga": datetime.now().strftime("%d/%m/%Y")}])
                        df_ex = consultar_datos("Presupuestos_Opus")
                        # Eliminamos entradas previas de la misma obra para evitar duplicidad de presupuesto
                        df_ex = df_ex[df_ex['Obra'].apply(normalizar_texto) != obra_n]
                        conn.update(worksheet="Presupuestos_Opus", data=pd.concat([df_ex, nuevo_p], ignore_index=True))
                        st.success("✅ Presupuesto actualizado")
                except:
                    st.error("❌ Formato de Excel no reconocido.")

    elif menu == "⚙️ Configuración":
        st.header("⚙️ Gestión de Usuarios")
        with st.form("new_user"):
            u, p, r = st.text_input("Usuario"), st.text_input("Password"), st.selectbox("Rol", ["admin", "arquitecto", "campo"])
            if st.form_submit_button("🔨 Crear"):
                df_u = consultar_datos("Usuarios")
                nuevo_u = pd.DataFrame([{"USUARIO": u.upper(), "PASSWORD": p, "ROL": r, "NOMBRE": u}])
                conn.update(worksheet="Usuarios", data=pd.concat([df_u, nuevo_u], ignore_index=True))
                st.success(f"✅ Usuario {u} creado.")

                    