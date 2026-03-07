# Planovani_smen_fermato

Jednoduchá webová aplikace pro plánování směn (Flask + SQLite).

## 🚀 Rychlý start

1) Vytvořte a aktivujte virtuální prostředí:

```bash
python -m venv .venv
source .venv/bin/activate
```

2) Nainstalujte závislosti:

```bash
pip install -r requirements.txt
```

3) Inicializujte databázi:

```bash
flask init-db
```

4) Vytvořte prvního uživatele:

```bash
flask create-user <username> -n "Display Name"
```

5) Spusťte aplikaci:

```bash
python run.py
```

Aplikace poběží na `http://localhost:5000`.

---

## 🔐 Konfigurace (env proměnné)

Nastavte prostředí pro SMTP (pokud chcete posílat emaily):

- `SECRET_KEY` – tajný klíč pro Flask session
- `MAIL_SERVER` – např. `smtp.gmail.com`
- `MAIL_PORT` – obvykle `587`
- `MAIL_USE_TLS` – `true|false`
- `MAIL_USERNAME` – přihlašovací jméno
- `MAIL_PASSWORD` – heslo
- `MAIL_DEFAULT_SENDER` – adresa odesílatele

---

## 🗂️ Struktura projektu

- `app/` – zdrojový kód aplikace
  - `routes/` – webové routy
  - `models/` – práce s databází
  - `services/` – logika pro plánování / export / emaily
- `instance/` – runtime data (databáze, uploady, exporty)
- `schema.sql` – databázové schéma + seed (výchozí data)

---

## 🛠️ Tipy

- Pokud potřebujete reset databáze, smažte soubor `instance/planovani_smen.db` a spusťte `flask init-db`.
- Pro vývoj zapněte `FLASK_ENV=development` (nebo `FLASK_DEBUG=1`).
