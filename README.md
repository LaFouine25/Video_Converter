# Video Converter - H.264 vers HEVC

Script Python de conversion vidéo automatisée pour optimiser l'espace disque tout en conservant la qualité.

## 📋 Sommaire
- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Utilisation](#-utilisation)
- [Comportement détaillé](#-comportement-détaillé)
- [Gestion des erreurs](#-gestion-des-erreurs)
- [Journalisation](#-journalisation)
- [Exemples](#-exemples)
- [Évolutions récentes](#-évolutions-récentes)

---

## 🎯 Fonctionnalités

### Conversion vidéo
- **Scan automatique** des fichiers vidéo (MKV, MP4, AVI) dans les répertoires configurés
- **Détection des codecs** vidéo (H.264/x264, HEVC/H.265, AV1)
- **Conversion H.264 → HEVC** via FFmpeg avec encodage matériel (NVENC)
- **Comparaison des tailles** avant/après conversion
- **Seuil de réduction** : conservation du fichier original si la réduction est < 10% (ou < 2% pour le traitement uniquement audio)

### Gestion des pistes audio
- **Détection des langues** audio (français, anglais, etc.)
- **Correction des métadonnées** : conversion des tags "Avestan" en "Français"
- **Ré-encodage intelligent** :
  - Si **au moins une piste FR** existe : suppression des pistes non-FR (sans ré-encodage)
  - Si **aucune piste FR** : ré-encodage de TOUTES les pistes en **AAC 128kbps** avec conservation du nombre de canaux original
- **Préservation de la qualité** : copie des pistes audio si pas de ré-encodage nécessaire

### Gestion des sous-titres
- **Détection des codecs** de sous-titres (textuels, bitmap)
- **Exclusion des sous-titres non supportés** : PGS, HDMV, codecs numériques
- **Copie sans ré-encodage** pour éviter les erreurs FFmpeg (text→text ou bitmap→bitmap uniquement)

### Optimisation
- **Analyse approfondie** des fichiers avec `analyzeduration` et `probesize` augmentés
- **Gestion de l'espace disque** : désactivation des backups si espace < 10%
- **Backups automatiques** avec timestamp pour les fichiers originaux

---

## 📦 Prérequis

### Logiciels requis
- **Python 3.6+**
- **FFmpeg 4.0+** (avec support NVENC pour l'encodage HEVC matériel)
- **FFprobe** (inclus avec FFmpeg)

### Installation des dépendances

#### Sur Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y python3 ffmpeg
```

#### Sur macOS (avec Homebrew)
```bash
brew install python3 ffmpeg
```

#### Sur Windows (avec Chocolatey)
```bash
choco install python ffmpeg
```

---

## 🚀 Installation

1. Cloner le dépôt :
```bash
git clone https://github.com/LaFouine25/Dev_Perso.git
cd Dev_Perso/video_converter
```

2. Rendre le script exécutable :
```bash
chmod +x video_converter.py
```

---

## ⚙️ Configuration

### Fichier de configuration
Créer un fichier `video_converter.conf` au format JSON :

```json
{
  "directories": [
    "/chemin/vers/vos/videos",
    "/autre/chemin/optionnel"
  ],
  "keep_backup": true
}
```

#### Options disponibles
| Option | Type | Description | Défaut |
|--------|------|-------------|--------|
| `directories` | `list` | Liste des répertoires à scanner | *Obligatoire* |
| `keep_backup` | `bool` | Conserver les backups des fichiers originaux | `true` |

### Paramètres internes (modifiables dans le code)

#### Conversion vidéo
```python
FFMPEG_HEVC_PARAMS = [
    "-c:v", "hevc_nvenc",
    "-preset", "p7",
    "-tune", "hq",
    "-rc", "constqp",
    "-qp", "23",
    "-profile", "main10",
]
```

#### Audio
```python
AAC_BITRATE = '128k'
AAC_CHANNELS = 2  # Stéréo
AAC_CODEC = 'aac'
FRENCH_LANGUAGE_CODES = ['fr', 'fre', 'fr-FR', 'fr-CA', 'fr-CQ', 'fra']
```

#### Seuil de réduction
```python
SIZE_REDUCTION_THRESHOLD = 0.10  # 10%
SIZE_REDUCTION_THRESHOLD_AUDIO_ONLY = 0.02  # 2% (traitement uniquement audio)
```

#### Analyse FFprobe
```python
FFPROBE_ANALYZE_DURATION = 10000000  # 10MB
FFPROBE_PROBE_SIZE = 100000000  # 100MB
```

---

## 🎬 Utilisation

### Mode 1 : Scan complet des répertoires configurés
```bash
python3 video_converter.py
```

### Mode 2 : Traiter un fichier spécifique
```bash
python3 video_converter.py /chemin/vers/le/fichier.mkv
```

### Mode 3 : Traiter un répertoire spécifique
```bash
python3 video_converter.py /chemin/vers/le/repertoire/
```

### Mode 4 : Utiliser un fichier de configuration personnalisé
```bash
python3 video_converter.py ma_config.conf
```

### Mode 5 : Configuration + cible spécifiques
```bash
python3 video_converter.py ma_config.conf /chemin/vers/le/fichier.mkv
```

---

## 🔍 Comportement détaillé

### Détection des fichiers
1. Scan récursif des répertoires configurés
2. Détection des extensions : `.mkv`, `.mp4`, `.avi`
3. Ignore les fichiers déjà traités (marqueurs `.converted_hevc` et `.failed_conversion`)

### Analyse des flux
1. **Vidéo** : détection du codec, résolution, durée
2. **Audio** : détection du codec, langue, bitrate, nombre de canaux
3. **Sous-titres** : détection du codec, langue

### Traitement

#### Conversion vidéo
- Seule la vidéo **H.264** est convertie en **HEVC**
- Les fichiers déjà en HEVC ou AV1 sont ignorés
- Conversion avec encodage matériel (NVENC) pour les performances

#### Traitement audio
| Scénario | Action |
|----------|--------|
| Piste FR détectée | Conservation de la piste FR, suppression des non-FR |
| Aucune piste FR | Ré-encodage de TOUTES les pistes en AAC 128kbps |
| Piste avec tag "Avestan" | Correction en "Français (France)" |

#### Traitement sous-titres
- **Copie sans ré-encodage** pour tous les sous-titres supportés
- **Exclusion** des sous-titres bitmap (PGS, HDMV) ou codecs non standard
- Conservation des sous-titres textuels (SRT, ASS, etc.)

### Sortie
- Les fichiers **MP4 + H.264** sont convertis en **MKV + HEVC**
- Les autres extensions conservent leur format d'origine
- Ajout du suffixe `_hevc` au nom du fichier

---

## ⚠️ Gestion des erreurs

### Erreurs gérées
- **Espace disque insuffisant** : désactivation automatique des backups
- **Fichier corrompu** : marquage comme échoué, exclusion des traitements futurs
- **Codec non supporté** : exclusion des flux concernés
- **FFmpeg/FFprobe introuvable** : arrêt avec message d'erreur clair

### Fichiers de marqueurs
- `.converted_hevc` : liste des fichiers déjà convertis
- `.failed_conversion` : liste des fichiers ayant échoué

---

## 📝 Journalisation

### Fichier de log
- **Nom** : `video_converter.log` (ou personnalisé)
- **Contenu** :
  - Début/fin de chaque conversion
  - Tailles avant/après
  - Commandes FFmpeg exécutées
  - Erreurs rencontrées
  - Temps d'exécution

### Niveau de détail
- **INFO** : opérations principales, résumés
- **DEBUG** : détails techniques (activable via modification du code)

---

## 📌 Exemples

### Exemple 1 : Conversion simple
```bash
$ python3 video_converter.py
[2024-01-01 10:00:00,000] INFO - DEBUT DE LA CONVERSION VIDEO
[2024-01-01 10:00:00,001] INFO - Configuration chargée depuis video_converter.conf
[2024-01-01 10:00:00,002] INFO - Répertoires à scanner: /videos
[2024-01-01 10:00:00,005] INFO - Trouvé 5 fichiers vidéo à traiter
[2024-01-01 10:00:00,010] INFO - Fichiers H.264 à convertir: 3
[2024-01-01 10:05:00,123] INFO - Conversion terminée en 300.12 secondes
[2024-01-01 10:05:00,124] INFO - Fichiers convertis avec succès: 3
```

### Exemple 2 : Traitement d'un fichier spécifique
```bash
$ python3 video_converter.py /videos/mon_film.mkv
[2024-01-01 10:10:00,000] INFO - Traitement du fichier cible: /videos/mon_film.mkv
[2024-01-01 10:10:00,001] INFO - Codec: h264
[2024-01-01 10:10:00,002] INFO - Pistes audio: 2 (FR, EN)
[2024-01-01 10:10:00,003] INFO - Suppression de la piste audio non-FR (index 1)
[2024-01-01 10:15:00,123] INFO - Réduction de taille: 35.20% (4500MB -> 2925MB)
```

### Exemple 3 : Ré-encodage audio
```bash
$ python3 video_converter.py /videos/film_anglais.mkv
[2024-01-01 10:20:00,000] INFO - Traitement du fichier cible: /videos/film_anglais.mkv
[2024-01-01 10:20:00,001] INFO - Codec: h264
[2024-01-01 10:20:00,002] INFO - Pistes audio: 1 (EN, 320kbps, 5.1)
[2024-01-01 10:20:00,003] INFO - Ré-encodage de 1 pistes audio en AAC 128kbps (pas de piste française)
[2024-01-01 10:25:00,123] INFO - Fichier converti avec succès
```

---

## 📈 Évolutions récentes

### v1.4.0 - Gestion audio avancée
- **Ré-encodage multiple** : Si aucune piste FR, ré-encodage de TOUTES les pistes audio en AAC 128kbps
- **Conservation des canaux** : Maintien du nombre de canaux original lors du ré-encodage
- **Suppression sélective** : Si piste FR présente, suppression des pistes non-FR sans ré-encodage

### v1.3.0 - Correction des sous-titres
- **Fix FFmpeg** : Ajout de `-c:s copy` pour éviter les erreurs de ré-encodage des sous-titres
- **Exclusion des codecs bitmap** : Détection et exclusion des sous-titres PGS/HDMV
- **Détection améliorée** : Extraction des tags de langue pour les sous-titres

### v1.2.0 - Détection des codecs
- **Fix ffprobe** : Augmentation de `analyzeduration` (10MB) et `probesize` (100MB)
- **Détection complète** : Résolution des erreurs "Could not find codec parameters"
- **Analyse approfondie** : Meilleure détection des flux audio/sous-titres

### v1.1.0 - Ré-encodage audio
- **Ré-encodage AAC** : Conversion des pistes audio non-FR en AAC 128kbps stéréo
- **Détection des langues** : Support de `fr`, `fre`, `fr-FR`, `fr-CA`, `fr-CQ`, `fra`
- **Optimisation espace** : Réduction de la taille pour les fichiers avec audio haute qualité non-FR

### v1.0.0 - Version initiale
- Conversion H.264 → HEVC
- Correction des tags audio "Avestan" → "Français"
- Gestion des backups
- Journalisation complète

---

## 🛠️ Contribuer

Les contributions sont les bienvenues ! Pour contribuer :

1. Forker le dépôt
2. Créer une branche de fonctionnalité (`git checkout -b feature/nouvelle-fonction`)
3. Committer vos modifications (`git commit -m 'Ajout de la nouvelle fonction'`)
4. Pousser vers la branche (`git push origin feature/nouvelle-fonction`)
5. Ouvrir une Pull Request

---

## 📜 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🙏 Remerciements

- **FFmpeg** : [https://ffmpeg.org](https://ffmpeg.org)
- **Python** : [https://python.org](https://python.org)
- **Toute la communauté open-source** pour leurs contributions

---

*Dernière mise à jour : Août 2026*
