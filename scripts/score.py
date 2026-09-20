#!/usr/bin/env python3
"""
Calcule le score de caution a partir d'une bibliotheque Spotify.

Entrees acceptees :
  - un CSV Exportify (Liked Songs)
  - le fichier YourLibrary.json de l'export officiel Spotify

Usage :
    python3 scripts/score.py data/liked_songs.csv
    python3 scripts/score.py data/YourLibrary.json --json resultat.json
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# --- Constantes de ponderation (voir SCORING.md) ---------------------------

KNOWLEDGE_WEIGHT = 1.0   # multiplicateur max pour les ajouts post-revelation
CEILING = 0.5            # valeur de S qui vaut 100/100
BANNED_BONUS = 2.0       # points retires par artiste banni present dans la base
BANNED_BONUS_CAP = 10.0

STATUS_LABELS = {
    "convicted": "condamne",
    "charged": "poursuivi / mis en examen",
    "accused_multiple": "accusations multiples",
    "accused_single": "accusation isolee",
    "controversy": "propos / comportements",
    "cleared": "classe / relaxe",
}


# --- Normalisation des noms ------------------------------------------------

def normalize(name):
    """Minuscules, sans accents, sans ponctuation, espaces reduits."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def split_artists(field):
    """Exportify separe les artistes multiples par des virgules."""
    parts = re.split(r"\s*,\s*|\s+feat\.?\s+|\s+&\s+", field)
    return [p.strip() for p in parts if p.strip()]


# --- Lecture des entrees ---------------------------------------------------

def load_csv(path):
    """Retourne une liste de (artiste, titre, date_ajout|None)."""
    tracks = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
        artist_col = cols.get("artist name(s)") or cols.get("artist name") or cols.get("artist")
        title_col = cols.get("track name") or cols.get("name") or cols.get("title")
        added_col = cols.get("added at") or cols.get("added_at")
        if not artist_col:
            sys.exit("Colonne artiste introuvable. Colonnes vues : %s" % reader.fieldnames)
        for row in reader:
            title = (row.get(title_col) or "").strip() if title_col else ""
            added = parse_date(row.get(added_col)) if added_col else None
            for artist in split_artists(row.get(artist_col) or ""):
                tracks.append((artist, title, added))
    return tracks


def load_library_json(path):
    """YourLibrary.json de l'export officiel. Pas de date d'ajout disponible."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    tracks = []
    for item in data.get("tracks", []):
        artist = (item.get("artist") or "").strip()
        title = (item.get("track") or "").strip()
        if artist:
            tracks.append((artist, title, None))
    banned = [b.get("name", "") for b in data.get("bannedArtists", []) if b.get("name")]
    return tracks, banned


def parse_date(value):
    if not value:
        return None
    value = value.strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value[:len(datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    return None


def parse_public_since(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


# --- Base de reference -----------------------------------------------------

def load_artists_db(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    index = {}
    for entry in data.get("artists", []):
        if entry.get("name", "").startswith("EXEMPLE"):
            continue
        for label in [entry["name"]] + entry.get("aliases", []):
            index[normalize(label)] = entry
    return index


# --- Calcul ----------------------------------------------------------------

def compute(tracks, db, banned_names):
    total = len(tracks)
    if total == 0:
        sys.exit("Aucun titre lu dans le fichier.")

    all_artists = {normalize(a) for a, _, _ in tracks}
    per_artist = defaultdict(lambda: {"n": 0, "n_post": 0, "n_dated": 0})

    for artist, _title, added in tracks:
        entry = db.get(normalize(artist))
        if not entry:
            continue
        bucket = per_artist[entry["name"]]
        bucket["entry"] = entry
        bucket["n"] += 1
        since = parse_public_since(entry.get("public_since"))
        if added and since:
            bucket["n_dated"] += 1
            if added >= since:
                bucket["n_post"] += 1

    rows = []
    S = 0.0
    flagged_tracks = 0

    for name, b in per_artist.items():
        entry = b["entry"]
        gravity = float(entry.get("gravity", 0))
        share = b["n"] / total
        km = 1.0
        if b["n_dated"]:
            km = 1.0 + KNOWLEDGE_WEIGHT * (b["n_post"] / b["n_dated"])
        contribution = (gravity / 5.0) * share * km
        S += contribution
        flagged_tracks += b["n"]
        rows.append({
            "artist": name,
            "status": entry.get("status", "?"),
            "status_label": STATUS_LABELS.get(entry.get("status"), entry.get("status", "?")),
            "gravity": gravity,
            "tracks": b["n"],
            "tracks_after_reveal": b["n_post"],
            "tracks_dated": b["n_dated"],
            "knowledge_multiplier": round(km, 2),
            "share_pct": round(100 * share, 2),
            "contribution": round(contribution, 5),
        })

    rows.sort(key=lambda r: r["contribution"], reverse=True)

    score = 100.0 * min(1.0, S / CEILING)

    banned_hits = [n for n in banned_names if normalize(n) in db]
    malus = min(BANNED_BONUS_CAP, BANNED_BONUS * len(banned_hits))
    score = max(0.0, score - malus)

    # Points par artiste : la somme reconstitue le score avant plafonnement,
    # pour que chaque ligne soit tracable.
    for r in rows:
        r["points"] = round(100.0 * r["contribution"] / CEILING, 2)

    return {
        "score": round(score, 1),
        "raw_S": round(S, 5),
        "ceiling": CEILING,
        "banned_bonus": round(malus, 1),
        "banned_matched": banned_hits,
        "total_tracks": total,
        "total_artists": len(all_artists),
        "flagged_tracks": flagged_tracks,
        "flagged_artists": len(rows),
        "pct_artists": round(100 * len(rows) / max(1, len(all_artists)), 1),
        "pct_tracks": round(100 * flagged_tracks / total, 1),
        "detail": rows,
    }


# --- Affichage -------------------------------------------------------------

def render(res):
    out = []
    out.append("")
    out.append("  SCORE DE CAUTION : %.1f / 100" % res["score"])
    out.append("  %s" % verdict(res["score"]))
    out.append("")
    out.append("  Artistes concernes : %s%% (%d sur %d)"
               % (res["pct_artists"], res["flagged_artists"], res["total_artists"]))
    out.append("  Titres concernes   : %s%% (%d sur %d)"
               % (res["pct_tracks"], res["flagged_tracks"], res["total_tracks"]))
    if res["banned_matched"]:
        out.append("  Bonus bannis       : -%.1f pts (%s)"
                   % (res["banned_bonus"], ", ".join(res["banned_matched"])))
    out.append("")

    if not res["detail"]:
        out.append("  Aucun artiste de ta bibliotheque ne figure dans la base.")
        out.append("  Cela peut vouloir dire que la base est incomplete.")
        return "\n".join(out)

    out.append("  %-28s %-26s %6s %8s %7s" % ("ARTISTE", "STATUT", "TITRES", "APRES", "POINTS"))
    out.append("  " + "-" * 79)
    for r in res["detail"]:
        out.append("  %-28s %-26s %6d %8s %7.2f" % (
            r["artist"][:28],
            r["status_label"][:26],
            r["tracks"],
            "%d/%d" % (r["tracks_after_reveal"], r["tracks_dated"]) if r["tracks_dated"] else "n/d",
            r["points"],
        ))
    out.append("")
    out.append("  APRES = titres ajoutes apres que l'affaire soit publique.")
    out.append("  Ponderations et limites : voir SCORING.md")
    return "\n".join(out)


def verdict(score):
    if score >= 75:
        return "Tu ne separes pas beaucoup."
    if score >= 50:
        return "La separation est selective."
    if score >= 25:
        return "Quelques angles morts."
    if score > 0:
        return "Bibliotheque plutot degagee."
    return "Rien a signaler dans la base actuelle."


# --- Entree ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Score de caution Spotify")
    ap.add_argument("input", help="CSV Exportify ou YourLibrary.json")
    ap.add_argument("--artists", default="artists.json", help="base de reference")
    ap.add_argument("--banned", default="", help="artistes bannis, separes par des virgules")
    ap.add_argument("--json", dest="json_out", help="ecrire le resultat en JSON")
    ap.add_argument("--ceiling", type=float, help="sensibilite du score (defaut 0.5)")
    args = ap.parse_args()

    global CEILING
    if args.ceiling:
        CEILING = args.ceiling

    path = Path(args.input)
    if not path.exists():
        sys.exit("Fichier introuvable : %s" % path)

    banned = [b.strip() for b in args.banned.split(",") if b.strip()]
    if path.suffix.lower() == ".json":
        tracks, banned_from_file = load_library_json(path)
        banned.extend(banned_from_file)
    else:
        tracks = load_csv(path)

    db = load_artists_db(args.artists)
    if not db:
        print("Attention : la base artists.json est vide.\n", file=sys.stderr)

    res = compute(tracks, db, banned)
    print(render(res))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print("\n  Resultat ecrit dans %s" % args.json_out)


if __name__ == "__main__":
    main()
