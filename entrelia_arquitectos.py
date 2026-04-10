import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ENTRELIA - Control de Obra", layout="centered")

# --- ESTILO ---
st.markdown("""
    <style>
    .stHeader { background-color: #1E90FF; padding: 10px; border-radius: 10px; color: white; text-align: center; }
    .card { background-color: #161b22; padding: 20px; border-radius: 15px; border-left: 5px solid #1E90FF; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- TÍTULO ---
st.markdown("<div class='stHeader'><h1>ENTRELIA 🏗️</h1><p>Gestión de Rentabilidad para Arquitectos</p></div>", unsafe_allow_html=True)
st.write("")

# --- 1. PERFIL DEL PROYECTO ---
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        obra = st.text_input("Nombre de la Obra", value="Residencial Playa")
    with col2:
        presupuesto_total = st.number_input("Presupuesto Total (MXN)", value=500000, step=1000)
    st.markdown('</div>', unsafe_allow_html=True)

# --- 2. BASE DE DATOS DE MATERIALES (SIMULADA) ---
# Aquí es donde después conectaremos con las ferreterías de Quintana Roo
materiales_db = {
    "Cemento Gris (Saco 50kg)": 240.0,
    "Varilla 3/8 (Tramo)": 185.0,
    "Arena (m3)": 450.0,
    "Grava (m3)": 520.0,
    "Pintura Blanca (Cubeta)": 2100.0
}

# --- 3. REGISTRO DE COMPRAS ---
st.subheader("📝 Registro de Insumos")

if 'gastos' not in st.session_state:
    st.session_state.gastos = []

with st.form("registro_gasto"):
    col_mat, col_cant = st.columns([2, 1])
    with col_mat:
        mat_sel = st.selectbox("Material / Insumo", list(materiales_db.keys()))
    with col_cant:
        cantidad = st.number_input("Cantidad", min_value=1, value=1)
    
    boton_agregar = st.form_submit_button("Añadir a la Obra")
    
    if boton_agregar:
        precio_u = materiales_db[mat_sel]
        total_item = precio_u * cantidad
        st.session_state.gastos.append({"Material": mat_sel, "Cant": cantidad, "Total": total_item})

# --- 4. DASHBOARD DE RENTABILIDAD (EL CORAZÓN DEL PLAN) ---
st.divider()
total_gastado = sum(item['Total'] for item in st.session_state.gastos)
diferencia = presupuesto_total - total_gastado
porcentaje_uso = (total_gastado / presupuesto_total) * 100

st.subheader("📊 Estado de Rentabilidad")
c1, c2, c3 = st.columns(3)
c1.metric("Gastado", f"${total_gastado:,.2f}")
c2.metric("Disponible", f"${diferencia:,.2f}")
c3.metric("Uso del Presupuesto", f"{porcentaje_uso:.1f}%")

if porcentaje_uso > 90:
    st.warning("⚠️ ¡Cuidado! Estás llegando al límite del presupuesto.")
elif total_gastado > 0:
    st.success("✅ La obra mantiene un margen de utilidad saludable.")

# --- 5. DETALLE DE GASTOS ---
if st.session_state.gastos:
    with st.expander("Ver desglose de gastos"):
        st.table(st.session_state.gastos)
        if st.button("Limpiar Registro"):
            st.session_state.gastos = []
            st.rerun()

st.info("💡 Próxima función: Conexión con ferreterías locales para cotización en tiempo real.")