"""The tiny agent that the pipeline packages (stage 2). It reads its gateway wiring from the build, not from code."""
import json
from pathlib import Path

WIRING = json.loads((Path(__file__).resolve().parent / "wiring.json").read_text()) \
    if (Path(__file__).resolve().parent / "wiring.json").exists() else {}

INSTRUCTION = "You are a helpful assistant. Keep answers short."
