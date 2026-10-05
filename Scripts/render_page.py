import pymupdf

doc = pymupdf.open(r"D:\FactoryKA\documents\7.pdf")
page = doc[17]  # page 18 is index 17 (0-based)
pix = page.get_pixmap(dpi=300)  # high resolution render
pix.save(r"D:\FactoryKA\test4_page18_highres.png")
print("Saved high-res version of page 18")