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

logger = logging.getLogger(__name__)

# Using ffmpeg-python to add metadata to video files
# This implementation embeds creation time and geolocation data directly into videos
# while also creating sidecar JSON files as a backup

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

def get_output_filename(root_folder, out_folder, image_path, preserve_extension=False):
    """
    Generates the output file path for a processed image or video.
    
    Args:
        root_folder: The source root folder path
        out_folder: The destination root folder path
        image_path: The original image/video file path
        preserve_extension: If True, keep the original file extension (for videos)
        
    Returns:
        The path where the processed media should be saved
    """
    # Convert string paths to Path objects
    root_path = Path(root_folder)
    out_path = Path(out_folder)
    image_path_obj = Path(image_path)
    
    # Get file extension
    if preserve_extension:
        # Keep original extension for videos
        new_image_name = image_path_obj.name
    else:
        # Convert images to jpg
        new_image_name = image_path_obj.stem + ".jpg"
    
    # Calculate relative path from root folder
    relative_path = image_path_obj.parent.relative_to(root_path)
    
    # Build output path
    return str(out_path / relative_path / new_image_name)

def processFolder(root_folder: str, edited_word: str, optimize: int, out_folder: str, max_dimension):
    errorCounter = 0
    successCounter = 0

    images = get_images_from_folder(root_folder, edited_word)

    logger.info(f"Total media files found: {len(images)}")

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
        ext_lower = ext[1:].casefold()

        # Check if the file is a supported media format
        if ext_lower in mediaCodecs:
            # Process videos differently from images
            if ext_lower in videoCodecs:
                try:
                    # For videos, we need to handle metadata differently
                    logger.info(f"Processing video file: {image_path}")
                    
                    # Get output path preserving the original extension
                    new_media_path = get_output_filename(root_folder, out_folder, image_path, preserve_extension=True)
                    
                    # Create output directory if it doesn't exist
                    output_dir = Path(new_media_path).parent
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Read metadata 
                    with open(metadata_path, encoding="utf8") as f:
                        metadata = json.load(f)
                    
                    # Apply metadata - for videos we'll use ffmpeg
                    timeStamp = int(metadata['photoTakenTime']['timestamp'])
                    date_str = datetime.datetime.fromtimestamp(timeStamp).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Prepare metadata to be added to the video
                    metadata_dict = {
                        'creation_time': date_str
                    }
                    
                    # Add geo metadata if available
                    if 'geoData' in metadata and 'latitude' in metadata['geoData'] and 'longitude' in metadata['geoData']:
                        lat = metadata['geoData']['latitude']
                        lng = metadata['geoData']['longitude']
                        altitude = metadata['geoData'].get('altitude', 0)
                        
                        # Add location data to metadata
                        metadata_dict.update({
                            'location': f"{lat} {lng}",
                            'latitude': str(lat),
                            'longitude': str(lng),
                            'altitude': str(altitude)
                        })
                        
                        logger.info(f"Adding geo metadata to video: lat={lat}, lng={lng}, alt={altitude}")
                    
                    # Create output directory if it doesn't exist
                    output_dir = Path(new_media_path).parent
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        # Use a temp file for processing
                        with tempfile.NamedTemporaryFile(suffix=Path(image_path).suffix, delete=False) as temp_file:
                            temp_path = temp_file.name
                        
                        # Process the video with ffmpeg to add metadata
                        logger.info(f"Adding metadata to video using FFmpeg: {new_media_path}")
                        
                        # Copy the input file first
                        shutil.copy2(image_path, temp_path)
                        
                        # Build metadata arguments
                        ffmpeg_metadata = {}
                        for key, value in metadata_dict.items():
                            ffmpeg_metadata[f"metadata:{key}"] = value
                        
                        # Create FFmpeg instance
                        ffmpeg_process = (
                            FFmpeg()
                            .option("y")  # Overwrite output file if it exists
                            .input(temp_path)
                            .output(new_media_path, codec="copy", **ffmpeg_metadata)
                        )
                        
                        # Execute FFmpeg
                        ffmpeg_process.execute()
                        
                        # Clean up temp file
                        os.unlink(temp_path)
                        
                        # Set file creation and modification time
                        setFileCreationTime(new_media_path, timeStamp)
                        
                        logger.info(f"Successfully added metadata to video: {new_media_path}")
                    except Exception as e:
                        logger.error(f"Error with ffmpeg metadata: {str(e)}")
                        # Fallback to just copying the file if ffmpeg fails
                        logger.info(f"Falling back to simple copy for video: {image_path}")
                        shutil.copy2(image_path, new_media_path)
                        setFileCreationTime(new_media_path, timeStamp)
                    
                    # Create a sidecar metadata file as a backup reference
                    sidecar_path = str(Path(new_media_path).with_suffix('.metadata.json'))
                    with open(sidecar_path, 'w', encoding="utf8") as f:
                        json.dump(metadata, f, indent=2)
                    
                    successCounter += 1
                except Exception as e:
                    logger.error(f"Error processing video {image_path}: {str(e)}")
                    errorCounter += 1
                continue
                
            # Process images with Pillow
            try:
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
                    except Exception as e:
                        logger.warning(f"Failed to add EXIF data: {str(e)}")
                        image.save(new_image_path, quality=optimize)
                else:
                    image.save(new_image_path, quality=optimize)

                setFileCreationTime(new_image_path, timeStamp)
                
                successCounter += 1
            except Exception as e:
                logger.error(f"Error processing image {image_path}: {str(e)}")
                errorCounter += 1
        else:
            logger.warning(f"Media format is not supported: {image_path}")
            errorCounter += 1

    logger.info("Metadata merging has been finished")
    logger.info(f"Success: {successCounter} media files processed")
    logger.info(f"Failed: {errorCounter} media files")
    logger.info("Videos have been processed with ffmpeg to embed metadata directly")

