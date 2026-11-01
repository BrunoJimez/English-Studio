import json
import logging
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import storage

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio")
ASR_LOCK = threading.Lock()
MODELS = {}
CANCELLED = set()
CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def check_cancel(movie_id):
    if movie_id in CANCELLED:
        raise ValueError("Processamento cancelado. Você pode tentar novamente.")


def run_process(args, movie_id=None):
    # Capture errors to a file so a long movie cannot fill an OS pipe.
    import tempfile
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=errors, creationflags=CREATE_FLAGS)
        try:
            while process.poll() is None:
                if movie_id:
                    check_cancel(movie_id)
                time.sleep(0.25)
            if process.returncode:
                errors.seek(0)
                detail = errors.read().decode("utf-8", errors="replace")[-1500:]
                logging.error("Media conversion: %s", detail)
                raise ValueError("Não foi possível ler o vídeo/áudio. Verifique se o arquivo é válido, tem áudio e não possui DRM.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                            capture_output=True, timeout=40, creationflags=CREATE_FLAGS)
    if result.returncode:
        raise ValueError("Arquivo de mídia inválido ou formato não reconhecido pelo FFmpeg.")
    data = json.loads(result.stdout)
    if not any(s["codec_type"] == "audio" for s in data["streams"]):
        raise ValueError("Este arquivo não tem uma faixa de áudio.")
    return data


def get_model(config):
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    key = (config["whisper_model"], config["device"])
    if key not in MODELS:
        MODELS.clear()
        try:
            model_path = download_model(key[0], cache_dir=str(storage.DATA / "models"), local_files_only=True)
        except Exception:
            model_path = download_model(key[0], cache_dir=str(storage.DATA / "models"))
        MODELS[key] = WhisperModel(model_path, device=key[1], compute_type="int8" if key[1] == "cpu" else "float16", cpu_threads=4)
    return MODELS[key]


def transcribe_audio(path, config=None):
    with ASR_LOCK:
        model = get_model(config or storage.settings())
        results, _ = model.transcribe(str(path), language="en", vad_filter=True, beam_size=5)
        return " ".join(s.text.strip() for s in results).strip()


def process_movie(movie_id, config):
    folder = storage.DATA / "media" / movie_id
    try:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise ValueError("Instale FFmpeg e adicione ffmpeg e ffprobe ao PATH do Windows.")
        item = storage.movie(movie_id)
        source = folder / item["original"]
        storage.update_movie(movie_id, status="processing", progress=2, message="Lendo as faixas de vídeo e áudio…")
        metadata = probe(source)
        audio_streams = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
        chosen_audio = next((s for s in audio_streams if s.get("tags", {}).get("language", "").lower() in {"eng", "en", "en-us", "en-gb"}), audio_streams[0])
        audio_map = f'0:{chosen_audio["index"]}'
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration <= 0:
            raise ValueError("Não foi possível determinar a duração deste arquivo.")
        storage.update_movie(movie_id, duration=duration, progress=5, message="Preparando vídeo compatível com o player…")
        if not (folder / "playback.mp4").exists():
            video_stream = next((s for s in metadata["streams"] if s["codec_type"] == "video"), None)
            if not video_stream:
                raise ValueError("Escolha um arquivo que contenha vídeo e áudio.")
            if video_stream["codec_name"] == "h264" and video_stream.get("pix_fmt") == "yuv420p":
                video_args = ["-c:v", "copy"]
            else:
                video_args = ["-vf", "scale=-2:trunc(min(720\\,ih)/2)*2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
            run_process(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", "0:v:0", "-map", audio_map, *video_args,
                         "-c:a", "aac", "-ac", "2", "-movflags", "+faststart", str(folder / "preview.tmp.mp4")], movie_id)
            (folder / "preview.tmp.mp4").replace(folder / "playback.mp4")
        storage.update_movie(movie_id, progress=15, message="Separando o áudio para reconhecer as falas…")
        audio = folder / "audio.wav"
        if not audio.exists():
            temp_audio = folder / "audio.tmp.wav"
            run_process(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", audio_map, "-vn", "-ar", "16000", "-ac", "1", str(temp_audio)], movie_id)
            temp_audio.replace(audio)
        storage.update_movie(movie_id, progress=20, message="Carregando Whisper. No primeiro uso, o modelo será baixado…")
        with ASR_LOCK:
            check_cancel(movie_id)
            model = get_model(config)
            results, _ = model.transcribe(str(audio), language="en", word_timestamps=True, vad_filter=True, beam_size=5)
            with storage.connect() as db:
                db.execute("DELETE FROM segments WHERE movie_id=?", (movie_id,))
            count = 0
            for index, segment in enumerate(results):
                check_cancel(movie_id)
                words = [{"start": w.start, "end": w.end, "word": w.word, "probability": w.probability} for w in segment.words or []]
                with storage.connect() as db:
                    db.execute("INSERT INTO segments(movie_id,idx,start,end,text,words) VALUES(?,?,?,?,?,?)",
                               (movie_id, index, segment.start, segment.end, segment.text.strip(), json.dumps(words)))
                count += 1
                storage.update_movie(movie_id, progress=min(99, 20+79*segment.end/duration), message=f"Reconhecendo diálogos · {int(segment.end//60)} de {int(duration//60)} min · {count} falas")
        check_cancel(movie_id)
        if not count:
            raise ValueError("Nenhuma fala em inglês foi reconhecida. Verifique a faixa de áudio do vídeo.")
        storage.update_movie(movie_id, status="ready", progress=100, message=f"{count} falas prontas para estudar")
    except Exception as exc:
        logging.exception("Movie processing failed")
        message = str(exc)
        if "cuda" in message.lower() or "cublas" in message.lower() or "cudnn" in message.lower():
            message = "CUDA indisponível. Selecione CPU nas configurações e tente novamente."
        storage.update_movie(movie_id, status="error", message=message[:600])
    finally:
        CANCELLED.discard(movie_id)


def start_movie(movie_id):
    CANCELLED.discard(movie_id)
    storage.update_movie(movie_id, status="queued", progress=0, message="Na fila de processamento…")
    POOL.submit(process_movie, movie_id, storage.settings())
