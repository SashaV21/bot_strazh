FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*


RUN mkdir -p /usr/share/tesseract-ocr/5/tessdata \
    && wget -O /usr/share/tesseract-ocr/5/tessdata/eng.traineddata \
       https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata \
    && wget -O /usr/share/tesseract-ocr/5/tessdata/rus.traineddata \
       https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata


WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
