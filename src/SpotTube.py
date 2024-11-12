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
from thefuzz import fuzz


class DataHandler:
    def __init__(self):
        logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
        self.logger = logging.getLogger()

        app_name_text = os.path.basename(__file__).replace(".py", "")
        release_version = os.environ.get("RELEASE_VERSION", "unknown")
        self.logger.warning(f"{'*' * 50}\n")
        self.logger.warning(f"{app_name_text} Version: {release_version}\n")
        self.logger.warning(f"{'*' * 50}")

        self.spotify_client_id = os.environ.get("spotify_client_id", "abc")
        self.spotify_client_secret = os.environ.get("spotify_client_secret", "123")
        self.thread_limit = int(os.environ.get("thread_limit", "1"))
        self.artist_track_selection = os.environ.get("artist_track_selection", "all")
        self.sleep_interval = 0
        self.download_folder = "downloads"
        self.config_folder = "config"
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
        full_cookies_path = os.path.join(self.config_folder, "cookies.txt")
        self.cookies_path = full_cookies_path if os.path.exists(full_cookies_path) else None
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

        if "artist" in link:
            unique_tracks = set()
            artist_albums = []
            offset = 0
            limit = 50

            artist_info = sp.artist(link)
            artist_name = artist_info.get("name", "Unknown Artist")

            if self.artist_track_selection == "top":
                try:
                    top_tracks = sp.artist_top_tracks(link)
                    for item in top_tracks["tracks"]:
                        track_title = item["name"]
                        artists = [artist["name"] for artist in item["artists"]]
                        artists_str = ", ".join(artists)
                        release_date = item.get("album", {}).get("release_date", "Unknown Date")
                        track_info = {"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": artist_name, "ReleaseDate": release_date}
                        if (track_info["Artist"], track_info["Title"]) not in unique_tracks:
                            unique_tracks.add((track_info["Artist"], track_info["Title"]))
                            track_list.append(track_info)
                    sorted_tracks = sorted(track_list, key=lambda x: x["ReleaseDate"])
                    return sorted_tracks

                except Exception as e:
                    self.logger.error(f"Error fetching artist's top tracks: {str(e)}")
                    return []

            while True:
                try:
                    response = sp.artist_albums(link, include_groups="album,single", limit=limit, offset=offset)
                    if response is None:
                        break
                    albums = response.get("items", [])
                    artist_albums.extend(albums)
                    if response.get("next") is None:
                        break
                    offset += limit

                except Exception as e:
                    self.logger.error(f"Error fetching artist's albums: {str(e)}")
                    break

            for album in artist_albums:
                album_id = album["id"]
                try:
                    album_info = sp.album(album_id)
                    album_name = album_info["name"]
                    release_date = album_info["release_date"]

                    album_tracks = sp.album_tracks(album_id)
                    for item in album_tracks["items"]:
                        track_title = item["name"]
                        artists = [artist["name"] for artist in item["artists"]]
                        artists_str = ", ".join(artists)
                        track_info = {"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": artist_name, "ReleaseDate": release_date}
                        if (track_info["Artist"], track_info["Title"]) not in unique_tracks:
                            unique_tracks.add((track_info["Artist"], track_info["Title"]))
                            track_list.append(track_info)
                        else:
                            pass

                except Exception as e:
                    self.logger.error(f"Error parsing track from album {album['name']}: {str(e)}")

            sorted_tracks = sorted(track_list, key=lambda x: x["ReleaseDate"])
            return sorted_tracks

        elif "track" in link:
            track_info = sp.track(link)
            album_name = track_info["album"]["name"]
            track_title = track_info["name"]
            artists = [artist["name"] for artist in track_info["artists"]]
            artists_str = ", ".join(artists)
            track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": ""})
            return track_list

        elif "album" in link:
            album_info = sp.album(link)
            album_name = album_info["name"]
            album = sp.album_tracks(link)
            for item in album["items"]:
                try:
                    track_title = item["name"]
                    artists = [artist["name"] for artist in item["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": album_name})

                except Exception as e:
                    self.logger.error(f"Error Parsing Item in Album: {str(item)} - {str(e)}")

            return track_list

        else:
            playlist = sp.playlist(link)
            playlist_name = playlist["name"]
            number_of_tracks = playlist["tracks"]["total"]
            fields = "items(track(name,artists(name)),added_at)"

            offset = 0
            limit = 100
            all_items = []
            while offset < number_of_tracks:
                results = sp.playlist_items(link, fields=fields, limit=limit, offset=offset)
                all_items.extend(results["items"])
                offset += limit

            all_items_sorted = sorted(all_items, key=lambda x: x["added_at"], reverse=False)
            for item in all_items_sorted:
                try:
                    track = item["track"]
                    track_title = track["name"]
                    artists = [artist["name"] for artist in track["artists"]]
                    artists_str = ", ".join(artists)
                    track_list.append({"Artist": artists_str, "Title": track_title, "Status": "Queued", "Folder": playlist_name})

                except Exception as e:
                    self.logger.error(f"Error Parsing Item in Playlist: {str(item)} - {str(e)}")

            return track_list

    def find_youtube_link_and_download(self, song):
        try:
            self.ytmusic = YTMusic()
            artist = song["Artist"]
            title = song["Title"]
            cleaned_artist = self.string_cleaner(artist).lower()
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
                # Try again but check for a partial match
                for item in search_results:
                    cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                    cleaned_youtube_artists = ", ".join(self.string_cleaner(x["name"]).lower() for x in item["artists"])

                    title_ratio = 100 if all(word in cleaned_title for word in cleaned_youtube_title.split()) else fuzz.ratio(cleaned_title, cleaned_youtube_title)
                    artist_ratio = 100 if cleaned_artist in cleaned_youtube_artists else fuzz.ratio(cleaned_artist, cleaned_youtube_artists)

                    if title_ratio >= 90 and artist_ratio >= 90:
                        found_link = "https://www.youtube.com/watch?v=" + item["videoId"]
                        break
                else:
                    # Default to first result if Top result is not found
                    found_link = "https://www.youtube.com/watch?v=" + search_results[0]["videoId"]

                    # Search for Top result specifically
                    top_search_results = self.ytmusic.search(query=cleaned_title, limit=5)
                    cleaned_youtube_title = self.string_cleaner(top_search_results[0]["title"]).lower()
                    if "Top result" in top_search_results[0]["category"] and top_search_results[0]["resultType"] == "song" or top_search_results[0]["resultType"] == "video":
                        cleaned_youtube_artists = ", ".join(self.string_cleaner(x["name"]).lower() for x in top_search_results[0]["artists"])
                        title_ratio = 100 if cleaned_title in cleaned_youtube_title else fuzz.ratio(cleaned_title, cleaned_youtube_title)
                        artist_ratio = 100 if cleaned_artist in cleaned_youtube_artists else fuzz.ratio(cleaned_artist, cleaned_youtube_artists)
                        if (title_ratio >= 90 and artist_ratio >= 40) or (title_ratio >= 40 and artist_ratio >= 90):
                            found_link = "https://www.youtube.com/watch?v=" + top_search_results[0]["videoId"]

        except Exception as e:
            self.logger.error(f"Error downloading song: {title}. Error message: {e}")
            song["Status"] = "Search Failed"

        else:
            if found_link:
                song["Status"] = "Link Found"
                file_name = os.path.join(self.string_cleaner(folder), self.string_cleaner(title) + " - " + self.string_cleaner(artist))
                full_file_path = os.path.join(self.download_folder, file_name)

                if not os.path.exists(full_file_path + ".mp3"):
                    try:
                        ydl_opts = {
                            "logger": self.logger,
                            "ffmpeg_location": "/usr/bin/ffmpeg",
                            "format": "bestaudio",
                            "outtmpl": full_file_path,
                            "quiet": False,
                            "progress_hooks": [lambda d: self.progress_callback(d, song)],
                            "writethumbnail": True,
                            "updatetime": False,
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
                        if self.cookies_path:
                            ydl_opts["cookiefile"] = self.cookies_path
                        yt_downloader = yt_dlp.YoutubeDL(ydl_opts)
                        yt_downloader.download([found_link])
                        self.logger.warning("yt_dl Complete : " + found_link)
                        song["Status"] = "Processing Complete"

                        self.stop_downloading_event.wait(self.sleep_interval)

                    except Exception as e:
                        self.logger.error(f"Error downloading song: {found_link}. Error message: {e}")
                        song["Status"] = "Download Failed"

                else:
                    song["Status"] = "File Already Exists"
                    self.logger.warning("File Already Exists: " + artist + " " + title)
            else:
                song["Status"] = "No Link Found"
                self.logger.warning("No Link Found for: " + artist + " " + title)

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
                        self.logger.warning("Searching for Song: " + song["Title"] + " - " + song["Artist"])
                        self.futures.append(executor.submit(self.find_youtube_link_and_download, song))
                    concurrent.futures.wait(self.futures)

            self.running_flag = False
            if not self.stop_downloading_event.is_set():
                self.status = "Complete"
                self.logger.warning("Finished")

            else:
                self.status = "Stopped"
                self.logger.warning("Stopped")
                self.download_list = []
                self.percent_completion = 0

        except Exception as e:
            self.logger.error(f"Error in Master Queue: {str(e)}")
            self.status = "Stopped"
            self.logger.warning("Stopped")
            self.running_flag = False

    def progress_callback(self, d, song):
        if self.stop_downloading_event.is_set():
            raise Exception("Cancelled")
        if d["status"] == "finished":
            self.logger.warning("Download complete")

        elif d["status"] == "downloading":
            self.logger.warning(f'Downloaded {d["_percent_str"]} of {d["_total_bytes_str"]} at {d["_speed_str"]}')
            percent_str = d["_percent_str"].replace("%", "").strip()
            percent_complete = percent_str if percent_str else 0
            song["Status"] = f"{percent_complete}% Downloaded"

    def monitor(self):
        while not self.stop_monitoring_event.is_set():
            self.percent_completion = 100 * (self.index / len(self.download_list)) if self.download_list else 0
            custom_data = {"Data": self.download_list, "Status": self.status, "Percent_Completion": self.percent_completion}
            socketio.emit("progress_status", custom_data)
            self.stop_monitoring_event.wait(1)

    def string_cleaner(self, input_string):
        raw_string = re.sub(r'[\/:*?"<>|]', " ", input_string)
        temp_string = re.sub(r"\s+", " ", raw_string)
        cleaned_string = temp_string.strip()
        return cleaned_string


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

data_handler = DataHandler()


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
            thread.daemon = True
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
            thread.daemon = True
            thread.start()

        ret = {"Status": "Success"}

    except Exception as e:
        data_handler.logger.error(f"Error Handling Download Request from UI {str(e)}")
        ret = {"Status": "Error", "Data": str(e)}

    finally:
        socketio.emit("download", ret)


@socketio.on("connect")
def connection():
    if data_handler.monitor_active_flag == False:
        data_handler.stop_monitoring_event.clear()
        thread = threading.Thread(target=data_handler.monitor)
        thread.daemon = True
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
    data_handler.logger.warning("Clear List Request")
    data_handler.stop_downloading_event.set()
    for future in data_handler.futures:
        if not future.done():
            future.cancel()
    if data_handler.running_flag == False:
        data_handler.download_list = []
        data_handler.futures = []


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
