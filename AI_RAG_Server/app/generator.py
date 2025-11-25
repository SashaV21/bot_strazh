# app/generator.py
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from retriever import get_retriever
from system_prompt import system_PROMPT
import os

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def build_rag_chain():
    # Получаем IP хоста из переменной окружения (см. Шаг 2)
    host_ip = os.getenv("HOST_IP", "host.docker.internal")
    llm = OllamaLLM(
        model="mistral",
        temperature=0.2,
        base_url=f"http://{host_ip}:11434"
    )
    retriever = get_retriever()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_PROMPT),
        ("human", "Текст для проверки: {question}"),
        ("system", "Ответ:")
    ])

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain, retriever