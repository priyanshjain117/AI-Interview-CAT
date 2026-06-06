import os
import tempfile
import wave
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


class VoiceProcessingError(RuntimeError):
    pass


class VoiceService:
    def __init__(self, audio_dir: Path) -> None:
        self.audio_dir = audio_dir
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._whisper_model = None
        self._kokoro_pipeline = None

    async def transcribe(self, upload: UploadFile) -> tuple[str, str | None, float | None]:
        content = await upload.read()
        if not content:
            raise VoiceProcessingError("Audio recording is empty.")
        if len(content) > 25 * 1024 * 1024:
            raise VoiceProcessingError("Audio recording is too large.")

        suffix = Path(upload.filename or "answer.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            model = self._load_whisper_model()
            segments, info = model.transcribe(temp_path, vad_filter=True)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            if not transcript:
                raise VoiceProcessingError("No speech was detected in the recording.")
            duration = getattr(info, "duration", None)
            language = getattr(info, "language", None)
            return transcript, language, duration
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def synthesize_question(self, text: str, interviewer_id: str) -> str | None:
        pipeline = self._load_kokoro_pipeline()
        if not pipeline:
            return None

        try:
            voice = self._kokoro_voice(interviewer_id)
            filename = f"{uuid4()}.wav"
            output_path = self.audio_dir / filename
            generator = pipeline(text, voice=voice)
            audio_chunks = [audio for _, _, audio in generator]
            if not audio_chunks:
                return None

            import numpy as np

            audio = np.concatenate(audio_chunks)
            self._write_wav(output_path, audio, sample_rate=24000)
            return f"/audio/{filename}"
        except Exception:
            return None

    def _load_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise VoiceProcessingError("Faster Whisper is not installed.") from exc

        model_name = os.getenv("WHISPER_MODEL", "base.en")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        try:
            self._whisper_model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:
            raise VoiceProcessingError(
                "Faster Whisper model is unavailable. Configure WHISPER_MODEL or install the local model files."
            ) from exc
        return self._whisper_model

    def _load_kokoro_pipeline(self):
        if self._kokoro_pipeline is not None:
            return self._kokoro_pipeline
        try:
            from kokoro import KPipeline
        except ImportError:
            return None

        try:
            self._kokoro_pipeline = KPipeline(lang_code=os.getenv("KOKORO_LANG", "a"))
        except Exception:
            return None
        return self._kokoro_pipeline

    def _kokoro_voice(self, interviewer_id: str) -> str:
        if interviewer_id == "academic":
            return os.getenv("KOKORO_VOICE_ACADEMIC", "af_sarah")
        if interviewer_id == "pressure":
            return os.getenv("KOKORO_VOICE_PRESSURE", "am_adam")
        return os.getenv("KOKORO_VOICE_MBA", "af_nicole")

    def _write_wav(self, path: Path, audio, sample_rate: int) -> None:
        import numpy as np

        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())
