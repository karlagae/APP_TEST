import streamlit as st
import pandas as pd
from datetime import datetime, date
from sqlalchemy import create_engine, text
from io import BytesIO

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Inteligencia en Licitaciones | Seguimiento",
    layout="wide",
)

DB_PATH = "seguimiento.db"
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)

# =========================
# HELPERS
# =========================
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS apoyos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_registro TEXT,
            institucion TEXT,
            unidad TEXT,
            contacto TEXT,
            email TEXT,
            telefono TEXT,
            tipo_apoyo TEXT,
            descripcion TEXT,
            responsable TEXT,
            estatus TEXT,
            prioridad TEXT,
            fecha_compromiso TEXT,
            fecha_cierre TEXT,
            notas TEXT
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS licitaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT,
            titulo TEXT,
            institucion TEXT,
            unidad TEXT,
            estado TEXT,
            integrador TEXT,
            monto_estimado REAL,
            fecha_publicacion TEXT,
            junta_aclaraciones TEXT,
            apertura TEXT,
            fallo TEXT,
            firma_contrato TEXT,
            pidio_apoyo INTEGER,
            apoyo_id INTEGER,
            carta_enviada INTEGER,
            razon_social TEXT,
            estatus TEXT,
            responsable TEXT,
            link TEXT,
            notas TEXT
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS powerbi_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            embed_url TEXT
        );
        """))

        # Registro inicial settings
        conn.execute(text("""
        INSERT OR IGNORE INTO powerbi_settings (id, embed_url)
        VALUES (1, '');
        """))

def df_to_excel_bytes(df: pd.DataFrame, sheet_name="data") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def sql_df(query: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        res = conn.execute(text(query), params or {})
        rows = res.fetchall()
        cols = res.keys()
    return pd.DataFrame(rows, columns=cols)

def bool_to_int(x: bool) -> int:
    return 1 if x else 0

def safe_date_str(d):
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y-%m-%d")
    return str(d)

def badge(estatus: str):
    if not estatus:
        return "—"
    e = estatus.lower().strip()
    if "cerr" in e or "final" in e or "hecho" in e:
        return "✅ " + estatus
    if "pend" in e or "abier" in e or "en pro" in e:
        return "🟡 " + estatus
    if "bloq" in e or "rech" in e or "cancel" in e:
        return "🔴 " + estatus
    return "🔵 " + estatus




# =========================
# HELPERS PARA RESUMEN / TABLERO
# =========================
HOY = date.today()

def dias_a(fecha):
    if fecha is None or str(fecha).strip() == "":
        return None
    try:
        return (datetime.fromisoformat(str(fecha)).date() - HOY).days
    except:
        try:
            return (pd.to_datetime(fecha).date() - HOY).days
        except:
            return None

def semaforo(d):
    if d is None:
        return "—"
    if d < 0:
        return f"🔴 Vencido ({abs(d)} días)"
    if d == 0:
        return "🟠 Hoy"
    if d <= 7:
        return f"🟡 En {d} días"
    return f"🟢 En {d} días"

# =========================
# HELPERS PARA TIMELINE (MINI-GANTT)
# =========================
def clamp(x, a, b):
    return max(a, min(b, x))

def pos_pct(dias, ventana):
    """Convierte días (0..ventana) a porcentaje (0..100)."""
    if dias is None:
        return None
    return 100 * (clamp(dias, 0, ventana) / ventana)

def timeline_html(dias_ja, dias_ap, dias_fa, ventana=60):
    """Barra horizontal con marcadores JA/AP/FA."""
    marks = [
        ("JA", dias_ja, "#2E86DE"),
        ("AP", dias_ap, "#F39C12"),
        ("FA", dias_fa, "#27AE60"),
    ]

    dots = []
    for label, d, color in marks:
        if d is None:
            continue
        p = pos_pct(d, ventana)
        dots.append(f"""
        <div style="position:absolute; left:calc({p}% - 7px); top:-6px;
            width:14px; height:14px; border-radius:50%;
            background:{color}; border:2px solid white;
            box-shadow:0 1px 3px rgba(0,0,0,.25);" title="{label}: {d} días"></div>
        <div style="position:absolute; left:calc({p}% - 12px); top:14px;
            font-size:11px; color:#111; font-weight:600;">{label}</div>
        """)

    base = f"""
    <div style="position:relative; width:100%; height:34px; margin-top:6px;">
      <div style="position:absolute; left:0; top:6px; right:0; height:8px;
        background:#E9EEF5; border-radius:999px;"></div>
      <div style="position:absolute; left:0; top:3px; width:2px; height:14px;
        background:#111; opacity:.55;"></div>
      <div style="position:absolute; left:0; top:-14px; font-size:11px; color:#111; opacity:.7;">Hoy</div>
      {''.join(dots)}
    </div>
    """
    return base


# =========================
# DB INIT
# =========================
init_db()

# =========================
# UI: SIDEBAR NAV
# =========================
st.sidebar.title("📌 Menú")
page = st.sidebar.radio(
    "Ir a:",
    ["Excel (Base oficial)", "Licitaciones en curso", "Seguimiento de Apoyos", "Power BI", "Calendario"],
    index=0
)


st.sidebar.markdown("---")
st.sidebar.caption("Base local: SQLite (seguimiento.db)")


# =========================
# PAGE 0: EXCEL (BASE OFICIAL)
# =========================
if page == "Excel (Base oficial)":
    st.title("📘 Excel (Base oficial)")
    st.caption("Aquí cargas el Excel maestro. La app lo usa como base para licitaciones y seguimiento.")

    excel_file = st.file_uploader("Sube tu Excel maestro", type=["xlsx"], key="excel_master")

    c1, c2, c3 = st.columns(3)

    with c1:
        if excel_file and st.button("✅ Importar / Actualizar en la base", use_container_width=True):
           df_excel = pd.read_excel(excel_file)
           ins, upd = upsert_licitaciones_from_excel(df_excel)
           st.success(f"Importación lista. Insertadas: {ins} | Actualizadas: {upd}")
           st.rerun()

    with c2:
       ver_excel = excel_file and st.button("👁️ Ver Excel aquí", use_container_width=True)



    with c3:
        df_db = sql_df("SELECT * FROM licitaciones ORDER BY id DESC;")
        st.download_button(
            "⬇️ Descargar Excel actualizado",
            data=df_to_excel_bytes(df_db, "licitaciones"),
            file_name="SEGUIMIENTO_LIC_actualizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

if ver_excel:
    df_excel = pd.read_excel(excel_file)

    st.markdown("---")
    st.subheader("📊 Visor del Excel maestro")

    visor = st.container(border=True)
    visor.dataframe(
        df_excel,
        use_container_width=True,
        height=780
    )




# =========================
# PAGE 1: APOYOS
# =========================
elif page == "Seguimiento de Apoyos":

    st.title("🤝 Seguimiento de Apoyos")
    st.caption("Registro y seguimiento de a quiénes se les dio apoyo, estatus, responsable y fechas clave.")

    colA, colB = st.columns([1.05, 1.6], gap="large")

    with colA:
        st.subheader("➕ Nuevo / Editar apoyo")

        # Selector de edición
        apoyos_df = sql_df("SELECT * FROM apoyos ORDER BY id DESC;")
        edit_id = st.selectbox(
            "Editar apoyo existente (opcional)",
            options=[None] + (apoyos_df["id"].tolist() if not apoyos_df.empty else []),
            format_func=lambda x: "— Nuevo —" if x is None else f"ID {x}"
        )

        current = {}
        if edit_id is not None and not apoyos_df.empty:
            current = apoyos_df[apoyos_df["id"] == edit_id].iloc[0].to_dict()

        def g(key, default=""):
            return current.get(key, default) if current else default

        fecha_registro = st.date_input("Fecha de registro", value=date.fromisoformat(g("fecha_registro", date.today().isoformat())))
        institucion = st.text_input("Institución", value=g("institucion"))
        unidad = st.text_input("Unidad / Hospital", value=g("unidad"))
        contacto = st.text_input("Contacto", value=g("contacto"))
        email = st.text_input("Email", value=g("email"))
        telefono = st.text_input("Teléfono", value=g("telefono"))

        tipo_apoyo = st.selectbox(
            "Tipo de apoyo",
            ["", "Técnico", "Comercial", "Administrativo", "Documentación", "Otro"],
            index=["", "Técnico", "Comercial", "Administrativo", "Documentación", "Otro"].index(g("tipo_apoyo", "")) if g("tipo_apoyo", "") in ["", "Técnico", "Comercial", "Administrativo", "Documentación", "Otro"] else 0
        )

        descripcion = st.text_area("Descripción del apoyo", value=g("descripcion"), height=100)

        responsable = st.text_input("Responsable", value=g("responsable"))

        estatus = st.selectbox(
            "Estatus",
            ["Pendiente", "En proceso", "Cerrado", "Bloqueado"],
            index=["Pendiente", "En proceso", "Cerrado", "Bloqueado"].index(g("estatus", "Pendiente")) if g("estatus", "Pendiente") in ["Pendiente", "En proceso", "Cerrado", "Bloqueado"] else 0
        )

        prioridad = st.selectbox(
            "Prioridad",
            ["Baja", "Media", "Alta", "Crítica"],
            index=["Baja", "Media", "Alta", "Crítica"].index(g("prioridad", "Media")) if g("prioridad", "Media") in ["Baja", "Media", "Alta", "Crítica"] else 1
        )

        fecha_compromiso = st.date_input("Fecha compromiso (opcional)", value=(date.fromisoformat(g("fecha_compromiso")) if g("fecha_compromiso") else date.today()))
        fecha_cierre = st.date_input("Fecha cierre (opcional)", value=(date.fromisoformat(g("fecha_cierre")) if g("fecha_cierre") else date.today()))
        notas = st.text_area("Notas", value=g("notas"), height=90)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Guardar", use_container_width=True):
                payload = {
                    "fecha_registro": safe_date_str(fecha_registro),
                    "institucion": institucion.strip(),
                    "unidad": unidad.strip(),
                    "contacto": contacto.strip(),
                    "email": email.strip(),
                    "telefono": telefono.strip(),
                    "tipo_apoyo": tipo_apoyo,
                    "descripcion": descripcion.strip(),
                    "responsable": responsable.strip(),
                    "estatus": estatus,
                    "prioridad": prioridad,
                    "fecha_compromiso": safe_date_str(fecha_compromiso) if fecha_compromiso else "",
                    "fecha_cierre": safe_date_str(fecha_cierre) if fecha_cierre else "",
                    "notas": notas.strip(),
                }
                with engine.begin() as conn:
                    if edit_id is None:
                        conn.execute(text("""
                            INSERT INTO apoyos (
                                fecha_registro, institucion, unidad, contacto, email, telefono,
                                tipo_apoyo, descripcion, responsable, estatus, prioridad,
                                fecha_compromiso, fecha_cierre, notas
                            ) VALUES (
                                :fecha_registro, :institucion, :unidad, :contacto, :email, :telefono,
                                :tipo_apoyo, :descripcion, :responsable, :estatus, :prioridad,
                                :fecha_compromiso, :fecha_cierre, :notas
                            );
                        """), payload)
                        st.success("Apoyo guardado.")
                    else:
                        payload["id"] = int(edit_id)
                        conn.execute(text("""
                            UPDATE apoyos SET
                                fecha_registro=:fecha_registro,
                                institucion=:institucion,
                                unidad=:unidad,
                                contacto=:contacto,
                                email=:email,
                                telefono=:telefono,
                                tipo_apoyo=:tipo_apoyo,
                                descripcion=:descripcion,
                                responsable=:responsable,
                                estatus=:estatus,
                                prioridad=:prioridad,
                                fecha_compromiso=:fecha_compromiso,
                                fecha_cierre=:fecha_cierre,
                                notas=:notas
                            WHERE id=:id;
                        """), payload)
                        st.success("Apoyo actualizado.")
                st.rerun()

        with c2:
            if st.button("🧹 Limpiar (nuevo)", use_container_width=True):
                st.rerun()

        with c3:
            if edit_id is not None:
                if st.button("🗑️ Eliminar", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM apoyos WHERE id=:id;"), {"id": int(edit_id)})
                    st.warning("Apoyo eliminado.")
                    st.rerun()

    with colB:
        st.subheader("📋 Lista de apoyos")

        # Filtros
        f1, f2, f3, f4 = st.columns([1,1,1,1])
        with f1:
            q = st.text_input("Buscar (institución/unidad/contacto/responsable)", "")
        with f2:
            est = st.selectbox("Estatus", ["(Todos)", "Pendiente", "En proceso", "Cerrado", "Bloqueado"], index=0)
        with f3:
            pr = st.selectbox("Prioridad", ["(Todas)", "Baja", "Media", "Alta", "Crítica"], index=0)
        with f4:
            tipo = st.selectbox("Tipo", ["(Todos)", "Técnico", "Comercial", "Administrativo", "Documentación", "Otro"], index=0)

        df = sql_df("SELECT * FROM apoyos ORDER BY id DESC;")
        if not df.empty:
            # filtros
            if q.strip():
                s = q.lower().strip()
                mask = (
                    df["institucion"].fillna("").str.lower().str.contains(s) |
                    df["unidad"].fillna("").str.lower().str.contains(s) |
                    df["contacto"].fillna("").str.lower().str.contains(s) |
                    df["responsable"].fillna("").str.lower().str.contains(s)
                )
                df = df[mask]
            if est != "(Todos)":
                df = df[df["estatus"] == est]
            if pr != "(Todas)":
                df = df[df["prioridad"] == pr]
            if tipo != "(Todos)":
                df = df[df["tipo_apoyo"] == tipo]

            # Mini resumen
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", len(df))
            c2.metric("Pendientes", int((df["estatus"] == "Pendiente").sum()))
            c3.metric("En proceso", int((df["estatus"] == "En proceso").sum()))
            c4.metric("Cerrados", int((df["estatus"] == "Cerrado").sum()))

            show = df.copy()
            show["estatus"] = show["estatus"].apply(badge)
            st.dataframe(show, use_container_width=True, height=520)

            # Export
            exp1, exp2 = st.columns(2)
            with exp1:
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=df_to_excel_bytes(df, "apoyos"),
                    file_name="apoyos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp2:
                st.download_button(
                    "⬇️ Descargar CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="apoyos.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("Aún no hay apoyos registrados.")

# =========================
# PAGE 2: LICITACIONES
# =========================
elif page == "Licitaciones":
    st.title("📄 Licitaciones")
    st.caption("Registro completo de licitaciones + checks de apoyo, carta enviada, razón social y fechas.")

    # ⬇️ AQUÍ PEGAS EL BLOQUE DEL EXCEL ⬇️
    st.subheader("📥 Excel oficial (subir / consultar / descargar)")

    excel_file = st.file_uploader("Sube tu Excel de seguimiento", type=["xlsx"], key="excel_licit")

    colx1, colx2, colx3 = st.columns(3)

    with colx1:
        if excel_file and st.button("✅ Importar / Actualizar desde Excel", use_container_width=True):
            df_excel = pd.read_excel(excel_file)
            ins, upd = upsert_licitaciones_from_excel(df_excel)
            st.success(f"Importación lista. Insertadas: {ins} | Actualizadas: {upd}")
            st.rerun()

    with colx2:
        if excel_file and st.button("👁️ Ver Excel aquí (vista previa)", use_container_width=True):
            df_excel = pd.read_excel(excel_file)
            st.dataframe(df_excel, use_container_width=True, height=420)

    with colx3:
        if st.button("⬇️ Descargar Excel actualizado (desde la base)", use_container_width=True):
            df_db = sql_df("SELECT * FROM licitaciones ORDER BY id DESC;")
            st.download_button(
                "Descargar ahora",
                data=df_to_excel_bytes(df_db, "licitaciones"),
                file_name="SEGUIMIENTO_LIC_actualizado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # ⬆️ AQUÍ TERMINA EL BLOQUE DEL EXCEL ⬆️

    colA, colB = st.columns([1.05, 1.6], gap="large")

    with colA:
        st.subheader("➕ Nueva / Editar licitación")

        lic_df = sql_df("SELECT * FROM licitaciones ORDER BY id DESC;")
        edit_id = st.selectbox(
            "Editar licitación existente (opcional)",
            options=[None] + (lic_df["id"].tolist() if not lic_df.empty else []),
            format_func=lambda x: "— Nueva —" if x is None else f"ID {x}"
        )

        current = {}
        if edit_id is not None and not lic_df.empty:
            current = lic_df[lic_df["id"] == edit_id].iloc[0].to_dict()

        def g(key, default=""):
            return current.get(key, default) if current else default

        clave = st.text_input("Clave / Expediente", value=g("clave"))
        titulo = st.text_input("Título", value=g("titulo"))
        institucion = st.text_input("Institución", value=g("institucion"))
        unidad = st.text_input("Unidad / Hospital", value=g("unidad"))
        estado = st.text_input("Estado", value=g("estado"))
        integrador = st.text_input("Integrador (si aplica)", value=g("integrador"))
        monto = st.number_input("Monto estimado (opcional)", min_value=0.0, value=float(g("monto_estimado", 0.0) or 0.0), step=1000.0)

        f_pub = st.date_input("Fecha publicación (opcional)", value=(date.fromisoformat(g("fecha_publicacion")) if g("fecha_publicacion") else date.today()))
        ja = st.date_input("Junta de aclaraciones (opcional)", value=(date.fromisoformat(g("junta_aclaraciones")) if g("junta_aclaraciones") else date.today()))
        apertura = st.date_input("Apertura (opcional)", value=(date.fromisoformat(g("apertura")) if g("apertura") else date.today()))
        fallo = st.date_input("Fallo (opcional)", value=(date.fromisoformat(g("fallo")) if g("fallo") else date.today()))
        firma = st.date_input("Firma contrato (opcional)", value=(date.fromisoformat(g("firma_contrato")) if g("firma_contrato") else date.today()))

        st.markdown("### ✅ Checks y control")
        pidio_apoyo = st.checkbox("Pidió apoyo", value=bool(g("pidio_apoyo", 0)))
        carta_enviada = st.checkbox("Carta enviada", value=bool(g("carta_enviada", 0)))
        razon_social = st.text_input("Razón social (si aplica)", value=g("razon_social"))
        estatus = st.selectbox(
            "Estatus",
            ["Abierta", "En análisis", "En gestión", "Cerrada", "Cancelada"],
            index=["Abierta", "En análisis", "En gestión", "Cerrada", "Cancelada"].index(g("estatus", "Abierta")) if g("estatus", "Abierta") in ["Abierta", "En análisis", "En gestión", "Cerrada", "Cancelada"] else 0
        )
        responsable = st.text_input("Responsable", value=g("responsable"))
        link = st.text_input("Link (ComprasMX/drive/etc.)", value=g("link"))
        notas = st.text_area("Notas", value=g("notas"), height=110)

        # Vincular apoyo (si pidio_apoyo)
        apoyo_id = None
        if pidio_apoyo:
            apoyos_df = sql_df("SELECT id, institucion, unidad, contacto, estatus FROM apoyos ORDER BY id DESC;")
            if not apoyos_df.empty:
                apoyos_df["label"] = apoyos_df.apply(lambda r: f'ID {r["id"]} | {r["institucion"]} | {r["unidad"]} | {r["contacto"]} | {r["estatus"]}', axis=1)
                options = [None] + apoyos_df["id"].tolist()
                apoyo_id = st.selectbox(
                    "Vincular a un apoyo existente (opcional)",
                    options=options,
                    index=0 if g("apoyo_id") in [None, "", 0] else (options.index(int(g("apoyo_id")) ) if int(g("apoyo_id")) in options else 0),
                    format_func=lambda x: "— Sin vínculo —" if x is None else apoyos_df.loc[apoyos_df["id"]==x, "label"].values[0]
                )
            else:
                st.info("No hay apoyos registrados aún (puedes crear uno en la pestaña de Apoyos).")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Guardar", use_container_width=True):
                payload = {
                    "clave": clave.strip(),
                    "titulo": titulo.strip(),
                    "institucion": institucion.strip(),
                    "unidad": unidad.strip(),
                    "estado": estado.strip(),
                    "integrador": integrador.strip(),
                    "monto_estimado": float(monto or 0.0),
                    "fecha_publicacion": safe_date_str(f_pub) if f_pub else "",
                    "junta_aclaraciones": safe_date_str(ja) if ja else "",
                    "apertura": safe_date_str(apertura) if apertura else "",
                    "fallo": safe_date_str(fallo) if fallo else "",
                    "firma_contrato": safe_date_str(firma) if firma else "",
                    "pidio_apoyo": bool_to_int(pidio_apoyo),
                    "apoyo_id": int(apoyo_id) if apoyo_id else None,
                    "carta_enviada": bool_to_int(carta_enviada),
                    "razon_social": razon_social.strip(),
                    "estatus": estatus,
                    "responsable": responsable.strip(),
                    "link": link.strip(),
                    "notas": notas.strip(),
                }
                with engine.begin() as conn:
                    if edit_id is None:
                        conn.execute(text("""
                            INSERT INTO licitaciones (
                                clave, titulo, institucion, unidad, estado, integrador, monto_estimado,
                                fecha_publicacion, junta_aclaraciones, apertura, fallo, firma_contrato,
                                pidio_apoyo, apoyo_id, carta_enviada, razon_social, estatus, responsable, link, notas
                            ) VALUES (
                                :clave, :titulo, :institucion, :unidad, :estado, :integrador, :monto_estimado,
                                :fecha_publicacion, :junta_aclaraciones, :apertura, :fallo, :firma_contrato,
                                :pidio_apoyo, :apoyo_id, :carta_enviada, :razon_social, :estatus, :responsable, :link, :notas
                            );
                        """), payload)
                        st.success("Licitación guardada.")
                    else:
                        payload["id"] = int(edit_id)
                        conn.execute(text("""
                            UPDATE licitaciones SET
                                clave=:clave,
                                titulo=:titulo,
                                institucion=:institucion,
                                unidad=:unidad,
                                estado=:estado,
                                integrador=:integrador,
                                monto_estimado=:monto_estimado,
                                fecha_publicacion=:fecha_publicacion,
                                junta_aclaraciones=:junta_aclaraciones,
                                apertura=:apertura,
                                fallo=:fallo,
                                firma_contrato=:firma_contrato,
                                pidio_apoyo=:pidio_apoyo,
                                apoyo_id=:apoyo_id,
                                carta_enviada=:carta_enviada,
                                razon_social=:razon_social,
                                estatus=:estatus,
                                responsable=:responsable,
                                link=:link,
                                notas=:notas
                            WHERE id=:id;
                        """), payload)
                        st.success("Licitación actualizada.")
                st.rerun()

        with c2:
            if st.button("🧹 Limpiar (nueva)", use_container_width=True):
                st.rerun()

        with c3:
            if edit_id is not None:
                if st.button("🗑️ Eliminar", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM licitaciones WHERE id=:id;"), {"id": int(edit_id)})
                    st.warning("Licitación eliminada.")
                    st.rerun()

    with colB:
        st.subheader("📋 Lista de licitaciones")

        f1, f2, f3, f4 = st.columns([1.2,1,1,1])
        with f1:
            q = st.text_input("Buscar (clave/título/institución/unidad/responsable)", "")
        with f2:
            est = st.selectbox("Estatus", ["(Todos)", "Abierta", "En análisis", "En gestión", "Cerrada", "Cancelada"], index=0)
        with f3:
            ap = st.selectbox("Apoyo", ["(Todos)", "Pidió apoyo", "No pidió apoyo"], index=0)
        with f4:
            carta = st.selectbox("Carta", ["(Todas)", "Enviada", "No enviada"], index=0)

        df = sql_df("SELECT * FROM licitaciones ORDER BY id DESC;")
        if not df.empty:
            if q.strip():
                s = q.lower().strip()
                mask = (
                    df["clave"].fillna("").str.lower().str.contains(s) |
                    df["titulo"].fillna("").str.lower().str.contains(s) |
                    df["institucion"].fillna("").str.lower().str.contains(s) |
                    df["unidad"].fillna("").str.lower().str.contains(s) |
                    df["responsable"].fillna("").str.lower().str.contains(s)
                )
                df = df[mask]
            if est != "(Todos)":
                df = df[df["estatus"] == est]
            if ap == "Pidió apoyo":
                df = df[df["pidio_apoyo"] == 1]
            elif ap == "No pidió apoyo":
                df = df[df["pidio_apoyo"] == 0]
            if carta == "Enviada":
                df = df[df["carta_enviada"] == 1]
            elif carta == "No enviada":
                df = df[df["carta_enviada"] == 0]

            # métricas
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", len(df))
            c2.metric("Con apoyo", int((df["pidio_apoyo"] == 1).sum()))
            c3.metric("Carta enviada", int((df["carta_enviada"] == 1).sum()))
            c4.metric("Abiertas", int((df["estatus"] == "Abierta").sum()))

            show = df.copy()
            show["pidio_apoyo"] = show["pidio_apoyo"].apply(lambda x: "✅" if x == 1 else "—")
            show["carta_enviada"] = show["carta_enviada"].apply(lambda x: "📨" if x == 1 else "—")
            show["estatus"] = show["estatus"].apply(badge)

            st.dataframe(show, use_container_width=True, height=520)

            exp1, exp2 = st.columns(2)
            with exp1:
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=df_to_excel_bytes(df, "licitaciones"),
                    file_name="licitaciones.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with exp2:
                st.download_button(
                    "⬇️ Descargar CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="licitaciones.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("Aún no hay licitaciones registradas.")

# =========================
# PAGE 3: RESUMEN (CONTROL OPERATIVO)
# =========================
elif page == "Resumen":
    st.title("🚦 Resumen (control operativo)")
    st.caption("Semáforo + ranking de urgencia y timeline (mini-Gantt) por licitación. Power BI se mantiene como dashboard exclusivo.")

    df = sql_df("""
        SELECT id, clave, titulo, institucion, unidad, responsable, estatus,
               junta_aclaraciones, apertura, fallo, link
        FROM licitaciones
        ORDER BY id DESC;
    """)

    if df.empty:
        st.info("Aún no hay licitaciones registradas.")
    else:
        # Parse fechas
        for c in ["junta_aclaraciones", "apertura", "fallo"]:
            df[c] = pd.to_datetime(df[c], errors="coerce")

        # Controles
        c1, c2, c3, c4 = st.columns([1.1, 1.1, 1.2, 1.6])
        with c1:
            modo = st.selectbox("Mostrar", ["Más urgentes primero", "Todo"], index=0)
        with c2:
            ventana = st.slider("Ventana timeline (días)", 14, 180, 60)
        with c3:
            filtro_estatus = st.selectbox("Estatus", ["(Todos)", "Abierta", "En análisis", "En gestión", "Cerrada", "Cancelada"], index=0)
        with c4:
            filtro_resp = st.text_input("Responsable (contiene)", "")

        # Días a eventos
        df["dias_JA"] = df["junta_aclaraciones"].dt.date.apply(dias_a)
        df["dias_AP"] = df["apertura"].dt.date.apply(dias_a)
        df["dias_FA"] = df["fallo"].dt.date.apply(dias_a)

        def min_no_null(row):
            vals = [row["dias_JA"], row["dias_AP"], row["dias_FA"]]
            vals = [v for v in vals if v is not None]
            return min(vals) if vals else None

        df["dias_min"] = df.apply(min_no_null, axis=1)

        # Filtros
        if filtro_estatus != "(Todos)":
            df = df[df["estatus"] == filtro_estatus]
        if filtro_resp.strip():
            s = filtro_resp.strip().lower()
            df = df[df["responsable"].fillna("").str.lower().str.contains(s)]

        if modo == "Más urgentes primero":
            df = df.sort_values("dias_min", ascending=True, na_position="last")

        # KPIs rápidos
        total = len(df)
        vencidas = int(((df["dias_min"].notna()) & (df["dias_min"] < 0)).sum())
        hoy = int(((df["dias_min"].notna()) & (df["dias_min"] == 0)).sum())
        en7 = int(((df["dias_min"].notna()) & (df["dias_min"] >= 1) & (df["dias_min"] <= 7)).sum())

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total", total)
        k2.metric("🔴 Vencidas", vencidas)
        k3.metric("🟠 Hoy", hoy)
        k4.metric("🟡 En 7 días", en7)

        st.markdown("---")
        st.subheader("🚨 Semáforo de urgencia")

        venc_df = df[(df["dias_min"].notna()) & (df["dias_min"] < 0)].copy().sort_values("dias_min", ascending=True)
        hoy_df  = df[(df["dias_min"].notna()) & (df["dias_min"] == 0)].copy()
        en7_df  = df[(df["dias_min"].notna()) & (df["dias_min"] >= 1) & (df["dias_min"] <= 7)].copy().sort_values("dias_min", ascending=True)

        a, b, c = st.columns(3, gap="large")
        with a:
            st.markdown("### 🔴 Vencido")
            st.caption("Eventos que ya pasaron.")
            st.dataframe(venc_df[["clave","institucion","unidad","responsable","dias_min"]].head(12),
                         use_container_width=True, height=260)
        with b:
            st.markdown("### 🟠 Hoy")
            st.caption("Eventos que caen hoy.")
            st.dataframe(hoy_df[["clave","institucion","unidad","responsable","dias_min"]].head(12),
                         use_container_width=True, height=260)
        with c:
            st.markdown("### 🟡 En 7 días")
            st.caption("Eventos próximos (1 a 7 días).")
            st.dataframe(en7_df[["clave","institucion","unidad","responsable","dias_min"]].head(12),
                         use_container_width=True, height=260)

        st.markdown("---")
        st.subheader("📍 Timeline (mini-Gantt) por licitación")

        # Mostramos top (para no saturar)
        top = df.head(30) if modo == "Más urgentes primero" else df.head(30)

        for _, r in top.iterrows():
            with st.container(border=True):
                left, right = st.columns([1.15, 2.15], gap="large")

                with left:
                    st.write(f"**{r.get('clave','')}** — {badge(r.get('estatus',''))}")
                    st.write(f"{r.get('institucion','')} | {r.get('unidad','')}")
                    st.write(f"Resp: {r.get('responsable','') or '—'}")
                    st.write(f"JA: {semaforo(r.get('dias_JA'))}")
                    st.write(f"Apertura: {semaforo(r.get('dias_AP'))}")
                    st.write(f"Fallo: {semaforo(r.get('dias_FA'))}")

                with right:
                    st.markdown(
                        timeline_html(r.get("dias_JA"), r.get("dias_AP"), r.get("dias_FA"), ventana=ventana),
                        unsafe_allow_html=True
                    )
                    if r.get("link"):
                        st.link_button("Abrir link", r["link"])

        st.markdown("---")
        st.subheader("⬇️ Exportar (lo que estás viendo)")
        export_cols = ["clave","titulo","institucion","unidad","responsable","estatus","dias_JA","dias_AP","dias_FA","dias_min","link"]
        exp = df.copy()
        exp["estatus"] = exp["estatus"].apply(lambda x: x or "")
        st.download_button(
            "Descargar Excel",
            data=df_to_excel_bytes(exp[export_cols], "resumen"),
            file_name="resumen_operativo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# =========================
# PAGE 4: TABLERO (KANBAN TIPO JIRA)
# =========================
elif page == "Tablero":
    st.title("🧩 Tablero (tipo Jira)")
    st.caption("Vista Kanban por estatus. Cambia el estatus desde cada tarjeta.")

    df = sql_df("""
        SELECT id, clave, titulo, institucion, unidad, responsable, estatus,
               junta_aclaraciones, apertura, fallo, link
        FROM licitaciones
        ORDER BY id DESC;
    """)

    if df.empty:
        st.info("Aún no hay licitaciones registradas.")
    else:
        for c in ["junta_aclaraciones", "apertura", "fallo"]:
            df[c] = pd.to_datetime(df[c], errors="coerce")

        df["dias_JA"] = df["junta_aclaraciones"].dt.date.apply(dias_a)
        df["dias_AP"] = df["apertura"].dt.date.apply(dias_a)
        df["dias_FA"] = df["fallo"].dt.date.apply(dias_a)

        estados = ["Abierta", "En análisis", "En gestión", "Cerrada", "Cancelada"]

        # Filtros rápidos
        f1, f2 = st.columns([1.2, 2.0])
        with f1:
            fil_est = st.selectbox("Filtrar estatus", ["(Todos)"] + estados, index=0)
        with f2:
            fil_txt = st.text_input("Buscar (clave / institución / unidad / responsable)", "")

        dff = df.copy()
        if fil_est != "(Todos)":
            dff = dff[dff["estatus"] == fil_est]
        if fil_txt.strip():
            s = fil_txt.strip().lower()
            mask = (
                dff["clave"].fillna("").str.lower().str.contains(s) |
                dff["institucion"].fillna("").str.lower().str.contains(s) |
                dff["unidad"].fillna("").str.lower().str.contains(s) |
                dff["responsable"].fillna("").str.lower().str.contains(s)
            )
            dff = dff[mask]

        cols = st.columns(len(estados), gap="large")

        for col, est in zip(cols, estados):
            subset = dff[dff["estatus"] == est].copy()

            # Orden interno: más urgente primero
            def min_no_null(row):
                vals = [row["dias_JA"], row["dias_AP"], row["dias_FA"]]
                vals = [v for v in vals if v is not None]
                return min(vals) if vals else 999999

            subset["dias_min"] = subset.apply(min_no_null, axis=1)
            subset = subset.sort_values("dias_min", ascending=True)

            with col:
                st.markdown(f"### {badge(est)}")
                st.caption(f"{len(subset)} items")

                if subset.empty:
                    st.write("—")
                else:
                    for _, r in subset.iterrows():
                        with st.container(border=True):
                            st.write(f"**{r.get('clave','')}**")
                            st.write(f"{r.get('institucion','')} | {r.get('unidad','')}")
                            st.write(f"Resp: {r.get('responsable','') or '—'}")
                            st.write(f"JA: {semaforo(r.get('dias_JA'))}")
                            st.write(f"Fallo: {semaforo(r.get('dias_FA'))}")

                            nuevo = st.selectbox("Mover a:", estados, index=estados.index(est), key=f"move_{r['id']}")
                            if nuevo != est:
                                if st.button("Actualizar", key=f"btn_{r['id']}", use_container_width=True):
                                    with engine.begin() as conn:
                                        conn.execute(text("UPDATE licitaciones SET estatus=:e WHERE id=:id;"), {"e": nuevo, "id": int(r["id"])})
                                    st.success("Actualizado.")
                                    st.rerun()

                            if r.get("link"):
                                st.link_button("Abrir", r["link"])


# =========================
# PAGE 3: POWER BI
# =========================
elif page == "Power BI":
    st.title("📊 Power BI")
    st.caption("Pega tu URL de 'embed' (Public o Share/Embed). La app la guarda y la muestra aquí.")

    settings = sql_df("SELECT * FROM powerbi_settings WHERE id=1;")
    current_url = settings["embed_url"].iloc[0] if not settings.empty else ""

    st.subheader("⚙️ Configuración")
    new_url = st.text_input("Power BI Embed URL", value=current_url, help="Ejemplo: https://app.powerbi.com/view?r=... o embed con reportId")

    if st.button("💾 Guardar URL"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE powerbi_settings SET embed_url=:u WHERE id=1;"), {"u": new_url.strip()})
        st.success("URL guardada.")
        st.rerun()

    st.markdown("---")
    st.subheader("👁️ Vista del reporte")

    if current_url.strip():
        # Iframe
        st.components.v1.iframe(current_url, height=760, scrolling=True)
    else:
        st.info("Aún no hay URL configurada. Pégala arriba y guárdala.")

# =========================
# PAGE 4: CALENDARIO
# =========================
elif page == "Calendario":
    st.title("🗓️ Calendario de licitaciones")
    st.caption("Se arma desde las fechas de: Publicación, Junta de Aclaraciones, Apertura, Fallo, Firma de Contrato.")

    lic = sql_df("SELECT id, clave, titulo, institucion, unidad, responsable, link, fecha_publicacion, junta_aclaraciones, apertura, fallo, firma_contrato FROM licitaciones;")

    events = []
    if not lic.empty:
        def add_event(row, key, label):
            v = row.get(key)
            if v and str(v).strip():
                try:
                    d = datetime.fromisoformat(str(v)).date()
                    title = f"{label} | {row.get('clave','')}".strip()
                    desc = f"{row.get('titulo','')}\n{row.get('institucion','')} | {row.get('unidad','')}\nResp: {row.get('responsable','')}"
                    events.append({
                        "title": title,
                        "start": d.isoformat(),
                        "end": d.isoformat(),
                        "resourceId": str(row.get("id")),
                        "extendedProps": {"desc": desc, "link": row.get("link","")}
                    })
                except:
                    pass

        for _, r in lic.iterrows():
            add_event(r, "fecha_publicacion", "📌 Publicación")
            add_event(r, "junta_aclaraciones", "🗣️ Junta")
            add_event(r, "apertura", "📂 Apertura")
            add_event(r, "fallo", "🏁 Fallo")
            add_event(r, "firma_contrato", "✍️ Firma")

    # Intentar calendario visual
    try:
        from streamlit_calendar import calendar

        st.subheader("📅 Vista calendario")
        options = {
            "initialView": "dayGridMonth",
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
            "selectable": True,
            "editable": False,
        }

        cal = calendar(events=events, options=options, key="cal")
        st.caption("Tip: da clic en un evento y revisa la sección de detalle abajo.")

        st.subheader("🔎 Detalle del evento (último clic)")
        if cal and isinstance(cal, dict) and cal.get("eventClick"):
            ev = cal["eventClick"]["event"]
            st.write(f"**{ev.get('title','')}**")
            st.write(f"Fecha: {ev.get('start','')}")
            ext = ev.get("extendedProps", {}) or {}
            if ext.get("desc"):
                st.text(ext["desc"])
            if ext.get("link"):
                st.write(ext["link"])
        else:
            st.info("Da clic en un evento para ver detalles aquí.")

    except Exception:
        # Fallback tabla/agenda
        st.warning("No se pudo cargar el calendario visual (streamlit-calendar). Mostrando vista tipo agenda.")
        if events:
            evdf = pd.DataFrame(events)
            evdf = evdf.sort_values("start")
            st.dataframe(evdf[["start", "title", "resourceId"]], use_container_width=True, height=560)
        else:
            st.info("Aún no hay eventos (necesitas fechas en licitaciones).")

    st.markdown("---")
    st.subheader("📥 Exportar eventos")
    if events:
        evdf = pd.DataFrame(events)
        st.download_button(
            "⬇️ Descargar eventos (Excel)",
            data=df_to_excel_bytes(evdf, "eventos"),
            file_name="eventos_licitaciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info("No hay eventos para exportar.")

