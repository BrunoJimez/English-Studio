from app import teacher


def test_translation_score_uses_points_not_model_total(monkeypatch):
    monkeypatch.setattr(teacher, 'generate', lambda *args: {
        "pontos_significado": 70, "pontos_gramatica": 20, "pontos_ortografia": 10,
        "variacoes_regionais": ["An invented difference"],
    })
    result = teacher.teach('I need water.', 'Preciso de água.', 'translation')
    assert result['nota_traducao'] == 100
    assert result['variacoes_regionais'] == []


def test_repeated_corrections_are_collapsed(monkeypatch):
    row = {"trecho":"is you", "correcao":"are you", "explicacao":"Concordância com you."}
    monkeypatch.setattr(teacher, 'generate', lambda *args: {"correcoes":[row,row.copy()],"variacoes_regionais":[]})
    result = teacher.teach('How are you?', 'How is you?', 'dictation', 66.7)
    assert len(result['correcoes']) == 1


def test_regional_variants_are_contextual_and_conservative():
    assert teacher.regional_notes("I'm happy. How are you?") == []
    assert 'calçada' in teacher.regional_notes('Walk on the sidewalk.')[0]
    assert 'contexto' in teacher.regional_notes('I want some chips.')[0]


def test_you_agreement_does_not_invent_a_plural_only_rule():
    result=teacher.refine_agreement({"trecho":"How is you today?","correcao":"How are you today?","explicacao":"wrong"})
    assert 'singular' in result['explicacao'] and 'plural' in result['explicacao']


def test_correct_words_are_grounded_in_actual_answer(monkeypatch):
    monkeypatch.setattr(teacher, 'generate', lambda *args: {"acertos":["unspoken phrase"],"correcoes":[],"variacoes_regionais":[]})
    result = teacher.teach('one scene at a time','one seen at a time','dictation',80)
    assert result['acertos']==['Você reconheceu corretamente 4 de 5 palavras da referência normalizada.']
