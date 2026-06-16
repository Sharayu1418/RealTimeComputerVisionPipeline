#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Turns video files into "cameras".
# ffmpeg reads videos/camN.mp4 in an infinite loop (-stream_loop -1) at
# native speed (-re) and pushes it to mediamtx over RTSP. The ingest
# service then pulls rtsp://localhost:8554/camN exactly as it would pull
# from a real IP camera — same protocol, same reconnect semantics.
# Run AFTER `docker compose up` (mediamtx must be listening).
# ---------------------------------------------------------------------------
set -euo pipefail
for f in videos/cam*.mp4; do
  name=$(basename "$f" .mp4)
  echo "Streaming $f -> rtsp://localhost:8554/$name"
  ffmpeg -re -stream_loop -1 -i "$f" -c copy -f rtsp \
    "rtsp://localhost:8554/$name" \
    > /dev/null 2>&1 &
done
echo "All streams started. Ctrl+C or 'pkill ffmpeg' to stop."
wait
