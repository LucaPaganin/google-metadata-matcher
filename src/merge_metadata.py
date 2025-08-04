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
    parser = argparse.ArgumentParser()

    parser.add_argument('source_folder')
    parser.add_argument('output_folder')
    parser.add_argument('-w',  '--edited_word', default='edited', help="Google Photos 'edited' word translation")
    parser.add_argument('-o',  '--optimize', type=int, default=100, help='Optimalize the images (0 to 100), recommended: 75 (default: disabled)')
    parser.add_argument('-m',  '--max_dimension', type=dimension, help="Resize the image restricting the max width,height dimension")
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

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
