import streamlit as st
import pandas as pd
import numpy as np
import re
import html
import streamlit.components.v1 as components

st.set_page_config(page_title="Wellpass Hamburg", layout="wide")

st.title("💪 Wellpass Hamburg Kursübersicht")

# ------------------------------
# 📂 CSV einlesen
# ------------------------------
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("Wellpass.csv", sep=",", engine="python")
    except:
        df = pd.read_csv("Wellpass.csv", sep=";", engine="python")
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(how="all")
    return df

df_all = load_data()

# ------------------------------
# 🧹 Datenbereinigung
# ------------------------------
df_all = df_all[df_all["Ort"].notna()]
df_all = df_all[~df_all["Ort"].str.contains("unbekannt", case=False, na=False)]

def normalize_st_georg(ort):
    if not isinstance(ort, str):
        return ort
    ort_clean = ort.strip()
    patterns = [r"^St$", r"^St\.$", r"^St\s*Georg$", r"^St\.?\s*Georg$"]
    for p in patterns:
        if re.match(p, ort_clean, flags=re.IGNORECASE):
            return "St. Georg"
    return ort_clean

df_all["Ort"] = df_all["Ort"].apply(normalize_st_georg)

orte = sorted(df_all["Ort"].dropna().unique())

ort_farben = {
    ort: f"hsl({(hash(ort) % 360)}, 60%, 55%)"
    for ort in orte
}

# ------------------------------
# 🔍 Filtersteuerung
# ------------------------------
tage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

with st.sidebar:
    st.header("Filter")

    st.subheader("🗓️ Wochentage")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Alle Tage"):
            st.session_state["tage_filter"] = tage
    with col2:
        if st.button("Keine Tage"):
            st.session_state["tage_filter"] = []
    tage_filter = st.multiselect(
        "Tag auswählen", tage,
        default=st.session_state.get("tage_filter", tage),
        key="tage_filter"
    )

    st.subheader("📍 Studios")
    col3, col4 = st.columns(2)
    with col3:
        if st.button("Alle Orte"):
            st.session_state["ort_filter"] = orte
    with col4:
        if st.button("Keine Orte"):
            st.session_state["ort_filter"] = []
    ort_filter = st.multiselect(
        "Ort auswählen", orte,
        default=st.session_state.get("ort_filter", orte),
        key="ort_filter"
    )

    st.subheader("🏋️ Kurse")
    kurse = sorted(df_all["Kurs"].dropna().unique())
    col5, col6 = st.columns(2)
    with col5:
        if st.button("Alle Kurse"):
            st.session_state["kurs_filter"] = kurse
    with col6:
        if st.button("Keine Kurse"):
            st.session_state["kurs_filter"] = []
    kurs_filter = st.multiselect(
        "Kurs auswählen", kurse,
        default=st.session_state.get("kurs_filter", kurse),
        key="kurs_filter"
    )

    st.subheader("⏰ Uhrzeit")
    import datetime as dt
    min_time = dt.time(6, 0)
    max_time = dt.time(23, 0)
    start_time, end_time = st.slider(
        "Zeitraum auswählen",
        value=(min_time, max_time),
        min_value=min_time,
        max_value=max_time,
        step=dt.timedelta(minutes=30),
        format="HH:mm"
    )

    suchbegriff = st.text_input("🔎 Nach Kurs suchen")

# ------------------------------
# 🧩 Daten filtern
# ------------------------------
def parse_time_to_minutes(t_str):
    match = re.match(r"(\d{1,2}):(\d{2})", str(t_str))
    if match:
        h, m = map(int, match.groups())
        return h * 60 + m
    return None

start_minutes = start_time.hour * 60 + start_time.minute
end_minutes = end_time.hour * 60 + end_time.minute

filtered_df = df_all[
    (df_all["Tag"].isin(tage_filter)) &
    (df_all["Ort"].isin(ort_filter)) &
    (df_all["Kurs"].isin(kurs_filter))
].copy()

filtered_df["Uhrzeit_min"] = filtered_df["Uhrzeit"].apply(parse_time_to_minutes)
filtered_df = filtered_df[
    filtered_df["Uhrzeit_min"].between(start_minutes, end_minutes, inclusive="both")
]

if suchbegriff:
    begriffe = re.split(r"[,;\s]+", suchbegriff.strip())
    # ODER-Suche (mindestens ein Begriff trifft zu)
    pattern = "|".join(map(re.escape, begriffe))
    filtered_df = filtered_df[
        filtered_df["Kurs"].str.contains(pattern, case=False, na=False)
    ]

if filtered_df.empty:
    st.info("Keine Kurse für die aktuelle Auswahl gefunden.")
    st.dataframe(pd.DataFrame(columns=["Tag", "Uhrzeit", "Kurs", "Ort"]))
    st.stop()

# ------------------------------
# 🗂 Tabs
# ------------------------------
tab1, tab2 = st.tabs([
    "🕓 Stundenraster",
    "📅 Stundenplan-Ansicht"
])

# ------------------------------------------------------------
# 🕓 TAB 1 – Stundenraster
# ------------------------------------------------------------
with tab1:
    st.markdown("### 🕓 Stundenraster")

    hide_empty = st.checkbox("🔘 Nur Stunden mit Kursen anzeigen", value=False)
    compact_mode = st.checkbox("📏 Kompakter Modus", value=False)

    tage_order = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]

    def parse_start_time(zeit_str):
        match = re.match(r"(\d{1,2}):(\d{2})", str(zeit_str))
        if match:
            h, m = map(int, match.groups())
            return h * 60 + m
        return None

    df_time = filtered_df.copy()
    df_time["Start_min"] = df_time["Uhrzeit"].apply(parse_start_time)
    df_time = df_time.dropna(subset=["Start_min"])
    df_time["Stunde"] = (df_time["Start_min"] // 60).astype(int)

    min_hour = int(df_time["Stunde"].min())
    max_hour = int(df_time["Stunde"].max())

    if hide_empty:
        stunden_mit_kursen = sorted(df_time["Stunde"].unique())
    else:
        stunden_mit_kursen = list(range(min_hour, max_hour + 1))

    if compact_mode:
        cell_min_height = "40px"
        font_size = "0.8rem"
        padding = "3px"
    else:
        cell_min_height = "60px"
        font_size = "0.9rem"
        padding = "6px"

    css = f"""
    <style>
    .timetable {{
        display: grid;
        grid-template-columns: 80px repeat(7, 1fr);
        width: 100%;
    }}
    .time-cell {{
        background: #f1f3f5;
        font-weight: 600;
        font-size: 0.85rem;
        text-align: right;
        padding-right: 6px;
        border-bottom: 1px solid #dee2e6;
    }}
    .day-header {{
        text-align: center;
        background: #dee2e6;
        font-weight: 700;
        padding: 8px 0;
        border-bottom: 2px solid #adb5bd;
    }}
    .cell {{
        border-bottom: 1px solid #dee2e6;
        padding: {padding};
        background: #fff;
        min-height: {cell_min_height};
    }}
    .course-block {{
        border-radius: 10px;
        color: white;
        padding: {padding};
        margin-bottom: 4px;
        line-height: 1.25;
        font-size: {font_size};
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .time {{ font-weight: 600; display: block; }}
    .coursename {{ font-weight: 500; display: block; margin-top: 2px; }}
    .studio {{ font-style: italic; font-size: 0.85rem; opacity: 0.9; }}
    </style>
    """

    html_content = ['<div class="timetable">']

    html_content.append('<div></div>')
    for tag in tage_order:
        html_content.append(f'<div class="day-header">{tag}</div>')

    for hour in stunden_mit_kursen:
        html_content.append(f'<div class="time-cell">{hour:02d}:00<br>{hour+1:02d}:00</div>')

        for tag in tage_order:
            day_df = (
                df_time[(df_time["Tag"] == tag) & (df_time["Stunde"] == hour)]
                .sort_values("Start_min")  # <-- NEU: Sortierung nach Startzeit!
            )
            cell_html = ""
            for _, row in day_df.iterrows():
                zeit = html.escape(str(row["Uhrzeit"]))
                kurs = html.escape(str(row["Kurs"]))
                ort = html.escape(str(row["Ort"]))
                color = ort_farben.get(row["Ort"], "#666")
                cell_html += f'''
                    <div class="course-block" style="background:{color};">
                        <span class="time">{zeit}</span>
                        <span class="coursename">{kurs}</span>
                        <span class="studio">{ort}</span>
                    </div>
                '''
            html_content.append(f'<div class="cell">{cell_html}</div>')

    html_content.append("</div>")
    full_html = css + "\n".join(html_content)
    components.html(full_html, height=900, scrolling=True)

# ------------------------------------------------------------
# 📅 TAB 2 – Stundenplan
# ------------------------------------------------------------
with tab2:
    st.markdown("### 🕓 Stundenplan – Stundenweise Ansicht")

    tage_order = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]

    def parse_start_time(zeit_str):
        match = re.match(r"(\d{1,2}):(\d{2})", str(zeit_str))
        if match:
            h, m = map(int, match.groups())
            return h * 60 + m
        return None

    df_time = filtered_df.copy()
    df_time["Start_min"] = df_time["Uhrzeit"].apply(parse_start_time)
    df_time = df_time.dropna(subset=["Start_min"])
    df_time["Stunde"] = (df_time["Start_min"] // 60).astype(int)

    min_hour = int(df_time["Stunde"].min())
    max_hour = int(df_time["Stunde"].max())

    css = """
    <style>
    .week-container {
        display: flex;
        gap: 12px;
        overflow-x: auto;
        padding: 20px 10px;
    }
    .day-column {
        flex: 1;
        min-width: 200px;
        background: #f8f9fa;
        border-radius: 10px;
        padding: 6px;
    }
    .day-header {
        text-align: center;
        font-weight: 700;
        background: #dee2e6;
        border-radius: 6px;
        padding: 6px;
        margin-bottom: 10px;
    }
    .hour-block {
        background: #e9ecef;
        border-radius: 6px;
        padding: 6px;
        margin-bottom: 8px;
    }
    .hour-label {
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 4px;
        color: #495057;
    }
    .course-block {
        border-radius: 10px;
        color: white;
        padding: 6px 8px;
        margin-bottom: 6px;
        line-height: 1.25;
        font-size: 0.9rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .time { font-weight: 600; display: block; }
    .coursename { font-weight: 500; display: block; margin-top: 2px; }
    .studio { font-style: italic; font-size: 0.85rem; opacity: 0.9; }
    </style>
    """

    html_content = ['<div class="week-container">']

    for tag in tage_order:
        day_df = df_time[df_time["Tag"] == tag].sort_values("Start_min")
        if not day_df.empty:
            html_content.append(f'<div class="day-column"><div class="day-header">{tag}</div>')
            for hour in range(min_hour, max_hour + 1):
                hour_df = day_df[day_df["Stunde"] == hour]
                if not hour_df.empty:
                    html_content.append(f'<div class="hour-block"><div class="hour-label">{hour:02d}:00 – {hour+1:02d}:00</div>')
                    for _, row in hour_df.iterrows():
                        zeit = html.escape(str(row["Uhrzeit"]))
                        kurs = html.escape(str(row["Kurs"]))
                        ort = html.escape(str(row["Ort"]))
                        color = ort_farben.get(row["Ort"], "#666")
                        html_content.append(f'''
                            <div class="course-block" style="background:{color};">
                                <span class="time">{zeit}</span>
                                <span class="coursename">{kurs}</span>
                                <span class="studio">{ort}</span>
                            </div>
                        ''')
                    html_content.append("</div>")
            html_content.append("</div>")

    html_content.append("</div>")
    full_html = css + "\n".join(html_content)
    components.html(full_html, height=900, scrolling=True)
