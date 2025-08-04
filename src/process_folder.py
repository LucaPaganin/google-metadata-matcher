import os
from pathlib import Path
from auxFunctions import *
import json
import logging
from PIL import Image
from pillow_heif import register_heif_opener

logger = logging.getLogger(__name__)

register_heif_opener()

OrientationTagID = 274

def get_images_from_folder(folder: str, edited_word: str):
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
            files.extend(get_images_from_folder(str(item), edited_word))
            continue
            
        # Process JSON files
        if item.is_file() and item.suffix.lower() == ".json" and item.stem != "metadata":
            # Search for the corresponding media file
            media_file = searchMedia(str(folder_path), item, edited_word)
            # Add the tuple of (json_path, media_path) to our results
            files.append((str(item), media_file))
    
    return files

def get_output_filename(root_folder, out_folder, image_path):
    """
    Generates the output file path for a processed image.
    
    Args:
        root_folder: The source root folder path
        out_folder: The destination root folder path
        image_path: The original image file path
        
    Returns:
        The path where the processed image should be saved
    """
    # Convert string paths to Path objects
    root_path = Path(root_folder)
    out_path = Path(out_folder)
    image_path_obj = Path(image_path)
    
    # Get filename without extension and add .jpg extension
    new_image_name = image_path_obj.stem + ".jpg"
    
    # Calculate relative path from root folder
    relative_path = image_path_obj.parent.relative_to(root_path)
    
    # Build output path
    return str(out_path / relative_path / new_image_name)

def processFolder(root_folder: str, edited_word: str, optimize: int, out_folder: str, max_dimension):
    errorCounter = 0
    successCounter = 0

    images = get_images_from_folder(root_folder, edited_word)

    logger.info(f"Total images found: {len(images)}")

    for entry in progressBar(images):
        metadata_path = entry[0]
        image_path = entry[1]

        logger.info(f"Current file: {image_path}")

        if not image_path:
            logger.warning(f"Missing image for: {metadata_path}")
            errorCounter += 1
            continue

        # Use Path object for extension extraction
        image_path_obj = Path(image_path)
        ext = image_path_obj.suffix

        if not ext[1:].casefold() in piexifCodecs:
            logger.warning(f"Photo format is not supported: {image_path}")
            errorCounter += 1
            continue
        
        image = Image.open(image_path, mode="r").convert('RGB')
        image_exif = image.getexif()
        if OrientationTagID in image_exif:
            orientation = image_exif[OrientationTagID]

            if orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)
            elif orientation == 8:
                image = image.rotate(90, expand=True)

        if max_dimension:
            image.thumbnail(max_dimension)

        new_image_path = get_output_filename(root_folder, out_folder, image_path)

        # Create output directory if it doesn't exist
        output_dir = Path(new_image_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, encoding="utf8") as f: 
            metadata = json.load(f)

        timeStamp = int(metadata['photoTakenTime']['timestamp'])
        if "exif" in image.info:
            try:
                new_exif = adjust_exif(image.info["exif"], metadata)
                image.save(new_image_path, quality=optimize, exif=new_exif)
            except:
                image.save(new_image_path, quality=optimize)
        else:
            image.save(new_image_path, quality=optimize)

        setFileCreationTime(new_image_path, timeStamp)

        successCounter += 1

    logger.info("Metadata merging has been finished")
    logger.info(f"Success: {successCounter}")
    logger.info(f"Failed: {errorCounter}")

