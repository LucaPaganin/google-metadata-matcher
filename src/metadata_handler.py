import os
import json
import logging
from pathlib import Path
import datetime
import shutil
import tempfile
from PIL import Image
from ffmpeg import FFmpeg
from typing import Dict, Any, Tuple, Optional, Union

logger = logging.getLogger(__name__)

class MediaMetadataHandler:
    """
    Class responsible for handling metadata operations on media files.
    Supports both images and videos.
    """
    
    # Orientation tag ID for EXIF data
    ORIENTATION_TAG_ID = 274
    
    def __init__(self, root_folder: str, out_folder: str, optimize: int = 75, max_dimension: Optional[Tuple[int, int]] = None):
        """
        Initialize the MediaMetadataHandler.
        
        Args:
            root_folder: Source folder path containing Google Photos takeout data
            out_folder: Output folder path for processed media files
            optimize: Quality level for image optimization (0-100)
            max_dimension: Optional tuple (width, height) for max image dimensions
        """
        self.root_folder = root_folder
        self.out_folder = out_folder
        self.optimize = optimize
        self.max_dimension = max_dimension
        self.success_counter = 0
        self.error_counter = 0
        
    def get_output_filename(self, image_path: str, preserve_extension: bool = False) -> str:
        """
        Generates the output file path for a processed image or video.
        
        Args:
            image_path: The original image/video file path
            preserve_extension: If True, keep the original file extension (for videos)
            
        Returns:
            The path where the processed media should be saved
        """
        # Convert string paths to Path objects
        root_path = Path(self.root_folder)
        out_path = Path(self.out_folder)
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
    
    def process_media_file(self, metadata_path: str, media_path: str, media_codecs: list, video_codecs: list) -> bool:
        """
        Process a media file (image or video) with its associated metadata.
        
        Args:
            metadata_path: Path to the JSON metadata file
            media_path: Path to the media file (image or video)
            media_codecs: List of supported media codecs
            video_codecs: List of supported video codecs
            
        Returns:
            True if processing was successful, False otherwise
        """
        if not media_path:
            logger.warning(f"Missing media file for: {metadata_path}")
            self.error_counter += 1
            return False
            
        # Use Path object for extension extraction
        media_path_obj = Path(media_path)
        ext = media_path_obj.suffix
        ext_lower = ext[1:].casefold()
        
        # Check if the file is a supported media format
        if ext_lower not in media_codecs:
            logger.warning(f"Media format is not supported: {media_path}")
            self.error_counter += 1
            return False
            
        # Process videos differently from images
        if ext_lower in video_codecs:
            return self._process_video(metadata_path, media_path)
        else:
            return self._process_image(metadata_path, media_path)
    
    def _process_video(self, metadata_path: str, video_path: str) -> bool:
        """
        Process a video file, embedding metadata using FFmpeg.
        
        Args:
            metadata_path: Path to the JSON metadata file
            video_path: Path to the video file
            
        Returns:
            True if processing was successful, False otherwise
        """
        try:
            # For videos, we need to handle metadata differently
            logger.info(f"Processing video file: {video_path}")
            
            # Get output path preserving the original extension
            new_media_path = self.get_output_filename(video_path, preserve_extension=True)
            
            # Create output directory if it doesn't exist
            output_dir = Path(new_media_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Read metadata 
            with open(metadata_path, encoding="utf8") as f:
                metadata = json.load(f)
            
            # Apply metadata - for videos we'll use ffmpeg
            timestamp = int(metadata['photoTakenTime']['timestamp'])
            date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            try:
                # Use a temp file for processing
                with tempfile.NamedTemporaryFile(suffix=Path(video_path).suffix, delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Process the video with ffmpeg to add metadata
                logger.info(f"Adding metadata to video using FFmpeg: {new_media_path}")
                
                # Copy the input file first
                shutil.copy2(video_path, temp_path)
                
                # Prepare output options with metadata
                output_options = {
                    "c": "copy",  # Use codec copy (no re-encoding)
                    # Add metadata directly as options
                    "metadata:creation_time": date_str
                }
                
                # Add geo metadata if available
                if 'geoData' in metadata and 'latitude' in metadata['geoData'] and 'longitude' in metadata['geoData']:
                    lat = metadata['geoData']['latitude']
                    lng = metadata['geoData']['longitude']
                    altitude = metadata['geoData'].get('altitude', 0)
                    
                    # Add location metadata to the output options
                    location_str = f"{lat} {lng}"
                    output_options.update({
                        "metadata:location": location_str,
                        "metadata:latitude": str(lat),
                        "metadata:longitude": str(lng),
                        "metadata:altitude": str(altitude)
                    })
                    
                    logger.info(f"Adding geo metadata to video: lat={lat}, lng={lng}, alt={altitude}")
                
                # Create FFmpeg instance with all metadata arguments
                ffmpeg_process = (
                    FFmpeg()
                    .option("y")  # Overwrite output file if it exists
                    .input(temp_path)
                    .output(new_media_path, output_options)  # Pass as dictionary, not as kwargs
                )
                
                # Execute FFmpeg
                ffmpeg_process.execute()
                
                # Clean up temp file
                os.unlink(temp_path)
                
                # Set file creation and modification time
                self._set_file_creation_time(new_media_path, timestamp)
                
                logger.info(f"Successfully added metadata to video: {new_media_path}")
            except Exception as e:
                logger.error(f"Error with ffmpeg metadata: {str(e)}")
                # Fallback to just copying the file if ffmpeg fails
                logger.info(f"Falling back to simple copy for video: {video_path}")
                shutil.copy2(video_path, new_media_path)
                self._set_file_creation_time(new_media_path, timestamp)
            
            # Create a sidecar metadata file as a backup reference
            sidecar_path = str(Path(new_media_path).with_suffix('.metadata.json'))
            with open(sidecar_path, 'w', encoding="utf8") as f:
                json.dump(metadata, f, indent=2)
            
            self.success_counter += 1
            return True
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
            self.error_counter += 1
            return False
    
    def _process_image(self, metadata_path: str, image_path: str) -> bool:
        """
        Process an image file, embedding EXIF metadata.
        
        Args:
            metadata_path: Path to the JSON metadata file
            image_path: Path to the image file
            
        Returns:
            True if processing was successful, False otherwise
        """
        try:
            # Open and process the image
            image = Image.open(image_path, mode="r").convert('RGB')
            image_exif = image.getexif()
            
            # Handle orientation
            if self.ORIENTATION_TAG_ID in image_exif:
                orientation = image_exif[self.ORIENTATION_TAG_ID]
                
                if orientation == 3:
                    image = image.rotate(180, expand=True)
                elif orientation == 6:
                    image = image.rotate(270, expand=True)
                elif orientation == 8:
                    image = image.rotate(90, expand=True)
                    
            # Resize if max dimension is set
            if self.max_dimension:
                image.thumbnail(self.max_dimension)
                
            # Prepare output path
            new_image_path = self.get_output_filename(image_path)
            
            # Create output directory if it doesn't exist
            output_dir = Path(new_image_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Read metadata
            with open(metadata_path, encoding="utf8") as f:
                metadata = json.load(f)
                
            # Get timestamp for file creation time
            timestamp = int(metadata['photoTakenTime']['timestamp'])
            
            # Save with EXIF data if available
            if "exif" in image.info:
                try:
                    # Adjust EXIF data with metadata - this requires the adjust_exif function from auxFunctions
                    from auxFunctions import adjust_exif
                    new_exif = adjust_exif(image.info["exif"], metadata)
                    image.save(new_image_path, quality=self.optimize, exif=new_exif)
                except Exception as e:
                    logger.warning(f"Failed to add EXIF data: {str(e)}")
                    image.save(new_image_path, quality=self.optimize)
            else:
                image.save(new_image_path, quality=self.optimize)
                
            # Set file creation time
            self._set_file_creation_time(new_image_path, timestamp)
            
            self.success_counter += 1
            return True
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            self.error_counter += 1
            return False
    
    def _set_file_creation_time(self, file_path: str, timestamp: int) -> None:
        """
        Set the file creation and modification times based on metadata.
        
        Args:
            file_path: Path to the file
            timestamp: Unix timestamp to set
        """
        try:
            # Import from auxFunctions to maintain compatibility
            from auxFunctions import setFileCreationTime
            setFileCreationTime(file_path, timestamp)
        except Exception as e:
            logger.warning(f"Failed to set file creation time: {str(e)}")
    
    def get_stats(self) -> Tuple[int, int]:
        """
        Get the success and error counters.
        
        Returns:
            Tuple of (success_count, error_count)
        """
        return (self.success_counter, self.error_counter)
