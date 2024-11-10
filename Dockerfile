FROM python:3.12-alpine

# Set build arguments
ARG RELEASE_VERSION
ENV RELEASE_VERSION=${RELEASE_VERSION}

# Create User
ARG UID=1000
ENV UID=${UID}
ARG GID=1000
ENV GID=${GID}

RUN addgroup -g $GID general_user && \
    adduser -D -u $UID -G general_user -s /bin/sh general_user

# Install ffmpeg
RUN apk update && apk add --no-cache ffmpeg

# Create directories and set permissions
COPY . /spottube
WORKDIR /spottube
RUN mkdir -p /spottube/downloads
RUN chown -R $UID:$GID /spottube
RUN chmod -R 777 /spottube/downloads

# Install requirements and run code as general_user
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
USER general_user
CMD ["gunicorn","src.SpotTube:app", "-c", "gunicorn_config.py"]
