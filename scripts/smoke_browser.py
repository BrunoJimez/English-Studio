"""Real browser check. Run against the local app, no mocks."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width":1440,"height":1100}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto('http://127.0.0.1:8765', wait_until='networkidle')
        page.get_by_role('heading', name='Aprenda com cada cena.').wait_for()
        page.screenshot(path=str(ROOT/'tmp'/'desktop.png'), full_page=True)
        page.locator('#open-settings').click()
        page.locator('#settings-dialog').wait_for(state='visible')
        assert page.locator('#model-select option').count() > 0
        page.locator('#settings-dialog .close-dialog').click()
        page.locator('#nav-history').click()
        page.get_by_role('heading', name='Seu inglês em movimento.').wait_for()
        page.locator('#nav-study').click()
        page.set_viewport_size({"width":390,"height":844})
        page.screenshot(path=str(ROOT/'tmp'/'mobile.png'), full_page=True)
        overflow = page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,id:e.id,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right})).slice(0,20)")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Horizontal overflow on mobile: {overflow}'
        assert not errors, errors
        browser.close()
    print('Browser: desktop, mobile, settings, history, no JS errors: OK')


if __name__ == '__main__':
    main()
