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
# HELPERS DE UI (DASHBOARD)
# =========================
def section_header(title: str, subtitle: str = "", theme: str = "gray", chip: str = ""):
    cls = {"blue": "section-blue", "orange": "section-orange", "gray": "section-gray"}.get(theme, "section-gray")
    chip_html = f'<span class="chip">{chip}</span>' if chip else ""
    st.markdown(
        f"""
        <div class="section {cls}">
          <h3>{title}{chip_html}</h3>
          <small>{subtitle}</small>
        </div>
        """,
        unsafe_allow_html=True
    )

def tidy_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    out = out.replace({None: "", "None": "", "nan": "", "NaN": ""}).fillna("")
    return out

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
    [
        "Excel (Base oficial)",
        "Licitaciones en curso",
        "Seguimiento de Apoyos",
        "Resumen",
        "Tablero",
        "Power BI",
        "Calendario",
    ]
)


st.sidebar.markdown("---")
st.sidebar.caption("Base local: SQLite (seguimiento.db)")

# =========================
# ESTILO (Dashboard look)
# =========================
st.markdown(
    """
    <style>


/* =========================
   KPI COLORES
   ========================= */

.kpi-blue {
    background: linear-gradient(135deg, #1e3a8a, #3b82f6);
    color: white;
}

.kpi-green {
    background: linear-gradient(135deg, #065f46, #10b981);
    color: white;
}

.kpi-yellow {
    background: linear-gradient(135deg, #92400e, #f59e0b);
    color: white;
}

.kpi-light {
    background: linear-gradient(135deg, #e0f2fe, #bae6fd);
    color: #0f172a;
}

/* que el texto interno herede bien */
.kpi-blue .kpi-lbl,
.kpi-green .kpi-lbl,
.kpi-yellow .kpi-lbl {
    color: rgba(255,255,255,.85);
}




    /* ancho y aire */
    .block-container {
        padding-top: 1.3rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* barra de filtros */
    .filters-row [data-testid="stTextInput"],
    .filters-row [data-testid="stSelectbox"] {
        margin-bottom: 0px;
    }

    /* tarjetas KPI */
    .kpi-wrap {
        border-radius: 14px;
        padding: 16px 18px;
        background: white;
        border: 1px solid #e9edf5;
        box-shadow: 0 6px 18px rgba(15,23,42,.06);
    }

    .kpi-num {
        font-size: 34px;
        font-weight: 800;
        line-height: 1.0;
        margin: 0;
    }

    .kpi-lbl {
        font-size: 14px;
        opacity: .75;
        margin-top: 6px;
    }

    /* tabs más limpios */
    button[data-baseweb="tab"] {
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }

    /* tabla */
    [data-testid="stDataFrame"] {
        border: 1px solid #eef2f7;
        border-radius: 12px;
        overflow: hidden;
    }

    /* ================= NUEVO ESTILO ================= */

    .section {
        border-radius: 14px;
        padding: 12px 14px;
        margin: 8px 0 10px 0;
        border: 1px solid rgba(15,23,42,.08);
        box-shadow: 0 6px 18px rgba(15,23,42,.06);
    }

    .section h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 800;
    }

    .section small {
        opacity: .75;
    }

    .section-blue {
        background: linear-gradient(90deg, rgba(59,130,246,.18), rgba(59,130,246,.05));
    }

    .section-orange {
        background: linear-gradient(90deg, rgba(245,158,11,.20), rgba(245,158,11,.06));
    }

    .section-gray {
        background: linear-gradient(90deg, rgba(148,163,184,.22), rgba(148,163,184,.06));
    }

    .chip {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid rgba(15,23,42,.10);
        background: rgba(255,255,255,.65);
        margin-left: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True
)





# =========================
# PAGE 0: EXCEL (BASE OFICIAL)
# =========================

# ---- Excel -> DB (upsert) helpers ----

def _norm_col(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


def _pick_col(cols, *candidates):
    """Return the real column name in cols matching any candidate (case/space-insensitive)."""
    norm_map = {_norm_col(c): c for c in cols}
    for cand in candidates:
        key = _norm_col(cand)
        if key in norm_map:
            return norm_map[key]
    return None


def _to_date_str(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    try:
        dt = pd.to_datetime(x, errors="coerce")
        if pd.isna(dt):
            return ""
        return dt.date().isoformat()
    except Exception:
        return ""


def upsert_licitaciones_from_excel(df_excel: pd.DataFrame):
    """Upsert rows from the Excel maestro into table 'licitaciones' using 'clave' as key."""
    if df_excel is None or df_excel.empty:
        return 0, 0

    df = df_excel.copy()

    # Try to map columns (update the candidates anytime your Excel changes)
    col_clave = _pick_col(df.columns, "NUMERO DE LA LICITACIÓN", "NUMERO DE LA LICITACION", "CLAVE", "EXPEDIENTE")
    col_titulo = _pick_col(df.columns, "TITULO", "DESCRIPCION", "ESPECIALIDAD SERV.INT (LAB)")
    col_institucion = _pick_col(df.columns, "CONVOCANTE", "INSTITUCION")
    col_unidad = _pick_col(df.columns, "UNIDAD", "HOSPITAL")
    col_estado = _pick_col(df.columns, "ESTADO")
    col_integrador = _pick_col(df.columns, "DISTRIBUIDOR ACTUAL", "INTEGRADOR", "LICITANTE GANADOR")
    col_monto = _pick_col(df.columns, "MONTO", "MONTO ESTIMADO", "IMPORTE")

    col_pub = _pick_col(df.columns, "FECHA DE PUBLICACIÓN", "FECHA DE PUBLICACION", "PUBLICACION")
    col_ja = _pick_col(df.columns, "JUNTA DE ACLARACIONES", "JA", "JUNTA")
    col_apertura = _pick_col(df.columns, "APERTURA", "PROPUESTA ECONOMICA")
    col_fallo = _pick_col(df.columns, "FALLO")
    col_firma = _pick_col(df.columns, "FIRMA", "FIRMA CONTRATO", "FIRMA DE CONTRATO")

    col_razon = _pick_col(df.columns, "RAZON SOCIAL")
    col_estatus = _pick_col(df.columns, "ESTATUS DE LA LICITACION", "ESTATUS")
    col_responsable = _pick_col(df.columns, "ELABORO", "RESPONSABLE")

    if not col_clave:
        # Without clave we can't upsert safely
        return 0, 0

    inserted = 0
    updated = 0

    # Iterate rows
    for _, r in df.iterrows():
        clave = str(r.get(col_clave, "") or "").strip()
        if not clave:
            continue

        payload = {
            "clave": clave,
            "titulo": str(r.get(col_titulo, "") or "").strip() if col_titulo else "",
            "institucion": str(r.get(col_institucion, "") or "").strip() if col_institucion else "",
            "unidad": str(r.get(col_unidad, "") or "").strip() if col_unidad else "",
            "estado": str(r.get(col_estado, "") or "").strip() if col_estado else "",
            "integrador": str(r.get(col_integrador, "") or "").strip() if col_integrador else "",
            "monto_estimado": float(r.get(col_monto)) if (col_monto and pd.notna(r.get(col_monto))) else 0.0,
            "fecha_publicacion": _to_date_str(r.get(col_pub)) if col_pub else "",
            "junta_aclaraciones": _to_date_str(r.get(col_ja)) if col_ja else "",
            "apertura": _to_date_str(r.get(col_apertura)) if col_apertura else "",
            "fallo": _to_date_str(r.get(col_fallo)) if col_fallo else "",
            "firma_contrato": _to_date_str(r.get(col_firma)) if col_firma else "",
            "pidio_apoyo": 0,
            "apoyo_id": None,
            "carta_enviada": 0,
            "razon_social": str(r.get(col_razon, "") or "").strip() if col_razon else "",
            "estatus": str(r.get(col_estatus, "") or "").strip() if col_estatus else "",
            "responsable": str(r.get(col_responsable, "") or "").strip() if col_responsable else "",
            "link": "",
            "notas": "",
        }

        with engine.begin() as conn:
            exists = conn.execute(text("SELECT id FROM licitaciones WHERE clave=:c LIMIT 1"), {"c": clave}).fetchone()
            if exists:
                payload["id"] = int(exists[0])
                conn.execute(text("""
                    UPDATE licitaciones SET
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
                        razon_social=:razon_social,
                        estatus=:estatus,
                        responsable=:responsable
                    WHERE id=:id;
                """), payload)
                updated += 1
            else:
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
                inserted += 1

    return inserted, updated


if page == "Excel (Base oficial)":
    st.title("📘 Excel (Base oficial)")
    st.caption("Aquí cargas el Excel maestro. La app lo usa como base para licitaciones y seguimiento.")

    excel_file = st.file_uploader("Sube tu Excel maestro", type=["xlsx"], key="excel_base")

    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        if excel_file and st.button("✅ Importar / Actualizar en la base", use_container_width=True):
            df_excel = pd.read_excel(excel_file)
            ins, upd = upsert_licitaciones_from_excel(df_excel)
            st.success(f"Importación lista. Insertadas: {ins} | Actualizadas: {upd}")
            st.rerun()

    with c2:
        ver_excel = st.toggle("👁️ Ver Excel aquí", value=True, disabled=excel_file is None)

    with c3:
        df_db = sql_df("SELECT * FROM licitaciones ORDER BY id DESC;")
        st.download_button(
            "⬇️ Descargar Excel actualizado",
            data=df_to_excel_bytes(df_db, "licitaciones"),
            file_name="SEGUIMIENTO_LIC_actualizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("📊 Visor del Excel maestro")

    if excel_file and ver_excel:
        df_excel = pd.read_excel(excel_file)
        visor = st.container(border=True)
        visor.dataframe(df_excel, use_container_width=True, height=720)
    else:
        st.info("Sube tu Excel para visualizarlo aquí. Si solo quieres ver licitaciones, ve a 'Licitaciones en curso'.")


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
# PAGE: LICITACIONES EN CURSO (Dashboard)
# =========================
elif page == "Licitaciones en curso":
    st.title("📄 Licitaciones en curso")
    st.caption("Aquí solo se muestra lo guardado en la base (SQLite). Para cargar masivo: Excel (Base oficial) → ✅ Importar / Actualizar en la base.")

    df = sql_df("SELECT * FROM licitaciones ORDER BY id DESC;")

    if df.empty:
        st.warning("Aún no hay licitaciones en la base. Ve a: Excel (Base oficial) → sube tu Excel → ✅ Importar / Actualizar en la base.")
        st.stop()

    # -------------------------
    # 1) FILTROS (arriba)
    # -------------------------
    fcol1, fcol2, fcol3, fcol4, fcol5, fcol6 = st.columns([1.7, 1, 1, 1, 1, 1], gap="small")
    with st.container():
        st.markdown('<div class="filters-row">', unsafe_allow_html=True)

        with fcol1:
            q = st.text_input("🔎 Buscar licitación…", value="", placeholder="clave / título / institución / unidad / responsable")

        with fcol2:
            inst_opts = ["(Todas)"] + sorted([x for x in df["institucion"].fillna("").unique().tolist() if str(x).strip() != ""])
            inst = st.selectbox("Institución", inst_opts, index=0)

        with fcol3:
            integ_opts = ["(Todos)"] + sorted([x for x in df["integrador"].fillna("").unique().tolist() if str(x).strip() != ""])
            integ = st.selectbox("Integrador", integ_opts, index=0)

        with fcol4:
            tipo_opts = ["(Todos)"]
            # si más adelante guardas TIPO LIC, aquí lo usamos. Por ahora lo dejamos.
            tipo = st.selectbox("Tipo", tipo_opts, index=0)

        with fcol5:
            estatus_opts = ["(Todos)"] + sorted([x for x in df["estatus"].fillna("").unique().tolist() if str(x).strip() != ""])
            est = st.selectbox("Estatus", estatus_opts, index=0)

        with fcol6:
            carta = st.selectbox("Carta", ["(Todas)", "Enviada", "No enviada"], index=0)

        st.markdown("</div>", unsafe_allow_html=True)

    # aplicar filtros
    f = df.copy()

    if q.strip():
        s = q.lower().strip()
        mask = (
            f["clave"].fillna("").str.lower().str.contains(s) |
            f["titulo"].fillna("").str.lower().str.contains(s) |
            f["institucion"].fillna("").str.lower().str.contains(s) |
            f["unidad"].fillna("").str.lower().str.contains(s) |
            f["responsable"].fillna("").str.lower().str.contains(s)
        )
        f = f[mask]

    if inst != "(Todas)":
        f = f[f["institucion"] == inst]

    if integ != "(Todos)":
        f = f[f["integrador"] == integ]

    if est != "(Todos)":
        f = f[f["estatus"] == est]

    if carta == "Enviada":
        f = f[f["carta_enviada"] == 1]
    elif carta == "No enviada":
        f = f[f["carta_enviada"] == 0]

    # -------------------------
    # 2) KPIs (tarjetas)
    # -------------------------
    total = len(f)
    con_apoyo = int((f["pidio_apoyo"] == 1).sum()) if "pidio_apoyo" in f.columns else 0
    carta_enviada = int((f["carta_enviada"] == 1).sum()) if "carta_enviada" in f.columns else 0
    abiertas = int((f["estatus"] == "Abierta").sum()) if "estatus" in f.columns else 0

    k1, k2, k3, k4 = st.columns(4, gap="large")
    with k1:
        st.markdown(f'<div class="kpi-wrap"><div class="kpi-num">{total}</div><div class="kpi-lbl">Total licitaciones</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi-wrap"><div class="kpi-num">{con_apoyo}</div><div class="kpi-lbl">Con apoyo</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi-wrap"><div class="kpi-num">{carta_enviada}</div><div class="kpi-lbl">Carta enviada</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="kpi-wrap"><div class="kpi-num">{abiertas}</div><div class="kpi-lbl">Abiertas</div></div>', unsafe_allow_html=True)

    st.markdown("")

    # -------------------------
    # 3) FORMULARIO DESPLEGABLE (Nueva / Editar)
    # -------------------------
    with st.expander("➕ Nueva / Editar licitación", expanded=False):
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

        with st.form("form_lic", clear_on_submit=False):
            cA, cB, cC = st.columns(3)
            with cA:
                clave = st.text_input("Clave / Expediente", value=g("clave"))
                institucion = st.text_input("Institución", value=g("institucion"))
                unidad = st.text_input("Unidad / Hospital", value=g("unidad"))
            with cB:
                titulo = st.text_input("Título", value=g("titulo"))
                estado = st.text_input("Estado", value=g("estado"))
                integrador = st.text_input("Integrador (si aplica)", value=g("integrador"))
            with cC:
                monto = st.number_input("Monto estimado (opcional)", min_value=0.0, value=float(g("monto_estimado", 0.0) or 0.0), step=1000.0)
                estatus_form = st.text_input("Estatus", value=g("estatus"))
                responsable = st.text_input("Responsable", value=g("responsable"))

            cD, cE, cF, cG, cH = st.columns(5)
            with cD:
                f_pub = st.text_input("Fecha publicación (YYYY-MM-DD)", value=g("fecha_publicacion"))
            with cE:
                ja = st.text_input("Junta aclaraciones (YYYY-MM-DD)", value=g("junta_aclaraciones"))
            with cF:
                apertura = st.text_input("Apertura (YYYY-MM-DD)", value=g("apertura"))
            with cG:
                fallo = st.text_input("Fallo (YYYY-MM-DD)", value=g("fallo"))
            with cH:
                firma = st.text_input("Firma contrato (YYYY-MM-DD)", value=g("firma_contrato"))

            st.markdown("### ✅ Checks")
            cc1, cc2, cc3 = st.columns([1,1,2])
            with cc1:
                pidio_apoyo = st.checkbox("Pidió apoyo", value=bool(g("pidio_apoyo", 0)))
            with cc2:
                carta_chk = st.checkbox("Carta enviada", value=bool(g("carta_enviada", 0)))
            with cc3:
                razon_social = st.text_input("Razón social", value=g("razon_social"))

            link = st.text_input("Link (ComprasMX/drive/etc.)", value=g("link"))
            notas = st.text_area("Notas", value=g("notas"), height=100)

            guardar = st.form_submit_button("💾 Guardar")

        if guardar:
            payload = {
                "clave": clave.strip(),
                "titulo": titulo.strip(),
                "institucion": institucion.strip(),
                "unidad": unidad.strip(),
                "estado": estado.strip(),
                "integrador": integrador.strip(),
                "monto_estimado": float(monto or 0.0),
                "fecha_publicacion": (f_pub or "").strip(),
                "junta_aclaraciones": (ja or "").strip(),
                "apertura": (apertura or "").strip(),
                "fallo": (fallo or "").strip(),
                "firma_contrato": (firma or "").strip(),
                "pidio_apoyo": bool_to_int(pidio_apoyo),
                "apoyo_id": None,
                "carta_enviada": bool_to_int(carta_chk),
                "razon_social": razon_social.strip(),
                "estatus": estatus_form.strip(),
                "responsable": responsable.strip(),
                "link": (link or "").strip(),
                "notas": (notas or "").strip(),
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

    # -------------------------
    # -------------------------
    # 4) SECCIONES BONITAS (Bases vs Solicitudes)
    # -------------------------
    def _render_table(df_in: pd.DataFrame):
        show = tidy_df(df_in.copy())
        if show is None or show.empty:
            st.info("Sin registros para mostrar.")
            return

        if "pidio_apoyo" in show.columns:
            show["pidio_apoyo"] = show["pidio_apoyo"].apply(lambda x: "✅" if str(x) in ["1", "True", "true"] else "—")
        if "carta_enviada" in show.columns:
            show["carta_enviada"] = show["carta_enviada"].apply(lambda x: "📨" if str(x) in ["1", "True", "true"] else "—")

        cols = [c for c in [
            "id","clave","titulo","institucion","unidad","estado","integrador","monto_estimado",
            "fecha_publicacion","junta_aclaraciones","apertura","fallo","firma_contrato",
            "pidio_apoyo","carta_enviada","estatus","responsable","link"
        ] if c in show.columns]
        show = show[cols] if cols else show
        st.dataframe(show, use_container_width=True, height=520)

    f_show = tidy_df(f)

    # Separación por clave (sin depender de DB)
    if "clave" in f_show.columns:
        bases_df = f_show[f_show["clave"].astype(str).str.contains(r"(^LA-|^LP-|^PC-|^LV-)", regex=True, na=False)].copy()
        sc_df    = f_show[f_show["clave"].astype(str).str.contains(r"(^SC-)", regex=True, na=False)].copy()
    else:
        bases_df, sc_df = f_show.head(0), f_show.head(0)

    # Fallback: si por alguna razón se vacía, muestra todo en Bases
    if bases_df.empty and not f_show.empty:
        bases_df = f_show.copy()

    section_header("📁 Bases", "Licitaciones tipo base (según clave).", theme="blue", chip=str(len(bases_df)))
    _render_table(bases_df)

    st.markdown("")
    section_header("🧾 Solicitudes de cotización", "Solicitudes tipo SC (según clave).", theme="orange", chip=str(len(sc_df)))
    _render_table(sc_df)

    st.markdown("---")
    section_header("📋 Lista completa (filtrada)", "Incluye lo que estás viendo con filtros.", theme="gray", chip=str(len(f_show)))
    _render_table(f_show)

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

