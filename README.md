# Kakuro Game

A Flask-based Kakuro game that runs locally with SQLite and can be deployed to Render with a Neon PostgreSQL database.

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

By default, the app uses a local SQLite database file named `kakuro.db`.

To recreate the local database and import puzzles:

```bash
python database.py reset
```

If `DATABASE_URL` is set, the app automatically switches to PostgreSQL. This is the mode you want for Neon and Render.

## Render + Neon

The app is now ready to deploy on Render with Neon:

1. Create a Neon database and copy its connection string.
2. In Render, create a new web service from this repo.
3. Set `DATABASE_URL` in Render to your Neon connection string.
4. Set `SECRET_KEY` in Render to a long random value.
5. Deploy using the included `render.yaml`, or use these commands manually:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn wsgi:app
```

### Required environment variables

- `DATABASE_URL`: your Neon PostgreSQL connection string
- `SECRET_KEY`: Flask session secret

### Optional environment variables

- `AUTO_LOAD_PUZZLES=true`: imports `puzzles_import.json` automatically when the `puzzles` table is empty
- `SESSION_COOKIE_SECURE=true`: keeps cookies secure behind HTTPS, which is the right default on Render
- `FLASK_DEBUG=false`: local debugging only

### Neon connection string

Use the full Neon Postgres connection string. If `sslmode=require` is missing, the app adds it automatically for PostgreSQL connections.

Example format:

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

### First deploy behavior

On startup, the app:

- creates the tables if they do not exist
- imports puzzles from `puzzles_import.json` if the puzzle catalog is empty

That means a fresh Neon database can be deployed without a separate manual migration step for this project.
