# spotify-feminism-score

Un outil qui lit ta bibliothèque Spotify et te renvoie un score de « je ne sépare pas
l'homme de l'artiste » : plus tu es proche de 100, plus ton écoute cautionne des
artistes mis en cause.

Ce n'est pas un tribunal et ce n'est pas une mesure morale. C'est un miroir chiffré,
avec des pondérations arbitraires et assumées comme telles, que tu es invité·e à
contester. La méthode complète est dans [SCORING.md](SCORING.md).

## Ce que ça calcule

- **Score de caution /100** — combine la place qu'occupent les artistes mis en cause
  dans ta bibliothèque, la gravité de chaque affaire, et le fait que tu aies ajouté
  ces titres avant ou après que l'affaire soit devenue publique.
- **% d'artistes concernés** — la part des artistes distincts de ta bibliothèque
  qui figurent dans la base.
- **% de titres concernés** — souvent très différent du précédent : trois artistes
  peuvent peser un quart de tes likes.
- **Le détail** — un tableau par artiste, avec statut judiciaire, nombre de titres,
  et contribution exacte au score, pour que chaque point soit traçable.

## Étape 1 — Récupérer ses données

Deux chemins, au choix.

**Exportify** (rapide). Va sur <https://exportify.net>, connecte-toi, et exporte la
ligne « Liked Songs » en CSV. Tu obtiens notamment la colonne `Added At`, qui est
la donnée la plus importante du lot.

**Export officiel Spotify** (lent mais garanti, aucune app à créer). Compte →
Sécurité et confidentialité → Paramètres de confidentialité → coche « Données du
compte » → Demander les données. Lien reçu sous ~5 jours. Le fichier utile est
`YourLibrary.json`, qui contient tes titres et albums sauvegardés — et un champ
`bannedArtists` listant les artistes que tu as marqués « ne plus jouer ».

Note : l'export de base ne contient pas les nombres d'écoutes. Pour ça il faut
demander l'historique d'écoute étendu, qui met plusieurs semaines.

## Étape 2 — Lancer le calcul

Dépose ton fichier dans `data/` (le dossier est gitignoré, tes données ne partent
pas sur GitHub), puis :

```bash
python3 scripts/score.py data/liked_songs.csv
```

Options utiles :

```bash
--artists artists.json     # base de référence (défaut : artists.json)
--banned "Nom1,Nom2"       # artistes que tu as bannis, pour le bonus
--json resultat.json       # export machine du résultat
--ceiling 0.5              # sensibilité du score (voir SCORING.md)
```

## Enrichir la base, depuis GitHub

Trois workflows, dans l'onglet **Actions** du dépôt. Rien à installer, rien à
lancer sur ta machine.

**1 · Chercher des artistes** — bouton « Run workflow », tu colles une liste de
noms séparés par des virgules. Le job interroge Wikidata et ouvre une pull request
contenant `review/candidates.json`. Aucune bibliothèque n'est lue : seuls des noms
d'artistes circulent, donc aucune donnée personnelle ne passe par GitHub.

**Relecture** — dans la PR, onglet Files changed, tu édites le fichier directement
dans le navigateur : statut réel à la place de `A_VERIFIER`, gravité, date de
révélation, résumé factuel, source de presse. Tu supprimes les homonymes.

**2 · Fusionner dans la base** — un second bouton applique les brouillons relus à
`artists.json` et ouvre une PR. Tout ce qui est resté incomplet est écarté, et le
journal du job dit lesquels et pourquoi.

**Vérifier la base** tourne tout seul à chaque modification d'`artists.json` :
statuts valides, gravité dans les clous, relaxe forcément à 0, au moins une source
hors Wikidata, pas de doublon, et une alerte si un résumé écrit « condamné » alors
que le statut dit autre chose.

Une fois la seconde PR fusionnée, le site se met à jour tout seul.

## Enrichir la base, en local

`scripts/enrich.py` repère les artistes de ta bibliothèque absents d'`artists.json`,
interroge Wikidata (propriété P1399, « condamné pour ») et dépose des brouillons.

```bash
python3 scripts/enrich.py data/Liked_Songs.csv --min-tracks 10
```

Il n'écrit jamais dans `artists.json` directement. Chaque brouillon sort avec le
statut `A_VERIFIER`, et la fusion refuse toute entrée dont le statut n'a pas été
corrigé à la main, dont la gravité est vide, ou dont les sources se limitent à
Wikidata. Wikidata dit « condamné pour X » sans dire si un appel a infirmé, ni
quand l'affaire est devenue publique : c'est ce que la relecture humaine apporte.

```bash
# après avoir édité data/candidates.json
python3 scripts/enrich.py --apply data/candidates.json
python3 scripts/score.py data/Liked_Songs.csv
```

`--dry-run` affiche la liste des manquants et la requête SPARQL sans toucher au réseau.

## Étape 3 — La version partageable

`index.html` à la racine est le site. Il ne fait aucun appel à Spotify : il lit le
fichier que la personne dépose, et calcule tout dans son navigateur. Aucune donnée
ne transite, il n'y a rien à héberger, et donc aucune app Spotify à créer, aucune
allowlist, aucune obligation d'être Premium.

Pour le mettre en ligne : Settings → Pages → Source `main`, dossier `/ (root)`.
Le site sera sur `https://clemscb.github.io/spotify-feminism-score/`.

Pour le tester en local, il faut un serveur — la page charge `artists.json` par
`fetch`, ce qui échoue en ouvrant le fichier directement :

```bash
python3 -m http.server
# puis http://localhost:8000
```

Le seul point de dépendance est Exportify : si le service tombe, le parcours
principal tombe avec lui. C'est pourquoi la page accepte aussi le
`YourLibrary.json` de l'export officiel.

## Sur le nom du dépôt

`feminism-score` cadre le projet sur les violences sexistes et sexuelles, qui
représentent effectivement la majorité des cas. La base de données est en réalité
plus large : elle peut accueillir du racisme, de l'antisémitisme, des violences
non genrées. À toi de décider si tu restreins le périmètre au cadrage du nom ou si
tu élargis le nom au périmètre — mais les deux doivent finir par coïncider, sinon
le score dit autre chose que ce qu'il annonce.

## Prudence

La base `artists.json` nomme des personnes réelles et leur associe des accusations.
Trois règles non négociables pour y contribuer :

1. Uniquement des faits publics, documentés, avec source vérifiable.
2. Le statut judiciaire exact — condamné, poursuivi, accusé, affaire classée — jamais
   de glissement de l'un vers l'autre.
3. La présomption d'innocence s'applique aussi dans un fichier JSON.

## Licence

MIT pour le code. La base `artists.json` est fournie telle quelle, sans garantie
d'exhaustivité ni d'exactitude, et ne constitue pas une imputation de culpabilité.
