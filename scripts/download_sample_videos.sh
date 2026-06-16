#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Grab a couple of free traffic clips to use as simulated cameras.
# Any mp4 works — these are just suggestions. Drop files into ./videos/.
# Reproducibility matters: benchmark against the SAME files every time so
# latency changes are attributable to YOUR code, not different footage.
# ---------------------------------------------------------------------------
set -euo pipefail
mkdir -p videos
echo "Download 2-3 traffic videos (e.g. from pexels.com, search 'traffic')"
echo "and save them as videos/cam1.mp4, videos/cam2.mp4, ..."
echo "MOT challenge sequences (motchallenge.net) also work well for tracking tests."
