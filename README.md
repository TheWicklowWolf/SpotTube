![Build Status](https://github.com/TheWicklowWolf/SpotTube/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/spottube.svg)


![spottube](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/a99d7c70-c37c-4d65-b25d-04bf3bfdd37a)


SpotTube is a tool for downloading Spotify Artists/Albums/Tracks/Playlists via yt-dlp.


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
      - artist_track_selection=all
    volumes:
      - /path/to/config:/spottube/config
      - /data/media/spottube:/spottube/downloads
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    restart: unless-stopped
```


## Configuration via environment variables

Certain values can be set via environment variables:

* __PUID__: The user ID to run the app with. Defaults to `1000`. 
* __PGID__: The group ID to run the app with. Defaults to `1000`.
* __thread_limit__: Max number of threads to use. Defaults to `1`.
* __artist_track_selection__: Select which tracks to download for an artist, options are `all` or `top`. Defaults to `all`.


## Cookies (optional)
To utilize a cookies file with yt-dlp, follow these steps:

* Generate Cookies File: Open your web browser and use a suitable extension (e.g. cookies.txt for Firefox) to extract cookies for a user on YT.

* Save Cookies File: Save the obtained cookies into a file named `cookies.txt` and put it into the config folder.


---


![image](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/6a52236b-330f-4761-97c0-3a526c22604f)


---


![SpotTubeDark](https://github.com/TheWicklowWolf/SpotTube/assets/111055425/5e4f0ed2-07e5-4915-bfb8-56e2e4a06b02)


---


https://hub.docker.com/r/thewicklowwolf/spottube