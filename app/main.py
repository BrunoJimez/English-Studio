import json
import logging
import math
import shutil
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, model_validator
from . import storage, media, scoring, teacher, export

ACTION_LOCK = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    storage.init_db()
    yield


app = FastAPI(title="English Studio", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def local_only(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-study-app") != "english-studio":
        return JSONResponse({"detail": "Requisição não autorizada."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
    return response


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": str(exc)[:700]}, status_code=400)


@app.exception_handler(KeyError)
async def key_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=404)


class Config(BaseModel):
    whisper_model: Literal["tiny.en", "base.en", "small.en", "medium.en", "large-v3"]
    device: Literal["cpu", "cuda"]
    ollama_model: str = Field(min_length=1, max_length=100)


class Scene(BaseModel):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("O fim deve ser posterior ao início.")
        if self.end - self.start > 180:
            raise ValueError("Escolha uma cena de até 3 minutos para estudar.")
        return self


class Answer(Scene):
    answer: str = Field(min_length=1, max_length=5000)
    mode: Literal["dictation", "translation"] = "dictation"
    explain: bool = True


class EditSegment(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


def reference_for(movie_id, scene):
    item = storage.movie(movie_id)
    if item["status"] != "ready":
        raise ValueError("Aguarde o processamento completo do vídeo.")
    if scene.end > item["duration"] + 0.25:
        raise ValueError("O fim da cena ultrapassa a duração do vídeo.")
    text = scoring.excerpt(storage.segments(movie_id), scene.start, scene.end)
    if not text:
        raise ValueError("Nenhuma fala reconhecida nesse intervalo. Escolha outra cena.")
    if len(scoring.tokens(text)) > 800:
        raise ValueError("Há palavras demais nesta cena. Selecione um intervalo menor.")
    return text


@app.get("/api/health")
def health():
    return {"app": "english-studio", "status": "ok"}


@app.get("/api/settings")
def get_settings():
    error = None
    try:
        models = teacher.local_models()
    except Exception:
        models, error = [], "Abra o Ollama para usar explicações e traduções."
    return {**storage.settings(), "models": models, "ollama_error": error,
            "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), "data_path": str(storage.DATA)}


@app.put("/api/settings")
def put_settings(config: Config):
    if config.ollama_model not in teacher.local_models():
        raise ValueError("Escolha um dos modelos locais instalados.")
    with storage.connect() as db:
        db.executemany("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", config.model_dump().items())
    return {"ok": True}


@app.get("/api/movies")
def movies():
    with storage.connect() as db:
        rows = db.execute("SELECT * FROM movies ORDER BY created_at DESC, rowid DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/movies")
async def upload_movie(file: UploadFile = File(...)):
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv", ".mpeg", ".mpg", ".ts", ".m2ts", ".flv"}:
        raise ValueError("Formato não reconhecido. Use MP4, MKV, AVI, MOV, WebM, WMV, MPEG, TS ou FLV.")
    movie_id = uuid.uuid4().hex
    folder = storage.DATA / "media" / movie_id
    folder.mkdir()
    original = "original" + suffix
    size = 0
    try:
        with (folder / original).open("wb") as out:
            while chunk := await file.read(4*1024*1024):
                size += len(chunk)
                if size > 20*1024**3:
                    raise ValueError("O limite por vídeo é 20 GB.")
                if shutil.disk_usage(folder).free < 512*1024**2:
                    raise ValueError("Espaço insuficiente em disco.")
                out.write(chunk)
        if not size:
            raise ValueError("O arquivo está vazio.")
        with storage.connect() as db:
            db.execute("INSERT INTO movies(id,title,original) VALUES(?,?,?)", (movie_id, Path(file.filename).stem[:180], original))
    except Exception:
        # Folder is generated by the server and strictly beneath its media directory.
        shutil.rmtree(folder)
        raise
    finally:
        await file.close()
    media.start_movie(movie_id)
    return storage.movie(movie_id)


@app.get("/api/movies/{movie_id}")
def get_movie(movie_id: str):
    item = storage.movie(movie_id)
    return {**item, "segments": storage.segments(movie_id) if item["status"] == "ready" else []}


@app.post("/api/movies/{movie_id}/retry")
def retry_movie(movie_id: str):
    with ACTION_LOCK:
        item = storage.movie(movie_id)
        if item["status"] != "error":
            raise ValueError("Somente um processamento com erro pode ser reiniciado.")
        media.start_movie(movie_id)
    return {"ok": True}


@app.post("/api/movies/{movie_id}/cancel")
def cancel_movie(movie_id: str):
    if storage.movie(movie_id)["status"] in ("queued", "processing"):
        media.CANCELLED.add(movie_id)
    return {"ok": True}


@app.get("/api/movies/{movie_id}/video")
def video(movie_id: str):
    storage.movie(movie_id)
    path = storage.DATA / "media" / movie_id / "playback.mp4"
    if not path.exists():
        raise HTTPException(404, "Vídeo ainda não está pronto.")
    return FileResponse(path, media_type="video/mp4")


@app.post("/api/movies/{movie_id}/reference")
def reference(movie_id: str, scene: Scene):
    return {"text": reference_for(movie_id, scene)}


@app.put("/api/movies/{movie_id}/segments/{idx}")
def edit_segment(movie_id: str, idx: int, edit: EditSegment):
    if storage.movie(movie_id)["status"] != "ready":
        raise ValueError("Aguarde o processamento.")
    if not edit.text.strip():
        raise ValueError("A fala não pode ficar vazia.")
    with ACTION_LOCK, storage.connect() as db:
        if db.execute("SELECT 1 FROM jobs WHERE movie_id=? AND status IN ('queued','processing')", (movie_id,)).fetchone():
            raise ValueError("Aguarde a tradução em andamento antes de editar a referência.")
        cursor = db.execute("UPDATE segments SET text=?, words='[]', translation=NULL WHERE movie_id=? AND idx=?", (edit.text.strip(), movie_id, idx))
        if not cursor.rowcount:
            raise HTTPException(404, "Fala não encontrada.")
    return {"ok": True}


@app.post("/api/movies/{movie_id}/evaluate")
def evaluate(movie_id: str, answer: Answer):
    if not answer.answer.strip():
        raise ValueError("Escreva ou grave sua resposta primeiro.")
    ref = reference_for(movie_id, answer)
    result = {"reference": ref, "mode": answer.mode, "lesson": None, "teacher_error": None}
    if answer.mode == "dictation":
        result.update(scoring.compare(ref, answer.answer))
    if answer.explain or answer.mode == "translation":
        try:
            result["lesson"] = teacher.teach(ref, answer.answer, answer.mode, result.get("score"))
        except Exception as exc:
            logging.exception("Teacher failed")
            if answer.mode == "translation":
                raise ValueError(f"A tradução precisa do professor local: {exc}") from exc
            result["teacher_error"] = str(exc)[:700]
    if answer.mode == "translation":
        result["score"] = result["lesson"]["nota_traducao"]
        result["method"] = "Estimativa da IA local: significado 70%, gramática 20%, ortografia 10%. Traduções equivalentes podem receber a mesma nota."
    with storage.connect() as db:
        db.execute("INSERT INTO attempts(movie_id,start,end,mode,answer,result) VALUES(?,?,?,?,?,?)",
                   (movie_id, answer.start, answer.end, answer.mode, answer.answer, json.dumps(result, ensure_ascii=False)))
    return result


@app.post("/api/audio/transcribe")
async def audio_transcribe(file: UploadFile = File(...)):
    import asyncio
    temp = storage.DATA / ("voice-" + uuid.uuid4().hex + ".audio")
    try:
        size = 0
        with temp.open("wb") as out:
            while chunk := await file.read(1024*1024):
                size += len(chunk)
                if size > 25*1024*1024:
                    raise ValueError("O áudio da resposta deve ter no máximo 25 MB.")
                out.write(chunk)
        metadata = await asyncio.to_thread(media.probe, temp)
        if float(metadata.get("format", {}).get("duration", 0)) > 190:
            raise ValueError("Grave uma resposta de até 3 minutos.")
        text = await asyncio.to_thread(media.transcribe_audio, temp)
        if not text:
            raise ValueError("Nenhuma fala reconhecida. Grave novamente em um ambiente mais silencioso.")
        return {"text": text, "note": "Revise a transcrição antes de corrigir. A nota compara palavras reconhecidas; não mede pronúncia ou sotaque."}
    finally:
        temp.unlink(missing_ok=True)
        await file.close()


def translation_job(job_id, movie_id, model):
    try:
        all_segments = storage.segments(movie_id)
        pending = [s for s in all_segments if not s.get("translation")]
        total = len(all_segments)
        with storage.connect() as db:
            db.execute("UPDATE jobs SET status='processing',message='Traduzindo os diálogos…' WHERE id=?", (job_id,))
        completed = total - len(pending)
        for i in range(0, len(pending), 10):
            batch = pending[i:i+10]
            context = " ".join(s["text"] for s in all_segments[max(0, batch[0]["idx"]-3):batch[0]["idx"]])
            result = teacher.translate_batch(batch, context, model)
            with storage.connect() as db:
                for row in result:
                    db.execute("UPDATE segments SET translation=? WHERE movie_id=? AND idx=?", (row["texto"], movie_id, row["id"]))
                completed += len(batch)
                db.execute("UPDATE jobs SET progress=?,message=? WHERE id=?", (round(100*completed/max(total,1), 1), f"{completed} de {total} falas traduzidas", job_id))
        with storage.connect() as db:
            db.execute("UPDATE jobs SET status='ready',progress=100,message='Tradução completa. PDF e legendas disponíveis.' WHERE id=?", (job_id,))
    except Exception as exc:
        logging.exception("Translation failed")
        with storage.connect() as db:
            db.execute("UPDATE jobs SET status='error',message=? WHERE id=?", (str(exc)[:700], job_id))


@app.post("/api/movies/{movie_id}/translate")
def translate_movie(movie_id: str):
    if storage.movie(movie_id)["status"] != "ready":
        raise ValueError("Aguarde a transcrição do vídeo.")
    with ACTION_LOCK, storage.connect() as db:
        current = db.execute("SELECT * FROM jobs WHERE movie_id=? AND status IN ('queued','processing')", (movie_id,)).fetchone()
        if current:
            return dict(current)
        job_id = uuid.uuid4().hex
        db.execute("INSERT INTO jobs(id,movie_id,kind,status,message) VALUES(?,?,'translation','queued','Aguardando professor local…')", (job_id, movie_id))
    media.POOL.submit(translation_job, job_id, movie_id, storage.settings()["ollama_model"])
    return {"id": job_id, "status": "queued"}


@app.get("/api/jobs")
def jobs():
    with storage.connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT 20")]


@app.get("/api/movies/{movie_id}/subtitles")
def subtitles(movie_id: str, language: Literal["en", "pt"] = "en"):
    storage.movie(movie_id)
    rows = storage.segments(movie_id)
    if language == "pt" and any(not s["translation"] for s in rows):
        raise ValueError("Traduza o filme completo antes de ativar as legendas em português.")
    return Response(export.vtt(rows, language), media_type="text/vtt", headers={"Cache-Control": "no-store"})


@app.get("/api/movies/{movie_id}/export")
def export_pdf(movie_id: str, language: Literal["en", "pt", "bilingual"] = "bilingual"):
    item = storage.movie(movie_id)
    if item["status"] != "ready":
        raise ValueError("Aguarde a transcrição completa.")
    rows = storage.segments(movie_id)
    if language != "en" and any(not s["translation"] for s in rows):
        raise ValueError("Traduza o filme completo antes de exportar em português ou bilíngue.")
    return Response(export.pdf(item, rows, language), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="english-studio-{language}.pdf"'})


@app.get("/api/history")
def history():
    with storage.connect() as db:
        rows = db.execute("SELECT a.*,m.title FROM attempts a JOIN movies m ON m.id=a.movie_id ORDER BY a.id DESC LIMIT 100").fetchall()
    return [{**dict(r), "result": json.loads(r["result"])} for r in rows]


app.mount("/", StaticFiles(directory=storage.ROOT / "static", html=True), name="static")
