import chromadb
from chromadb.utils import embedding_functions
from scipy.spatial.distance import cosine

ef = embedding_functions.DefaultEmbeddingFunction()
claims = [
    "All damaged cells are eliminated through autophagy.",
    "Autophagy gets rid of every damaged cell."
]
embeddings = ef(claims)
dist = cosine(embeddings[0], embeddings[1])
print(f"Distance: {dist}")
