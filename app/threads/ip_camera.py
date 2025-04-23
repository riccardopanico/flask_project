import os
import streamlit as st
import requests

def run_app():
    st.set_page_config(
        page_title="📡 IP Camera Viewer",
        page_icon="📷",
        layout="wide"
    )

    st.markdown("""
        <style>
            .title { font-size: 2em; font-weight: 600; margin-bottom: 10px; }
            .subtitle { font-size: 1.3em; font-weight: 500; margin-top: 20px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="title">📡 IP Camera Viewer con YOLO & Counter</div>', unsafe_allow_html=True)

    stream_url = 'http://192.168.0.92:8080/video'

    st.sidebar.header("🔌 Telecamere disponibili")
    st.sidebar.markdown("Seleziona la sorgente video da monitorare.")
    st.sidebar.code(stream_url)

    try:
        available = requests.head(stream_url, timeout=2).status_code == 200
    except Exception:
        available = False

    vid_col, param_col = st.columns([3, 1])

    with vid_col:
        st.markdown('<div class="subtitle">🟢 Video Live</div>', unsafe_allow_html=True)
        if available:
            st.markdown(
                f'<img src="{stream_url}" style="width:100%; border-radius:10px; box-shadow: 0 0 10px rgba(0,0,0,0.2);"/>',
                unsafe_allow_html=True
            )
        else:
            st.error("❌ Stream non raggiungibile")

    with param_col:
        st.markdown('<div class="subtitle">⚙️ Parametri YOLO</div>', unsafe_allow_html=True)
        if available:
            conf = st.slider("🎯 Confidence", 0.0, 1.0, 0.25, 0.01)
            iou = st.slider("📏 IoU Threshold", 0.0, 1.0, 0.45, 0.01)
            bb = st.toggle("📦 Bounding Boxes", value=True)
            cnt = st.toggle("🔢 Contatore Oggetti", value=True)
            orient = st.radio("📐 Orientazione Linea", ["Verticale", "Orizzontale"])
            direction = st.selectbox(
                "🔁 Direzione Conteggio",
                {
                    'rl': 'Destra → Sinistra',
                    'lr': 'Sinistra → Destra',
                    'tb': 'Alto → Basso',
                    'bt': 'Basso → Alto'
                }.keys(),
                format_func=lambda k: {
                    'rl': 'Destra → Sinistra',
                    'lr': 'Sinistra → Destra',
                    'tb': 'Alto → Basso',
                    'bt': 'Basso → Alto'
                }[k]
            )

            if st.button("✅ Applica Parametri"):
                try:
                    params_url = stream_url.replace('/video', '/set_params')
                    payload = {
                        'conf_thres': conf,
                        'iou_thres': iou,
                        'apply_bb': bb,
                        'apply_count': cnt,
                        'orientation': 0 if orient == "Verticale" else 1,
                        'direction': direction
                    }
                    r = requests.post(params_url, json=payload, timeout=3)
                    if r.ok:
                        st.success("✅ Parametri aggiornati correttamente!")
                    else:
                        st.error("❌ Errore nell'invio dei parametri.")
                except Exception as e:
                    st.error(f"❌ Eccezione durante l'invio: {e}")

            st.divider()
            st.markdown('<div class="subtitle">📈 Conteggi Correnti</div>', unsafe_allow_html=True)
            if st.button("🔄 Aggiorna Contatori"):
                try:
                    counts = requests.get(stream_url.replace('/video', '/get_counts'), timeout=2).json()
                    if counts:
                        for cls, val in counts.items():
                            st.metric(label=f"🔹 {cls}", value=val)
                    else:
                        st.info("Nessun attraversamento registrato.")
                except Exception as e:
                    st.error(f"Errore durante il fetch: {e}")
        else:
            st.info("⚠️ Configura i parametri quando lo stream è attivo.")

def run(app):
    from flask import current_app
    with app.app_context():
        name = os.path.splitext(os.path.basename(__file__))[0]
        cfg = current_app.config['MODULES']['threads']['config'].get(name, {})
        cfg["script_path"] = os.path.abspath(__file__)
        current_app.streamlit_manager.register(name, cfg)

if __name__ == "__main__":
    run_app()
