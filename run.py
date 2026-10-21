"""Daily entry point.

  python run.py              # full run: write, render, publish
  python run.py --no-publish # everything except uploading (to check quality)
  python run.py --quick      # tiny test video (2 chapters, 1 short, English only)
"""
import argparse
import logging

from engine import pipeline
from engine.util import load_config

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    if args.quick:
        cfg["long_video"].update(target_minutes=2, sections=2)
        cfg["shorts"]["per_video"] = 1
        cfg["quality"]["max_rewrites"] = 0
        cfg["languages"] = {"en": cfg["languages"]["en"]}
    pipeline.run(cfg, publish=not args.no_publish)
