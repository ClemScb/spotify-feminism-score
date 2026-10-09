#!/usr/bin/env python3
"""
Controle la coherence de artists.json. Lance automatiquement par GitHub Actions
a chaque modification de la base, et utilisable en local :

    python3 scripts/validate.py
"""

import json
import re
import sys
from pathlib import Path

VALID_STATUS = {
    "convicted", "admitted", "charged", "accused_multiple", "accused_single",
    "dismissed", "investigation", "no_bill", "acquitted", "controversy",
}
NEUTRAL = {"acquitted"}
DATE = re.compile(r"^(\d{4}(-\d{2})?)?$")


def main():
    path = Path("artists.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.exit("artists.json illisible : %s" % exc)

    errors, warnings = [], []
    seen = {}

    for i, a in enumerate(data.get("artists", [])):
        tag = a.get("name") or "entree #%d" % i
        if tag.startswith("EXEMPLE"):
            continue

        if not a.get("name"):
            errors.append("%s : champ name manquant" % tag)
        if a.get("status") not in VALID_STATUS:
            errors.append("%s : statut inconnu %r" % (tag, a.get("status")))

        g = a.get("gravity")
        if not isinstance(g, (int, float)):
            errors.append("%s : gravity doit etre un nombre" % tag)
        elif not 0 <= g <= 5:
            errors.append("%s : gravity hors de 0-5 (%s)" % (tag, g))
        elif a.get("status") in NEUTRAL and g != 0:
            errors.append("%s : une relaxe doit avoir gravity 0, pas %s" % (tag, g))

        if not DATE.match(str(a.get("public_since", ""))):
            errors.append("%s : public_since doit etre AAAA, AAAA-MM ou vide" % tag)

        srcs = a.get("sources") or []
        if not srcs:
            errors.append("%s : aucune source" % tag)
        elif all("wikidata.org" in s for s in srcs):
            errors.append("%s : il faut au moins une source hors Wikidata" % tag)

        summary = a.get("summary") or ""
        if len(summary) < 40:
            errors.append("%s : summary trop court pour etre factuel" % tag)
        low = summary.lower()
        if a.get("status") != "convicted" and re.search(r"\bcondamn", low) and "non" not in low:
            warnings.append("%s : le resume dit 'condamne' mais le statut est %s"
                            % (tag, a.get("status")))
        if not a.get("categories"):
            warnings.append("%s : aucun chef renseigne" % tag)

        key = (a.get("name") or "").strip().lower()
        if key in seen:
            errors.append("%s : doublon" % tag)
        seen[key] = True

    total = len([a for a in data.get("artists", []) if not str(a.get("name", "")).startswith("EXEMPLE")])
    print("%d entrees controlees." % total)

    for w in warnings:
        print("  avertissement : %s" % w)
    for e in errors:
        print("  ERREUR : %s" % e)

    if errors:
        sys.exit("\n%d erreur(s). La base n'est pas valide." % len(errors))
    print("Base valide.")


if __name__ == "__main__":
    main()
