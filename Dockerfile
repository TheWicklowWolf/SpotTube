FROM python:3.11-slim
COPY . /spottube
WORKDIR /spottube
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn","src.SpotTube:app", "-c", "gunicorn_config.py"]