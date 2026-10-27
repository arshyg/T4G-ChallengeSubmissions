"""Retrieval over the Orca archive (provided; you don't need to change it).

The transcripts in corpus/transcripts.jsonl are already split into short passages
("segments"), each with an episode, timestamp and speaker. This module ranks them
against a query with BM25, a classic keyword-relevance score, after applying any
platform / speaker / date filters. People's names in the query don't count toward
relevance (use the speaker filter for that), and passages scoring below MIN_SCORE are
dropped, so a topic the archive never covers returns no results. A query with no topic
words at all (just a name, or "what did she say") lists the filtered passages in time
order instead, so speaker + date filters alone still work. Weakly related
passages can still come back: deciding whether they actually answer the question is
the agent's job.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / "corpus"
MIN_SCORE = 1.0
_STOP = set("""a an and are as at be been but by did do does for from had has have he her his i if in
into is it its me my no not of on or our she so that the their them then there they this to was we
were what when where which who why will with would you your about said say says""".split())
# Words that describe the question rather than a topic; they don't count toward relevance.
_GENERIC = set("""say said saying statement statements comment comments remark remarks quote quotes
quoted mention mentions mentioned talk talked talking discuss discussed speak spoke spoken word words
think thought view views position positions stance opinion opinions claim claims around then
cable news tv youtube tiktok podcast podcasts video videos show shows episode episodes interview
interviews appearance appearances clip clips""".split())


def _tokens(text):
    out = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in _STOP:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.append(word)
    return out


def load_segments():
    with open(CORPUS / "transcripts.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Index:
    def __init__(self, segments, k1=1.5, b=0.75):
        self.segments = segments
        self.docs = [_tokens(s["text"]) for s in segments]
        self.k1, self.b = k1, b
        self.avg_len = sum(map(len, self.docs)) / max(len(self.docs), 1)
        self.names = {t for s in segments for t in _tokens(s["speaker"])}
        df = Counter(t for doc in self.docs for t in set(doc))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def _score(self, query_terms, i):
        doc = self.docs[i]
        tf = Counter(doc)
        score = 0.0
        for t in query_terms:
            if t in tf:
                f = tf[t]
                score += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(doc) / self.avg_len))
        return score

    def search(self, query, keep=lambda segment: True, top_k=5, min_score=MIN_SCORE):
        generic = {g for word in _GENERIC for g in _tokens(word)}
        terms = [t for t in _tokens(query) if t not in self.names and t not in generic]
        if not terms:
            # No topic to rank by: list what the filters allow, oldest first.
            kept = [s for s in self.segments if keep(s)]
            kept.sort(key=lambda s: (s["date"], s["timestamp"]))
            return [dict(s, score=0.0) for s in kept[:top_k]]
        scored = []
        for i, seg in enumerate(self.segments):
            if keep(seg):
                s = self._score(terms, i)
                if s >= min_score:
                    scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [dict(self.segments[i], score=round(s, 3)) for s, i in scored[:top_k]]


_INDEX = None


def get_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = Index(load_segments())
    return _INDEX
