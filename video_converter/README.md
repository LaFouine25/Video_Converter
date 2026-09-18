# Video Converter - H.264 vers HEVC

Script Python pour convertir automatiquement les fichiers vidéo H.264 en HEVC avec FFmpeg.

## Fonctionnalités

- 🔍 Scan récursif des répertoires configurés
- 📹 Détection des fichiers MKV, MP4, AVI
- 🎯 Identification des codecs vidéo (H.264, HEVC, AV1)
- ⚡ Conversion H.264 → HEVC via FFmpeg avec NVENC
- 📊 Comparaison des tailles avant/après conversion
- ✅ Conservation uniquement si réduction ≥ 10%
- 🚫 Marquage des fichiers échoués pour éviter les retraitements
- 📝 Journalisation complète

## Prérequis

- Python 3.7+
- FFmpeg 4.4+ (avec support NVENC pour NVIDIA)
- Système d'exploitation: Linux, macOS, Windows (avec WSL)

### Installation des dépendances

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3 ffmpeg
```

#### macOS (Homebrew)
```bash
brew install python ffmpeg
```

#### Windows (Chocolatey)
```powershell
choco install python ffmpeg
```

## Installation

1. Cloner ou télécharger ce dépôt
2. Modifier le fichier de configuration
3. Exécuter le script

## Configuration

### Fichier `video_converter.conf`

```json
{
    "directories": [
        "/chemin/vers/vos/videos",
        "/autre/chemin/avec/videos"
    ],
    "min_size_mb": 10,
    "max_size_gb": 50,
    "keep_backup": true
}
```

**Options:**
- `directories`: Liste des répertoires à scanner (répertoires relatifs ou absolus)
- `min_size_mb`: Taille minimale des fichiers à traiter (en Mo)
- `max_size_gb`: Taille maximale des fichiers à traiter (en Go)
- `keep_backup`: Conserver les backups des fichiers originaux

### Paramètres FFmpeg

Les paramètres de conversion sont définis dans le script:
- Codec: `hevc_nvenc` (utilise l'encodage matériel NVIDIA)
- Preset: `p7` (qualité optimale)
- Tune: `hq` (optimisation pour la qualité)
- RC: `constqp` (contrôle du débit constant QP)
- QP: `23` (valeur de quantification)
- Profile: `main10` (profile H.265/HEVC)
- Audio: `copy` (copie sans ré-encodage)
- Sous-titres: `copy` (copie sans ré-encodage)

## Utilisation

### Exécution basique
```bash
python video_converter.py
```

### Avec un fichier de configuration personnalisé
```bash
python video_converter.py mon_config.conf
```

### Réduire la résolution d'un cran (`-R`)

Par défaut, la conversion H.264 → HEVC conserve la résolution d'origine (un film 1080p reste 1080p, un 4K reste 4K).

L'option **`-R`** (reduce) force une réduction d'un cran vers le bas parmi les résolutions standard :

| Résolution source | Résolution cible |
|-------------------|------------------|
| 4K (3840×2160)    | 1080p (1920×1080) |
| 1080p (1920×1080) | 720p (1280×720)   |
| 720p (1280×720)   | inchangée (déjà minimale) |

L'option `-R` est **uniquement accessible en ligne de commande** et peut être placée n'importe où parmi les arguments :

```bash
# Cible un répertoire en réduisant la résolution
python video_converter.py -R /chemin/vers/videos
python video_converter.py /chemin/vers/videos -R

# Config personnalisée + cible + réduction
python video_converter.py mon_config.conf -R /chemin/vers/videos
```

Notes :
- `-R` s'applique à toute vidéo **ré-encodée** : H.264 → HEVC, et aussi HEVC/AV1 → HEVC lorsque `process_audio_for_modern_codecs` est activé dans la configuration (le fichier arrive alors dans le pipeline de conversion). Sans cette option, les fichiers déjà en HEVC/AV1 ne sont pas traités et ne sont donc pas affectés par `-R`.
- Réduire la résolution d'un fichier HEVC/AV1 nécessite de **ré-encoder** la vidéo (impossible avec `-c:v copy`), donc la conversion est plus longue.
- Un fichier déjà en 720p (ou plus bas) n'est pas réduit.
- Une résolution intermédiaire (ex. 1440p) est rabaissée au cran standard immédiatement inférieur.

### Exemple de sortie
```
2024-01-15 10:30:00 - INFO - Configuration chargée depuis video_converter.conf
2024-01-15 10:30:00 - INFO - Répertoires à scanner: /videos/movies, /videos/series
2024-01-15 10:30:01 - INFO - Scan du répertoire: /videos/movies
2024-01-15 10:30:02 - INFO - Trouvé 50 fichiers vidéo à traiter
2024-01-15 10:30:03 - INFO - Fichiers H.264 à convertir: 25
2024-01-15 10:30:04 - INFO - Conversion de /videos/movies/movie1.mkv vers /videos/movies/movie1_hevc.mkv
2024-01-15 10:35:00 - INFO - Conversion terminée en 296.50 secondes
2024-01-15 10:35:00 - INFO - Réduction de taille: 45.20% (15000000000 -> 8200000000 bytes)
2024-01-15 10:35:01 - INFO - Fichier converti avec succès et remplacé
...
2024-01-15 11:30:00 - INFO - RESUME DE LA CONVERSION
2024-01-15 11:30:00 - INFO - Durée totale: 0:59:59
2024-01-15 11:30:00 - INFO - Fichiers convertis avec succès: 20
2024-01-15 11:30:00 - INFO - Fichiers échoués ou ignorés: 5
```

## Fichiers générés

- `video_converter.log`: Journal des opérations
- `.failed_conversion`: Liste des fichiers échoués
- `.converted_hevc`: Liste des fichiers déjà convertis
- `*.backup_YYYYMMDD_HHMMSS`: Backups des fichiers originaux

## Personnalisation

### Changer les paramètres FFmpeg

Modifier les constantes dans le script:
```python
FFMPEG_HEVC_PARAMS = [
    "-c:v", "hevc_nvenc",
    "-preset", "p7",
    "-tune", "hq",
    "-rc", "constqp",
    "-qp", "23",
    "-profile", "main10",
    "-c:a", "copy",
    "-c:s", "copy",
    "-map", "0"
]
```

### Changer le seuil de réduction

```python
SIZE_REDUCTION_THRESHOLD = 0.10  # 10%
```

## Dépannage

### Erreur: ffmpeg non trouvé
```
ERREUR: ffmpeg et ffprobe sont requis. Veuillez les installer.
```
**Solution:** Installer FFmpeg comme indiqué dans les prérequis.

### Erreur: Impossible de détecter le codec
```
Codec inconnu pour /chemin/fichier.mkv, ignoré
```
**Solution:** Vérifier que le fichier est valide avec `ffprobe /chemin/fichier.mkv`

### Erreur: Pas de GPU NVIDIA
```
Error while opening encoder for output stream #0:0 - hardware encoder (codec hevc) not available
```
**Solution:** Utiliser un autre encodeur:
- `libx265` pour le CPU (plus lent)
- `hevc_amf` pour AMD
- `hevc_videotoolbox` pour macOS

## Contribution

Les contributions sont les bienvenues ! Ouvrez une issue ou soumettez une pull request.

## Licence

MIT
