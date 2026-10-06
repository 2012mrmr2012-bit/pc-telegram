FROM python:3.11-slim

WORKDIR /app

# منع إنشاء ملفات pyc وتشغيل مخرجات بايثون مباشرة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "start_server.py"]
