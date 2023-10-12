![Build Status](https://github.com/TheWicklowWolf/SpotTube/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/spottube.svg)

<p align="center">

![spottube](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/a99d7c70-c37c-4d65-b25d-04bf3bfdd37a)

</p>

Web GUI for adding Spotify Playlists/Albums to metube.


## Run using docker-compose

```yaml
version: "2.1"
services:
  huntorr:
    image: thewicklowwolf/spottube:latest
    container_name: spottube
    environment:
      - spotify_client_id=abc
      - spotify_client_secret=123
      - metube_address=http://192.168.1.2:8080
    ports:
      - 5000:5000
    restart: unless-stopped
```

---

<p align="center">

![image](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/6a52236b-330f-4761-97c0-3a526c22604f)

</p>


https://hub.docker.com/r/thewicklowwolf/spottube
