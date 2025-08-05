import os
from process_folder import processFolder
import argparse
import logging

logger = logging.getLogger(__name__)


def dimension(s):
    try:
        width, height = map(int, s.split(','))
        return (width, height)
    except:
        raise argparse.ArgumentTypeError("Dimension must be width,height")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process Google Photos metadata and apply it to media files (images and videos)"
    )

    parser.add_argument('source_folder', help="Source folder containing Google Photos takeout data")
    parser.add_argument('output_folder', help="Output folder for processed media files")
    parser.add_argument('-w',  '--edited_word', default='edited', help="Google Photos 'edited' word translation")
    parser.add_argument('-o',  '--optimize', type=int, default=100, help='Optimize images (0 to 100), recommended: 75 (default: 100)')
    parser.add_argument('-m',  '--max_dimension', type=dimension, help="Resize images restricting the max width,height dimension (e.g., 1920,1080)")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--videos', action='store_true', default=True, help='Process video files (creates sidecar metadata files, default: enabled)')

    args = parser.parse_args()

    loglevel = logging.INFO if args.verbose else logging.WARNING

    # Configure logging format
    logging.basicConfig(
        level=loglevel,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if not os.path.exists(args.source_folder):
      logger.error('Target folder doesn\'t exist')
      exit()

    processFolder(args.source_folder, args.edited_word, args.optimize, args.output_folder, args.max_dimension)
