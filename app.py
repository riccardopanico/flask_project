import os
import glob
import time
import shutil
import yaml
import subprocess
import cv2
import queue
import threading
import io
from datetime import datetime
import torch
import streamlit as st
from ultralytics import YOLO
from contextlib import redirect_stdout

# ----- DIRECTORIES -----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
for d in [MODELS_DIR, DATASETS_DIR, OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# ----- SOURCE MANAGEMENT -----
def list_available_cameras(max_cameras=10):
    available = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(f"Webcam {i} (Index {i})")
            cap.release()
    return available


def select_source():
    source_options = ["webcam", "video", "image"]
    if "source_type" not in st.session_state:
        st.session_state["source_type"] = source_options[0]
    selected = st.sidebar.selectbox(
        "📡 Seleziona la sorgente", source_options,
        index=source_options.index(st.session_state["source_type"]),
        key="source_select"
    )
    st.session_state["source_type"] = selected
    return selected


def upload_file(source_type):
    file_types = {
        "video": ["mp4", "mov", "avi", "mkv", "webm"],
        "image": ["jpg", "jpeg", "png", "bmp", "tiff", "webp"]
    }.get(source_type, [])
    media_file = st.sidebar.file_uploader("📤 Carica un file", type=file_types, key="file_upload")
    if media_file:
        unique_name = f"{int(time.time())}_{media_file.name}"
        temp_path = os.path.join(TEMP_DIR, unique_name)
        with open(temp_path, "wb") as f:
            f.write(media_file.read())
        return temp_path
    return None


def select_webcam():
    cameras = list_available_cameras()
    if not cameras:
        st.sidebar.warning("⚠️ Nessuna webcam disponibile!")
        return None
    selected_cam = st.sidebar.selectbox("📸 Seleziona una webcam:", cameras, key="webcam_select")
    try:
        return int(selected_cam.split("Index ")[-1].rstrip(")"))
    except:
        st.sidebar.error("⚠️ Errore nella selezione della webcam.")
        return None

# ----- MODEL SELECTION -----
def get_model_info(model_path):
    size = os.path.getsize(model_path) / (1024 * 1024)
    return {"size": f"{size:.2f} MB"}


def select_models():
    model_files = sorted(
        glob.glob(os.path.join(MODELS_DIR, "*.pt")) +
        glob.glob(os.path.join(MODELS_DIR, "*.onnx"))
    )
    model_names = [os.path.basename(p) for p in model_files]
    if not model_names:
        st.sidebar.warning("⚠️ Nessun modello trovato in 'models/'!")
        return {}
    if "selected_models" not in st.session_state:
        st.session_state["selected_models"] = model_names[:1]
    selected = st.sidebar.multiselect(
        "📌 Seleziona i modelli", model_names,
        default=st.session_state["selected_models"]
    )
    st.session_state["selected_models"] = selected
    if selected:
        st.sidebar.subheader("📊 Dettagli Modelli Selezionati")
        for m in selected:
            info = get_model_info(os.path.join(MODELS_DIR, m))
            st.sidebar.text(f"{m} - {info['size']}")
    return {m: YOLO(os.path.join(MODELS_DIR, m)) for m in selected}

# ----- INFERENCE PARAMETERS -----
def set_inference_parameters(source_type):
    st.sidebar.subheader("📌 Parametri Inferenza")
    if "inference_params" not in st.session_state:
        st.session_state["inference_params"] = {
            "confidence": 0.5,
            "iou_threshold": 0.45,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "save_output": False,
            "save_video": False,
            "save_frames": False,
            "save_annotated_frames": False,
            "save_labels": False,
            "save_crop_boxes": False,
            "frame_skip": 1,
            "output_resolution": None,
            "num_workers": 4,
            "manual_capture_enabled": False
        }
    params = st.session_state["inference_params"]
    params["confidence"] = st.sidebar.slider(
        "🎯 Confidence Threshold", 0.0, 1.0,
        params["confidence"], 0.01
    )
    params["iou_threshold"] = st.sidebar.slider(
        "📏 IoU Threshold", 0.0, 1.0,
        params["iou_threshold"], 0.01
    )
    params["device"] = st.sidebar.selectbox(
        "💻 Seleziona dispositivo", ["cuda","mps","cpu"],
        index=["cuda","mps","cpu"].index(params["device"])
    )
    params["save_output"] = st.sidebar.checkbox(
        "💾 Salva output inferenza", value=params["save_output"]
    )
    if params["save_output"]:
        if source_type != "image":
            params["save_video"] = st.sidebar.checkbox(
                "🎥 Salva video", value=params["save_video"]
            )
        params["save_frames"] = st.sidebar.checkbox(
            "🖼️ Salva frames", value=params["save_frames"]
        )
        if params["save_frames"]:
            params["save_labels"] = st.sidebar.checkbox(
                "📝 Salva labels YOLO", value=params["save_labels"]
            )
            params["save_crop_boxes"] = st.sidebar.checkbox(
                "✂️ Salva crop dei bounding box", value=params["save_crop_boxes"]
            )
            params["save_annotated_frames"] = st.sidebar.checkbox(
                "📍 Salva frames con box", value=params["save_annotated_frames"]
            )
            params["save_only_with_detections"] = st.sidebar.checkbox(
                "💾 Salva solo se ci sono box", value=False
            )
    params["frame_skip"] = st.sidebar.slider(
        "🎞️ Inferenza ogni N frame", 1, 30, params["frame_skip"]
    )
    params["num_workers"] = st.sidebar.slider(
        "🛠️ Worker inferenza", 1,
        min(8, os.cpu_count() or 4), params["num_workers"]
    )
    resolution_options = {
        "Usa risoluzione originale": None,
        "YOLO Default (640x640)": (640, 640),
        "1280x720 (HD)": (1280, 720),
        "1920x1080 (Full HD)": (1920, 1080),
        "256x256 (Bassa Risoluzione)": (256, 256)
    }
    label = st.sidebar.selectbox(
        "📏 Seleziona risoluzione output",
        list(resolution_options.keys())
    )
    params["output_resolution"] = resolution_options[label]
    params["manual_capture_enabled"] = st.sidebar.checkbox(
        "🔲 Abilita Scatta Foto manuale",
        value=params.get("manual_capture_enabled", False)
    )
    return params

# ----- DATASET MANAGEMENT -----
def list_datasets():
    datasets = []
    if not os.path.exists(OUTPUT_DIR):
        return datasets
    for model_name in os.listdir(OUTPUT_DIR):
        model_path = os.path.join(OUTPUT_DIR, model_name)
        if os.path.isdir(model_path):
            for session in os.listdir(model_path):
                session_path = os.path.join(model_path, session)
                if os.path.isdir(session_path):
                    for split in ["train", "val", "test"]:
                        images_path = os.path.join(session_path, split, "images")
                        labels_path = os.path.join(session_path, split, "labels")
                        if os.path.exists(images_path) and os.path.exists(labels_path):
                            datasets.append({
                                "modello": model_name,
                                "data": session,
                                "path": session_path,
                                "split": split
                            })
    return datasets


def merge_datasets(selected_datasets, target_name="merged_dataset", class_list=[]):
    target_path = os.path.abspath(os.path.join(DATASETS_DIR, target_name))
    os.makedirs(target_path, exist_ok=True)
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(target_path, split, "images"), exist_ok=True)
        os.makedirs(os.path.join(target_path, split, "labels"), exist_ok=True)
    for dataset in selected_datasets:
        model_name = dataset["modello"]
        session_name = dataset["data"]
        split = dataset["split"]
        dataset_path = os.path.abspath(dataset["path"])
        for data_type in ["images", "labels"]:
            source_folder = os.path.join(dataset_path, split, data_type)
            target_folder = os.path.join(target_path, split, data_type)
            if os.path.exists(source_folder) and os.listdir(source_folder):
                for file in os.listdir(source_folder):
                    file_ext = file.split(".")[-1]
                    file_base = file.replace(f".{file_ext}", "")
                    new_file_name = f"{model_name}_{session_name}_{file_base}.{file_ext}"
                    shutil.copy(
                        os.path.join(source_folder, file),
                        os.path.join(target_folder, new_file_name)
                    )
    yaml_path = os.path.join(target_path, "data.yaml")
    data_yaml = {
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": len(class_list),
        "names": class_list
    }
    with open(yaml_path, "w") as file:
        yaml.dump(data_yaml, file, default_flow_style=False, allow_unicode=True)
    return target_path


def delete_dataset(dataset_path):
    if os.path.exists(dataset_path):
        shutil.rmtree(dataset_path, ignore_errors=True)
        time.sleep(0.5)
        return not os.path.exists(dataset_path)
    return False


def dataset_management_ui():
    datasets = list_datasets()
    if not datasets:
        st.sidebar.warning("⚠️ Nessun dataset trovato in `output/`.")
        return
    if st.button("🔄 Aggiorna lista"):
        st.rerun()
    selected_datasets = []
    for dataset in datasets:
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
        with col1:
            st.text(f"📂 {dataset['modello']}")
        with col2:
            st.text(f"📅 {dataset['data']}")
        with col3:
            st.text(f"🔹 {dataset['split']}")
        with col4:
            sel = st.checkbox(
                "Seleziona", key=f"{dataset['modello']}_{dataset['data']}_{dataset['split']}"
            )
            if sel:
                selected_datasets.append(dataset)
        with col5:
            if st.button(
                "🗑️", key=f"delete_{dataset['modello']}_{dataset['data']}_{dataset['split']}"
            ):
                if delete_dataset(dataset['path']):
                    st.success(f"✅ Dataset `{dataset['modello']}` eliminato con successo.")
                    st.rerun()
                else:
                    st.error(f"❌ Errore nell'eliminazione di `{dataset['modello']}`.")
    if not selected_datasets:
        st.warning("⚠️ Seleziona almeno un dataset per procedere con il merge.")
        return
    if "dataset_name" not in st.session_state:
        st.session_state["dataset_name"] = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dataset_name = st.text_input(
        "Nome per il dataset unito:",
        st.session_state["dataset_name"],
        key="dataset_name_input"
    )
    st.session_state["dataset_name"] = dataset_name
    class_list = st.session_state.get("class_input", "model_1\nmodel_2\nmodel_3").split("\n")
    class_list = [cls.strip() for cls in class_list if cls.strip()]
    if st.button("Conferma/Merge"):
        if dataset_name.strip():
            target_path = merge_datasets(selected_datasets, dataset_name, class_list)
            st.success(f"✅ Merge completato! Dataset salvato in `{target_path}`")
        else:
            st.warning("⚠️ Devi inserire un nome per il dataset unito!")

# ----- TRAINING UI -----
def select_pretrained_model():
    pt_files = sorted(glob.glob(os.path.join(MODELS_DIR, "*.pt")))
    if not pt_files:
        st.warning("⚠️ Nessun modello trovato nella cartella 'models'!")
        return None
    model_names = [os.path.basename(p) for p in pt_files]
    selected_model = st.sidebar.selectbox("📌 Seleziona il modello YOLO", model_names)
    return os.path.join(MODELS_DIR, selected_model)


def select_training_dataset():
    yaml_files = sorted(
        glob.glob(os.path.join(DATASETS_DIR, "**", "*.yaml"), recursive=True)
    )
    if not yaml_files:
        st.warning("⚠️ Nessun dataset trovato nella cartella 'datasets'!")
        return None
    dataset_names = [os.path.relpath(f, DATASETS_DIR) for f in yaml_files]
    selected_dataset = st.sidebar.selectbox("📂 Seleziona dataset di allenamento", dataset_names)
    return os.path.join(DATASETS_DIR, selected_dataset)


def training_interface():
    st.subheader("🎯 Training YOLOv8")
    model_path = select_pretrained_model()
    dataset_path = select_training_dataset()
    if not model_path or not dataset_path:
        return
    epochs = st.sidebar.slider("Epochs", 1, 1000, 50)
    batch_size = st.sidebar.slider("Batch Size", 1, 128, 16)
    learning_rate = st.sidebar.number_input("Learning Rate (lr0)", 1e-6, 1.0, 0.01, step=0.001)
    optimizer = st.sidebar.selectbox("Optimizer", ["SGD", "Adam"], index=1)
    momentum = None
    if optimizer == "SGD":
        momentum = st.sidebar.slider("Momentum (solo per SGD)", 0.0, 1.0, 0.937, 0.001)
    use_early_stopping = st.sidebar.checkbox("Usa Early Stopping", value=False)
    patience = None
    if use_early_stopping:
        patience = st.sidebar.slider("Patience Early Stopping (epoch)", 1, 200, 50)
    single_cls = st.sidebar.checkbox("Single Class Detection", value=False)
    use_resume = st.sidebar.checkbox("Resume training (se possibile)", value=False)

    model = YOLO(model_path)
    with io.StringIO() as buf, redirect_stdout(buf):
        model.info()
        summary_str = buf.getvalue()
    with st.expander("Mostra struttura modello YOLO"):
        st.text(summary_str)
    st.write("---")
    freeze_value = st.sidebar.slider("Numero di layer da congelare (freeze)", 0, 30, 0)
    start_tensorboard = st.sidebar.checkbox("Lancia TensorBoard", value=False)
    tb_process = None
    if st.button("🚀 Avvia Training"):
        st.success("Training avviato! Controlla la console per i dettagli.")
        if start_tensorboard:
            try:
                tb_process = subprocess.Popen(["tensorboard", "--logdir", "runs/train", "--port", "6006"]);
                time.sleep(2);
                st.info("TensorBoard avviato su http://localhost:6006")
            except FileNotFoundError:
                st.warning("TensorBoard non trovato! Assicurati di installarlo.")
        train_args = {
            "optimizer": optimizer,
            "data": dataset_path,
            "epochs": epochs,
            "batch": batch_size,
            "lr0": learning_rate,
            "single_cls": single_cls,
            "freeze": freeze_value,
            # augmentazioni realistiche
            "translate": 0.1,
            "scale": 0.15,
            "shear": 0.1,
            "hsv_h": 0.015,
            "hsv_s": 0.6,
            "hsv_v": 0.4,
            "fliplr": 0.5,
            "flipud": 0.5
        }
        if optimizer == "SGD" and momentum is not None:
            train_args["momentum"] = momentum
        if use_early_stopping and patience is not None:
            train_args["patience"] = patience
        if use_resume:
            train_args["resume"] = True
        model.train(**train_args)
        st.success("✅ Training completato!")
        if tb_process:
            tb_process.terminate()
            st.info("TensorBoard arrestato.")

# ----- INFERENCE ENGINE -----
class InferenceEngine:
    def __init__(self, models, source_type, source, session_id, static_class_id=None, **params):
        self.models = models
        self.source_type = source_type
        self.source = source
        self.session_id = session_id or "default_session"
        self.static_class_id = static_class_id
        self.params = params
        self.video_queues = {}
        self.video_threads = {}
        self.video_writers = {}

    def run(self, num_columns):
        grid = [st.columns(num_columns) for _ in range((len(self.models) + num_columns - 1) // num_columns)]
        cap = cv2.VideoCapture(self.source if self.source_type != "webcam" else int(self.source))
        if not cap.isOpened():
            st.error("Errore nell'apertura del video o webcam.")
            return
        fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
        orig_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        frame_size = self.params["output_resolution"] or orig_size
        frame_holders = [col.empty() for row in grid for col in row]
        output_dirs = {model: self._create_output_dir(model) for model in self.models}
        if self.params.get("save_video", False):
            self._initialize_video_workers(output_dirs, frame_size, fps)
        frame_counter = 0
        while cap.isOpened() and st.session_state.get("inf_running", False):
            success, frame = cap.read()
            if not success:
                break
            frame_counter += 1
            if frame_counter % self.params["frame_skip"] != 0:
                continue
            if self.params["output_resolution"]:
                frame = cv2.resize(frame, self.params["output_resolution"])
            for i, (model_name, model) in enumerate(self.models.items()):
                model.to(self.params["device"])
                results = model(frame, conf=self.params["confidence"], iou=self.params["iou_threshold"])
                annotated = results[0].plot()
                frame_holders[i].image(annotated, channels="BGR")
                if self.params.get("save_output", False):
                    self._save_frame_and_labels(frame, annotated, output_dirs[model_name], model_name, frame_counter, results)
                if st.session_state.get("save_frame_flag", False):
                    self._save_manual_frame(frame, annotated, output_dirs[model_name], frame_counter, results)
            if st.session_state.get("save_frame_flag", False):
                st.session_state["save_frame_flag"] = False
        cap.release()
        cv2.destroyAllWindows()
        self._terminate_video_workers()

    def _create_output_dir(self, model_name):
        base_output_dir = os.path.join(OUTPUT_DIR, model_name, self.session_id)
        paths = {
            "train_images": os.path.join(base_output_dir, "train", "images"),
            "train_labels": os.path.join(base_output_dir, "train", "labels"),
            "crops": os.path.join(base_output_dir, "crops"),
            "videos": os.path.join(base_output_dir, "videos"),
            "manual": os.path.join(base_output_dir, "manual_captures")
        }
        for p in paths.values():
            os.makedirs(p, exist_ok=True)
        return paths

    def _initialize_video_workers(self, output_dirs, frame_size, fps):
        codec = cv2.VideoWriter_fourcc(*'mp4v')
        num_workers = self.params.get("num_workers", 4)
        for model_name, odir in output_dirs.items():
            video_path = os.path.join(odir["videos"], f"{model_name}_output.mp4")
            self.video_queues[model_name] = queue.Queue(maxsize=30)
            self.video_writers[model_name] = cv2.VideoWriter(video_path, codec, fps, frame_size)
            threads = []
            for _ in range(num_workers):
                t = threading.Thread(target=self._video_worker, args=(model_name,), daemon=True)
                t.start()
                threads.append(t)
            self.video_threads[model_name] = threads

    def _video_worker(self, model_name):
        while True:
            frame = self.video_queues[model_name].get()
            if frame is None:
                break
            self.video_writers[model_name].write(frame)
            self.video_queues[model_name].task_done()

    def _terminate_video_workers(self):
        for model_name, threads in self.video_threads.items():
            for _ in threads:
                self.video_queues[model_name].put(None)
            for t in threads:
                t.join()
            self.video_writers[model_name].release()

    def _save_frame_and_labels(self, frame, annotated_frame, output_dir, model_name, frame_counter, results):
        has_detections = results[0].boxes is not None and len(results[0].boxes) > 0
        if self.params.get("save_only_with_detections", False) and not has_detections:
            return
        if self.params.get("save_frames", False):
            to_save = annotated_frame if self.params.get("save_annotated_frames", False) else frame
            cv2.imwrite(os.path.join(output_dir["train_images"], f"frame_{frame_counter}.jpg"), to_save)
        if self.params.get("save_video", False):
            self.video_queues[model_name].put(
                annotated_frame if self.params.get("save_annotated_frames", False) else frame
            )
        if self.params.get("save_labels", False):
            self._save_yolo_labels(output_dir["train_labels"], frame_counter, results)
        if self.params.get("save_crop_boxes", False):
            self._save_cropped_boxes(frame, output_dir["crops"], frame_counter, results)

    def _save_manual_frame(self, frame, annotated_frame, output_dir, frame_counter, results):
        if not (self.params.get("save_output", False) and self.params.get("save_frames", False)):
            return
        has_detections = results[0].boxes is not None and len(results[0].boxes) > 0
        if self.params.get("save_only_with_detections", False) and not has_detections:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        to_save = annotated_frame if self.params.get("save_annotated_frames", False) else frame
        cv2.imwrite(os.path.join(output_dir["manual"], f"{ts}.jpg"), to_save)
        if self.params.get("save_labels", False):
            lbl_path = os.path.join(output_dir["manual"], f"{ts}.txt")
            with open(lbl_path, "w") as f:
                for box in (results[0].boxes or []):
                    x_center, y_center, w, h = box.xywhn.tolist()[0]
                    cls_id = self.static_class_id if self.static_class_id is not None else int(box.cls)
                    f.write(f"{cls_id} {x_center} {y_center} {w} {h}\n")
        if self.params.get("save_crop_boxes", False):
            for idx, box in enumerate(results[0].boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                crop = frame[y1:y2, x1:x2]
                path = os.path.join(output_dir["manual"], f"{ts}_crop{idx}.jpg")
                cv2.imwrite(path, crop)

    def _save_yolo_labels(self, labels_dir, frame_counter, results):
        os.makedirs(labels_dir, exist_ok=True)
        path = os.path.join(labels_dir, f"frame_{frame_counter}.txt")
        with open(path, "w") as f:
            if results[0].boxes is not None:
                for box in results[0].boxes:
                    x_center, y_center, w, h = box.xywhn.tolist()[0]
                    cls_id = self.static_class_id if self.static_class_id is not None else int(box.cls)
                    f.write(f"{cls_id} {x_center} {y_center} {w} {h}\n")

    def _save_cropped_boxes(self, frame, crops_dir, frame_counter, results):
        os.makedirs(crops_dir, exist_ok=True)
        for idx, box in enumerate(results[0].boxes):
            try:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                crop = frame[y1:y2, x1:x2]
                path = os.path.join(crops_dir, f"crop_{frame_counter}_{idx}.jpg")
                cv2.imwrite(path, crop)
            except:
                pass

# ----- APPLICATION ENTRYPOINT -----
def run_app():
    st.title("YOLO Model Inference & Training")
    dataset_management_ui()
    st.sidebar.header("Training YOLO")
    training_interface()
    models = select_models()
    source_type = select_source()
    source = select_webcam() if source_type == "webcam" else upload_file(source_type)
    if source is None:
        st.warning("⚠️ Seleziona una sorgente valida prima di avviare l'inferenza.")
        return
    params = set_inference_parameters(source_type)
    st.sidebar.subheader("Inserisci le Classi")
    default_classes = "model_1\nmodel_2\nmodel_3"
    class_input = st.sidebar.text_area(
        "Inserisci le classi (una per riga):",
        value=st.session_state.get("class_input", default_classes),
        key="class_textarea"
    )
    class_list = [cls.strip() for cls in class_input.split("\n") if cls.strip()]
    st.session_state["class_input"] = class_input
    selected_class_id = None
    if class_list:
        st.sidebar.subheader("Seleziona la Classe di Riferimento")
        selected_class = st.sidebar.radio(
            "Classe da usare come ID fisso:", class_list,
            key="class_radio"
        )
        selected_class_id = class_list.index(selected_class)
    num_columns = st.sidebar.slider("Numero di colonne", 1, 12, 3)
    if "inf_running" not in st.session_state:
        st.session_state["inf_running"] = False
    if st.sidebar.button("▶️ Avvia Inferenza"):
        st.session_state["inf_running"] = True
        st.session_state["save_frame_flag"] = False
    if st.sidebar.button("⏹️ Ferma Inferenza"):
        st.session_state["inf_running"] = False
    if st.session_state.get("inf_running") and params.get("manual_capture_enabled", False):
        if st.sidebar.button("📸 Scatta Foto"):
            st.session_state["save_frame_flag"] = True
    session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") if params.get("save_output") else "temp_session"
    engine = InferenceEngine(
        models, source_type, source, session_id,
        static_class_id=selected_class_id, **params
    )
    if st.session_state.get("inf_running"):
        engine.run(num_columns)

if __name__ == "__main__":
    st.set_page_config(page_title="YOLOv8 Streamlit Inference", layout="wide")
    run_app()
