# app/main.py
import sys
import os
import re
import logging
from web_searcher import law_searcher
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
import uvicorn
from generator import build_rag_chain

def extract_laws_from_answer(answer):
    """Извлекает список законов после слова 'ЗАКОНЫ:'"""
    match = re.search(r'ЗАКОНЫ:\s*([^\n]+)', answer, re.IGNORECASE)
    if match:
        laws_text = match.group(1).strip()
        laws = [law.strip() for law in laws_text.split('|') if law.strip()]
        logging.error(laws)
        return laws
    return []

def add_law_links_to_answer(answer, laws):
    """Добавляет ссылки на законы к ответу"""
    if not laws:
        return answer
    
    links_section = "\n\nНайдены ссылки на законы:"
    links_added = False
    
    for i, law in enumerate(laws, 1):
        link = law_searcher.web_searcher(law)
        if link:
            # HTML для Телеграма: <a href="ссылка">текст</a>
            links_section += f"\n{i}. <a href='{link}'>{law}</a>"
            links_added = True
    
    if links_added:
        return answer + links_section
    else:
        print("Не найдено ссылок")
        return answer

app = FastAPI(title="RAG API version 0")

# Получаем и цепочку, и ретривер
qa_chain, retriever = build_rag_chain()

@app.post("/ask")
async def ask(request: Request):
    try:
        data = await request.json()
        question = data.get("question")
        if not question:
            return {"error": "Question is required"}

        # Получаем ответ
        answer = qa_chain.invoke(question)

        # Получаем источники отдельно
        docs = retriever.invoke(question)
        sources = [
            {
                "page_content": doc.page_content[:500],
                "metadata": doc.metadata
            }
            for doc in docs[:3]
        ]
        
        # ИЗВЛЕКАЕМ ЗАКОНЫ И ДОБАВЛЯЕМ ССЫЛКИ
        laws = extract_laws_from_answer(answer)
        final_answer = add_law_links_to_answer(answer, laws)
        
        return {
            "answer": final_answer, 
            "sources": sources,
            "laws_found": laws
        }

    except Exception as e:
        print("Error:", e)
        return {"error": str(e)}

if __name__ == "__main__":
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
    print("Запуск RAG API сервера...")
    print("Документация API: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)