from db import load_chroma_db

def get_retriever(top_k=3):
    db = load_chroma_db()
    retriever = db.as_retriever(search_kwargs={"k": top_k})
    return retriever