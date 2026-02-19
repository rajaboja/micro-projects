import pytesseract
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import fitz
import re
from pathlib import Path
import pandas as pd
import sys

DPI = 300

def parse_songs(txt):
    "Extract structured song data from OCR text"
    pattern = r'^(?=[^a-z0-9 ]*[A-Z])[^a-z]+$'
    song_re = re.compile(r'(\d+)[.,]\s*(.+?)\s+Film:\s*(.+?)(?:\s+Artistes?:\s*(.+?))?(?=\n\d+[.,]\s|\Z)', re.DOTALL)
    parts = re.split(f'({pattern})', txt, flags=re.MULTILINE)
    songs = []
    for i in range(1, len(parts), 2):
        hdr,content = parts[i].strip(),parts[i+1]
        for m in song_re.finditer(content):
            artists = re.sub(r'\s+', ' ', m[4]).strip() if m[4] else ''
            songs.append(dict(section=hdr, song_number=int(m[1]), title=m[2].strip(), film=m[3].strip(), artists=artists))
    return songs
def extract_text(img, psm=6, lang='eng'): return pytesseract.image_to_string(img, config=f'--psm {psm} --oem 1 --dpi {DPI}', lang=lang).strip()
def clean_img(
    img: Image.Image,
    contrast: float = 1.6,
    threshold: int | None = 175
) -> Image.Image:
    
    work = ImageOps.grayscale(img)

    if contrast and contrast != 1.0:
        work = ImageEnhance.Contrast(work).enhance(contrast)

    work = work.filter(
        ImageFilter.UnsharpMask(radius=3)
    )

    if threshold is not None:
        t = int(threshold)
        work = work.point(lambda p: 255 if p > t else 0)

    return work
def img_to_patches(img, top_frac=0.15, y_tolerance=50, offset=5):
    "Split image into header and column patches for improved OCR accuracy"
    cleaned = clean_img(img)
    top_h = int(cleaned.height * top_frac)
    top_region = cleaned.crop((0, 0, cleaned.width, top_h))
    text = pytesseract.image_to_data(top_region, output_type=pytesseract.Output.DATAFRAME)
    nums = text[text.text.astype(str).str.match(r'^\d+[.,]?$', na=False)]
    min_top = nums['top'].min()
    col_starts = sorted(nums[nums['top'] < min_top + y_tolerance]['left'].tolist())
    header_img = cleaned.crop((0, 0, cleaned.width, max(0, min_top-offset)))
    bounds = [max(0, x-offset) for x in col_starts] + [cleaned.width]
    cols = [cleaned.crop((bounds[i], max(0, min_top-offset), bounds[i+1], cleaned.height)) for i in range(len(bounds)-1)]
    return [header_img] + cols
def process_page(page, f):
    text = page.get_text()
    if text.strip(): f.write(text + '\n\n')
    else:
        pix = page.get_pixmap(dpi=DPI)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        patches = img_to_patches(img)
        f.write('\n\n'.join([extract_text(p) for p in patches]) + '\n\n')

def process_pdf(pdf_path, out_path):
    with open(out_path, 'w') as f:
        doc = fitz.open(pdf_path)
        total = len(doc)
        for i,page in enumerate(doc, 1):
            process_page(page, f)
            print(f'\r{i}/{total}', end='')
        print('\nDone!')
        doc.close()
def main():
    if len(sys.argv) < 2: print("Usage: python script.py <pdf_path> [output_parquet]"); sys.exit(1)
    pdf_path = sys.argv[1]
    txt_path = Path(pdf_path).stem + '.txt'
    out_path = sys.argv[2] if len(sys.argv) > 2 else Path(pdf_path).stem + '.parquet'
    process_pdf(pdf_path, txt_path)
    songs = parse_songs(Path(txt_path).read_text())
    df = pd.DataFrame(songs).drop_duplicates()
    df.to_parquet(out_path, index=False)
    print(f'Saved {len(df)} songs to {out_path}')

if __name__ == '__main__': main()
