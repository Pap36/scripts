import os
from pathlib import Path

downloads_path = str(Path.home() / "Downloads")

# get all extensions from all files in the Downloads folder on Mac OS
def get_extensions():
    # get all files in the Downloads folder
    files = os.listdir(downloads_path)
    # get all extensions from all files without duplicates
    extensions = list(set([processExtension(os.path.splitext(file)[1]) for file in files]))
    return extensions, files

# remove the dot from extensions if it exists
def processExtension(extension):
    return extension[::-1].strip(".")[::-1]

# print(get_extensions())

# we leave files without extensions as they are
# everything else gets grouped in folders with their extension name
def group_files():
    extensions, files = get_extensions()
    # create folders for all extensions
    for extension in extensions:
        if extension == "":
            continue
        if not os.path.exists(downloads_path + "/" + extension):
            os.makedirs(downloads_path + "/" + extension)
    # move files to their respective folders
    for file in files:
        extension = os.path.splitext(file)[1][::-1].strip(".")[::-1]
        if extension == "":
            continue
        os.rename(downloads_path + "/" + file, downloads_path + "/" + extension + "/" + file)

group_files()