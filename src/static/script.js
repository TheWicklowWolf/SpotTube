var download_button = document.getElementById('download-button');
var clear_button = document.getElementById('clear-button');
var search_box = document.getElementById('search-box');
var config_modal = document.getElementById('config-modal');
var save_message = document.getElementById("save-message");
var save_changes_button = document.getElementById("save-changes-button");
var spotify_client_id = document.getElementById("spotify_client_id");
var spotify_client_secret = document.getElementById("spotify_client_secret");
var sleep_interval = document.getElementById("sleep_interval");
var progress_bar = document.getElementById('progress-status-bar');
var progress_table = document.getElementById('progress-table').getElementsByTagName('tbody')[0];
var socket = io();

function updateProgressBar(percentage, status) {
    progress_bar.style.width = percentage + "%";
    progress_bar.ariaValueNow = percentage + "%";
    progress_bar.classList.remove("progress-bar-striped");
    progress_bar.classList.remove("progress-bar-animated");

    if (status === "Running") {
        progress_bar.classList.remove("bg-primary", "bg-danger", "bg-dark");
        progress_bar.classList.add("bg-success");
        progress_bar.classList.add("progress-bar-animated");

    } else if (status === "Stopped") {
        progress_bar.classList.remove("bg-primary", "bg-success", "bg-dark");
        progress_bar.classList.add("bg-danger");

    } else if (status === "Idle") {
        progress_bar.classList.remove("bg-success", "bg-danger", "bg-dark");
        progress_bar.classList.add("bg-primary");

    } else if (status === "Complete") {
        progress_bar.classList.remove("bg-primary", "bg-success", "bg-danger");
        progress_bar.classList.add("bg-dark");
    }
    progress_bar.classList.add("progress-bar-striped");
}

download_button.addEventListener('click', function () {
    socket.emit("download", { "Link": search_box.value });
});

search_box.addEventListener('keydown', function (event) {
    if (event.key === "Enter") {
        socket.emit("download", { "Link": search_box.value });
    }
});

socket.on("download", (response) => {
    if (response.Status == "Success") {
        search_box.value = "";
    }
    else {
        search_box.value = response.Data;
        setTimeout(function () {
            search_box.value = "";
        }, 2000);
    }
});

clear_button.addEventListener('click', function () {
    socket.emit("clear");
});

config_modal.addEventListener('show.bs.modal', function (event) {
    socket.emit("loadSettings");

    function handleSettingsLoaded(settings) {
        spotify_client_id.value = settings.spotify_client_id;
        spotify_client_secret.value = settings.spotify_client_secret;
        sleep_interval.value = settings.sleep_interval;
        socket.off("settingsLoaded", handleSettingsLoaded);
    }
    socket.on("settingsLoaded", handleSettingsLoaded);
});

save_changes_button.addEventListener("click", () => {
    socket.emit("updateSettings", {
        "spotify_client_id": spotify_client_id.value,
        "spotify_client_secret": spotify_client_secret.value,
        "sleep_interval": sleep_interval.value,
    });
    save_message.style.display = "block";
    setTimeout(function () {
        save_message.style.display = "none";
    }, 1000);
});

socket.on("progress_status", (response) => {
    progress_table.innerHTML = '';
    response.Data.forEach(function (item) {
        var row = progress_table.insertRow();
        var cellArtist = row.insertCell(0);
        var cellTitle = row.insertCell(1);
        var cellStatus = row.insertCell(2);

        cellArtist.innerHTML = item.Artist;
        cellTitle.innerHTML = item.Title;
        cellStatus.innerHTML = item.Status;
    });
    var percent_completion = response.Percent_Completion;
    var actual_status = response.Status;
    updateProgressBar(percent_completion, actual_status);
})

const themeSwitch = document.getElementById('themeSwitch');
const savedTheme = localStorage.getItem('theme');
const savedSwitchPosition = localStorage.getItem('switchPosition');

if (savedSwitchPosition) {
    themeSwitch.checked = savedSwitchPosition === 'true';
}

if (savedTheme) {
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
}

themeSwitch.addEventListener('click', () => {
    if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    } else {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
    localStorage.setItem('theme', document.documentElement.getAttribute('data-bs-theme'));
    localStorage.setItem('switchPosition', themeSwitch.checked);
});

