import os
import time
import re
from datetime import datetime
import piexif
from fractions import Fraction
import logging
from tqdm import tqdm
import io
from pathlib import Path

logger = logging.getLogger(__name__)

# Image formats that can be processed with piexif
piexifCodecs = [k.casefold() for k in ['TIF', 'TIFF', 'JPEG', 'JPG', 'HEIC', 'PNG']]

# Video formats that should be copied without image processing
videoCodecs = [k.casefold() for k in ['MOV', 'MP4', 'AVI', 'MKV', 'WEBM', '3GP']]

# All supported media formats
mediaCodecs = piexifCodecs + videoCodecs

class TqdmToLogger(io.StringIO):
    """
    Output stream for tqdm which will output to logger module instead of stdout.
    """
    def __init__(self, logger, level=logging.INFO):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level
        self.buf = ""
        
    def write(self, buf):
        self.buf = buf.strip('\r\n\t ')
        
    def flush(self):
        if self.buf:
            self.logger.log(self.level, self.buf)

def progressBar(iterable, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r", upLines = 0):
    """
    Creates a progress bar for an iterable using tqdm with logging.
    Returns a generator that yields items from the iterable while updating the progress bar.
    
    Parameters are kept for backward compatibility but most are handled by tqdm directly.
    """
    # Create a tqdm progress bar with logger as output
    tqdm_out = TqdmToLogger(logger)
    for item in tqdm(iterable, 
                     desc=prefix,
                     file=tqdm_out,
                     leave=True, 
                     ncols=length+20,
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'):
        yield item

# Function to search media associated to the JSON
def searchMedia(path, item: Path, editedWord):
    file_stem = item.stem

    title = fixTitle(file_stem)

    (file_name, ext) = os.path.splitext(title)

    # Process with three separate regex patterns for clarity
    title_no_o = re.sub(r'\._o?$', '', title)
    title_no_metadata = re.sub(r'\.supplemental-metadata', '', title_no_o)
    title_fixed = re.sub(r'\.supp(\w*(-\w*)?)?', '', title_no_metadata)

    possible_titles = [
        title,
        title_fixed,
        file_name,
        f"{file_name}_",
        f"{title}_",
        f"{title_fixed}_",
    ]
    suffixes = {ext.lstrip(".") for ext in item.suffixes}
    suffixes = suffixes.intersection(piexifCodecs)
    if not suffixes:
        suffixes = set(piexifCodecs)

    for ext in suffixes:
        possible_titles.extend([
                f"{title_fixed}.{ext}",
                f"{file_name}.{ext}",
                f"{file_name}-{editedWord}.{ext}",
                f"{file_name}(1).{ext}",
                f"{title}_.{ext}",
                f"{title_fixed}_.{ext}",
                f"{title}_o.{ext}",
                f"{title_fixed}_o.{ext}",
            ])

    media_candidates = [Path(path) / title for title in possible_titles]

    # add glob retrieved files
    media_candidates.extend([
        f for f in Path(path).glob(f"{file_stem}*") 
        if f.is_file() and ".json" not in f.suffixes
    ])

    media_path = None
    for filepath in media_candidates:
        if filepath.exists():
            media_path = filepath
            break

    if not media_path:
        logger.warning(f"Media file not found for: {title}")

    return media_path
    

# Supress incompatible characters
def fixTitle(title):
    return str(title).replace("%", "").replace("<", "").replace(">", "").replace("=", "").replace(":", "").replace("?","").replace(
        "¿", "").replace("*", "").replace("#", "").replace("&", "").replace("{", "").replace("}", "").replace("\\", "").replace(
        "@", "").replace("!", "").replace("¿", "").replace("+", "").replace("|", "").replace("\"", "").replace("\'", "")

# Recursive function to search name if its repeated
def checkIfSameName(title, titleFixed, matchedFiles, recursionTime):
    if titleFixed in matchedFiles:
        (file_name, ext) = os.path.splitext(titleFixed)
        titleFixed = file_name + "(" + str(recursionTime) + ")" + "." + ext
        return checkIfSameName(title, titleFixed, matchedFiles, recursionTime + 1)
    else:
        return titleFixed

def setFileCreationTime(filepath, timeStamp):
    date = datetime.fromtimestamp(timeStamp)
    modTime = time.mktime(date.timetuple())
    os.utime(filepath, (modTime, modTime))

def to_deg(value, loc):
    """convert decimal coordinates into degrees, munutes and seconds tuple
    Keyword arguments: value is float gps-value, loc is direction list ["S", "N"] or ["W", "E"]
    return: tuple like (25, 13, 48.343 ,'N')
    """
    if value < 0:
        loc_value = loc[0]
    elif value > 0:
        loc_value = loc[1]
    else:
        loc_value = ""
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min = int(t1)
    sec = round((t1 - min) * 60, 5)
    return (deg, min, sec, loc_value)


def change_to_rational(number):
    """convert a number to rational
    Keyword arguments: number
    return: tuple like (1, 2), (numerator, denominator)
    """
    f = Fraction(str(number))
    return (f.numerator, f.denominator)

def set_geo_exif(exif_dict, lat, lng, altitude):
    lat_deg = to_deg(lat, ["S", "N"])
    lng_deg = to_deg(lng, ["W", "E"])

    exiv_lat = (change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2]))
    exiv_lng = (change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2]))

    altitudeRef = 1 if altitude > 0 else 0 

    gps_ifd = {
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
        piexif.GPSIFD.GPSAltitudeRef: altitudeRef,
        piexif.GPSIFD.GPSAltitude: change_to_rational(round(abs(altitude), 2)),
        piexif.GPSIFD.GPSLatitudeRef: lat_deg[3],
        piexif.GPSIFD.GPSLatitude: exiv_lat,
        piexif.GPSIFD.GPSLongitudeRef: lng_deg[3],
        piexif.GPSIFD.GPSLongitude: exiv_lng,
    }

    exif_dict['GPS'] = gps_ifd

def set_date_exif(exif_dict, timestamp):
    dateTime = datetime.fromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
    exif_dict['0th'][piexif.ImageIFD.DateTime] = dateTime
    exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
    exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = dateTime
    exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = dateTime

def adjust_exif(exif_info, metadata):
    timeStamp = int(metadata['photoTakenTime']['timestamp'])

    exif_dict = piexif.load(exif_info)

    del exif_dict["thumbnail"]

    lat = metadata['geoData']['latitude']
    lng = metadata['geoData']['longitude']
    altitude = metadata['geoData']['altitude']

    set_date_exif(exif_dict, timeStamp)
    set_geo_exif(exif_dict, lat, lng, altitude)

    try:
        return piexif.dump(exif_dict)
    except:
        exif_dict['Exif'][piexif.ExifIFD.SceneType] = b'1'
        return piexif.dump(exif_dict)