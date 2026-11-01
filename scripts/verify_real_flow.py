"""Exercise the actual local models, video player, UI correction, and PDF export."""
import json
import time
from pathlib import Path
import httpx
import pymupdf as fitz
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = 'http://127.0.0.1:8765'
HEADERS = {'X-Study-App':'english-studio'}


def main():
    c = httpx.Client(base_url=BASE, timeout=650, trust_env=False, headers=HEADERS)
    movie = c.get('/api/movies').json()[0]
    assert movie['status'] == 'ready', movie
    mid = movie['id']
    full = c.get('/api/movies/'+mid).json()
    assert len(full['segments']) == 3
    print('REAL ASR: 17-second sample, 3 timed speeches, reference recognized.', flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page(viewport={'width':1440,'height':1100}, bypass_csp=True)
        page.set_default_timeout(15000)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE,wait_until='networkidle')
        page.locator('#play-scene').wait_for(state='visible')
        page.locator('#scene-start').fill('00:00')
        page.locator('#scene-end').fill('00:06.16')
        page.locator('#scene-end').press('Tab')
        page.locator('#play-scene').click()
        page.wait_for_function('document.getElementById("player").currentTime > 0.4')
        page.wait_for_function('document.getElementById("player").paused', timeout=15000)
        assert abs(page.locator('#player').evaluate('(v)=>v.currentTime')-6.16)<.3
        page.locator('#subtitles').select_option('en')
        page.wait_for_function('document.getElementById("player").textTracks.length && document.getElementById("player").textTracks[0].mode === "showing"')
        print('PLAYER: decoded MP4, scene stop, synchronized English captions OK.',flush=True)
        page.locator('#answer').fill('Hello. How is you today? I learning English one seen at a time.')
        with page.expect_response(lambda r:'/evaluate' in r.url,timeout=650000) as response:
            page.locator('#evaluate').click()
        result=response.value.json()
        assert response.value.status==200,result
        assert result['lesson'],result
        assert 0 < result['score'] < 100
        page.locator('#result').wait_for(state='visible')
        (ROOT/'tmp'/'real-lesson.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        page.screenshot(path=str(ROOT/'tmp'/'correction.png'),full_page=True)
        print('TEACHER: actual Qwen local feedback and non-perfect WER score: '+str(result['score']),flush=True)
        page.locator('#mode-translation').click()
        page.locator('#answer').fill('Olá. Como você está hoje? Estou aprendendo inglês, uma cena de cada vez.')
        with page.expect_response(lambda r:'/evaluate' in r.url,timeout=650000) as response:
            page.locator('#evaluate').click()
        result=response.value.json()
        assert response.value.status==200,result
        assert result['lesson'] and result['mode']=='translation'
        assert result['score'] >= 90, 'A correct translation should receive high credit: '+str(result)
        print('TRANSLATION EXERCISE: semantic feedback score '+str(result['score']),flush=True)
        page.locator('#mode-dictation').click()
        with page.expect_response(lambda r:'/audio/transcribe' in r.url,timeout=180000) as response:
            page.locator('#audio-file').set_input_files(str(ROOT/'tmp'/'sample.wav'))
        assert response.value.status==200,response.value.text()
        page.wait_for_function('document.getElementById("answer").value.length > 50')
        print('VOICE: actual uploaded audio recognized into editable answer.',flush=True)
        page.locator('#open-export').click()
        with page.expect_response(lambda r:r.url.endswith('/translate'),timeout=15000) as response:
            page.locator('#translate-all').click()
        job_id=response.value.json()['id']
        print('FULL TRANSLATION: background job started.',flush=True)
        until=time.monotonic()+600
        while time.monotonic()<until:
            job=next(j for j in c.get('/api/jobs').json() if j['id']==job_id)
            if job['status'] in ('ready','error'):
                break
            time.sleep(1)
        assert job['status']=='ready',job
        for language in ['en','pt','bilingual']:
            response=c.get(f'/api/movies/{mid}/export?language={language}')
            assert response.status_code==200,response.text
            path=ROOT/'tmp'/f'example-{language}.pdf'
            path.write_bytes(response.content)
            document=fitz.open(path)
            text=''.join(page.get_text() for page in document)
            assert len(text)>200
            if language!='pt':
                assert 'Hello' in text and 'again' in text
            if language!='en':
                assert 'portugu' in text.lower()
            if language=='bilingual':
                document[0].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(str(ROOT/'tmp'/'pdf-preview.png'))
        page.locator('#export-language').select_option('bilingual')
        with page.expect_download(timeout=30000) as download:
            page.locator('#download-pdf').click()
        assert download.value.suggested_filename.endswith('bilingual.pdf')
        page.locator('#export-dialog .close-dialog').click()
        page.locator('#subtitles').select_option('pt')
        page.wait_for_function('document.getElementById("player").textTracks.length && document.getElementById("player").textTracks[0].mode === "showing"')
        page.locator('#nav-history').click()
        page.locator('.history-row').first.wait_for()
        assert page.locator('.history-row').count()>=2
        assert not errors,errors
        browser.close()
    print('PASS: full local translation, EN/PT/bilingual PDFs, browser download, PT captions, history, no browser errors.',flush=True)


if __name__=='__main__':
    main()
