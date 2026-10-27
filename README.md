# Structural Drawing Bot v1.1 — one project, separate floor files

This version is organized around the user's current workflow: each floor has its own PDF and DWG files.

## Main workflow
1. Upload each drawing as a Telegram **Document**.
2. Select floor, structural element, zone/grid, and drawing number/title.
3. The original PDF/DWG is saved without conversion or editing.
4. Browse `Floor → Element` to retrieve the relevant files, or use text search.
5. The bot returns the original file as uploaded.

## What's included
- Telegram bot code (`bot.py`)
- SQLite index (`drawings.db`, created at first run)
- Original file storage folder (`drawings/`)
- Floor and element browsing, search, recent files
- Supports `.pdf` and `.dwg` extensions

## Setup — Windows
1. Install Python 3.10+.
2. Extract the ZIP.
3. Open Command Prompt in the extracted folder.
4. Run:
   `py -m venv .venv`
   `.venv\Scripts\activate`
   `pip install -r requirements.txt`
5. Set your token for this terminal session:
   `set TELEGRAM_BOT_TOKEN=PASTE_TOKEN_FROM_BOTFATHER`
6. Run:
   `python bot.py`

## Setup — Linux VPS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='PASTE_TOKEN_FROM_BOTFATHER'
python bot.py
```

Create a bot using Telegram's official `@BotFather`. Keep the token private.

## Suggested naming standard
Use names such as:
- `B2-SLAB-SD-001.pdf`
- `B2-SLAB-SD-001.dwg`
- `L05-BEAM-SD-014.pdf`
- `L05-BEAM-SD-014.dwg`

If PDF and DWG are matching representations of the same drawing, enter the same floor, element, zone, and drawing number for both. They will appear together in the search results. The v1.1 interface does not yet pair them into a single result card.

## Original-file preservation
- Files are stored as original bytes with a unique stored filename; the original filename is retained in the database and used when sending the file back.
- No conversion, PDF export, DWG edit, or drawing geometry parsing occurs in v1.1.
- Back up both `drawings/` and `drawings.db`.
- The bot's local disk must remain available while running.
- Telegram upload/download limits and the server's disk limits may restrict very large DWG files. Test with representative project files before relying on this in production.

## Not included yet
- OCR/full-text search inside PDFs.
- Reading DWG entities or detecting beam/column marks automatically.
- Automatic revision/status approval and access permissions.
- Cloud storage or automated backups.
- Engineering validation. Retrieved drawings should still be checked against the approved revision and project document-control procedure.
