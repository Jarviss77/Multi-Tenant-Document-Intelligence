import spacy

class Tokenizer:
    def __init__(self, model_name: str = "en_core_web_sm", lightweight: bool = False):
        if lightweight:
            self.nlp = spacy.blank("en")
            if not self.nlp.has_pipe("senter"):
                self.nlp.add_pipe("senter")
        else:
            self.nlp = spacy.load(model_name)
            if not self.nlp.has_pipe("senter"):
                try:
                    self.nlp.add_pipe("senter")
                except ValueError:
                    pass

    def tokenize(self, text: str) -> list[str]:
        doc = self.nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]