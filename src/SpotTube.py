import logging
import os
import sys
import threading
import re
from ytmusicapi import YTMusic
from flask import Flask, render_template
from flask_socketio import SocketIO
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import concurrent.futures


class Data_Handler:
    def __init__(self, spotify_client_id, spotify_client_secret, thread_limit):
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.sleep_interval = 0
        self.thread_limit = thread_limit
        self.download_folder = "downloads"
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
        self.reset()

    def reset(self):
        self.download_list = []
        self.futures = []
        self.stop_downloading_event = threading.Event()
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

    def find_youtube_link_and_download(self, song):
        try:
            self.ytmusic = YTMusic()
            artist = song["Artist"]
            title = song["Title"]
            cleaned_title = self.string_cleaner(title).lower()
            folder = song["Folder"]

            found_link = None
            search_results = self.ytmusic.search(query=artist + " " + title, filter="songs", limit=5)

            for item in search_results:
                cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                if cleaned_title in cleaned_youtube_title:
                    found_link = "https://www.youtube.com/watch?v=" + item["videoId"]
                    break
            else:
                # Try again but reverse the check otherwise select top result
                if len(search_results):
                    for item in search_results:
                        cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                        if all(word in cleaned_title for word in cleaned_youtube_title.split()):
                            found_link = "https://www.youtube.com/watch?v=" + item["videoId"]
                            break
                    else:
                        found_link = "https://www.youtube.com/watch?v=" + search_results[0]["videoId"]

        except Exception as e:
            logger.error(f"Error downloading song: {title}. Error message: {e}")
            song["Status"] = "Search Failed"

        else:
            if found_link:
                song["Status"] = "Link Found"
                file_name = os.path.join(self.string_cleaner(folder), self.string_cleaner(title) + " - " + self.string_cleaner(artist))
                full_file_path = os.path.join(self.download_folder, file_name)

                if not os.path.exists(full_file_path + ".mp3"):
                    try:
                        ydl_opts = {
                            "ffmpeg_location": "/usr/bin/ffmpeg",
                            "format": "251/best",
                            "outtmpl": full_file_path,
                            "quiet": False,
                            "progress_hooks": [self.progress_callback],
                            "sleep_interval": self.sleep_interval,
                            "writethumbnail": True,
                            "postprocessors": [
                                {
                                    "key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3",
                                    "preferredquality": "0",
                                },
                                {
                                    "key": "EmbedThumbnail",
                                },
                                {
                                    "key": "FFmpegMetadata",
                                },
                            ],
                        }
                        yt_downloader = yt_dlp.YoutubeDL(ydl_opts)
                        yt_downloader.download([found_link])
                        logger.warning("yt_dl Complete : " + found_link)
                        song["Status"] = "Download Complete"

                    except Exception as e:
                        logger.error(f"Error downloading song: {found_link}. Error message: {e}")
                        song["Status"] = "Download Failed"

                else:
                    song["Status"] = "File Already Exists"
                    logger.warning("File Already Exists: " + artist + " " + title)
            else:
                song["Status"] = "No Link Found"
                logger.warning("No Link Found for: " + artist + " " + title)

        finally:
            self.index += 1

    def master_queue(self):
        try:
            self.running_flag = True
            while not self.stop_downloading_event.is_set() and self.index < len(self.download_list):
                self.status = "Running"
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
                    self.futures = []
                    start_position = self.index
                    for song in self.download_list[start_position:]:
                        if self.stop_downloading_event.is_set():
                            break
                        logger.warning("Searching for Song: " + song["Title"] + " - " + song["Artist"])
                        self.futures.append(executor.submit(self.find_youtube_link_and_download, song))
                    concurrent.futures.wait(self.futures)

            self.running_flag = False
            if not self.stop_downloading_event.is_set():
                self.status = "Complete"
                logger.warning("Finished")

            else:
                self.status = "Stopped"
                logger.warning("Stopped")
                self.download_list = []
                self.percent_completion = 0

        except Exception as e:
            logger.error(str(e))
            self.status = "Stopped"
            logger.warning("Stopped")
            self.running_flag = False

    def progress_callback(self, d):
        if self.stop_downloading_event.is_set():
            raise Exception("Cancelled")
        if d["status"] == "finished":
            logger.warning("Download complete")

        elif d["status"] == "downloading":
            logger.warning(f'Downloaded {d["_percent_str"]} of {d["_total_bytes_str"]} at {d["_speed_str"]}')

    def monitor(self):
        while not self.stop_monitoring_event.is_set():
            self.percent_completion = 100 * (self.index / len(self.download_list)) if self.download_list else 0
            custom_data = {"Data": self.download_list, "Status": self.status, "Percent_Completion": self.percent_completion}
            socketio.emit("progress_status", custom_data)
            socketio.sleep(1)

    def string_cleaner(self, input_string):
        raw_string = re.sub(r'[\/:*?"<>|]', " ", input_string)
        temp_string = re.sub(r"\s+", " ", raw_string)
        cleaned_string = temp_string.strip()
        return cleaned_string


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

try:
    spotify_client_id = os.environ["spotify_client_id"]
    spotify_client_secret = os.environ["spotify_client_secret"]
    thread_limit = int(os.environ["thread_limit"])
except:
    spotify_client_id = "abc"
    spotify_client_secret = "123"
    thread_limit = 1

data_handler = Data_Handler(spotify_client_id, spotify_client_secret, thread_limit)


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("download")
def download(data):
    try:
        data_handler.stop_downloading_event.clear()
        if data_handler.monitor_active_flag == False:
            data_handler.stop_monitoring_event.clear()
            thread = threading.Thread(target=data_handler.monitor)
            thread.start()
            data_handler.monitor_active_flag = True

        link = data["Link"]
        ret = data_handler.spotify_extractor(link)
        if data_handler.status == "Complete":
            data_handler.download_list = []
        data_handler.download_list.extend(ret)
        if data_handler.status != "Running":
            data_handler.index = 0
            data_handler.status = "Running"
            thread = threading.Thread(target=data_handler.master_queue)
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
        "sleep_interval": data_handler.sleep_interval,
    }
    socketio.emit("settingsLoaded", data)


@socketio.on("updateSettings")
def updateSettings(data):
    data_handler.spotify_client_id = data["spotify_client_id"]
    data_handler.spotify_client_secret = data["spotify_client_secret"]
    data_handler.sleep_interval = int(data["sleep_interval"])


@socketio.on("disconnect")
def disconnect():
    data_handler.stop_monitoring_event.set()
    data_handler.monitor_active_flag = False


@socketio.on("clear")
def clear():
    logger.warning("Clear List Request")
    data_handler.stop_downloading_event.set()
    for future in data_handler.futures:
        if not future.done():
            future.cancel()
    if data_handler.running_flag == False:
        data_handler.download_list = []
        data_handler.futures = []


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
