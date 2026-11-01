import pymupdf
from app.export import pdf


def test_full_transcript_paginates_and_keeps_last_dialogue():
    rows = [{"idx":i,"start":i*31,"end":i*31+25,
             "text":f"Dialogue {i}: Could you give me a hand with this exercise? Practice makes progress.",
             "translation":f"Diálogo {i}: Você pode me ajudar com este exercício? A prática leva ao progresso."} for i in range(220)]
    rows[-1]['text'] = 'LAST DIALOGUE: This is the end of the whole movie.'
    rows[-1]['translation'] = 'ÚLTIMO DIÁLOGO: Este é o fim do filme inteiro.'
    result = pdf({"title":"Longa-metragem de validação"},rows,'bilingual')
    doc = pymupdf.open(stream=result,filetype='pdf')
    assert len(doc) > 10
    assert 'LAST DIALOGUE' in doc[-1].get_text()
    assert 'ÚLTIMO DIÁLOGO' in doc[-1].get_text()
    for index, page in enumerate(doc,1):
        text = page.get_text()
        assert 'English Studio' in text
        assert str(index) in text
