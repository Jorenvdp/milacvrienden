from flask import Flask, render_template, request, redirect, url_for
import json
import os
import requests
import base64
from urllib.parse import unquote

app = Flask(__name__)

ADMIN_PASSWORD = "vriendenmilac"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "milacvrienden_data.json")

SPELERS = [
    "Joren", "Jonas", "Mathias", "Ruben", "Tim", "Jelle",
    "Koen", "Yannick", "Kwinten", "Kris", "Lieven", "Davy"
]

def lege_seizoensdata():
    return {
        "stats": {s: {"goals": 0, "assists": 0} for s in SPELERS},
        "team": {"goals": 0, "tegen": 0},
        "wedstrijden": {}   # ✅ ZEER BELANGRIJK
    }
def push_json_to_github():
    print("🚀 push_json_to_github() CALLED")

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    branch = os.environ.get("GITHUB_BRANCH", "main")

    if not token or not repo:
        print("❌ GitHub push skipped: missing credentials")
        return

    url = f"https://api.github.com/repos/{repo}/contents/milacvrienden_data.json"

    with open("milacvrienden_data.json", "rb") as f:
        content = f.read()

    encoded = base64.b64encode(content).decode("utf-8")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    payload = {
        "message": "Update data via app",
        "content": encoded,
        "branch": branch
    }

    if sha:
        payload["sha"] = sha

    print("📤 Pushing JSON to GitHub...")
    response = requests.put(url, headers=headers, json=payload)
    print("✅ GitHub response:", response.status_code, response.text)

def laad_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def bewaar_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def herbereken_stats(seizoen, data):
    # stats resetten
    data[seizoen]["stats"] = {s: {"goals": 0, "assists": 0} for s in SPELERS}
    data[seizoen]["team"]["goals"] = 0
    data[seizoen]["team"]["tegen"] = 0

    for wedstrijd in data[seizoen].get("wedstrijden", {}).values():
        data[seizoen]["team"]["goals"] += wedstrijd["goals"]
        data[seizoen]["team"]["tegen"] += wedstrijd["tegen"]

        for doelpunt in wedstrijd["doelpunten"]:
            maker = doelpunt.get("maker")
            assist = doelpunt.get("assist")

            # ✅ Alleen verwerken als het GEEN owngoal is
            if maker != "OWONGOAL":

                if maker in data[seizoen]["stats"]:
                    data[seizoen]["stats"][maker]["goals"] += 1

                if assist and assist != "Geen" and assist in data[seizoen]["stats"]:
                    data[seizoen]["stats"][assist]["assists"] += 1

def normaliseer_naam(naam):
    return naam.strip().lower()

@app.route("/kies_seizoen")
def kies_seizoen():
    seizoen = request.args.get("seizoen")
    return redirect(url_for("overzicht", seizoen=seizoen))

@app.route("/", methods=["GET", "POST"])
def index():
    data = laad_data()
    seizoenen = sorted(data.keys())

    return render_template(
        "index.html",
        seizoenen=seizoenen
    )

@app.route("/nieuw_seizoen", methods=["POST"])
def nieuw_seizoen():
    if request.form.get("password") != ADMIN_PASSWORD:
        return "Geen toegang", 403

    seizoen = request.form["seizoen"]
    data = laad_data()

    if seizoen not in data:
        data[seizoen] = lege_seizoensdata()   # ✅ DIT IS CRUCIAAL
        bewaar_data(data)

    return redirect(url_for("index"))

@app.route("/wedstrijd/<seizoen>", methods=["GET", "POST"])
def wedstrijd(seizoen):
    data = laad_data()

    if request.method == "POST":
        # ✅ hier pas beginnen we aan form-data
        wedstrijdnaam = request.form["wedstrijdnaam"]
        goals = int(request.form["goals"])
        tegen = int(request.form["tegen"])

        wedstrijd_data = {
            "goals": goals,
            "tegen": tegen,
            "doelpunten": []
        }

        # ✅ maker bestaat ALLEEN hierbinnen
        for i in range(goals):
            maker = request.form.get(f"maker{i}")
            assist = request.form.get(f"assist{i}")

            if maker in ("Owngoal", "OWONGOAL"):
                wedstrijd_data["doelpunten"].append({
                    "maker": "OWONGOAL",
                    "assist": None
                })
            else:
                wedstrijd_data["doelpunten"].append({
                    "maker": maker,
                    "assist": assist
                })

        data[seizoen]["wedstrijden"][wedstrijdnaam] = wedstrijd_data

        herbereken_stats(seizoen, data)
        bewaar_data(data)
        push_json_to_github()

        return redirect(url_for("overzicht", seizoen=seizoen))

    # ✅ BIJ GET: hier mag GEEN maker-logica staan
    return render_template("wedstrijd.html",seizoen=seizoen,spelers=SPELERS)

@app.route("/wedstrijd/bewerk/<seizoen>/<wedstrijdnaam>", methods=["GET", "POST"])
def wedstrijd_bewerken(seizoen, wedstrijdnaam):

    wedstrijdnaam = unquote(wedstrijdnaam)
    data = laad_data()
    wedstrijd = data[seizoen]["wedstrijden"][wedstrijdnaam]

    if request.method == "POST":

        # ✅ WACHTWOORDCHECK ALLEEN BIJ POST
        if request.form.get("password") != ADMIN_PASSWORD:
            return "Geen toegang", 403

        goals = int(request.form["goals"])
        tegen = int(request.form["tegen"])

        wedstrijd["goals"] = goals
        wedstrijd["tegen"] = tegen
        wedstrijd["doelpunten"] = []

        for i in range(goals):
            maker = request.form[f"maker{i}"]
            assist = request.form[f"assist{i}"]
            wedstrijd["doelpunten"].append({
                "maker": maker,
                "assist": assist
            })

        herbereken_stats(seizoen, data)
        bewaar_data(data)
        return redirect(url_for("wedstrijden_lijst", seizoen=seizoen))

    # ✅ GET mag NOOIT wachtwoord checken
    return render_template(
        "wedstrijd_bewerk.html",
        seizoen=seizoen,
        wedstrijdnaam=wedstrijdnaam,
        wedstrijd=wedstrijd,
        spelers=SPELERS
    )

@app.route("/wedstrijden/<seizoen>")
def wedstrijden_lijst(seizoen):
    data = laad_data()
    wedstrijden = data[seizoen].get("wedstrijden", {})
    return render_template(
        "wedstrijden.html",
        seizoen=seizoen,
        wedstrijden=wedstrijden
    )

@app.route("/overzicht/<seizoen>")
def overzicht(seizoen):
    data = laad_data()[seizoen]

    goals = sorted(data["stats"].items(), key=lambda x: x[1]["goals"], reverse=True)
    assists = sorted(data["stats"].items(), key=lambda x: x[1]["assists"], reverse=True)
    combo = sorted(
        data["stats"].items(),
        key=lambda x: x[1]["goals"] + x[1]["assists"],
        reverse=True
    )

    return render_template(
        "overzicht.html",
        seizoen=seizoen,
        data=data,
        goals=goals,
        assists=assists,
        combo=combo
    )

if __name__ == "__main__":
    app.run()
