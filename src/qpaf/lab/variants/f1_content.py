"""F1: label-free content features from OCR text, the query and their overlap (docs/feature_lab/F1).

Asset `page_text`: JSONL {"page_id", "text"} for every OCR page of the corpus. IDF and vocabulary come from the
whole corpus, which carries no labels. Columns, in order (PAGE_SIDE first, so f1_page_only keeps a prefix):
p_log_tokens, p_empty, p_numeric_ratio, p_log_lines, q_has_number, q_numeric_intent, q_max_idf, q_mean_idf,
q_oov_ratio, i_coverage, i_idf_coverage, i_number_match, i_bigram_coverage.
"""
import json
import math
import re

import numpy as np

from . import Variant

TOKEN, NUMBER = re.compile(r'\w+'), re.compile(r'\d+(?:[.,]\d+)*')
NUMERIC_INTENT = ('how many', 'how much', 'percentage', 'percent', 'ratio', 'total', 'average',
                  'bao nhiêu', 'tỷ lệ', 'phần trăm', 'tổng')
PAGE_SIDE = 4
SHIFT = 1 << 32  # bigram ID = first*SHIFT + second


def tokens(text):
    return TOKEN.findall(text.lower())


class Corpus:
    """Token-ID arrays, bigram IDs, numbers and page-side features for every OCR page."""
    def __init__(self, path):
        self.vocab, self.pages = {}, {}
        with open(path, encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['page_id'] in self.pages:
                    raise ValueError(f"page_text: duplicate page {row['page_id']}")
                toks = tokens(row['text'])
                ids = np.array([self.vocab.setdefault(t, len(self.vocab)) for t in toks], dtype=np.int64)
                lines = sum(1 for part in row['text'].splitlines() if part.strip())
                self.pages[row['page_id']] = {
                    'ids': np.unique(ids), 'bigrams': np.unique(ids[:-1]*SHIFT+ids[1:]),
                    'numbers': frozenset(NUMBER.findall(row['text'])),
                    'side': [math.log1p(len(toks)), float(len(toks) < 5),
                             sum(any(c.isdigit() for c in t) for t in toks)/max(len(toks), 1), math.log1p(lines)]}
        df = np.zeros(len(self.vocab))
        for page in self.pages.values():
            df[page['ids']] += 1
        self.idf = np.log((len(self.pages)-df+0.5)/(df+0.5)+1)  # BM25-style IDF, label-free


def content_features(path, columns=None):
    """page_features hook over the corpus at `path`; `columns` keeps only the first N columns."""
    corpus = Corpus(path)

    def page_features(query_id, text, page_ids, raw):
        toks = tokens(text)
        known = np.array(sorted({corpus.vocab[t] for t in toks if t in corpus.vocab}), dtype=np.int64)
        idf = corpus.idf[known] if known.size else np.zeros(1)
        q_ids = [corpus.vocab.get(t, -1) for t in toks]
        q_bigrams = np.array([a*SHIFT+b for a, b in zip(q_ids, q_ids[1:]) if a >= 0 and b >= 0], dtype=np.int64)
        numbers, lowered = set(NUMBER.findall(text)), text.lower()
        query_side = [float(bool(numbers)), float(any(k in lowered for k in NUMERIC_INTENT)),
                      float(idf.max()), float(idf.mean()), 1-known.size/max(len(set(toks)), 1)]
        rows = []
        for page_id in page_ids:
            page = corpus.pages.get(page_id)
            if page is None:
                raise KeyError(f'page_text has no OCR row for page {page_id} (query {query_id})')
            hit = np.isin(known, page['ids'], assume_unique=True)
            rows.append(page['side']+query_side+[
                hit.mean() if known.size else 0., (idf*hit).sum()/idf.sum() if known.size and idf.sum() > 0 else 0.,
                float(bool(numbers & page['numbers'])),
                np.isin(q_bigrams, page['bigrams']).mean() if q_bigrams.size else 0.])
        return np.asarray(rows, dtype=np.float64)[:, :columns]
    return page_features


def build(assets):
    return Variant('f1_content', page_features=content_features(assets['page_text']))
