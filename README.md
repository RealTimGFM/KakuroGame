# Kakuro Game

A small Kakuro game

## Download

```bash
cd KakuroGame
```

## Run

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Activate it:

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the app:

```bash
python app.py
```

5. Open your browser at:

```text
http://127.0.0.1:5000
```

## Database

The app uses a local SQLite database file named `kakuro.db`.

To recreate the database and import puzzles:

```bash
python database.py reset
```
