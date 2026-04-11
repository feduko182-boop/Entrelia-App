import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(
    page_title="ENTRELIA v2.0", 
    page_icon="https://i.ibb.co/LzNf2qD/entrelia-logo.png", 
    layout="wide"
)
# --- MOSTRAR LOGO ---
col_izq, col_centro, col_der = st.columns([1, 2, 1])
with col_centro:
    st.image("https://i.ibb.co/LzNf2qD/entrelia-logo.png", use_container_width=True)

st.markdown("---")
def crear_conexion():
    return sqlite3.connect(DB_NAME)

def consultar(sql):
    conn = crear_conexion()
    try:
        df = pd.read_sql(sql, conn)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def inicializar_db():
    conn = crear_conexion()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS obras (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, ubicacion TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS plan_cuentas (id INTEGER PRIMARY KEY AUTOINCREMENT, rubro TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, obra_id INTEGER, 
                  cuenta_id INTEGER, proveedor TEXT, detalle TEXT, monto REAL, 
                  unidad TEXT, tipo_pago TEXT)''')
    conn.commit()
    conn.close()

inicializar_db()

# --- 2. INTERFAZ LATERAL ---
st.sidebar.title("🏗️ ENTRELIA")
menu = st.sidebar.radio("Ir a:", ["📊 Dashboard", "📝 Registrar Gasto", "🏗️ Obras", "⚙️ Configuración"])

# --- 3. SECCIONES ---

if menu == "📊 Dashboard":
    st.header("📊 Resumen de Inversión")
    query = """
        SELECT m.fecha, o.nombre as Obra, p.rubro as Categoria, m.monto, m.proveedor, m.detalle
        FROM movimientos m
        JOIN obras o ON m.obra_id = o.id
        JOIN plan_cuentas p ON m.cuenta_id = p.id
    """
    df_master = consultar(query)
    if not df_master.empty:
        c1, c2 = st.columns(2)
        c1.metric("Gasto Total", f"${df_master['monto'].sum():,.2f}")
        c2.metric("Obras Activas", df_master['Obra'].nunique())
        st.plotly_chart(px.pie(df_master, values='monto', names='Obra', title="Inversión por Obra"))
        st.dataframe(df_master, use_container_width=True)
    else:
        st.info("Aún no hay movimientos registrados.")

elif menu == "🏗️ Obras":
    st.header("🏗️ Gestión de Proyectos")
    with st.form("nueva_obra"):
        n = st.text_input("Nombre de la Obra")
        u = st.text_input("Ubicación")
        if st.form_submit_button("Crear Obra"):
            if n:
                conn = crear_conexion()
                conn.execute("INSERT INTO obras (nombre, ubicacion) VALUES (?,?)", (n, u))
                conn.commit()
                conn.close()
                st.success(f"Obra {n} creada!")
                st.rerun()
    st.subheader("Obras Actuales")
    st.dataframe(consultar("SELECT * FROM obras"), use_container_width=True)

elif menu == "📝 Registrar Gasto":
    st.header("📝 Nuevo Movimiento de Caja")
    df_o = consultar("SELECT * FROM obras")
    df_p = consultar("SELECT * FROM plan_cuentas")
    
    if df_o.empty or df_p.empty:
        st.warning("⚠️ Cargá una Obra y Rubros primero.")
    else:
        with st.form("form_gasto", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                f = st.date_input("Fecha", datetime.now())
                o = st.selectbox("Obra", df_o['nombre'].tolist())
                p = st.text_input("Proveedor")
                m = st.number_input("Monto ($)", min_value=0.0)
            with col2:
                r = st.selectbox("Rubro", df_p['rubro'].tolist())
                unid = st.selectbox("Unidad", ["Unidad", "MTS", "KG", "LTS", "VIAJE"])
                pago = st.selectbox("Método", ["Efectivo", "Transferencia"])
                d = st.text_area("Detalle")
            
            if st.form_submit_button("🔨 Guardar Gasto"):
                id_o = int(df_o[df_o['nombre'] == o]['id'].iloc[0])
                id_p = int(df_p[df_p['rubro'] == r]['id'].iloc[0])
                conn = crear_conexion()
                conn.execute("""INSERT INTO movimientos (fecha, obra_id, cuenta_id, proveedor, detalle, monto, unidad, tipo_pago) 
                             VALUES (?,?,?,?,?,?,?,?)""",
                             (f.strftime("%Y-%m-%d"), id_o, id_p, p, d, m, unid, pago))
                conn.commit()
                conn.close()
                st.success("¡Gasto guardado!")

elif menu == "⚙️ Configuración":
    st.header("⚙️ Cargar Rubros (Excel)")
    arch = st.file_uploader("Subí el Excel de Papá", type=["xlsx"])
    if arch:
        columna_encontrada = None
        df_final = None
        palabras_clave = ['rubro', 'cuenta', 'concepto', 'descripcion', 'item', 'nombre']

        # Intentamos buscar los encabezados en las primeras 10 filas
        for i in range(11):
            try:
                df_temp = pd.read_excel(arch, header=i)
                # Buscamos si alguna columna coincide con nuestras palabras clave
                match = [c for c in df_temp.columns if any(p in str(c).lower() for p in palabras_clave)]
                if match:
                    columna_encontrada = match[0]
                    df_final = df_temp
                    break
            except:
                continue

        if columna_encontrada:
            st.success(f"✅ ¡Por fin! Encontré la columna: '{columna_encontrada}'")
            if st.button("🚀 Sincronizar"):
                # Limpiamos los datos: quitamos vacíos y duplicados
                df_c = df_final[[columna_encontrada]].dropna().drop_duplicates()
                df_c.columns = ['rubro']
                
                # Guardamos en la base de datos
                conn = crear_conexion()
                conn.execute("DELETE FROM plan_cuentas")
                df_c.to_sql('plan_cuentas', conn, if_exists='append', index=False)
                conn.close()
                st.success("¡Rubros cargados y listos para usar!")
                st.rerun()
        else:
            # Si después de 10 filas no hay nada, te muestro qué vio en la última para ayudar
            st.error("No encontré la columna de Rubros en ninguna de las primeras 10 filas.")
            df_error = pd.read_excel(arch, header=0)
            st.write("Columnas detectadas al principio:", list(df_error.columns))
            st.info("Sugerencia: Abrí el Excel y fijate que la columna tenga un nombre claro como 'Rubro'.")