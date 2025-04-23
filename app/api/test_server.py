from flask import Flask, Response, request, jsonify
import cv2
from ultralytics import YOLO
from ultralytics.solutions.object_counter import ObjectCounter

app = Flask(__name__)
print("Flask app avviato==============================================")
# Inizializza videocamera e modello YOLOv11n (80 classi COCO)
cap = cv2.VideoCapture(0)
model = YOLO('yolo11n')

# ObjectCounter senza finestre di debug
counter = ObjectCounter(show=False, show_in=False, show_out=False)

# Contatori per classe
class_counts = {}

# Parametri di default
conf_thres   = 0.25    # soglia di confidenza
iou_thres    = 0.45    # soglia IoU
apply_bb     = True    # disegna bounding box
apply_count  = True    # abilita object counting
orientation  = 0       # 0 = verticale, 1 = orizzontale
direction    = 'rl'    # 'rl','lr','tb','bt'

def generate_frames():
    initialized = False
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 1) Bounding box
        if apply_bb:
            results = model(frame, conf=conf_thres, iou=iou_thres)[0]
            frame = results.plot()

        h, w = frame.shape[:2]
        # 2) Definisci linea di conteggio una sola volta
        if apply_count and not initialized:
            if orientation == 0:
                x = w // 2
                counter.region = [(x, 0), (x, h)]
            else:
                y = h // 2
                counter.region = [(0, y), (w, y)]
            counter.region_initialized = True
            initialized = True

        # 3) Counting e overlay
        if apply_count:
            res = counter.process(frame)
            frame = res.plot_im

            # Aggiorna class_counts da res.events
            for ev in getattr(res, 'events', []):
                cls = ev.cls_name  # nome della classe
                class_counts[cls] = class_counts.get(cls, 0) + 1

            # Seleziona quale valore mostrare
            if direction in ('rl', 'tb'):
                count_val = getattr(res, 'in_count', 0)
            else:
                count_val = getattr(res, 'out_count', 0)

            cv2.putText(
                frame,
                f"Count: {count_val}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        # 4) Encode e stream MJPEG
        _, buf = cv2.imencode('.jpg', frame)
        jpg = buf.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')

@app.route('/video')
def video():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/set_params', methods=['POST'])
def set_params():
    global conf_thres, iou_thres, apply_bb, apply_count, orientation, direction
    data = request.get_json(force=True)
    if 'conf_thres'  in data: conf_thres   = float(data['conf_thres'])
    if 'iou_thres'   in data: iou_thres    = float(data['iou_thres'])
    if 'apply_bb'    in data: apply_bb     = bool(data['apply_bb'])
    if 'apply_count' in data: apply_count  = bool(data['apply_count'])
    if 'orientation' in data: orientation  = int(data['orientation'])
    if 'direction'   in data: direction    = data['direction']
    return jsonify({
        'conf_thres':  conf_thres,
        'iou_thres':   iou_thres,
        'apply_bb':    apply_bb,
        'apply_count': apply_count,
        'orientation': orientation,
        'direction':   direction
    }), 200

@app.route('/get_counts')
def get_counts():
    """Restituisce il dizionario dei conteggi per classe."""
    return jsonify(class_counts), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
