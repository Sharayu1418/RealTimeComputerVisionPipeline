"""
Export yolov8n.pt -> ONNX and place it where Triton expects it.

Run this ONCE on your laptop (needs ultralytics installed locally, or run
it inside the detector container — see scripts/export_model.md).

Why ONNX? It's the portable interchange format: Triton's onnxruntime
backend runs it on CPU today and GPU on the T4 with zero changes.
The export bakes in a fixed 640x640 input, matching config.pbtxt.
"""

from ultralytics import YOLO
from pathlib import Path
import shutil

model = YOLO("yolov8n.pt")                      # downloads weights if absent
path = model.export(format="onnx", imgsz=640)   # -> yolov8n.onnx

dest = Path("model_repository/yolov8n/1/model.onnx")
dest.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(path, dest)
print(f"ONNX model placed at {dest} — Triton will load it on startup.")
