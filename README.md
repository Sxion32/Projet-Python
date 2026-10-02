# Spread souverains et risque politique en zone euro

Ce projet étudie la dynamique des spreads souverains entre l'OAT française et le Bund allemand autour d'événements politiques, en les comparant aux spreads italien et espagnol.

## Problématique

Le risque politique est-il devenu une composante propre de la prime de risque française depuis 2024 ?

## Période d'étude

Nous partons de la date du 1er janvier 2016, soit l'année précédant l'investiture de Macron, afin de couvrir à la fois la période avant et après ce changement politique.

## Objectif

- analyser les écarts de taux à 10 ans entre pays de la zone euro ;
- identifier les mouvements spécifiques à la France autour d'événements politiques ;
- comparer les évolutions françaises, italiennes et espagnoles ;
- distinguer les chocs européens des chocs purement nationaux.

## Structure du dépôt

- `main.py` : point d'entrée du projet ;
- `requirements.txt` : dépendances Python du projet ;
- `.env.example` : exemple de variables d’environnement locales ;
- `data/` : dossier pour les données et jeux de fichiers temporaires.

## Dépendances

Le projet s’exécute dans un environnement virtuel local, sans stockage de secrets dans le dépôt.

## Lancement

1. Créer un environnement virtuel :
   python -m venv .venv
2. L'activer :
   source .venv/bin/activate
3. Installer les dépendances :
   pip install -r requirements.txt
4. Lancer le projet :
   python main.py

## Sources

Les données doivent être collectées depuis des sources publiques et documentées, avec une attention particulière à la fréquence journalière pour mesurer les effets immédiats d'un événement.

## Notes méthodologiques

- Les séries mensuelles sont utiles pour la vue de long terme, mais pas pour mesurer l'effet d'un événement daté.
- Il faut raisonner en variations autour d'événements, pas seulement en niveaux.
- Le calendrier d'événements est construit et documenté dans le projet.
- La causalité doit être discutée avec prudence : une co-occurrence n'est pas une preuve.
