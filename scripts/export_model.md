# Exporting the model without installing anything locally

The detector image already has ultralytics, so run the export inside it:

    docker compose run --rm -v ${PWD}/model_repository:/app/model_repository detector python -c "from ultralytics import YOLO; from pathlib import Path; import shutil; p=YOLO('yolov8n.pt').export(format='onnx', imgsz=640); Path('model_repository/yolov8n/1').mkdir(parents=True, exist_ok=True); shutil.copy(p,'model_repository/yolov8n/1/model.onnx'); print('done')"

(PowerShell: replace ${PWD} with ${PWD} as-is, it works; cmd: use %cd%.)

Afterwards verify:  dir model_repository\yolov8n\1   -> should show model.onnx
