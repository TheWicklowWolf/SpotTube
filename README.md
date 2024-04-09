![Build Status](https://github.com/TheWicklowWolf/SpotTube/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/spottube.svg)


![spottube](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/a99d7c70-c37c-4d65-b25d-04bf3bfdd37a)


Web GUI for downloading Spotify Playlists/Albums.


## Run using docker-compose

```yaml
services:
  spottube:
    image: thewicklowwolf/spottube:latest
    container_name: spottube
    environment:
      - spotify_client_id=abc
      - spotify_client_secret=123
      - thread_limit=1
    volumes:
      - /path/to/config:/spottube/config
      - /data/media/spottube:/spottube/downloads
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    restart: unless-stopped
```

---


![image](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/6a52236b-330f-4761-97c0-3a526c22604f)


---


![SpotTubeDark](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/5e4f0ed2-07e5-4915-bfb8-56e2e4a06b02)


---

https://hub.docker.com/r/thewicklowwolf/spottube
