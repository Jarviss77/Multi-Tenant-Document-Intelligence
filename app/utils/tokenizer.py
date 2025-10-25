import re
from typing import List, Iterator, Optional

try:
    import spacy
except Exception:
    spacy = None


class Tokenizer:
    """
    Tokenizer that uses spaCy when available and safe, otherwise falls back to a lightweight regex splitter.
    Ensures a sentence boundary component ('sentencizer') is present so `doc.sents` is available.
    """

    def __init__(self, lightweight: bool = False, model: str = "en_core_web_sm"):
        self.lightweight = lightweight
        self.model_name = model
        self.nlp = None
        if not lightweight and spacy is not None:
            try:
                # disable heavy components we don't need, but ensure sentencizer is present
                self.nlp = spacy.load(self.model_name, disable=["parser", "ner"])
                if "sentencizer" not in self.nlp.pipe_names:
                    try:
                        self.nlp.add_pipe("sentencizer")
                    except Exception:
                        # compatibility for older spaCy versions
                        try:
                            self.nlp.add_pipe(self.nlp.create_pipe("sentencizer"))
                        except Exception:
                            # if we cannot add sentencizer, fall back to lightweight
                            self.nlp = None
                            self.lightweight = True
            except Exception:
                # model load failed -> fallback to lightweight
                self.nlp = None
                self.lightweight = True

    def _chunk_text(self, text: str, max_len: int) -> Iterator[str]:
        """Yield text slices of at most max_len characters, splitting at whitespace to avoid cutting words."""
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + max_len, text_len)
            if end < text_len:
                split_pos = text.rfind("\n", start, end)
                if split_pos == -1:
                    split_pos = text.rfind(" ", start, end)
                if split_pos == -1 or split_pos <= start:
                    split_pos = end
                end = split_pos
            yield text[start:end]
            start = end

    def _regex_split(self, text: str) -> List[str]:
        """Very lightweight sentence splitter using punctuation heuristics."""
        pattern = re.compile(r"(?<=[\.\?\!])\s+")
        parts = [p.strip() for p in pattern.split(text) if p and p.strip()]
        return parts

    def tokenize(self, text: str) -> List[str]:
        """Return list of sentence strings. Handles very large inputs by chunking for spaCy."""
        if not text:
            return []

        if self.lightweight or self.nlp is None:
            return self._regex_split(text)

        # spaCy available: ensure we don't feed text longer than allowed
        max_len = getattr(self.nlp, "max_length", 1_000_000)
        safe_max = max_len - 1000 if max_len > 1000 else max_len

        sentences: List[str] = []
        if len(text) <= safe_max:
            doc = self.nlp(text)
            # doc.sents is now available because we ensured sentencizer was added
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            return sentences

        # Chunk text and process incrementally
        for part in self._chunk_text(text, safe_max):
            doc = self.nlp(part)
            for sent in doc.sents:
                s = sent.text.strip()
                if s:
                    sentences.append(s)

        return sentences
