import json
import pytest
from fastapi.testclient import TestClient
from app import storage, teacher
from app.main import app

HEADERS = {"X-Study-App": "english-studio"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA", tmp_path)
    (tmp_path / "media").mkdir()
    with TestClient(app) as c:
        with storage.connect() as db:
            db.execute("INSERT INTO movies(id,title,original,duration,status) VALUES('demo','A lesson','x.mp4',20,'ready')")
            db.execute("INSERT INTO segments(movie_id,idx,start,end,text) VALUES('demo',0,0,8,'Hello there. I am ready.')")
            db.execute("INSERT INTO segments(movie_id,idx,start,end,text) VALUES('demo',1,10,18,'Let us watch again.')")
        yield c


def test_requires_local_header(client):
    assert client.post('/api/movies/demo/reference', json={"start":0,"end":8}).status_code == 403


@pytest.mark.parametrize('scene', [{"start":5,"end":4},{"start":-1,"end":3},{"start":0,"end":181}])
def test_invalid_intervals(client, scene):
    assert client.post('/api/movies/demo/reference',json=scene,headers=HEADERS).status_code == 422


def test_clip_and_silence_validation(client):
    assert client.post('/api/movies/demo/reference',json={"start":19,"end":20},headers=HEADERS).status_code == 400
    assert client.post('/api/movies/demo/reference',json={"start":0,"end":30},headers=HEADERS).status_code == 400


def test_correction_persists_and_survives_teacher_offline(client, monkeypatch):
    def offline(*args, **kwargs):
        raise ValueError('Offline')
    monkeypatch.setattr(teacher, 'teach', offline)
    response = client.post('/api/movies/demo/evaluate', headers=HEADERS, json={"start":0,"end":8,"answer":"Hello there I am ready","explain":True})
    assert response.status_code == 200
    assert response.json()['score'] == 100
    assert response.json()['teacher_error'] == 'Offline'
    saved = client.get('/api/history').json()
    assert len(saved) == 1 and saved[0]['result']['score'] == 100
    response = client.post('/api/movies/demo/evaluate', headers=HEADERS, json={"start":0,"end":8,"answer":"Olá, estou pronto","mode":"translation"})
    assert response.status_code == 400
    assert len(client.get('/api/history').json()) == 1


def test_edit_invalidates_translation_and_alignment(client):
    with storage.connect() as db:
        db.execute("UPDATE segments SET translation='Olá',words='[{\"word\":\"Hello\"}]' WHERE idx=0")
    response = client.put('/api/movies/demo/segments/0', headers=HEADERS, json={"text":"Good morning."})
    assert response.status_code == 200
    row = client.get('/api/movies/demo').json()['segments'][0]
    assert row['text'] == 'Good morning.' and row['translation'] is None and row['words'] == []


def test_translation_export_requires_complete_translation(client):
    assert client.get('/api/movies/demo/export?language=pt').status_code == 400
    assert client.get('/api/movies/demo/subtitles?language=pt').status_code == 400


def test_vtt_escapes_untrusted_tags(client):
    client.put('/api/movies/demo/segments/0',headers=HEADERS,json={"text":"<script>alert(1)</script> & goodbye"})
    response = client.get('/api/movies/demo/subtitles')
    assert response.status_code == 200
    assert '00:00:00.000 --> 00:00:08.000' in response.text
    assert '<script>' not in response.text


def test_video_range_requests(client, tmp_path):
    directory = tmp_path/'media'/'demo'
    directory.mkdir()
    (directory/'playback.mp4').write_bytes(b'0123456789')
    response = client.get('/api/movies/demo/video', headers={"Range":"bytes=2-5"})
    assert response.status_code == 206 and response.content == b'2345'


def test_wrong_model_and_cloud_model_rejected(client, monkeypatch):
    monkeypatch.setattr(teacher,'local_models', lambda: ['local:3b'])
    response = client.put('/api/settings',headers=HEADERS,json={"whisper_model":"base.en","device":"cpu","ollama_model":"remote:cloud"})
    assert response.status_code == 400
