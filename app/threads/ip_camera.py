import os
import requests

# 📡 IP Camera Viewer Frontend
PAGE_TITLE = "📡 IP Camera Viewer"

# Prima scelta: variabile di ambiente o default
API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def run_app():
    # Import Streamlit solo dentro run_app
    import streamlit as st
    from streamlit_autorefresh import st_autorefresh
    from streamlit_drawable_canvas import st_canvas

    # Se possibile, sovrascrivi API_BASE da secrets
    global API_BASE
    try:
        API_BASE = st.secrets.get("API_BASE", API_BASE)
    except Exception:
        pass

    # --- Funzioni interne ---
    def init_session():
        if 'camera_urls' not in st.session_state:
            st.session_state['camera_urls'] = {
                "Locale": {
                    "stream_url": f"{API_BASE}/api/ip_camera/stream/default",
                    "source_id": "default"
                }
            }
        if 'selected_camera' not in st.session_state:
            st.session_state['selected_camera'] = list(st.session_state['camera_urls'])[0]

    @st.cache_data(ttl=30)
    def fetch_json(url):
        try:
            r = requests.get(url, timeout=2)
            if r.ok:
                return r.json()
        except:
            pass
        return None

    def sidebar_add_camera():
        st.sidebar.subheader("➕ Aggiungi Camera")
        with st.sidebar.form("add_cam_form", clear_on_submit=True):
            name = st.text_input("Nome telecamera", "")
            url = st.text_input("URL MJPEG", "")
            sid = st.text_input("Source ID", "")
            submitted = st.form_submit_button("Aggiungi")
            if submitted:
                if name and url and sid:
                    st.session_state['camera_urls'][name] = {
                        "stream_url": url,
                        "source_id": sid
                    }
                    st.success(f"Camera '{name}' aggiunta!")
                else:
                    st.error("Compila tutti i campi!")

    def sidebar_camera_selector():
        st.sidebar.header("🔌 Telecamere")
        names = list(st.session_state['camera_urls'].keys())
        sel = st.sidebar.selectbox("Scegli camera", names, index=names.index(st.session_state['selected_camera']))
        st.session_state['selected_camera'] = sel
        return st.session_state['camera_urls'][sel]

    def sidebar_pipeline_control(source_id):
        st.sidebar.markdown("---")
        st.sidebar.subheader("🚦 Pipeline")
        col1, col2 = st.sidebar.columns(2)

        health = fetch_json(f"{API_BASE}/api/ip_camera/healthz/{source_id}")
        running = health and health.get("running", False)
        status = "🟢 Running" if running else "🔴 Stopped"
        st.sidebar.markdown(f"**Stato:** {status}")

        with col1:
            if st.button("▶️ Avvia"):
                r = requests.post(f"{API_BASE}/api/ip_camera/start/{source_id}")
                if r.ok:
                    st.experimental_rerun()
                else:
                    st.error(r.text)
        with col2:
            if st.button("⏹️ Ferma"):
                r = requests.post(f"{API_BASE}/api/ip_camera/stop/{source_id}")
                if r.ok:
                    st.experimental_rerun()
                else:
                    st.error(r.text)

    def sidebar_configuration(stream_url):
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Configurazione")
        refresh_rate = st.sidebar.slider("Refresh (sec)", 1, 30, 5)

        config = fetch_json(stream_url.replace('/stream', '/config')) or {}

        with st.sidebar.expander("Opzioni generali"):
            draw = st.checkbox("🎨 Disegna box", value=config.get("draw_boxes", False))
            cnt = st.checkbox("🔢 Conta oggetti", value=config.get("count_objects", False))

        with st.sidebar.expander("Linea di conteggio"):
            use_line = st.checkbox("Abilita linea", value=bool(config.get("count_line")))
            coords = config.get("count_line") or [[50, 50], [200, 50]]
            if use_line:
                canvas = st_canvas(
                    fill_color="",
                    stroke_width=2,
                    stroke_color="green",
                    background_color="#f0f0f0",
                    height=200,
                    width=200,
                    drawing_mode="line",
                    initial_drawing=[{"type": "line", "points": coords}],
                    key="countline_canvas"
                )
                if canvas.json_data and canvas.json_data["objects"]:
                    last = canvas.json_data["objects"][-1]
                    coords = [tuple(map(int, p)) for p in last["points"]]
            else:
                coords = None

        updated_behaviors = {}
        st.sidebar.markdown("**Modelli:**")
        for model_path, beh in (config.get("model_behaviors") or {}).items():
            with st.sidebar.expander(os.path.basename(model_path)):
                c = st.slider("Conf.", 0.0, 1.0, float(beh.get("confidence", 0.5)), 0.01, key=f"c_{model_path}")
                i = st.slider("IoU", 0.0, 1.0, float(beh.get("iou", 0.45)), 0.01, key=f"i_{model_path}")
                d = st.checkbox("Draw", value=beh.get("draw", False), key=f"d_{model_path}")
                co = st.checkbox("Count", value=beh.get("count", False), key=f"co_{model_path}")
                updated_behaviors[model_path] = {"confidence": c, "iou": i, "draw": d, "count": co}

        if st.sidebar.button("✅ Applica Configurazione"):
            payload = {
                "draw_boxes": draw,
                "count_objects": cnt,
                "count_line": coords,
                "model_behaviors": updated_behaviors
            }
            r = requests.post(stream_url.replace('/stream', '/config'), json=payload, timeout=3)
            if r.ok:
                st.sidebar.success("Configurazione aggiornata")
            else:
                st.sidebar.error("Errore aggiornamento")

        return refresh_rate

    def main_area(stream_url, refresh_rate):
        st.markdown("## 📺 Live Stream")
        col1, col2 = st.columns([3, 1])
        with col1:
            st_autorefresh(interval=refresh_rate * 1000, limit=None, key="refresh")
            st.image(stream_url, use_column_width=True)
        with col2:
            st.markdown("## 📊 Metriche")
            metrics = fetch_json(stream_url.replace('/stream', '/metrics')) or {}
            counters = metrics.get("counters", {})
            if counters:
                for cls, val in counters.items():
                    st.metric(label=cls, value=val)
            else:
                st.write("Nessuna metrica disponibile")

    # --- Avvio Streamlit ---
    init_session()
    st.set_page_config(page_title=PAGE_TITLE, page_icon="📷", layout="wide")
    st.title(PAGE_TITLE)

    sidebar_add_camera()
    cam = sidebar_camera_selector()
    sidebar_pipeline_control(cam["source_id"])
    refresh_rate = sidebar_configuration(cam["stream_url"])
    main_area(cam["stream_url"], refresh_rate)


def run(app):
    from flask import current_app
    with app.app_context():
        name = os.path.splitext(os.path.basename(__file__))[0]
        cfg = current_app.config['MODULES']['threads']['config'].get(name, {})
        cfg["script_path"] = os.path.abspath(__file__)
        current_app.streamlit_manager.register(name, cfg)


if __name__ == "__main__":
    run_app()
