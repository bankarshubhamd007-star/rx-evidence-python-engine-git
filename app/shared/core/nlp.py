"""
rag/nlp.py — Natural Language Processing Utilities
==================================================
Handles text normalization for BM25 sparse keyword retrieval.
Uses stemming and stop-word removal.
"""

import string
import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer

_stemmer: SnowballStemmer | None = None
_stop_words: set[str] | None = None

# Custom fluff words commonly found in highlighted web claims
_CUSTOM_STOP_WORDS = {
    "claim", "claims", "that", "this", "lacks", "solid", "scientific", "backing",
    "evidence", "shows", "proves", "suggests", "maybe", "why", "does", "is",
    "are", "the", "a", "an", "and", "or", "but", "if", "then", "else", "when",
    "how", "where", "what", "who", "which", "it", "they", "them", "their", "there"
}

def init_nlp() -> None:
    """Initialize NLTK resources. Downloads stopwords corpus if missing."""
    global _stemmer, _stop_words
    if _stemmer is not None:
        return
        
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
        
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger_eng')
    except LookupError:
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
        
    base_stopwords = set(stopwords.words('english'))
    _stop_words = base_stopwords.union(_CUSTOM_STOP_WORDS)
    _stemmer = SnowballStemmer('english')

def extract_search_keywords(text: str) -> str:
    """
    Extracts core medical keywords from a long conversational claim.
    Uses POS tagging to keep only Nouns, Adjectives, and Gerunds (e.g., 'shaving'),
    and limits the output to 4 words so strict APIs (PubMed) don't return 0 results.
    """
    init_nlp()
    
    # 1. Lowercase and remove punctuation
    text = text.lower().translate(str.maketrans('', '', string.punctuation))
    tokens = text.split()
    
    # 2. POS Tagging (done before stopword removal for better context accuracy)
    tags = nltk.pos_tag(tokens)
    
    # 3. Filter for Nouns (NN*), Adjectives (JJ*), Gerunds (VBG) that aren't stopwords
    allowed_tags = ('NN', 'JJ', 'VBG')
    keywords = []
    for word, tag in tags:
        # Ignore Pyright because init_nlp guarantees _stop_words is not None
        if word not in _stop_words and tag.startswith(allowed_tags):  # type: ignore
            keywords.append(word)
    
    # 4. Fallback if the strict tagging removed everything
    if not keywords:
        keywords = [t for t in tokens if t not in _stop_words] # type: ignore
    if not keywords:
        keywords = tokens
        
    # 5. Limit to max 4 words for optimal PubMed boolean matching
    return " ".join(keywords[:4])

def preprocess_text_for_bm25(text: str) -> list[str]:
    """
    Normalizes text for BM25 retrieval by:
    1. Lowercasing
    2. Removing punctuation
    3. Tokenizing
    4. Removing stop words
    5. Applying Snowball stemming
    """
    init_nlp()
    
    # 1 & 2. Lowercase and remove punctuation
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # 3. Tokenize (simple split since punctuation is gone)
    tokens = text.split()
    
    # 4 & 5. Stop word removal and stemming
    # (Safe to ignore Pyright errors since init_nlp ensures they are not None)
    processed = [_stemmer.stem(t) for t in tokens if t not in _stop_words] # type: ignore
    
    return processed
