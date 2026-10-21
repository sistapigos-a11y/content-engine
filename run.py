"""Entry point.

  python run.py                       # everything: write, render, publish (EN + ES)
  python run.py --no-publish          # everything except uploading (to check quality)
  python run.py --quick --no-publish  # tiny test video (2 chapters, 1 short, English only)
  python run.py --voice-test          # 2 short samples of your cloned voice (EN + ES)

  # used by GitHub Actions to run languages in parallel
  python run.py --stage write    --job NAME
  python run.py --stage produce  --job NAME --lang es
  python run.py --stage finalize --job NAME
"""
import argparse
import logging

from engine import pipeline, tts
from engine.util import ROOT, load_config

SAMPLES = {
    "en": "Three years ago, one man saw it coming. Everybody laughed at him. Nobody believed him. "
          "And then, on one cold night in Barcelona, everything changed.",
    "es": "Hace tres años, un hombre lo vio venir. Todos se rieron de él. Nadie le creyó. "
          "Y entonces, una noche fría en Barcelona, todo cambió.",
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["all", "write", "produce", "finalize"], default="all")
    ap.add_argument("--job")
    ap.add_argument("--lang")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--voice-test", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    if args.quick:
        cfg["long_video"].update(target_minutes=2, sections=2)
        cfg["shorts"]["per_video"] = 1
        cfg["quality"]["max_rewrites"] = 0
        cfg["languages"] = {"en": cfg["languages"]["en"]}

    if args.voice_test:
        out = ROOT / "work" / "voice-test"
        out.mkdir(parents=True, exist_ok=True)
        for lang, text in SAMPLES.items():
            path, words = tts.synthesize(text, lang, cfg, out / lang)
            logging.info("%s -> %s (%d words timed)", lang, path, len(words))
        raise SystemExit

    name = args.job or pipeline.job_name()
    if args.stage == "all":
        pipeline.run_all(cfg, publish=not args.no_publish)
    elif args.stage == "write":
        pipeline.write_stage(cfg, name)
    elif args.stage == "produce":
        pipeline.produce_stage(cfg, name, args.lang, publish=not args.no_publish)
    else:
        pipeline.finalize(cfg, name)
