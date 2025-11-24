from PIL import Image
import os

source = "assets/SeeSense Logo.png"
dest = "assets/logo_fixed.png"

try:
    if os.path.exists(source):
        img = Image.open(source)
        img.save(dest, "PNG")
        print(f"Successfully converted {source} to {dest}")
    else:
        print(f"Source file {source} not found")
except Exception as e:
    print(f"Error converting image: {e}")
