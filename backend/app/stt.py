"""Vosk speech-to-text.

The small English model is auto-downloaded (~40 MB) on first run if it is not
already present in VOSK_MODEL_DIR. Each WebSocket session gets its own
KaldiRecognizer instance (recognizers are not thread-safe; per-session
instances are the correct pattern for concurrent users).
"""
import json
import logging
import urllib.request
import zipfile
from pathlib import Path

from vosk import KaldiRecognizer, Model

log = logging.getLogger(__name__)

MODEL_DOWNLOAD_URL = (
    "https://alphacephei.com/vosk/models/{name}.zip"
)


def ensure_model(model_dir: str, model_name: str) -> Path:
    """Download and extract the Vosk model if missing. Returns the model path."""
    target = Path(model_dir) / model_name
    if (target / "am" / "final.mdl").exists() or (target / "model.conf").exists():
        log.info("Vosk model already present at %s", target)
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    url = MODEL_DOWNLOAD_URL.format(name=model_name)
    zip_path = Path(model_dir) / f"{model_name}.zip"
    log.info("Downloading Vosk model %s (~40 MB) ...", model_name)
    urllib.request.urlretrieve(url, zip_path)
    log.info("Extracting %s ...", zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(model_dir)
    zip_path.unlink(missing_ok=True)
    log.info("Vosk model ready at %s", target)
    return target


class SessionSTT:
    """One recognizer per user session. Feed it 16 kHz 16-bit mono PCM bytes."""

    def __init__(self, model: Model, sample_rate: int = 16000):
        self._rec = KaldiRecognizer(model, sample_rate)
        self._rec.SetWords(False)
        self._final_text_parts: list[str] = []

    def accept_audio(self, pcm_bytes: bytes) -> tuple[str, bool]:
        """Returns (text, is_final_sentence)."""
        if self._rec.AcceptWaveform(pcm_bytes):
            result = json.loads(self._rec.Result())
            text = result.get("text", "").strip()
            if text:
                self._final_text_parts.append(text)
            return text, True
        partial = json.loads(self._rec.PartialResult()).get("partial", "").strip()
        return partial, False

    def flush(self) -> str:
        """Finalize any buffered audio and return the full transcript."""
        final = json.loads(self._rec.FinalResult()).get("text", "").strip()
        if final:
            self._final_text_parts.append(final)
        full = " ".join(self._final_text_parts).strip()
        self._final_text_parts = []
        return full


class STTEngine:
    """Loads the Vosk model once; hands out per-session recognizers."""

    def __init__(self, model_dir: str, model_name: str, sample_rate: int = 16000):
        model_path = ensure_model(model_dir, model_name)
        log.info("Loading Vosk model from %s ...", model_path)
        self._model = Model(str(model_path))
        self._sample_rate = sample_rate
        log.info("Vosk model loaded.")

    def new_session(self) -> SessionSTT:
        return SessionSTT(self._model, self._sample_rate)
