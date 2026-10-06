import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import pymupdf

doc = pymupdf.open(os.path.join(config.DOCUMENTS_DIR, "7.pdf"))
page = doc[17]  # page 18 is index 17 (0-based)
pix = page.get_pixmap(dpi=300)  # high resolution render
pix.save(os.path.join(config.RESULTS_DIR, "test4_page18_highres.png"))
print("Saved high-res version of page 18")