FROM python:3.12


WORKDIR /app


COPY app.py .


RUN pip install fastapi uvicorn requests


CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]