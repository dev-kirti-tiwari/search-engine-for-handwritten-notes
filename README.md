---
title: NotesFinder
emoji: 🔎
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# NotesFinder

Search your handwritten notes and PDFs by keyword. Upload a photo of a notebook page or a PDF, and NotesFinder reads every page with OCR, tags its topics, and lets you jump straight to the page you need.

Built as a B.Tech CSE 2nd year mini project.

## Features

- **Upload JPG, JPEG, PNG and PDF** files, one or many at a time (up to 50 MB each).
- **OCR for handwriting and scans** using EasyOCR (Tesseract is supported as a fallback).
- **Text PDFs are read directly**, with no OCR needed. Scanned pages inside a PDF are detected and OCR'd automatically.
- **Ranked search** across all pages. Multi-word queries must match all words. Matches are highlighted.
- **Fuzzy matching** tolerates OCR mistakes and typos. Searching `compresion` still finds "compression", and a word cut off by OCR still matches. These results appear after exact ones with a "Similar match" label.
- **Auto topic tags** for each page, from a built-in list of computer-science topics plus frequent keywords.
- **Page preview** shows the original page image next to the extracted text, with next/previous navigation (also the arrow keys), click-to-zoom, and a copy-text button.
- **Dashboard** with stats, popular topics, a filterable notes list, and view/delete for each note.
- **Search within one file** or across everything.
- **Private**: everything runs and is stored on your own computer. Nothing is sent to any server.

## Tech stack

| Part | Tool |
|---|---|
| Backend | Python, Flask |
| Database | SQLite |
| PDF handling | PyMuPDF |
| Image handling | Pillow, OpenCV |
| OCR | EasyOCR (or Tesseract) |
| Frontend | HTML, CSS, vanilla JavaScript |

## Setup

You need Python 3.10 or newer.

```
pip install -r requirements.txt
pip install easyocr
python app.py
```

Then open http://127.0.0.1:5000

Notes:

- `easyocr` is a large install (it brings in PyTorch, about 1-2 GB). It is needed for handwriting and scanned pages.
- The first OCR run downloads the recognition model once. After that it works offline.
- The OCR model loads in the background when the server starts, which takes about 30 seconds. Uploads right after startup may wait a little.
- If you prefer Tesseract, install the Tesseract program and `pip install pytesseract`. The app detects whichever engine is available and prefers EasyOCR.
- If you add an OCR engine while the server is running, restart the server.

## How to use

1. Open **Dashboard** and drop one or more files into the upload box.
2. Wait while pages are processed. Large files and handwriting take longer.
3. Search from the home page, the dashboard or the **Search** page.
4. Click **Preview page** on a result to see the original page and its text. Use **Open file** for the full original.

### Tips for better handwriting results

- Photograph the page straight on, not at an angle.
- Use bright, even light with no shadows across the writing.
- Dark ink on plain paper works best.
- Fill the frame with the page, and keep the photo in focus.

OCR on handwriting is never perfect. Fuzzy search exists to cover small misreads, but very messy writing may still be missed.

## Project structure

```
app.py                  Flask app, routes and search
processing/
  ocr.py                OCR engine detection and text extraction
  pdf_processing.py     PDF text extraction and page previews
  tagging.py            Topic tag generation
templates/              HTML pages (home, dashboard, results)
static/                 CSS and JavaScript
database/notes.db       SQLite database (created automatically)
uploads/                Uploaded files and page previews (created automatically)
```

## How it works

1. **Upload**: the file is saved under `uploads/` and recorded in the `notes` table.
2. **Read**: for a PDF, each page is rendered to a preview image, and its text is taken directly, or from OCR if the page has almost no text. For an image, OCR runs on the photo after grayscale and contrast cleanup.
3. **Tag**: each page's text is matched against topic keywords and frequent words to produce tags.
4. **Store**: text, tags and previews are saved per page (`pages`, `tags`, `page_tags` tables).
5. **Search**: the query is split into words. Pages containing all words (in text or tags) are ranked first, by how often the phrase and words appear. Pages that match only approximately follow.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/upload` | Upload and process a file |
| GET | `/api/notes` | List notes |
| GET / DELETE | `/api/notes/<id>` | Note details / delete a note |
| GET | `/api/search?q=...&note_id=...` | Search pages |
| GET | `/api/pages/<id>` | Page text, tags and neighbours |
| GET | `/api/pages/<id>/image` | Page preview image |
| GET | `/api/notes/<id>/file` | Original uploaded file |
| GET | `/api/stats` | Counts, popular tags and OCR engine |

## Deploying publicly (Hugging Face Spaces)

NotesFinder needs a real server with disk space and enough memory for OCR, so it does not run on Vercel. The included `Dockerfile` is set up for Hugging Face Spaces:

1. Create a free account at huggingface.co and click **New Space**.
2. Choose **Docker** as the SDK (Blank template) and create it.
3. Upload every project file, including `Dockerfile`, `requirements.txt`, `app.py`, `processing/`, `templates/`, `static/` and this `README.md`. Do not upload `uploads/`, `database/` or `err.txt`.
4. The Space builds automatically (about 10 minutes the first time). Then it is live at `https://<your-username>-<space-name>.hf.space`.

Things to know:

- On the free tier the disk is **not persistent**. Uploaded notes disappear when the Space restarts or sleeps. For permanent storage, enable persistent storage in the Space settings (paid) and set the variable `DATA_DIR=/data`.
- The free tier has no GPU, so OCR is slow (a few seconds per page).
- There are no user accounts, so **everyone who visits sees all uploaded notes**. Do not put private notes on a public deployment.

## Limitations

- OCR accuracy depends on the handwriting and photo quality.
- Tags are tuned for computer-science notes. Other subjects get fewer topic tags, though search uses the full text, so it still works.
- Files are processed one request at a time, so very large PDFs can take a while.
- The built-in Flask server is for local use and demos, not for public deployment.
- There are no user accounts. Anyone who can open the app can see all notes.

## Possible future work

- Subject folders and filters
- Better handwriting models, and image deskewing before OCR
- Re-running OCR on older uploads
- Exporting extracted text
- User accounts
