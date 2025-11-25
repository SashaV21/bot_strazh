import sys
import os
import traceback

sys.path.append('app')

try:
    # Проверим базовые импорты
    from db import load_chroma_db
    print("✓ db imports OK")
    
    from retriever import get_retriever
    print("✓ retriever imports OK")
    
    from generator import build_rag_chain
    print("✓ generator imports OK")
    
    # Попробуем создать цепочку
    print("Building RAG chain...")
    qa_chain = build_rag_chain()
    print("✓ RAG chain built successfully!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    traceback.print_exc()