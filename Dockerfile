FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY . /spottube
WORKDIR /spottube
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn","src.SpotTube:app", "-c", "gunicorn_config.py"]