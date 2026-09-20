# Méthode de calcul

Tout ce qui suit est discutable. Les constantes sont dans `scripts/score.py` et
modifiables en ligne de commande. Si le résultat te paraît injuste, c'est
probablement qu'une de ces valeurs ne correspond pas à ton intuition — change-la.

## Les trois variables

### 1. Gravité (`gravity`, 0 à 5)

| Valeur | Statut | Ce que ça décrit | Compte |
|--------|--------|------------------|--------|
| 5 | `convicted` | Condamnation définitive, quelle que soit la nature des faits | oui |
| 4 | `admitted` | Faits reconnus publiquement par l'artiste | oui |
| 4 | `charged` | Mise en examen, procès en cours | en cours |
| 3 | `accused_multiple` | Accusations multiples, documentées, concordantes | en cours |
| 3 | `dismissed` | Classement sans suite, faute de preuves | en cours |
| 3 | `investigation` | Enquête ouverte, issue non établie | en cours |
| 3 | `no_bill` | Pas de mise en accusation, jamais jugé | en cours |
| 2 | `accused_single` | Accusation isolée, publique et documentée | en cours |
| 2 | `controversy` | Propos tenus par l'artiste en son nom propre | oui |
| 0 | `acquitted` | **Relaxe ou acquittement prononcé par une juridiction** | non |

Il n'y a **qu'une seule sortie** : une juridiction a examiné l'affaire et déclaré la
personne non coupable. Si la justice a tranché en sa faveur, il faut lui faire
confiance. Ses titres redeviennent des titres comme les autres et sortent aussi des
deux pourcentages ; l'entrée reste visible sous « Pour mémoire », parce que savoir
qu'une affaire a existé et comment elle s'est terminée a de la valeur.

Tout le reste — classement sans suite, enquête ouverte, refus de mise en accusation,
procès en cours — veut dire que l'affaire n'a **pas** été tranchée en faveur de la
personne. Un parquet qui manque de preuves ne prononce pas une innocence, et de
nouvelles plaintes restent possibles. Ces entrées comptent, et portent la mention
« en cours » pour que le lecteur ne les confonde jamais avec une condamnation.

Toutes les natures de condamnation entrent dans la base : violences sexuelles,
violences volontaires, haine raciale, mise en danger. La gravité permet ensuite de
pondérer entre elles — une rixe avec sursis et un viol n'ont pas à peser pareil.

### Ce qui est hors périmètre

Les polémiques portant sur des **paroles de chansons** qui n'ont donné lieu à aucune
procédure. Un texte où l'artiste met en scène un personnage n'est pas un acte. Dès
qu'une enquête est ouverte, en revanche, l'affaire entre dans la base.

### 2. Exposition

La part de ta bibliothèque occupée par l'artiste : `nombre de titres / total`.
Un artiste dont tu as liké 40 titres ne pèse pas comme un featuring oublié.

### 3. Connaissance de cause

C'est le cœur du score. Liker un morceau en 2014, avant que quoi que ce soit ne
sorte, relève du hasard. L'ajouter trois ans après la condamnation est un choix.

Pour chaque artiste, le champ `public_since` indique le mois où l'affaire est
devenue publique. Les titres ajoutés après cette date déclenchent un multiplicateur :

```
km = 1 + KNOWLEDGE_WEIGHT × (titres_ajoutés_après / titres_total_artiste)
```

Le multiplicateur ne s'applique qu'aux gravités positives : la connaissance de
cause aggrave ce qui est à charge, et n'a aucun sens pour une entrée neutre.

Avec `KNOWLEDGE_WEIGHT = 1.0` par défaut, le multiplicateur va de 1 (tout ajouté
avant) à 2 (tout ajouté après). Sans date d'ajout dans le fichier, `km = 1` :
l'outil ne présume pas la mauvaise foi.

## L'agrégation

Contribution d'un artiste :

```
contribution = (gravity / 5) × part_bibliothèque × km
```

Somme sur tous les artistes concernés :

```
S = Σ contributions          # 0 ≤ S ≤ 2 en théorie
score = 100 × min(1, S / CEILING)
```

`CEILING = 0.5` par défaut. Ce chiffre dit : « une bibliothèque où un quart des
titres sont d'artistes condamnés, tous likés avant révélation, vaut 100 ».
C'est arbitraire. Sans lui, les scores réalistes tourneraient autour de 3 ou 4
sur 100 et ne diraient rien à personne. Baisse-le pour un score plus sévère,
monte-le pour un score plus indulgent.

## Le bonus « bannedArtists »

Si tu fournis la liste des artistes que tu as marqués « ne plus jouer cet artiste »
dans Spotify, chacun qui figure aussi dans la base retire 2 points, plafonnés à 10.
C'est le contre-score : les gens que tu as activement écartés.

## Les deux pourcentages

```
% artistes = artistes concernés distincts / artistes distincts
% titres   = titres concernés / titres total
```

Ils sont donnés séparément parce qu'ils disent des choses différentes. Un écart
important entre les deux est en soi un résultat intéressant.

## Ce que ce score ne mesure pas

- **Les écoutes réelles.** Les likes disent ce que tu revendiques, pas ce que tu
  consommes. L'historique d'écoute étendu corrigerait ça, au prix de plusieurs
  semaines d'attente.
- **Le financement.** Un like ne rapporte rien à personne. Une écoute, si.
- **Les absents de la base.** Un score bas peut simplement signifier que tes
  artistes n'ont pas été documentés. L'outil mesure ce qu'il connaît.
- **Le fait de séparer ou non l'homme de l'artiste.** Il compte des corrélations
  entre une bibliothèque et une base de données. La question morale reste entière,
  et aucun nombre ne la tranchera.
