import os
from langchain_chroma import Chroma  # Обновленный импорт
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from embeddings import get_embedding_model
import logging
from config import DOCUMENTS_PATH, CHROMA_DB_PATH

def build_chroma_db():
    logging.info("getting docs")
    loader = DirectoryLoader(DOCUMENTS_PATH, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=500,
        length_function=len,
        add_start_index=True
    )

    logging.info("calculating chunks")
    chunks = text_splitter.split_documents(documents)
    
    logging.info("doing embeddings")
    embeddings = get_embedding_model()

    DB_vectors = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_PATH
    )

    print("chroma DB saved at ", CHROMA_DB_PATH)

def load_chroma_db():
    embeddings = get_embedding_model()
    return Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embeddings)