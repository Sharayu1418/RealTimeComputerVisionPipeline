"""
DETECTOR — Stage 2. Frames in, bounding boxes out.

Supports two backends:
  1. local  -> Ultralytics YOLO inside detector container
  2. triton -> Triton Inference Server over gRPC

Switch using .env:
  DETECTOR_BACKEND=local
  DETECTOR_BACKEND=triton
"""

import base64
import os
import time
from dataclasses import asdict

import cv2
import numpy as np

from common.schemas import Detections, Box, to_json, from_json, now_ms
from common.kafka_io import make_producer, make_consumer, publish
from common.metrics import (
    start_metrics_server,
    STAGE_E2E_MS,
    STAGE_PROC_MS,
    FRAMES_TOTAL,
    FRAMES_DROPPED,
)

MODEL_NAME = os.environ.get("MODEL_NAME", "yolov8n.pt")
CONF = float(os.environ.get("CONF_THRESHOLD", "0.35"))
DETECTOR_BACKEND = os.environ.get("DETECTOR_BACKEND", "local").lower()
TRITON_URL = os.environ.get("TRITON_URL", "triton:8001")
TRITON_MODEL_NAME = os.environ.get("TRITON_MODEL_NAME", "yolov8n")

STAGE = "detector"

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


class LocalYOLOBackend:
    def __init__(self):
        from ultralytics import YOLO

        print(f"[detector] Using LOCAL YOLO backend with model={MODEL_NAME}", flush=True)
        self.model = YOLO(MODEL_NAME)

    def infer(self, img: np.ndarray) -> list[Box]:
        results = self.model.predict(img, conf=CONF, verbose=False)

        boxes = []
        r = results[0]

        for b in r.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            cls_id = int(b.cls[0])

            boxes.append(
                Box(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    conf=float(b.conf[0]),
                    cls_id=cls_id,
                    cls_name=self.model.names[cls_id],
                )
            )

        return boxes


class TritonYOLOBackend:
    def __init__(self):
        import tritonclient.grpc as grpcclient

        print(
            f"[detector] Using TRITON backend url={TRITON_URL}, model={TRITON_MODEL_NAME}",
            flush=True,
        )

        self.grpcclient = grpcclient
        self.client = grpcclient.InferenceServerClient(url=TRITON_URL)

        if not self.client.is_server_live():
            raise RuntimeError("Triton server is not live")

        if not self.client.is_model_ready(TRITON_MODEL_NAME):
            raise RuntimeError(f"Triton model is not ready: {TRITON_MODEL_NAME}")

    def preprocess(self, img: np.ndarray) -> tuple[np.ndarray, int, int]:
        original_h, original_w = img.shape[:2]

        resized = cv2.resize(img, (640, 640))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        tensor = rgb.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)

        return tensor, original_w, original_h

    def postprocess(self, output: np.ndarray, original_w: int, original_h: int) -> list[Box]:
        # Expected output shape: [1, 84, 8400]
        if output.ndim == 3:
            output = output[0]

        # Convert [84, 8400] -> [8400, 84]
        predictions = output.T

        boxes_xywh = predictions[:, 0:4]
        class_scores = predictions[:, 4:]

        cls_ids = np.argmax(class_scores, axis=1)
        confs = np.max(class_scores, axis=1)

        keep = confs >= CONF
        boxes_xywh = boxes_xywh[keep]
        cls_ids = cls_ids[keep]
        confs = confs[keep]

        if len(boxes_xywh) == 0:
            return []

        candidate_boxes = []

        for box in boxes_xywh:
            cx, cy, w, h = box

            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2

            # Scale from 640x640 model input back to original frame size
            x1 = float(x1 * original_w / 640)
            y1 = float(y1 * original_h / 640)
            x2 = float(x2 * original_w / 640)
            y2 = float(y2 * original_h / 640)

            candidate_boxes.append([x1, y1, x2, y2])

        # NMS expects [x, y, w, h]
        nms_input = []
        for x1, y1, x2, y2 in candidate_boxes:
            nms_input.append([int(x1), int(y1), int(x2 - x1), int(y2 - y1)])

        indices = cv2.dnn.NMSBoxes(
            bboxes=nms_input,
            scores=confs.astype(float).tolist(),
            score_threshold=CONF,
            nms_threshold=0.45,
        )

        final_boxes = []

        if len(indices) == 0:
            return final_boxes

        for idx in indices.flatten():
            x1, y1, x2, y2 = candidate_boxes[idx]
            cls_id = int(cls_ids[idx])

            final_boxes.append(
                Box(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    conf=float(confs[idx]),
                    cls_id=cls_id,
                    cls_name=COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id),
                )
            )

        return final_boxes

    def infer(self, img: np.ndarray) -> list[Box]:
        tensor, original_w, original_h = self.preprocess(img)

        infer_input = self.grpcclient.InferInput(
            "images",
            tensor.shape,
            "FP32",
        )
        infer_input.set_data_from_numpy(tensor)

        infer_output = self.grpcclient.InferRequestedOutput("output0")

        result = self.client.infer(
            model_name=TRITON_MODEL_NAME,
            inputs=[infer_input],
            outputs=[infer_output],
        )

        output = result.as_numpy("output0")
        return self.postprocess(output, original_w, original_h)


if DETECTOR_BACKEND == "triton":
    backend = TritonYOLOBackend()
else:
    backend = LocalYOLOBackend()


def infer(img: np.ndarray) -> list[Box]:
    return backend.infer(img)


def main():
    start_metrics_server()

    producer = make_producer()
    consumer = make_consumer(group_id="detector", topics=["frames"])

    print(f"[detector] Started with backend={DETECTOR_BACKEND}", flush=True)

    while True:
        rec = consumer.poll(1.0)

        if rec is None or rec.error():
            continue

        frame = from_json(rec.value())
        cam = frame["camera_id"]
        t0 = time.time()

        jpeg = base64.b64decode(frame["jpeg_b64"])
        img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)

        if img is None:
            FRAMES_DROPPED.labels(STAGE, cam, "decode_fail").inc()
            continue

        boxes = infer(img)

        out = Detections(
            camera_id=cam,
            frame_id=frame["frame_id"],
            seq=frame["seq"],
            captured_ts=frame["captured_ts"],
            detect_ts=now_ms(),
            boxes=[asdict(b) for b in boxes],
            jpeg_b64=frame["jpeg_b64"],
        )

        publish(producer, "detections", key=cam, value=to_json(out))

        FRAMES_TOTAL.labels(STAGE, cam).inc()
        STAGE_PROC_MS.labels(STAGE, cam).observe((time.time() - t0) * 1000)
        STAGE_E2E_MS.labels(STAGE, cam).observe(now_ms() - frame["captured_ts"])


if __name__ == "__main__":
    main()