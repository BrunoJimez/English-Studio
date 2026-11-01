"""Test MediaRecorder with a synthetic browser microphone, never the physical device."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import time

root=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge', headless=True, args=[
        '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
        '--use-file-for-fake-audio-capture='+str(root/'tmp'/'sample.wav'),
    ])
    page=browser.new_page(permissions=['microphone'])
    page.goto('http://127.0.0.1:8765',wait_until='networkidle')
    page.locator('#record').click()
    page.get_by_role('button',name='Parar gravação').wait_for()
    # Capture enough of the known synthetic sentence to exercise the real ASR.
    time.sleep(8)
    with page.expect_response(lambda r:'/audio/transcribe' in r.url,timeout=180000) as response:
        page.get_by_role('button',name='Parar gravação').click()
    result=response.value.json()
    assert response.value.status==200,result
    assert len(result['text'])>10,result
    assert 'pronúncia' in result['note']
    browser.close()
print('Microphone UI -> MediaRecorder -> real audio upload -> Whisper -> editable text: PASS',flush=True)
