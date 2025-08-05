import os
from pathlib import Path
from auxFunctions import *
import json
import logging
from PIL import Image
from pillow_heif import register_heif_opener
import shutil
from ffmpeg import FFmpeg
import tempfile
import datetime
from metadata_handler import MediaMetadataHandler

logger = logging.getLogger(__name__)

# Using python-ffmpeg to add metadata to video files
# This implementation embeds creation time and geolocation data directly into videos
# while also creating sidecar JSON files as a backup

register_heif_opener()

OrientationTagID = 274

def get_images_from_folder(folder: str, edited_word: str, notfound_media: list):
    """
    Recursively finds JSON metadata files in a folder and its subfolders,
    and matches them with their corresponding media files.
    
    Args:
        folder: The folder path to search in
        edited_word: The suffix used for edited images (e.g. 'edited')
        
    Returns:
        A list of tuples (json_path, media_path) where media_path may be None if not found
    """
    files: list[tuple[str, str]] = []
    folder_path = Path(folder)
    
    # Iterate through all items in the directory
    for item in folder_path.iterdir():
        # Recursively process subdirectories
        if item.is_dir():
            files.extend(get_images_from_folder(str(item), edited_word, notfound_media))
            continue
            
        # Process JSON files
        if item.is_file() and item.suffix.lower() == ".json" and item.stem != "metadata":
            # Search for the corresponding media file
            media_file = searchMedia(str(folder_path), item, edited_word, notfound_media)
            # Add the tuple of (json_path, media_path) to our results
            files.append((str(item), media_file))
    
    return files

def processFolder(root_folder: str, edited_word: str, optimize: int, out_folder: str, max_dimension):
    """
    Process all media files in a folder structure, applying metadata from JSON files.
    
    Args:
        root_folder: Source folder path containing Google Photos takeout data
        edited_word: The suffix used for edited images (e.g. 'edited')
        optimize: Quality level for image optimization (0-100)
        out_folder: Output folder path for processed media files
        max_dimension: Optional tuple (width, height) for max image dimensions
    """
    # Initialize the media handler
    media_handler = MediaMetadataHandler(
        root_folder=root_folder,
        out_folder=out_folder,
        optimize=optimize,
        max_dimension=max_dimension
    )

    notfound_media = []
    # Get all media files with their metadata
    images = get_images_from_folder(root_folder, edited_word, notfound_media)
    
    logger.info(f"Total media files found: {len(images)}")
    
    # Process each media file
    for entry in progressBar(images):
        metadata_path = entry[0]
        media_path = entry[1]
        
        logger.info(f"Current file: {media_path}")
        
        # Process the media file using the handler
        media_handler.process_media_file(
            metadata_path=metadata_path,
            media_path=media_path,
            media_codecs=mediaCodecs,
            video_codecs=videoCodecs
        )
    
    # Get the final statistics
    success_count, error_count = media_handler.get_stats()
    
    logger.info("Metadata merging has been finished")
    logger.info(f"Success: {success_count} media files processed")
    logger.info(f"Failed: {error_count} media files")
    logger.info("Videos have been processed with ffmpeg to embed metadata directly")
    logger.info(f"Media files not found: {len(notfound_media)}")
    for item in notfound_media:
        logger.info(f" - {item}")
