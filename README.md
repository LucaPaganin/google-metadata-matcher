## Google photos takeout metadata merging into their images and videos

Original windows based version: [GooglePhotosMatcher](https://github.com/anderbggo/GooglePhotosMatcher)

This is a command line version which based on Python3 runtime only (Mac / Windows / Linux)

Takes a folder, collects all `.json` files which contain the metadata of the image/video, processes the media files and applies the metadata.

```
usage: merge_metadata.py [-h] [-w EDITED_WORD] [-o OPTIMIZE] [-m MAX_DIMENSION] [-v] [--videos]
                         source_folder output_folder

Process Google Photos metadata and apply it to media files (images and videos)

positional arguments:
  source_folder         Source folder containing Google Photos takeout data
  output_folder         Output folder for processed media files

optional arguments:
  -h, --help            show this help message and exit
  -w EDITED_WORD, --edited_word EDITED_WORD
                        Google Photos 'edited' word translation
  -o OPTIMIZE, --optimize OPTIMIZE
                        Optimize images (0 to 100), recommended: 75 (default: 100)
  -m MAX_DIMENSION, --max_dimension MAX_DIMENSION
                        Resize images restricting the max width,height dimension (e.g., 1920,1080)
  -v, --verbose         Enable verbose logging
  --videos              Process video files (creates sidecar metadata files, default: enabled)
```

## Features

- Keeps Geo coordinates
- Keeps creation time
- Recursive folders media processing
- PNG, HEIC Support
- Video support (MOV, MP4, AVI, MKV, etc.)
- Resize option for images
- Optimization option for images

## Media Handling

### Images
- Converted to JPG with embedded EXIF metadata
- Orientation corrected based on EXIF data
- Optional resizing and quality optimization

### Videos
- Preserved in their original format
- Metadata directly embedded using ffmpeg:
  - Creation timestamp
  - GPS coordinates (latitude, longitude, altitude)
- Backup metadata stored in sidecar JSON files
- File creation time also set at OS level

## Main Dependencies

- Pillow - Image Editor lib
- pillow-heif - Image Editor lib HEIC (Apple) support
- piexif - Adjust Metadata for image
- python-ffmpeg - Modern FFmpeg binding for video metadata

## Tutorial

- [Migrate Google Photos to iCloud](migrate_photos.md)
