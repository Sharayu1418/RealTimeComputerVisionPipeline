"""
TRITON BACKEND for the detector — the Phase 2 drop-in.

This file replaces the in-process YOLO call with a gRPC call to Triton.
The detector's main loop doesn't change AT ALL; main.py just picks a
backend based on DETECTOR_BACKEND (local | triton). That switchable seam
is the migration story you tell in interviews.

What the in-process Ultralytics call did for us silently, we now do
explicitly — and understanding these three steps IS understanding
deployment-grade inference:

  1. PREPROCESS  — letterbox the frame to 640x640, normalize, HWC->CHW.
  2. INFER       — ship the tensor to Triton; Triton fuses requests from
                   many cameras into one batched model call (dynamic batching).
  3. POSTPROCESS — decode the (84, 8400) raw output into boxes and run NMS
                   (the ONNX export contains NO NMS — that's on us now).
"""

import os

import cv2
import numpy as np
import tritonclient.grpc as grpcclient

from common.schemas import Box

TRITON_URL = os.environ.get("TRITON_URL", "triton:8001")   # gRPC port
MODEL_NAME_TRITON = os.environ.get("TRITON_MODEL", "yolov8n")
CONF = float(os.environ.get("CONF_THRESHOLD", "0.35"))
IOU_NMS = 0.45            # NMS overlap threshold; standard YOLO default
INPUT_SIZE = 640          # must match config.pbtxt dims and the ONNX export

# COCO class names, index-aligned with the model's 80 outputs.
COCO = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck",
    "boat","traffic light","fire hydrant","stop sign","parking meter","bench",
    "bird","cat","dog","horse","sheep","cow","elephant","bear","zebra",
    "giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee",
    "skis","snowboard","sports ball","kite","baseball bat","baseball glove",
    "skateboard","surfboard","tennis racket","bottle","wine glass","cup",
    "fork","knife","spoon","bowl","banana","apple","sandwich","orange",
    "broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
    "potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink",
    "refrigerator","book","clock","vase","scissors","teddy bear",
    "hair drier","toothbrush",
]

_client = grpcclient.InferenceServerClient(url=TRITON_URL)


def _letterbox(img: np.ndarray, size: int = INPUT_SIZE):
    """Resize keeping aspect ratio, pad the rest gray — same as YOLO training.
    Returns the tensor-ready image plus the scale/pad needed to map boxes
    BACK to original pixel coordinates afterwards."""
    h, w = img.shape[:2]
    scale = size / max(h, w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (nw, nh))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)   # gray pad
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas, scale, left, top


def infer(img: np.ndarray) -> list[Box]:
    """Same signature as the local backend's infer() — that's the seam."""
    # --- 1. preprocess -----------------------------------------------------
    canvas, scale, pad_x, pad_y = _letterbox(img)
    blob = canvas[:, :, ::-1].astype(np.float32) / 255.0     # BGR->RGB, 0..1
    blob = np.transpose(blob, (2, 0, 1))[None]               # HWC -> NCHW

    # --- 2. infer via Triton ------------------------------------------------
    inp = grpcclient.InferInput("images", blob.shape, "FP32")
    inp.set_data_from_numpy(blob)
    out = grpcclient.InferRequestedOutput("output0")
    result = _client.infer(MODEL_NAME_TRITON, inputs=[inp], outputs=[out])
    pred = result.as_numpy("output0")[0]      # (84, 8400)

    # --- 3. postprocess: decode + NMS ---------------------------------------
    pred = pred.T                              # (8400, 84): per-candidate rows
    boxes_xywh = pred[:, :4]                   # cx, cy, w, h in 640-space
    scores_all = pred[:, 4:]                   # 80 class scores per candidate
    cls_ids = scores_all.argmax(axis=1)
    confs = scores_all.max(axis=1)

    keep = confs >= CONF                       # confidence gate first (cheap)
    boxes_xywh, cls_ids, confs = boxes_xywh[keep], cls_ids[keep], confs[keep]
    if len(boxes_xywh) == 0:
        return []

    # cxcywh -> xyxy, then undo the letterbox to original pixel coords
    xy = boxes_xywh.copy()
    xy[:, 0] = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2       # x1
    xy[:, 1] = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2       # y1
    xy[:, 2] = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2       # x2
    xy[:, 3] = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2       # y2
    xy[:, [0, 2]] = (xy[:, [0, 2]] - pad_x) / scale
    xy[:, [1, 3]] = (xy[:, [1, 3]] - pad_y) / scale

    # NMS: drop overlapping duplicates of the same object. The ONNX export
    # has no NMS baked in (unlike the .pt path), so this step is mandatory —
    # skip it and every car gets 5 boxes.
    nms_boxes = [[float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
                 for x1, y1, x2, y2 in xy]
    idxs = cv2.dnn.NMSBoxes(nms_boxes, confs.tolist(), CONF, IOU_NMS)
    idxs = np.array(idxs).flatten() if len(idxs) else []

    out_boxes = []
    h, w = img.shape[:2]
    for i in idxs:
        x1, y1, x2, y2 = xy[i]
        out_boxes.append(Box(
            x1=float(max(0, x1)), y1=float(max(0, y1)),
            x2=float(min(w, x2)), y2=float(min(h, y2)),
            conf=float(confs[i]),
            cls_id=int(cls_ids[i]),
            cls_name=COCO[int(cls_ids[i])],
        ))
    return out_boxes
