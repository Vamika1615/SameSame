"""Builds every artifact into data/build/. Deterministic from config.SEED.

    python -m samesame.pipeline

M0: only writes the manifest. Each milestone adds a stage here.
"""
import json
import time

from samesame import config


def main():
    config.BUILD.mkdir(parents=True, exist_ok=True)
    manifest = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seed": config.SEED, "stages": ["m0"]}
    (config.BUILD / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("pipeline: wrote", config.BUILD / "manifest.json")


if __name__ == "__main__":
    main()
