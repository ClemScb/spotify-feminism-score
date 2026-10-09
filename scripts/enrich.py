#!/usr/bin/env python3
"""
Repere les artistes d'une bibliotheque absents de artists.json, interroge Wikidata,
et depose des BROUILLONS a verifier a la main.

Ce script n'ecrit JAMAIS dans artists.json tout seul. Wikidata dit "condamne pour X"
mais ne dit ni si un appel a infirme, ni la date de revelation publique, ni le statut
exact. Le remplissage automatique produirait des imputations non verifiees publiees
sous ton nom. La verification humaine est une etape obligatoire, pas une option.

Etape 1 - reperer et interroger :
    python3 scripts/enrich.py data/Liked_Songs.csv --min-tracks 5

    Ecrit data/candidates.json, avec un statut "A_VERIFIER" sur chaque entree.

Etape 2 - verifier a la main :
    Ouvrir data/candidates.json. Pour chaque candidat retenu : lire les sources,
    remplacer "A_VERIFIER" par un vrai statut, fixer gravity et public_since,
    ecrire un summary factuel, mettre au moins une source de presse.
    Supprimer les candidats hors sujet (homonymes, faits non pertinents).

Etape 3 - fusionner puis recalculer :
    python3 scripts/enrich.py --apply data/candidates.json
    python3 scripts/score.py data/Liked_Songs.csv

Sans reseau, --dry-run montre la liste des manquants et la requete SPARQL generee.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score import load_csv, load_library_json, normalize, load_artists_db  # noqa: E402

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "spotify-feminism-score/0.1 (https://github.com/ClemScb/spotify-feminism-score)"
BATCH = 40

# Professions musicales, pour ecarter les homonymes non musiciens.
MUSIC_OCCUPATIONS = [
    "Q177220",   # chanteur
    "Q639669",   # musicien
    "Q2252262",  # rappeur
    "Q753110",   # auteur-compositeur
    "Q36834",    # compositeur
    "Q488205",   # chanteur-compositeur
    "Q130857",   # DJ
    "Q183945",   # producteur de musique
]

SPARQL = """SELECT ?item ?itemLabel ?crime ?crimeLabel ?date ?article WHERE {
  VALUES ?name { %(names)s }
  VALUES ?occ { %(occs)s }
  ?item rdfs:label|skos:altLabel ?name .
  ?item wdt:P31 wd:Q5 ; wdt:P106 ?occ .
  OPTIONAL {
    ?item p:P1399 ?st .
    ?st ps:P1399 ?crime .
    OPTIONAL { ?st pq:P585 ?date . }
  }
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://fr.wikipedia.org/> .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}"""


def build_query(names):
    vals = " ".join('"%s"@fr "%s"@en' % (n.replace('"', ''), n.replace('"', ''))
                    for n in names)
    occs = " ".join("wd:" + q for q in MUSIC_OCCUPATIONS)
    return SPARQL % {"names": vals, "occs": occs}


def ask(query):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def library_artists(path):
    if path.suffix.lower() == ".json":
        tracks, _ = load_library_json(path)
    else:
        tracks = load_csv(path)
    counts = Counter()
    for t in tracks:
        counts[t[0]] += 1
    return counts


def cmd_find(args):
    path = Path(args.input)
    if not path.exists():
        sys.exit("Fichier introuvable : %s" % path)

    counts = library_artists(path)
    db = load_artists_db(args.artists)
    unknown = [(a, n) for a, n in counts.most_common()
               if n >= args.min_tracks and normalize(a) not in db]

    print("%d artistes dans la bibliotheque, %d absents de la base avec >= %d titres.\n"
          % (len(counts), len(unknown), args.min_tracks))
    if not unknown:
        print("Rien a enrichir.")
        return

    for a, n in unknown[:args.limit]:
        print("  %4d  %s" % (n, a))
    print()

    names = [a for a, _ in unknown[:args.limit]]
    if args.dry_run:
        print("--- requete SPARQL du premier lot ---\n")
        print(build_query(names[:BATCH]))
        return

    found = {}
    for i in range(0, len(names), BATCH):
        batch = names[i:i + BATCH]
        sys.stderr.write("Wikidata : lot %d/%d...\n" % (i // BATCH + 1, (len(names) - 1) // BATCH + 1))
        try:
            data = ask(build_query(batch))
        except Exception as exc:
            sys.exit("Echec de la requete Wikidata : %s\n"
                     "Ce script a besoin d'un acces reseau a query.wikidata.org." % exc)
        for row in data["results"]["bindings"]:
            label = row["itemLabel"]["value"]
            key = normalize(label)
            e = found.setdefault(key, {
                "name": label,
                "wikidata": row["item"]["value"],
                "wikipedia": row.get("article", {}).get("value"),
                "crimes": [],
            })
            if "crimeLabel" in row:
                crime = row["crimeLabel"]["value"]
                date = row.get("date", {}).get("value", "")[:7]
                entry = {"chef": crime, "date": date}
                if entry not in e["crimes"]:
                    e["crimes"].append(entry)
        time.sleep(1.2)

    # On ne garde que ce qui porte une condamnation declaree.
    drafts = []
    for a, n in unknown[:args.limit]:
        hit = found.get(normalize(a))
        if not hit or not hit["crimes"]:
            continue
        sources = [hit["wikidata"]]
        if hit["wikipedia"]:
            sources.append(hit["wikipedia"])
        drafts.append({
            "name": a,
            "aliases": [hit["name"]] if normalize(hit["name"]) != normalize(a) else [],
            "status": "A_VERIFIER",
            "gravity": None,
            "categories": [c["chef"] for c in hit["crimes"]],
            "public_since": "",
            "summary": "A REDIGER. Wikidata declare : "
                       + " ; ".join(c["chef"] + (" (" + c["date"] + ")" if c["date"] else "")
                                    for c in hit["crimes"])
                       + ". Verifier l'issue definitive (appel, relaxe), la date de "
                         "revelation publique, et ajouter au moins une source de presse.",
            "sources": sources,
            "_titres_dans_la_bibliotheque": n,
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"candidates": drafts}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("%d brouillon(s) ecrit(s) dans %s." % (len(drafts), out))
    print("Aucun n'entrera dans la base tant que son statut vaudra A_VERIFIER.")


def cmd_apply(args):
    cand = json.loads(Path(args.apply).read_text(encoding="utf-8"))
    base_path = Path(args.artists)
    base = json.loads(base_path.read_text(encoding="utf-8"))
    existing = {normalize(a["name"]) for a in base["artists"]}

    merged, skipped = [], []
    for c in cand.get("candidates", []):
        if c.get("status") == "A_VERIFIER" or not c.get("status"):
            skipped.append((c["name"], "statut non verifie"))
            continue
        if c.get("gravity") is None:
            skipped.append((c["name"], "gravity non renseignee"))
            continue
        press = [s for s in c.get("sources", []) if "wikidata.org" not in s]
        if not press:
            skipped.append((c["name"], "aucune source hors Wikidata"))
            continue
        if normalize(c["name"]) in existing:
            skipped.append((c["name"], "deja dans la base"))
            continue
        c.pop("_titres_dans_la_bibliotheque", None)
        base["artists"].append(c)
        merged.append(c["name"])

    if merged:
        base_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Fusionnes : %d" % len(merged))
    for m in merged:
        print("  + %s" % m)
    if skipped:
        print("\nEcartes : %d" % len(skipped))
        for name, why in skipped:
            print("  - %s (%s)" % (name, why))


def main():
    ap = argparse.ArgumentParser(description="Enrichissement de la base depuis Wikidata")
    ap.add_argument("input", nargs="?", help="CSV Exportify ou YourLibrary.json")
    ap.add_argument("--artists", default="artists.json")
    ap.add_argument("--out", default="data/candidates.json")
    ap.add_argument("--min-tracks", type=int, default=5,
                    help="ignorer les artistes en dessous de ce nombre de titres (defaut 5)")
    ap.add_argument("--limit", type=int, default=120, help="nombre max d'artistes interroges")
    ap.add_argument("--dry-run", action="store_true", help="n'interroge pas le reseau")
    ap.add_argument("--apply", help="fusionner les brouillons verifies de ce fichier")
    args = ap.parse_args()

    if args.apply:
        cmd_apply(args)
    elif args.input:
        cmd_find(args)
    else:
        ap.error("donne un fichier de bibliotheque, ou --apply data/candidates.json")


if __name__ == "__main__":
    main()
