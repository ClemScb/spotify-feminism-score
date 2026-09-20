# Méthode de calcul

Tout ce qui suit est discutable. Les constantes sont dans `scripts/score.py` et
modifiables en ligne de commande. Si le résultat te paraît injuste, c'est
probablement qu'une de ces valeurs ne correspond pas à ton intuition — change-la.

## Les trois variables

### 1. Gravité (`gravity`, 0 à 5)

| Valeur | Statut | Ce que ça décrit |
|--------|--------|------------------|
| 5 | `convicted` | Condamnation définitive pour des faits graves |
| 4 | `admitted` | Faits reconnus publiquement par l'artiste |
| 4 | `charged` | Mise en examen, procès en cours |
| 3 | `accused_multiple` | Accusations multiples, documentées, concordantes |
| 3 | `dismissed` | Classement sans suite : l'affaire **n'a pas été tranchée** |
| 2 | `accused_single` | Accusation isolée, publique et documentée |
| 2 | `controversy` | Propos tenus par l'artiste en son nom propre |
| 0 | `no_bill` | Pas de mise en accusation : l'enquête conclut à l'absence d'infraction |
| 0 | `acquitted` | **Relaxe prononcée par un tribunal** |

Les trois crans du bas ne doivent jamais être confondus, et c'est le point le plus
important de ce fichier.

Une **relaxe** est un jugement : une juridiction a examiné l'affaire et déclaré la
personne non coupable. Si la justice a tranché en sa faveur, il faut lui faire
confiance. La mise en cause est donc annulée, sans plus : l'entrée ne coûte rien,
mais elle ne rapporte rien non plus. Les titres de cet artiste redeviennent des
titres comme les autres, et sortent aussi des deux pourcentages.

Une **absence de mise en accusation** produit le même effet : l'enquête n'a pas
trouvé d'infraction, la gravité est nulle.

Les entrées à gravité nulle restent dans la base et s'affichent sous « Pour
mémoire ». Elles sont conservées parce que l'information a de la valeur — savoir
qu'une affaire a existé et comment elle s'est terminée — mais elles ne pèsent
nulle part.

Un **classement sans suite** signifie que le parquet estime les preuves
insuffisantes. Aucune juridiction n'a jugé, les faits ne sont ni établis ni
écartés, et de nouvelles plaintes restent possibles. C'est donc traité comme une
affaire ouverte, à la gravité des accusations — et surtout pas comme une relaxe.

La gravité et le statut sont deux champs distincts : le statut décrit la réalité
judiciaire, la gravité est la pondération qu'on choisit de lui donner. On peut
ajuster l'une sans falsifier l'autre.

### Ce qui est hors périmètre

Les polémiques portant sur des **paroles de chansons** n'entrent pas dans la base.
Un texte où l'artiste met en scène un personnage n'est pas un acte, et le score
suit des actes. Les propos tenus par l'artiste en son nom propre, eux, restent
dans le périmètre.

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
