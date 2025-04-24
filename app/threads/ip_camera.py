import os
import streamlit as st
import requests

# -----------------------------
# 📡 IP Camera Viewer Frontend
# -----------------------------
PAGE_TITLE = "📡 IP Camera Viewer"
API_PREFIX = "/api/ip_camera"

def run_app():
    from streamlit_autorefresh import st_autorefresh
    from streamlit_drawable_canvas import st_canvas

    # --- Init ---
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="📷",
        layout="wide",
    )

    st.markdown(
        """
        <style>
            .title { font-size: 2.5rem; font-weight: 700; margin-bottom: 1rem; }
            .subtitle { font-size: 1.25rem; font-weight: 600; margin-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"<div class='title'>{PAGE_TITLE} con Pipeline</div>", unsafe_allow_html=True)

    # --- Camera URLs gestione ---
    if 'camera_urls' not in st.session_state:
        st.session_state['camera_urls'] = {
            "Camera Locale": "http://localhost:5000/api/ip_camera/stream"
        }

    # --- Sidebar ---
    st.sidebar.header("🔌 Telecamere Disponibili")
    camera_selezionata = st.sidebar.selectbox(
        "Seleziona Telecamera",
        list(st.session_state['camera_urls'].keys())
    )

    stream_url = st.session_state['camera_urls'][camera_selezionata]
    st.session_state['selected_camera'] = camera_selezionata

    # --- Info Camera ---
    @st.cache_data(ttl=60)
    def fetch_camera_info(url):
        try:
            r = requests.get(f"{url.replace('/stream','/info')}", timeout=2)
            return r.json().get('camera', {})
        except:
            return {}

    camera_info = fetch_camera_info(stream_url)
    if camera_info:
        st.sidebar.subheader("ℹ️ Info Camera")
        st.sidebar.write(f"**Risoluzione:** {camera_info.get('width')}x{camera_info.get('height')}")
        st.sidebar.write(f"**FPS:** {camera_info.get('fps')}")
        st.sidebar.write(f"**Codec:** {camera_info.get('fourcc')}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Configurazione Pipeline")
    refresh_rate = st.sidebar.number_input("Refresh Live Ogni (sec)", 1, 30, 5)

    # --- Config attuale ---
    @st.cache_data(ttl=30)
    def fetch_config():
        try:
            r = requests.get(f"{stream_url.replace('/stream','/config')}", timeout=2)
            return r.json().get('config', {})
        except:
            return {}

    config = fetch_config()

    # --- Impostazioni principali ---
    draw = st.sidebar.checkbox("🎨 Disegna Bounding Boxes", value=config.get('draw_boxes', False))
    count = st.sidebar.checkbox("🔢 Conta Oggetti", value=config.get('count_objects', False))

    # --- Linea di conteggio ---
    st.sidebar.subheader("🖐️ Linea di Conteggio")
    use_line = st.sidebar.checkbox("Abilita Linea", value=bool(config.get('count_line')))
    line_coords = config.get('count_line') or [[50, 50], [200, 50]]
    coords = None

    if use_line:
        canvas_result = st_canvas(
            fill_color="",
            stroke_width=2,
            stroke_color="green",
            background_color="#f0f0f0",
            height=300,
            width=300,
            drawing_mode="line",
            initial_drawing=[{"type": "line", "points": line_coords}],
            key="canvas_countline"
        )
        if canvas_result.json_data and canvas_result.json_data["objects"]:
            last_line = canvas_result.json_data["objects"][-1]
            coords = [tuple(map(int, p)) for p in last_line["points"]]

    # --- Modelli e Parametri Specifici ---
    st.sidebar.subheader("🧠 Modelli & Parametri")
    model_behaviors = config.get("model_behaviors", {})
    updated_behaviors = {}

    for model_path, settings in model_behaviors.items():
        with st.sidebar.expander(f"📁 {os.path.basename(model_path)}"):
            conf = st.slider(f"🎯 Confidence - {os.path.basename(model_path)}", 0.0, 1.0, float(settings.get("confidence", 0.5)), 0.01)
            iou  = st.slider(f"📏 IoU - {os.path.basename(model_path)}", 0.0, 1.0, float(settings.get("iou", 0.45)), 0.01)
            draw_m = st.checkbox(f"🎨 Disegna", value=settings.get("draw", False), key=f"draw_{model_path}")
            count_m = st.checkbox(f"🔢 Conta", value=settings.get("count", False), key=f"count_{model_path}")
            updated_behaviors[model_path] = {
                "confidence": conf,
                "iou": iou,
                "draw": draw_m,
                "count": count_m
            }

    # --- Applica Config ---
    if st.sidebar.button("✅ Applica Configurazione"):
        payload = {
            "draw_boxes": draw,
            "count_objects": count,
            "count_line": coords,
            "model_behaviors": updated_behaviors
        }
        try:
            r = requests.post(f"{stream_url.replace('/stream','/config')}", json=payload, timeout=3)
            if r.ok:
                st.sidebar.success("✔️ Configurazione applicata")
            else:
                st.sidebar.error("Errore applicazione config")
        except Exception as e:
            st.sidebar.error(f"Errore: {e}")

    # --- UI Principale ---
    st_autorefresh(interval=refresh_rate * 1000, limit=None, key="refresh")
    tabs = st.tabs(["📺 Live", "📊 Metriche"])

    with tabs[0]:
        st.markdown("<div class='subtitle'>Live Stream</div>", unsafe_allow_html=True)
        if camera_info:
            st.image(stream_url, use_column_width=True)
        else:
            st.warning("⚠️ Stream non disponibile")

    with tabs[1]:
        st.markdown("<div class='subtitle'>📈 Conteggi & Statistiche</div>", unsafe_allow_html=True)
        try:
            metrics = requests.get(f"{stream_url.replace('/stream','/metrics')}", timeout=2).json()
            counters = metrics.get('counters', {})
            cols = st.columns(len(counters) or 1)
            for idx, (cls, val) in enumerate(counters.items()):
                cols[idx % len(cols)].metric(label=cls, value=val)
        except Exception as e:
            st.warning(f"Errore caricamento metriche: {e}")

    st.markdown("---")
    st.caption("🚀 Interfaccia Streamlit con supporto YOLOv8 e conteggio oggetti")


def run(app):
    from flask import current_app
    with app.app_context():
        name = os.path.splitext(os.path.basename(__file__))[0]
        cfg = current_app.config['MODULES']['threads']['config'].get(name, {})
        cfg["script_path"] = os.path.abspath(__file__)
        current_app.streamlit_manager.register(name, cfg)

if __name__ == "__main__":
    run_app()
