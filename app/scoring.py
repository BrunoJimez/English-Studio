"""Word-error-rate scoring, independent of the language model."""
import re
import unicodedata

CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are",
    "it's": "it is", "that's": "that is", "there's": "there is", "he's": "he is",
    "she's": "she is", "can't": "can not", "cannot": "can not", "won't": "will not",
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "couldn't": "could not", "wouldn't": "would not", "shouldn't": "should not",
    "i've": "i have", "you've": "you have", "we've": "we have", "they've": "they have",
    "i'll": "i will", "you'll": "you will", "he'll": "he will", "she'll": "she will",
    "we'll": "we will", "they'll": "they will", "let's": "let us",
}


def tokens(text):
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    words = re.findall(r"[\w]+(?:'[\w]+)*", text)
    return [t for word in words for t in CONTRACTIONS.get(word, word).split()]


def compare(reference, answer):
    ref, hyp = tokens(reference), tokens(answer)
    if not ref:
        raise ValueError("Não há fala reconhecida neste trecho. Escolha outra cena.")
    # Full dynamic programming produces a real minimum edit alignment (WER).
    dp = [list(range(len(hyp) + 1))]
    for i, word in enumerate(ref, 1):
        row = [i]
        for j, other in enumerate(hyp, 1):
            row.append(min(dp[i-1][j] + 1, row[j-1] + 1, dp[i-1][j-1] + (word != other)))
        dp.append(row)
    i, j, alignment = len(ref), len(hyp), []
    while i or j:
        if i and j and dp[i][j] == dp[i-1][j-1] + (ref[i-1] != hyp[j-1]):
            alignment.append({"kind": "correct" if ref[i-1] == hyp[j-1] else "replace", "expected": ref[i-1], "actual": hyp[j-1]})
            i, j = i-1, j-1
        elif i and dp[i][j] == dp[i-1][j] + 1:
            alignment.append({"kind": "missing", "expected": ref[i-1], "actual": ""})
            i -= 1
        else:
            alignment.append({"kind": "extra", "expected": "", "actual": hyp[j-1]})
            j -= 1
    alignment.reverse()
    errors = dp[-1][-1]
    return {"score": round(max(0, 1-errors/len(ref))*100, 1), "errors": errors,
            "word_count": len(ref), "alignment": alignment,
            "method": "WER: 100 × máximo(0, 1 − (trocas + omissões + extras) / palavras da referência). Maiúsculas e pontuação não afetam a nota; contrações comuns são expandidas. A gramática é comentada separadamente."}


def excerpt(segments, start, end):
    selected = []
    for s in segments:
        if s["end"] <= start or s["start"] >= end:
            continue
        if s.get("words"):
            words = [w["word"] for w in s["words"] if start <= (w["start"]+w["end"])/2 < end]
            if words:
                selected.append("".join(words).strip())
        else:
            # Edited segments have no trustworthy word-level alignment.
            selected.append(s["text"])
    return " ".join(selected).strip()
