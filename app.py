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
# DB INIT
# =========================
init_db()

# =========================
# UI: SIDEBAR NAV
# =========================
st.sidebar.title("📌 Menú")
page = st.sidebar.radio(
    "Ir a:",
    ["Seguimiento de Apoyos", "Licitaciones", "Power BI", "Calendario"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.caption("Base local: SQLite (seguimiento.db)")

# =========================
# PAGE 1: APOYOS
# =========================
if page == "Seguimiento de Apoyos":
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

