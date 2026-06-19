# Baseline YOLOv8n Accuracy Evaluation

## Goal

After validating the real-time vision pipeline for throughput, latency, GPU inference, and observability, the next step was to measure model quality on manually labeled traffic-camera frames.

This evaluation measures the baseline performance of the pretrained `yolov8n.pt` model before any fine-tuning.

## Dataset

The evaluation dataset was created by sampling frames from the simulated multi-camera traffic streams used in the real-time pipeline.

| Item                           |                          Value |
| ------------------------------ | -----------------------------: |
| Labeled frames                 |                             68 |
| Total object instances         |                            272 |
| Model evaluated                |     YOLOv8n pretrained on COCO |
| Image size                     |                            640 |
| Confidence threshold           |                           0.25 |
| Evaluation format              |              YOLOv8 validation |
| Classes present in labeled set | car, bus, truck, traffic light |

## Overall Results

| Metric       | Value |
| ------------ | ----: |
| Precision    | 0.431 |
| Recall       | 0.534 |
| mAP@0.5      | 0.475 |
| mAP@0.5:0.95 | 0.352 |

## Per-Class Results

| Class         | Images | Instances | Precision | Recall | mAP@0.5 | mAP@0.5:0.95 |
| ------------- | -----: | --------: | --------: | -----: | ------: | -----------: |
| car           |     49 |       115 |     0.582 |  0.904 |   0.717 |        0.537 |
| bus           |      2 |         2 |     0.000 |  0.000 |   0.000 |        0.000 |
| truck         |     10 |        11 |     0.535 |  0.364 |   0.374 |        0.280 |
| traffic light |     67 |       144 |     0.606 |  0.868 |   0.808 |        0.593 |

## Interpretation

The baseline YOLOv8n model performs strongest on traffic lights and cars. Traffic lights achieved high recall and strong mAP@0.5, which is useful for the traffic-camera setting. Cars also performed well, especially in recall.

Truck performance was weaker, mainly because trucks appeared less frequently and were visually similar to other vehicle classes. Bus performance was not meaningful because the evaluation set contained only 2 bus examples.

The overall mAP@0.5 of 0.475 and mAP@0.5:0.95 of 0.352 show that the pretrained model works as a baseline but would benefit from more labeled data and possible fine-tuning for traffic-specific objects.

## Next Steps

* Add more labeled examples for underrepresented classes such as bus and truck.
* Include person and stop sign examples if those classes are important for the final traffic-scene benchmark.
* Fine-tune YOLO only after expanding the labeled dataset.
* Compare baseline YOLOv8n results against a fine-tuned model.
* Track both accuracy metrics and pipeline latency to avoid improving accuracy while hurting real-time performance.
