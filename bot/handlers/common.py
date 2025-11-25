import io
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader

# Укажите путь к tesseract, если он не в PATH (обычно не нужно на Arch)
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def read_image(image_np):
    """
    Распознаёт текст на изображении (numpy array) с помощью Tesseract.
    Поддержка русского и английского языков.
    """
    try:
        # Конвертируем numpy array → PIL Image
        image = Image.fromarray(image_np)
        # Распознаём текст
        text = pytesseract.image_to_string(image, lang='rus+eng')
        return text.strip()
    except Exception as e:
        print(f"Ошибка Tesseract: {e}")
        return "Error occurred when parsing image"


def read_PDF(pdf_data):
    """
    Извлекает текст из PDF-файла (объект BytesIO).
    """
    try:
        text = ''
        pdf_file = PdfReader(pdf_data)
        for page in pdf_file.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted
        return text.strip()
    except Exception as e:
        print(f"Ошибка PDF: {e}")
        return "Error occurred when parsing PDF"