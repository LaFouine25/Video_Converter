#!/usr/bin/env python3
"""
Script de conversion vidéo H.264 vers HEVC

Fonctionnalités :
- Scan des fichiers vidéo (MKV, MP4, AVI) dans les répertoires configurés
- Détection des codecs vidéo (x264, HEVC, AV1)
- Conversion des fichiers H.264 vers HEVC via FFmpeg
- Comparaison des tailles avant/après conversion
- Gestion des conversions échouées (marquage)
- Journalisation complète

Auteur: Vibe Code
Date: 2024
"""

import os
import sys
import json
import time
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


# Configuration par défaut
DEFAULT_CONFIG_FILE = "video_converter.conf"
DEFAULT_LOG_FILE = "video_converter.log"
DEFAULT_FAILED_MARKER = ".failed_conversion"
DEFAULT_CONVERTED_MARKER = ".converted_hevc"

# Extensions vidéo supportées
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi'}

# Paramètres FFmpeg pour la conversion HEVC
FFMPEG_HEVC_PARAMS = [
    "-c:v", "hevc_nvenc",
    "-preset", "p7",
    "-tune", "hq",
    "-rc", "constqp",
    "-qp", "23",
    "-profile", "main10",
    "-c:a", "copy"
]

# Seuil de réduction de taille (10%)
SIZE_REDUCTION_THRESHOLD = 0.10

# Seuil minimal d'espace disque disponible (10%)
MIN_DISK_SPACE_THRESHOLD = 0.10

# Langues pour correction audio
AVESTAN_LANG = 'Avestan/ae;ave'
FRENCH_LANG = 'fre'


@dataclass
class VideoFile:
    """Représente un fichier vidéo avec ses métadonnées."""
    path: str
    size: int
    codec: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration: Optional[float]
    
    def __str__(self):
        return f"VideoFile({self.path}, codec={self.codec}, size={self.size} bytes)"


@dataclass
class ConversionResult:
    """Résultat d'une conversion."""
    original_file: str
    converted_file: str
    original_size: int
    converted_size: int
    success: bool
    error_message: Optional[str] = None
    
    def size_reduction(self) -> float:
        """Calcule le pourcentage de réduction de taille."""
        if self.original_size == 0:
            return 0.0
        return (self.original_size - self.converted_size) / self.original_size


class VideoConverter:
    """Classe principale pour la conversion vidéo."""
    
    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE, 
                 log_file: str = DEFAULT_LOG_FILE, 
                 target_path: Optional[str] = None):
        self.config_file = config_file
        self.log_file = log_file
        self.config: Dict = {}
        self.failed_files: set = set()
        self.converted_files: set = set()
        self.keep_backup: bool = True  # Valeur par défaut
        self.target_path = target_path  # Fichier ou répertoire cible
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """Configure la journalisation."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('VideoConverter')

    def _check_disk_space(self) -> bool:
        """Vérifie si l'espace disque disponible est suffisant."""
        try:
            # Obtenir l'espace disque total et disponible
            total, used, free = shutil.disk_usage("/")
            free_percent = free / total
            
            if free_percent < MIN_DISK_SPACE_THRESHOLD:
                self.logger.warning(
                    f"Espace disque faible ({free_percent*100:.2f}% libre). "
                    f"Désactivation des backups pour économiser de l'espace."
                )
                return False
            return True
        except Exception as e:
            self.logger.error(f"Impossible de vérifier l'espace disque: {e}")
            # En cas d'erreur, on assume qu'il y a assez d'espace
            return True
        
    def load_config(self) -> bool:
        """Charge la configuration depuis le fichier .conf."""
        try:
            if not os.path.exists(self.config_file):
                self.logger.error(f"Fichier de configuration introuvable: {self.config_file}")
                return False
            
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            # Validation de la configuration
            if 'directories' not in self.config:
                self.logger.error("Le fichier de configuration doit contenir une clé 'directories'")
                return False
            
            if not isinstance(self.config['directories'], list):
                self.logger.error("'directories' doit être une liste de chemins")
                return False
            
            # Charger l'option keep_backup depuis la config (défaut: True)
            self.keep_backup = self.config.get('keep_backup', True)
            
            # Vérifier l'espace disque disponible
            # Si espace < 10%, forcer keep_backup à False
            if not self._check_disk_space():
                self.keep_backup = False
            
            self.logger.info(f"Conserver les backups: {self.keep_backup}")
            
            self.logger.info(f"Configuration chargée depuis {self.config_file}")
            self.logger.info(f"Répertoires à scanner: {', '.join(self.config['directories'])}")
            return True
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Erreur de parsing JSON dans {self.config_file}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de la configuration: {e}")
            return False
    
    def load_markers(self) -> None:
        """Charge les marqueurs de fichiers échoués ou déjà convertis."""
        marker_dir = os.path.dirname(self.config_file) or '.'
        failed_marker = os.path.join(marker_dir, DEFAULT_FAILED_MARKER)
        converted_marker = os.path.join(marker_dir, DEFAULT_CONVERTED_MARKER)
        
        self.failed_files = self._load_marker_file(failed_marker)
        self.converted_files = self._load_marker_file(converted_marker)
        
        self.logger.info(f"Fichiers marqués comme échoués: {len(self.failed_files)}")
        self.logger.info(f"Fichiers déjà convertis: {len(self.converted_files)}")
    
    def _load_marker_file(self, marker_file: str) -> set:
        """Charge un fichier marqueur."""
        if os.path.exists(marker_file):
            try:
                with open(marker_file, 'r') as f:
                    return set(line.strip() for line in f if line.strip())
            except Exception as e:
                self.logger.warning(f"Impossible de lire {marker_file}: {e}")
        return set()
    
    def save_markers(self) -> None:
        """Sauvegarde les marqueurs de fichiers."""
        marker_dir = os.path.dirname(self.config_file) or '.'
        
        # Sauvegarde des fichiers échoués
        failed_marker = os.path.join(marker_dir, DEFAULT_FAILED_MARKER)
        with open(failed_marker, 'w') as f:
            for file_path in sorted(self.failed_files):
                f.write(file_path + '\n')
        
        # Sauvegarde des fichiers convertis
        converted_marker = os.path.join(marker_dir, DEFAULT_CONVERTED_MARKER)
        with open(converted_marker, 'w') as f:
            for file_path in sorted(self.converted_files):
                f.write(file_path + '\n')
        
        self.logger.info("Marqueurs sauvegardés")
    
    def scan_video_files(self) -> List[VideoFile]:
        """Scanne les répertoires pour trouver les fichiers vidéo."""
        video_files = []
        
        # Si un target_path est fourni, l'utiliser comme source
        if self.target_path:
            if os.path.isfile(self.target_path):
                # C'est un fichier unique - toujours traiter même s'il est marqué
                self.logger.info(f"Traitement du fichier cible: {self.target_path}")
                ext = os.path.splitext(self.target_path)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    video_file = self._create_video_file(self.target_path)
                    if video_file:
                        video_files.append(video_file)
                else:
                    self.logger.warning(f"Le fichier cible n'est pas une vidéo supportée: {self.target_path}")
            elif os.path.isdir(self.target_path):
                # C'est un répertoire, scanner récursivement
                self.logger.info(f"Scan du répertoire cible: {self.target_path}")
                for root, _, files in os.walk(self.target_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        ext = os.path.splitext(file)[1].lower()
                        
                        if ext in VIDEO_EXTENSIONS:
                            # Vérifier si le fichier est déjà marqué
                            abs_path = os.path.abspath(file_path)
                            if abs_path in self.failed_files or abs_path in self.converted_files:
                                self.logger.debug(f"Fichier déjà traité: {file_path}")
                                continue
                            
                            video_file = self._create_video_file(file_path)
                            if video_file:
                                video_files.append(video_file)
            else:
                self.logger.error(f"Chemin cible introuvable: {self.target_path}")
        else:
            # Utiliser la configuration
            for directory in self.config['directories']:
                if not os.path.exists(directory):
                    self.logger.warning(f"Répertoire introuvable: {directory}")
                    continue
                
                self.logger.info(f"Scan du répertoire: {directory}")
                
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        ext = os.path.splitext(file)[1].lower()
                        
                        if ext in VIDEO_EXTENSIONS:
                            # Vérifier si le fichier est déjà marqué
                            abs_path = os.path.abspath(file_path)
                            if abs_path in self.failed_files or abs_path in self.converted_files:
                                self.logger.debug(f"Fichier déjà traité: {file_path}")
                                continue
                            
                            video_file = self._create_video_file(file_path)
                            if video_file:
                                video_files.append(video_file)
        
        self.logger.info(f"Trouvé {len(video_files)} fichiers vidéo à traiter")
        return video_files
    
    def _create_video_file(self, file_path: str) -> Optional[VideoFile]:
        """Crée un objet VideoFile avec les métadonnées."""
        try:
            file_size = os.path.getsize(file_path)
            codec_info = self.get_video_codec(file_path)
            
            return VideoFile(
                path=file_path,
                size=file_size,
                codec=codec_info.get('codec'),
                width=codec_info.get('width'),
                height=codec_info.get('height'),
                duration=codec_info.get('duration')
            )
        except Exception as e:
            self.logger.error(f"Impossible de lire les métadonnées de {file_path}: {e}")
            return None
    
    def get_video_codec(self, file_path: str) -> Dict:
        """Récupère les informations du codec vidéo via ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-show_entries', 'format=duration',
                '-of', 'json',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            codec_info = {}
            
            if data.get('streams'):
                stream = data['streams'][0]
                codec_name = stream.get('codec_name', '')
                
                # Normalisation du nom du codec
                if 'h264' in codec_name.lower() or 'x264' in codec_name.lower():
                    codec_info['codec'] = 'h264'
                elif 'hevc' in codec_name.lower() or 'h265' in codec_name.lower():
                    codec_info['codec'] = 'hevc'
                elif 'av1' in codec_name.lower():
                    codec_info['codec'] = 'av1'
                else:
                    codec_info['codec'] = codec_name.lower()
                
                codec_info['width'] = stream.get('width')
                codec_info['height'] = stream.get('height')
            
            if data.get('format'):
                duration = data['format'].get('duration')
                if duration:
                    codec_info['duration'] = float(duration)
            
            return codec_info
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffprobe a échoué pour {file_path}: {e.stderr}")
            return {'codec': None}
        except json.JSONDecodeError as e:
            self.logger.error(f"Erreur de parsing ffprobe pour {file_path}: {e}")
            return {'codec': None}
        except Exception as e:
            self.logger.error(f"Erreur lors de la détection du codec pour {file_path}: {e}")
            return {'codec': None}
    
    def get_audio_streams_info(self, file_path: str) -> List[Dict]:
        """Récupère les informations des pistes audio via ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'a',
                '-show_entries', 'stream=index,codec_name',
                '-show_entries', 'stream_tags=language',
                '-of', 'json',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            audio_streams = []
            if data.get('streams'):
                for stream in data['streams']:
                    audio_info = {
                        'index': stream.get('index'),
                        'codec': stream.get('codec_name', ''),
                        'language': stream.get('tags', {}).get('language', '')
                    }
                    audio_streams.append(audio_info)
            return audio_streams
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des pistes audio pour {file_path}: {e}")
            return []
    
    def get_subtitle_streams_info(self, file_path: str) -> List[Dict]:
        """Récupère les informations des pistes de sous-titres via ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 's',
                '-show_entries', 'stream=index,codec_name',
                '-of', 'json',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            subtitle_streams = []
            if data.get('streams'):
                for stream in data['streams']:
                    subtitle_info = {
                        'index': stream.get('index'),
                        'codec': stream.get('codec_name', '')
                    }
                    subtitle_streams.append(subtitle_info)
            return subtitle_streams
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des pistes de sous-titres pour {file_path}: {e}")
            return []
    
    def needs_conversion(self, video_file: VideoFile) -> bool:
        """Détermine si un fichier doit être converti."""
        if video_file.codec is None:
            self.logger.warning(f"Codec inconnu pour {video_file.path}, ignoré")
            return False
        
        if video_file.codec.lower() == 'h264':
            self.logger.info(f"Fichier à convertir (H.264): {video_file.path}")
            return True
        
        self.logger.debug(f"Fichier déjà au format moderne ({video_file.codec}): {video_file.path}")
        return False
    
    def convert_to_hevc(self, video_file: VideoFile) -> ConversionResult:
        """Convertit un fichier vidéo en HEVC avec correction des pistes audio et exclusion des sous-titres non supportés."""
        # Générer le chemin de sortie (gère l'extension MKV si MP4 + H.264)
        output_path = self._generate_output_path(video_file.path, video_file.codec)
        
        # Vérifier et corriger les pistes audio
        audio_streams = self.get_audio_streams_info(video_file.path)
        metadata_cmd = []
        
        for audio in audio_streams:
            lang = audio.get('language', '')
            # Vérifier si la langue contient "Avestan" ou "ae" ou "ave" (différents formats possibles)
            if lang and ('Avestan' in lang or lang.lower() in ['ae', 'ave', 'ae;ave', 'ave;ae']):
                # Ajouter le metadata pour corriger la langue ET le titre
                if audio.get('index') is not None:
                    metadata_cmd.extend([
                        '-metadata:s:a:' + str(audio['index']), f'language={FRENCH_LANG}'
                    ])
                    self.logger.info(f"Correction de la langue audio (index {audio['index']}): {lang} -> {FRENCH_LANG}")
        
        # Vérifier les sous-titres et exclure ceux non supportés
        subtitle_streams = self.get_subtitle_streams_info(video_file.path)
        map_cmd = ['-map', '0']  # Par défaut, on map tout
        
        for subtitle in subtitle_streams:
            # Exclure les sous-titres avec codec non supporté (comme 94213)
            if subtitle.get('codec') and subtitle.get('codec').isdigit():
                # C'est un codec non standard, l'exclure
                if subtitle.get('index') is not None:
                    map_cmd.extend(['-map', '-s:' + str(subtitle['index'])])
                    self.logger.info(f"Exclusion du sous-titre non supporté (index {subtitle['index']}, codec: {subtitle['codec']})")
        
        # Construire la commande FFmpeg
        cmd = [
            'ffmpeg',
            '-i', video_file.path,
            *FFMPEG_HEVC_PARAMS,
            *map_cmd,
            '-map_metadata', '0',  # Copier les métadonnées du conteneur source
            *metadata_cmd,
            '-y',  # Écrase le fichier de sortie si il existe
            output_path
        ]
        
        self.logger.info(f"Conversion de {video_file.path} vers {output_path}")
        self.logger.info(f"Commande: {' '.join(cmd)}")
        
        try:
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            elapsed_time = time.time() - start_time
            
            self.logger.info(f"Conversion terminée en {elapsed_time:.2f} secondes")
            
            # Vérifier que le fichier de sortie existe
            if not os.path.exists(output_path):
                return ConversionResult(
                    original_file=video_file.path,
                    converted_file=output_path,
                    original_size=video_file.size,
                    converted_size=0,
                    success=False,
                    error_message="Fichier de sortie non créé"
                )
            
            converted_size = os.path.getsize(output_path)
            
            return ConversionResult(
                original_file=video_file.path,
                converted_file=output_path,
                original_size=video_file.size,
                converted_size=converted_size,
                success=True
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg a échoué: {e.stderr}"
            self.logger.error(error_msg)
            return ConversionResult(
                original_file=video_file.path,
                converted_file=output_path,
                original_size=video_file.size,
                converted_size=0,
                success=False,
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"Erreur lors de la conversion: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(
                original_file=video_file.path,
                converted_file=output_path,
                original_size=video_file.size,
                converted_size=0,
                success=False,
                error_message=error_msg
            )
    
    def _generate_output_path(self, input_path: str, video_codec: str = None) -> str:
        """Génère le chemin de sortie pour le fichier converti."""
        path_obj = Path(input_path)
        new_stem = f"{path_obj.stem}_hevc"
        
        # Si le fichier est en MP4 avec codec H.264, convertir en MKV
        if path_obj.suffix.lower() == '.mp4' and video_codec == 'h264':
            return str(path_obj.with_stem(new_stem).with_suffix('.mkv'))
        
        return str(path_obj.with_stem(new_stem))
    
    def process_conversion_result(self, result: ConversionResult) -> bool:
        """Traite le résultat d'une conversion."""
        abs_original = os.path.abspath(result.original_file)
        
        if not result.success:
            # Marquer comme échoué
            self.failed_files.add(abs_original)
            self.logger.error(f"Conversion échouée pour {result.original_file}: {result.error_message}")
            
            # Supprimer le fichier de sortie s'il existe
            if os.path.exists(result.converted_file):
                os.remove(result.converted_file)
                self.logger.info(f"Fichier temporaire supprimé: {result.converted_file}")
            
            return False
        
        # Vérifier la réduction de taille
        reduction = result.size_reduction()
        self.logger.info(f"Réduction de taille: {reduction*100:.2f}% ({result.original_size} -> {result.converted_size} bytes)")
        
        if reduction >= SIZE_REDUCTION_THRESHOLD:
            # Remplacer l'original par le converti
            self._replace_original(result)
            self.converted_files.add(abs_original)
            self.logger.info(f"Fichier converti avec succès et remplacé: {result.original_file}")
            return True
        else:
            # Supprimer le fichier converti (réduction insuffisante)
            os.remove(result.converted_file)
            self.failed_files.add(abs_original)  # Marquer pour éviter de refaire
            self.logger.info(f"Réduction insuffisante ({reduction*100:.2f}% < 10%), fichier original conservé")
            return False
    
    def _replace_original(self, result: ConversionResult) -> None:
        """Remplace le fichier original par le fichier converti."""
        # Déterminer le chemin final : si le converti est en .mkv et l'original en .mp4, garder .mkv
        final_path = result.original_file
        path_obj_orig = Path(result.original_file)
        path_obj_conv = Path(result.converted_file)
        
        if path_obj_conv.suffix.lower() == '.mkv' and path_obj_orig.suffix.lower() == '.mp4':
            # Changer l'extension de la destination finale en .mkv
            final_path = str(path_obj_orig.with_suffix('.mkv'))
        
        if self.keep_backup:
            # Sauvegarder l'original avec un timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{result.original_file}.backup_{timestamp}"
            
            try:
                # Renommer l'original en backup
                os.rename(result.original_file, backup_path)
                self.logger.info(f"Backup créé: {backup_path}")
            except Exception as e:
                self.logger.error(f"Erreur lors de la création du backup: {e}")
                raise
        else:
            # Supprimer directement l'original
            try:
                os.remove(result.original_file)
                self.logger.info(f"Fichier original supprimé: {result.original_file}")
            except Exception as e:
                self.logger.error(f"Erreur lors de la suppression de l'original: {e}")
                raise
        
        # Renommer le converti vers le chemin final (qui peut être .mkv)
        try:
            os.rename(result.converted_file, final_path)
            self.logger.info(f"Fichier converti déplacé vers: {final_path}")
        except Exception as e:
            self.logger.error(f"Erreur lors du remplacement: {e}")
            # Essayer de restaurer
            if os.path.exists(backup_path):
                os.rename(backup_path, result.original_file)


    def run(self) -> None:
        """Exécute le processus complet de conversion."""
        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("DEBUT DE LA CONVERSION VIDEO")
        self.logger.info("=" * 60)
        
        # Charger la configuration
        if not self.load_config():
            self.logger.error("Arrêt: impossibilité de charger la configuration")
            return
        
        # Charger les marqueurs
        self.load_markers()
        
        # Scanner les fichiers vidéo
        video_files = self.scan_video_files()
        
        if not video_files:
            self.logger.info("Aucun fichier vidéo à traiter")
            return
        
        # Traiter chaque fichier
        h264_files = [f for f in video_files if self.needs_conversion(f)]
        self.logger.info(f"Fichiers H.264 à convertir: {len(h264_files)}")
        
        success_count = 0
        fail_count = 0
        skip_count = 0
        
        for video_file in h264_files:
            self.logger.info(f"\nTraitement de: {video_file.path}")
            self.logger.info(f"  Codec: {video_file.codec}")
            self.logger.info(f"  Taille: {video_file.size} bytes")
            
            try:
                result = self.convert_to_hevc(video_file)
                if self.process_conversion_result(result):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                self.logger.error(f"Erreur inattendue lors du traitement de {video_file.path}: {e}")
                self.failed_files.add(os.path.abspath(video_file.path))
                fail_count += 1
        
        # Sauvegarder les marqueurs
        self.save_markers()
        
        # Résumé
        end_time = datetime.now()
        duration = end_time - start_time
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("RESUME DE LA CONVERSION")
        self.logger.info("=" * 60)
        self.logger.info(f"Durée totale: {duration}")
        self.logger.info(f"Fichiers convertis avec succès: {success_count}")
        self.logger.info(f"Fichiers échoués ou ignorés: {fail_count}")
        self.logger.info(f"Fichiers déjà traités: {skip_count}")
        self.logger.info("=" * 60)


def check_ffmpeg() -> bool:
    """Vérifie que ffmpeg et ffprobe sont disponibles."""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Point d'entrée principal."""
    print("Vérification des dépendances...")
    
    if not check_ffmpeg():
        print("ERREUR: ffmpeg et ffprobe sont requis. Veuillez les installer.")
        print("Sur Ubuntu/Debian: sudo apt install ffmpeg")
        print("Sur macOS: brew install ffmpeg")
        sys.exit(1)
    
    # Gestion des arguments
    config_file = DEFAULT_CONFIG_FILE
    log_file = DEFAULT_LOG_FILE
    target_path = None
    
    # Si des arguments sont fournis
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        
        # Vérifier si c'est un fichier de configuration
        if first_arg.endswith('.conf') or first_arg.endswith('.json'):
            config_file = first_arg
            log_file = os.path.splitext(first_arg)[0] + ".log"
            # Vérifier s'il y a un second argument (fichier/répertoire cible)
            if len(sys.argv) > 2:
                target_path = sys.argv[2]
        else:
            # C'est un fichier ou répertoire cible
            target_path = first_arg
            # Générer un nom de log basé sur le target
            if os.path.isfile(target_path):
                log_file = os.path.splitext(target_path)[0] + ".log"
            elif os.path.isdir(target_path):
                log_file = os.path.join(target_path, "conversion.log")
    
    print(f"Utilisation de la configuration: {config_file}")
    if target_path:
        print(f"Cible: {target_path}")
    print(f"Fichier de log: {log_file}")
    
    converter = VideoConverter(config_file, log_file, target_path)
    converter.run()


if __name__ == "__main__":
    main()
