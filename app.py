from flask import Flask, render_template, jsonify, send_from_directory
import os
import requests
from geopy.distance import geodesic
import asyncio
from bleak import BleakScanner
import threading
import time

app = Flask(__name__)

# -----------------------------
# Monastery Database
# -----------------------------
monasteries = {
    "Rumtek Monastery": {
        "gps": (27.317, 88.606),
        "beacon": "AA:BB:CC:DD:EE:FF",
        "location": "Gangtok, East Sikkim",
        "year": 1734,
        "audio": "rumtek.mp3"
    },
    "Pemayangtse Monastery": {
        "gps": (27.281, 88.257),
        "beacon": "11:22:33:44:55:66",
        "location": "Pelling, West Sikkim",
        "year": 1705,
        "audio": "pemayangtse.mp3"
    }
}

AUDIO_FOLDER = os.path.join(app.root_path, "static/audio")

# Global store for detected monastery
detected_monastery = {"name": None, "audio": None}


# -----------------------------
# Flask Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/monasteries")
def get_monasteries():
    return jsonify(monasteries)


@app.route("/api/detected")
def detected():
    return jsonify(detected_monastery)


@app.route("/audio/<filename>")
def get_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)


# -----------------------------
# GPS + Beacon Detection Logic
# -----------------------------
def gps_mode():
    """Check GPS location via IP and return nearest monastery."""
    try:
        res = requests.get("https://ipinfo.io/json").json()
        lat, lng = map(float, res["loc"].split(","))
        user_location = (lat, lng)
        print("📡 GPS Location:", user_location)

        for name, info in monasteries.items():
            distance = geodesic(user_location, info["gps"]).meters
            if distance < 5000:  # 5 km radius
                print(f"📍 Near {name} (GPS detected). Switching to Beacon mode...")
                return name
        return None
    except Exception as e:
        print("❌ Error getting GPS location:", e)
        return None


async def beacon_mode(monastery_name):
    """Scan for beacons to confirm indoor location."""
    try:
        target_beacon = monasteries[monastery_name]["beacon"]
        print(f"🔍 Scanning for beacon at {monastery_name}...")
        devices = await BleakScanner.discover(timeout=5.0)

        for d in devices:
            if target_beacon in str(d):
                print(f"🎉 Inside {monastery_name}! Playing audio {monasteries[monastery_name]['audio']}")
                detected_monastery["name"] = monastery_name
                detected_monastery["audio"] = monasteries[monastery_name]["audio"]
                return True
    except Exception as e:
        print("❌ Beacon scan error:", e)
    return False


def hybrid_location_workflow():
    """Continuously check GPS + Beacons."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        monastery_name = gps_mode()
        if monastery_name:
            success = loop.run_until_complete(beacon_mode(monastery_name))
            if not success:
                # Fallback: set based on GPS only
                detected_monastery["name"] = monastery_name
                detected_monastery["audio"] = monasteries[monastery_name]["audio"]
        else:
            detected_monastery["name"] = None
            detected_monastery["audio"] = None

        time.sleep(20)


# -----------------------------
# Run Flask + Background Workflow
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=hybrid_location_workflow, daemon=True).start()
    app.run(debug=True)
