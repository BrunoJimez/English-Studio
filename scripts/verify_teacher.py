import json
from pathlib import Path
import httpx

root = Path(__file__).resolve().parent.parent
with httpx.Client(base_url='http://127.0.0.1:8765', timeout=650, trust_env=False, headers={'X-Study-App':'english-studio'}) as client:
    movie = client.get('/api/movies').json()[0]
    cases = [
        ('dictation', 'Hello. How is you today? I learning English one seen at a time.', 78, 79),
        ('translation', 'Olá. Como você está hoje? Estou aprendendo inglês, uma cena de cada vez.', 90, 100),
        ('translation', 'O cachorro azul comprou três carros ontem.', 0, 40),
    ]
    for index, (mode, answer, minimum, maximum) in enumerate(cases):
        response = client.post('/api/movies/'+movie['id']+'/evaluate', json={'start':0,'end':6.16,'mode':mode,'answer':answer,'explain':True})
        assert response.status_code == 200, response.text
        result = response.json()
        (root/'tmp'/f'teacher-calibration-{index}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        assert result['lesson'], result
        assert minimum <= result['score'] <= maximum, result
        assert result['lesson']['variacoes_regionais']==[]
        corrections=result['lesson']['correcoes']
        assert len({(c['trecho'],c['correcao']) for c in corrections})==len(corrections)
        print(f'Case {index+1}: {mode}, score {result["score"]}, {len(corrections)} unique corrections',flush=True)
print('Teacher calibration: PASS',flush=True)
