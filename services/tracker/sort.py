"""
Simple SORT-compatible tracker for Phase 2 demo.

Input from tracker/main.py:
  dets = numpy array with shape (N, 4)
  each row = [x1, y1, x2, y2]

Output expected by tracker/main.py:
  list of dicts with:
  track_id, x1, y1, x2, y2, age

This is a lightweight pass-through tracker:
  - It assigns IDs.
  - It preserves boxes.
  - It allows tracker/main.py to reattach cls_name labels.
"""


class Sort:
    def __init__(self, *args, **kwargs):
        self.next_track_id = 1

    def update(self, dets):
        tracks = []

        if dets is None:
            return tracks

        for det in dets:
            if len(det) < 4:
                continue

            x1, y1, x2, y2 = det[:4]

            tracks.append({
                "track_id": self.next_track_id,
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y2),
                "age": 1,
            })

            self.next_track_id += 1

        return tracks