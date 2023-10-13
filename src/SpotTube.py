import logging
import os
import sys
import threading
import re
from ytmusicapi import YTMusic
import requests
from flask import Flask, render_template
from flask_socketio import SocketIO
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class Data_Handler:
    def __init__(self, spotify_client_id, spotify_client_secret, metube_address):
        self.full_metube_address = metube_address + "/add"
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.youtube_search_suffix = ""
        self.metube_sleep_interval = 15
        self.ytmusic = YTMusic()
        self.reset()

    def reset(self):
        self.metube_items = []
        self.stop_metube_event = threading.Event()
        self.stop_monitoring_event = threading.Event()
        self.monitor_active_flag = False
        self.status = "Idle"
        self.index = 0
        self.percent_completion = 0
        self.running_flag = False

    def spotify_extractor(self, link):
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=self.spotify_client_id, client_secret=self.spotify_client_secret))
        track_list = []

        if "album" in link:
            album_info = sp.album(link)
            album_name = album_info["name"]
            album = sp.album_tracks(link)
            for item in album["items"]:
                try:
                    track_title = item["name"]
                    artists = [artist["name"] for artist in item["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": album_name})
                except:
                    pass

        else:
            playlist = sp.playlist(link)
            playlist_name = playlist["name"]
            number_of_tracks = playlist["tracks"]["total"]
            fields = "items.track(name,artists.name)"

            offset = 0
            limit = 100
            all_items = []
            while offset < number_of_tracks:
                results = sp.playlist_items(link, fields=fields, limit=limit, offset=offset)
                all_items.extend(results["items"])
                offset += limit

            for item in all_items:
                try:
                    track = item["track"]
                    track_title = track["name"]
                    artists = [artist["name"] for artist in track["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": playlist_name})
                except:
                    pass

        return track_list

    def add_items(self):
        try:
            self.running_flag = True
            while not self.stop_metube_event.is_set() and self.index < len(self.metube_items):
                artist = self.metube_items[self.index]["Artist"]
                title = self.metube_items[self.index]["Title"]
                folder = self.metube_items[self.index]["Folder"]
                search_results = self.ytmusic.search(query=artist + " " + title + " " + self.youtube_search_suffix, filter="songs", limit=25)
                first_result = None
                cleaned_title = re.sub(r"[^\w\s]", "", title).lower()
                cleaned_title = re.sub(r"\s{2,}", " ", cleaned_title)
                for item in search_results:
                    cleaned_youtube_title = re.sub(r"[^\w\s]", "", item["title"]).lower()
                    cleaned_youtube_title = re.sub(r"\s{2,}", " ", cleaned_youtube_title)
                    if cleaned_title in cleaned_youtube_title:
                        first_result = "https://www.youtube.com/watch?v=" + item["videoId"]
                        break

                if first_result:
                    self.metube_items[self.index]["Status"] = "Link Found"
                    ret = self.add_to_metube(first_result, folder)
                    if ret == "Success":
                        self.metube_items[self.index]["Status"] = "Added to metube"
                        logger.info("Added: " + artist + " - " + title + " " + first_result)
                    else:
                        self.metube_items[self.index]["Status"] = "Error Adding to metube"
                        logger.info("Error Adding: " + artist + " - " + title + " " + first_result)
                        self.index += 1
                        self.percent_completion = 100 * (self.index / len(self.metube_items))
                        continue
                else:
                    self.metube_items[self.index]["Status"] = "No Link Found"
                    logger.info("No Link Found for: " + artist + " - " + title)
                    self.index += 1
                    self.percent_completion = 100 * (self.index / len(self.metube_items))
                    continue

                logger.info("Sleeping")
                self.index += 1
                self.percent_completion = 100 * (self.index / len(self.metube_items))
                if self.stop_metube_event.wait(timeout=self.metube_sleep_interval):
                    break
                logger.info("Sleeping Complete")

            self.running_flag = False
            if not self.stop_metube_event.is_set():
                self.status = "Complete"

            else:
                self.status = "Stopped"
                logger.info("Stopped")
                self.metube_items = []
                self.percent_completion = 0

        except Exception as e:
            logger.error(str(e))
            self.status = "Stopped"
            self.running_flag = False

    def add_to_metube(self, link, folder):
        try:
            payload = {"url": link, "quality": "best", "format": "mp3", "folder": folder}
            response = requests.post(self.full_metube_address, json=payload)
            if response.status_code == 200:
                return "Success"
            else:
                return str(response.status_code) + " : " + response.text
        except Exception as e:
            logger.error(str(e))
            return str(e)

    def monitor(self):
        while not self.stop_monitoring_event.is_set():
            custom_data = {"Data": self.metube_items, "Status": self.status, "Percent_Completion": self.percent_completion}
            socketio.emit("progress_status", custom_data)
            socketio.sleep(1)


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

try:
    spotify_client_id = os.environ["spotify_client_id"]
    spotify_client_secret = os.environ["spotify_client_secret"]
    metube_address = os.environ["metube_address"]
except:
    spotify_client_id = "abc"
    spotify_client_secret = "123"
    metube_address = "http://192.168.1.2:8080"

data_handler = Data_Handler(spotify_client_id, spotify_client_secret, metube_address)


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("download")
def download(data):
    try:
        data_handler.stop_metube_event.clear()
        if data_handler.monitor_active_flag == False:
            data_handler.stop_monitoring_event.clear()
            thread = threading.Thread(target=data_handler.monitor)
            thread.start()
            data_handler.monitor_active_flag = True

        link = data["Link"]
        ret = data_handler.spotify_extractor(link)
        data_handler.metube_items.extend(ret)
        if data_handler.status != "Running":
            data_handler.index = 0
            data_handler.status = "Running"
            thread = threading.Thread(target=data_handler.add_items)
            thread.start()

        ret = {"Status": "Success"}

    except Exception as e:
        logger.error(str(e))
        ret = {"Status": "Error", "Data": str(e)}

    finally:
        socketio.emit("download", ret)


@socketio.on("connect")
def connection():
    if data_handler.monitor_active_flag == False:
        data_handler.stop_monitoring_event.clear()
        thread = threading.Thread(target=data_handler.monitor)
        thread.start()
        data_handler.monitor_active_flag = True


@socketio.on("loadSettings")
def loadSettings():
    data = {
        "spotify_client_id": data_handler.spotify_client_id,
        "spotify_client_secret": data_handler.spotify_client_secret,
        "youtube_search_suffix": data_handler.youtube_search_suffix,
        "metube_sleep_interval": data_handler.metube_sleep_interval,
    }
    socketio.emit("settingsLoaded", data)


@socketio.on("updateSettings")
def updateSettings(data):
    data_handler.spotify_client_id = data["spotify_client_id"]
    data_handler.spotify_client_secret = data["spotify_client_secret"]
    data_handler.youtube_search_suffix = data["youtube_search_suffix"]
    data_handler.metube_sleep_interval = int(data["metube_sleep_interval"])


@socketio.on("disconnect")
def disconnect():
    data_handler.stop_monitoring_event.set()
    data_handler.monitor_active_flag = False


@socketio.on("clear")
def clear():
    logger.info("Clear List Request")
    data_handler.stop_metube_event.set()
    data_handler.percent_completion = 0
    custom_data = {"Data": data_handler.metube_items, "Status": data_handler.status, "Percent_Completion": data_handler.percent_completion}
    socketio.emit("progress_status", custom_data)
    if data_handler.running_flag == False:
        data_handler.metube_items = []


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
