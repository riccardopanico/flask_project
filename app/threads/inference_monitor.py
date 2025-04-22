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

# ----- DIRECTORY CONFIGURATION -----
# assumi che la struttura sia: PROJECT_ROOT/app/threads/inference.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR      = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR    = os.path.join(DATA_DIR, "models")
DATASETS_DIR  = os.path.join(DATA_DIR, "datasets")
OUTPUT_DIR    = os.path.join(DATA_DIR, "output")
TEMP_DIR      = os.path.join(DATA_DIR, "temp")

for d in (DATA_DIR, MODELS_DIR, DATASETS_DIR, OUTPUT_DIR, TEMP_DIR):
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
    options = ["webcam", "video", "image"]
    if "source_type" not in st.session_state:
        st.session_state["source_type"] = options[0]
    sel = st.sidebar.selectbox(
        "📡 Seleziona la sorgente", options,
        index=options.index(st.session_state["source_type"]),
        key="source_select"
    )
    st.session_state["source_type"] = sel
    return sel

def upload_file(source_type):
    types = {
        "video": ["mp4","mov","avi","mkv","webm"],
        "image": ["jpg","jpeg","png","bmp","tiff","webp"]
    }.get(source_type, [])
    f = st.sidebar.file_uploader("📤 Carica un file", type=types, key="file_upload")
    if f:
        name = f"{int(time.time())}_{f.name}"
        path = os.path.join(TEMP_DIR, name)
        with open(path, "wb") as out:
            out.write(f.read())
        return path
    return None

def select_webcam():
    cams = list_available_cameras()
    if not cams:
        st.sidebar.warning("⚠️ Nessuna webcam disponibile!")
        return None
    sel = st.sidebar.selectbox("📸 Seleziona una webcam:", cams, key="webcam_select")
    try:
        return int(sel.split("Index ")[-1].rstrip(")"))
    except:
        st.sidebar.error("⚠️ Errore nella selezione della webcam.")
        return None

# ----- MODEL SELECTION -----
def get_model_info(path):
    size_mb = os.path.getsize(path) / (1024*1024)
    return {"size": f"{size_mb:.2f} MB"}

def select_models():
    files = sorted(glob.glob(os.path.join(MODELS_DIR,"*.pt")) +
                   glob.glob(os.path.join(MODELS_DIR,"*.onnx")))
    names = [os.path.basename(p) for p in files]
    if not names:
        st.sidebar.warning("⚠️ Nessun modello trovato in 'models/'!")
        return {}
    if "selected_models" not in st.session_state:
        st.session_state["selected_models"] = names[:1]
    sel = st.sidebar.multiselect(
        "📌 Seleziona i modelli", names,
        default=st.session_state["selected_models"]
    )
    st.session_state["selected_models"] = sel
    if sel:
        st.sidebar.subheader("📊 Dettagli Modelli")
        for m in sel:
            info = get_model_info(os.path.join(MODELS_DIR,m))
            st.sidebar.text(f"{m} - {info['size']}")
    return {m: YOLO(os.path.join(MODELS_DIR,m)) for m in sel}

# ----- INFERENCE PARAMETERS -----
def set_inference_parameters(source_type):
    st.sidebar.subheader("📌 Parametri Inferenza")
    if "inference_params" not in st.session_state:
        st.session_state["inference_params"] = {
            "confidence":0.5,"iou_threshold":0.45,
            "device":"cuda" if torch.cuda.is_available() else "cpu",
            "save_output":False,"save_video":False,"save_frames":False,
            "save_annotated_frames":False,"save_labels":False,
            "save_crop_boxes":False,"frame_skip":1,
            "output_resolution":None,"num_workers":4,
            "manual_capture_enabled":False
        }
    p = st.session_state["inference_params"]
    p["confidence"] = st.sidebar.slider("🎯 Confidence",0.0,1.0,p["confidence"],0.01)
    p["iou_threshold"] = st.sidebar.slider("📏 IoU",0.0,1.0,p["iou_threshold"],0.01)
    p["device"] = st.sidebar.selectbox("💻 Dispositivo",["cuda","mps","cpu"],
                                       index=["cuda","mps","cpu"].index(p["device"]))
    p["save_output"] = st.sidebar.checkbox("💾 Salva output",value=p["save_output"])
    if p["save_output"]:
        if source_type!="image":
            p["save_video"]=st.sidebar.checkbox("🎥 Salva video",value=p["save_video"])
        p["save_frames"]=st.sidebar.checkbox("🖼️ Salva frames",value=p["save_frames"])
        if p["save_frames"]:
            p["save_labels"]=st.sidebar.checkbox("📝 Salva labels",value=p["save_labels"])
            p["save_crop_boxes"]=st.sidebar.checkbox("✂️ Salva crop",value=p["save_crop_boxes"])
            p["save_annotated_frames"]=st.sidebar.checkbox("📍 Salva frames box",value=p["save_annotated_frames"])
            p["save_only_with_detections"]=st.sidebar.checkbox("💾 Solo detections",value=False)
    p["frame_skip"] = st.sidebar.slider("🎞️ Frame skip",1,30,p["frame_skip"])
    p["num_workers"] = st.sidebar.slider("🛠️ Workers",1,min(8,os.cpu_count() or 4),p["num_workers"])
    opts = {
        "Originale":None,"YOLO Default (640x640)":(640,640),
        "1280x720 (HD)":(1280,720),"1920x1080 (Full HD)":(1920,1080),
        "256x256 (Bassa)":(256,256)
    }
    lbl = st.sidebar.selectbox("📏 Risoluzione",list(opts.keys()))
    p["output_resolution"] = opts[lbl]
    p["manual_capture_enabled"] = st.sidebar.checkbox("🔲 Scatta manuale",value=p["manual_capture_enabled"])
    return p

# ----- DATASET MANAGEMENT -----
def list_datasets():
    out=[]
    if not os.path.exists(OUTPUT_DIR):
        return out
    for mdl in os.listdir(OUTPUT_DIR):
        mp=os.path.join(OUTPUT_DIR,mdl)
        if os.path.isdir(mp):
            for sess in os.listdir(mp):
                sp=os.path.join(mp,sess)
                if os.path.isdir(sp):
                    for split in ("train","val","test"):
                        ip=os.path.join(sp,split,"images")
                        lp=os.path.join(sp,split,"labels")
                        if os.path.exists(ip) and os.path.exists(lp):
                            out.append({"modello":mdl,"data":sess,"path":sp,"split":split})
    return out

def merge_datasets(selected, target="merged_dataset", classes=[]):
    tgt=os.path.join(DATASETS_DIR,target)
    os.makedirs(tgt,exist_ok=True)
    for sp in ("train","val","test"):
        os.makedirs(os.path.join(tgt,sp,"images"),exist_ok=True)
        os.makedirs(os.path.join(tgt,sp,"labels"),exist_ok=True)
    for d in selected:
        mn, ses, sp = d["modello"], d["data"], d["split"]
        dp = d["path"]
        for dt in ("images","labels"):
            sf=os.path.join(dp,sp,dt)
            tf=os.path.join(tgt,sp,dt)
            if os.path.exists(sf):
                for f in os.listdir(sf):
                    ext=f.split(".")[-1]
                    base=f.replace(f".{ext}","")
                    new=f"{mn}_{ses}_{base}.{ext}"
                    shutil.copy(os.path.join(sf,f),os.path.join(tf,new))
    yml=os.path.join(tgt,"data.yaml")
    data_yaml={"train":"train/images","val":"val/images","test":"test/images",
               "nc":len(classes),"names":classes}
    with open(yml,"w") as yf:
        yaml.dump(data_yaml,yf,default_flow_style=False,allow_unicode=True)
    return tgt

def delete_dataset(path):
    if os.path.exists(path):
        shutil.rmtree(path,ignore_errors=True)
        time.sleep(0.5)
        return not os.path.exists(path)
    return False

def dataset_management_ui():
    ds = list_datasets()
    if not ds:
        st.sidebar.warning("⚠️ Nessun dataset in output/")
        return
    if st.button("🔄 Aggiorna"):
        st.rerun()
    sel=[]
    for d in ds:
        c1,c2,c3,c4,c5 = st.columns([3,2,1,1,1])
        with c1: st.text(f"📂 {d['modello']}")
        with c2: st.text(f"📅 {d['data']}")
        with c3: st.text(f"🔹 {d['split']}")
        with c4:
            chk = st.checkbox("Seleziona",key=f"{d['modello']}_{d['data']}_{d['split']}")
            if chk: sel.append(d)
        with c5:
            if st.button("🗑️",key=f"del_{d['modello']}_{d['data']}_{d['split']}"):
                if delete_dataset(d["path"]):
                    st.success(f"✅ Eliminato `{d['modello']}`")
                    st.rerun()
                else:
                    st.error(f"❌ Errore eliminazione `{d['modello']}`")
    if not sel:
        st.warning("⚠️ Seleziona almeno un dataset")
        return
    if "dataset_name" not in st.session_state:
        st.session_state["dataset_name"] = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    name = st.text_input("Nome dataset unito:",st.session_state["dataset_name"],key="ds_name")
    st.session_state["dataset_name"]=name
    classes = st.session_state.get("class_input","model_1\nmodel_2\nmodel_3").split("\n")
    classes = [c.strip() for c in classes if c.strip()]
    if st.button("Conferma Merge"):
        if name.strip():
            tp = merge_datasets(sel,name,classes)
            st.success(f"✅ Merge completato in `{tp}`")
        else:
            st.warning("⚠️ Inserisci un nome!")

# ----- TRAINING UI -----
def select_pretrained_model():
    pts = sorted(glob.glob(os.path.join(MODELS_DIR,"*.pt")))
    if not pts:
        st.warning("⚠️ Nessun modello in models/")
        return None
    names=[os.path.basename(p) for p in pts]
    sel=st.sidebar.selectbox("📌 Seleziona modello",names)
    return os.path.join(MODELS_DIR,sel)

def select_training_dataset():
    yams=sorted(glob.glob(os.path.join(DATASETS_DIR,"**","*.yaml"),recursive=True))
    if not yams:
        st.warning("⚠️ Nessun dataset in datasets/")
        return None
    names=[os.path.relpath(f,DATASETS_DIR) for f in yams]
    sel=st.sidebar.selectbox("📂 Seleziona dataset",names)
    return os.path.join(DATASETS_DIR,sel)

def training_interface():
    st.subheader("🎯 Training YOLOv8")
    mp = select_pretrained_model()
    dp = select_training_dataset()
    if not mp or not dp:
        return
    ep = st.sidebar.slider("Epochs",1,1000,50)
    bs = st.sidebar.slider("Batch size",1,128,16)
    lr = st.sidebar.number_input("Learning Rate",1e-6,1.0,0.01,step=0.001)
    opt = st.sidebar.selectbox("Optimizer",["SGD","Adam"],index=1)
    mom=None
    if opt=="SGD":
        mom=st.sidebar.slider("Momentum (SGD)",0.0,1.0,0.937,0.001)
    early=st.sidebar.checkbox("Early Stopping")
    pat=None
    if early:
        pat=st.sidebar.slider("Patience",1,200,50)
    single=st.sidebar.checkbox("Single Class")
    resume=st.sidebar.checkbox("Resume training")

    model = YOLO(mp)
    with io.StringIO() as buf, redirect_stdout(buf):
        model.info()
        summ=buf.getvalue()
    with st.expander("Struttura modello"):
        st.text(summ)
    st.write("---")
    freeze=st.sidebar.slider("Freeze layers",0,30,0)
    tb=False
    if st.sidebar.button("🚀 Avvia Training"):
        st.success("Training avviato! Controlla console.")
        if st.sidebar.checkbox("Lancia TensorBoard", value=False):
            try:
                tb_proc = subprocess.Popen(["tensorboard","--logdir","runs/train","--port","6006"])
                time.sleep(2)
                st.info("TensorBoard su http://localhost:6006")
            except FileNotFoundError:
                st.warning("TensorBoard non trovato!")
        args={"optimizer":opt,"data":dp,"epochs":ep,"batch":bs,"lr0":lr,
              "single_cls":single,"freeze":freeze,
              "translate":0.1,"scale":0.15,"shear":0.1,
              "hsv_h":0.015,"hsv_s":0.6,"hsv_v":0.4,
              "fliplr":0.5,"flipud":0.5}
        if mom is not None: args["momentum"]=mom
        if early and pat is not None: args["patience"]=pat
        if resume: args["resume"]=True
        model.train(**args)
        st.success("✅ Training completato!")
        if 'tb_proc' in locals():
            tb_proc.terminate()
            st.info("TensorBoard arrestato.")

# ----- INFERENCE ENGINE -----
class InferenceEngine:
    def __init__(self, models, src_type, source, sess_id, static_class_id=None, **params):
        self.models = models
        self.source_type = src_type
        self.source = source
        self.session_id = sess_id or "default_session"
        self.static_class_id = static_class_id
        self.params = params
        self.video_queues = {}
        self.video_threads = {}
        self.video_writers = {}

    def run(self, num_columns):
        grid = [st.columns(num_columns) for _ in range((len(self.models)+num_columns-1)//num_columns)]
        cap = cv2.VideoCapture(self.source if self.source_type!="webcam" else int(self.source))
        if not cap.isOpened():
            st.error("Errore apertura video/webcam.")
            return
        fps = int(cap.get(cv2.CAP_PROP_FPS) or 30)
        orig = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        frame_size = self.params["output_resolution"] or orig
        holders = [c.empty() for row in grid for c in row]
        out_dirs = {m: self._create_output_dir(m) for m in self.models}
        if self.params.get("save_video",False):
            self._initialize_video_workers(out_dirs, frame_size, fps)
        cnt=0
        while cap.isOpened() and st.session_state.get("inf_running",False):
            ok, frame = cap.read()
            if not ok: break
            cnt+=1
            if cnt % self.params["frame_skip"]!=0: continue
            if self.params["output_resolution"]:
                frame = cv2.resize(frame, self.params["output_resolution"])
            for i,(m_name,m) in enumerate(self.models.items()):
                m.to(self.params["device"])
                res = m(frame,conf=self.params["confidence"],iou=self.params["iou_threshold"])
                ann = res[0].plot()
                holders[i].image(ann,channels="BGR")
                if self.params.get("save_output"):
                    self._save_frame_and_labels(frame,ann,out_dirs[m_name],m_name,cnt,res)
                if st.session_state.get("save_frame_flag",False):
                    self._save_manual_frame(frame,ann,out_dirs[m_name],cnt,res)
            if st.session_state.get("save_frame_flag",False):
                st.session_state["save_frame_flag"]=False
        cap.release()
        cv2.destroyAllWindows()
        self._terminate_video_workers()

    def _create_output_dir(self, model_name):
        base = os.path.join(OUTPUT_DIR, model_name, self.session_id)
        paths={
            "train_images":os.path.join(base,"train","images"),
            "train_labels":os.path.join(base,"train","labels"),
            "crops":os.path.join(base,"crops"),
            "videos":os.path.join(base,"videos"),
            "manual":os.path.join(base,"manual_captures")
        }
        for p in paths.values():
            os.makedirs(p,exist_ok=True)
        return paths

    def _initialize_video_workers(self, out_dirs, frame_size, fps):
        codec = cv2.VideoWriter_fourcc(*'mp4v')
        nw = self.params.get("num_workers",4)
        for m,odir in out_dirs.items():
            vpath = os.path.join(odir["videos"],f"{m}_output.mp4")
            self.video_queues[m] = queue.Queue(maxsize=30)
            self.video_writers[m] = cv2.VideoWriter(vpath,codec,fps,frame_size)
            threads=[]
            for _ in range(nw):
                t=threading.Thread(target=self._video_worker,args=(m,),daemon=True)
                t.start()
                threads.append(t)
            self.video_threads[m]=threads

    def _video_worker(self, model_name):
        while True:
            frame=self.video_queues[model_name].get()
            if frame is None: break
            self.video_writers[model_name].write(frame)
            self.video_queues[model_name].task_done()

    def _terminate_video_workers(self):
        for m,threads in self.video_threads.items():
            for _ in threads: self.video_queues[m].put(None)
            for t in threads: t.join()
            self.video_writers[m].release()

    def _save_frame_and_labels(self, frame, ann, out_dir, m_name, cnt, res):
        has_det = res[0].boxes is not None and len(res[0].boxes)>0
        if self.params.get("save_only_with_detections",False) and not has_det:
            return
        if self.params.get("save_frames",False):
            to_save = ann if self.params.get("save_annotated_frames",False) else frame
            cv2.imwrite(os.path.join(out_dir["train_images"],f"frame_{cnt}.jpg"),to_save)
        if self.params.get("save_video",False):
            self.video_queues[m_name].put(ann if self.params.get("save_annotated_frames",False) else frame)
        if self.params.get("save_labels",False):
            self._save_yolo_labels(out_dir["train_labels"],cnt,res)
        if self.params.get("save_crop_boxes",False):
            self._save_cropped_boxes(frame,out_dir["crops"],cnt,res)

    def _save_manual_frame(self, frame, ann, out_dir, cnt, res):
        if not (self.params.get("save_output",False) and self.params.get("save_frames",False)):
            return
        has_det = res[0].boxes is not None and len(res[0].boxes)>0
        if self.params.get("save_only_with_detections",False) and not has_det:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        to_save = ann if self.params.get("save_annotated_frames",False) else frame
        cv2.imwrite(os.path.join(out_dir["manual"],f"{ts}.jpg"),to_save)
        if self.params.get("save_labels",False):
            lp=os.path.join(out_dir["manual"],f"{ts}.txt")
            with open(lp,"w") as f:
                for box in (res[0].boxes or []):
                    x_center,y_center,w,h = box.xywhn.tolist()[0]
                    cls_id = self.static_class_id if self.static_class_id is not None else int(box.cls)
                    f.write(f"{cls_id} {x_center} {y_center} {w} {h}\n")
        if self.params.get("save_crop_boxes",False):
            for idx,box in enumerate(res[0].boxes):
                try:
                    x1,y1,x2,y2 = map(int,box.xyxy[0])
                    crop=frame[y1:y2,x1:x2]
                    cv2.imwrite(os.path.join(out_dir["manual"],f"{ts}_crop{idx}.jpg"),crop)
                except: pass

# ----- ENTRYPOINT -----
def run_app():
    st.set_page_config(page_title="YOLOv8 Streamlit Inference", layout="wide")
    st.title("YOLO Model Inference & Training")
    dataset_management_ui()
    st.sidebar.header("Training YOLO")
    training_interface()
    models = select_models()
    src_type = select_source()
    src = select_webcam() if src_type=="webcam" else upload_file(src_type)
    if src is None:
        st.warning("⚠️ Seleziona sorgente valida.")
        return
    params = set_inference_parameters(src_type)
    st.sidebar.subheader("Inserisci le Classi")
    default="model_1\nmodel_2\nmodel_3"
    cls_input = st.sidebar.text_area("Classi (una riga ciascuna)",value=st.session_state.get("class_input",default),key="class_textarea")
    cls_list=[c.strip() for c in cls_input.split("\n") if c.strip()]
    st.session_state["class_input"]=cls_input
    sel_cls_id=None
    if cls_list:
        st.sidebar.subheader("Classe di Riferimento")
        sel = st.sidebar.radio("Classe fissa",cls_list,key="class_radio")
        sel_cls_id=cls_list.index(sel)
    num_cols = st.sidebar.slider("Numero colonne",1,12,3)
    if "inf_running" not in st.session_state:
        st.session_state["inf_running"]=False
    if st.sidebar.button("▶️ Avvia Inferenza"):
        st.session_state["inf_running"]=True
        st.session_state["save_frame_flag"]=False
    if st.sidebar.button("⏹️ Ferma Inferenza"):
        st.session_state["inf_running"]=False
    if st.session_state.get("inf_running") and params.get("manual_capture_enabled"):
        if st.sidebar.button("📸 Scatta Foto"):
            st.session_state["save_frame_flag"]=True
    sess_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") if params.get("save_output") else "temp_session"
    engine = InferenceEngine(models,src_type,src,sess_id,static_class_id=sel_cls_id,**params)
    if st.session_state.get("inf_running"):
        engine.run(num_cols)

if __name__ == "__main__":
    run_app()
