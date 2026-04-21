# Team Setup Guide (Do Not Share Keys)

Use this guide so every group member can run the project without sharing private credentials.

---

## Goal

Each person uses their **own** Google Cloud key file on their own computer.

Never share:
- `credentials/google-vision-key.json`

---

## 1) Create your own Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project picker (top bar) -> **New Project**.
3. Name it (example: `mtg-sorter-yourname`).
4. Create and switch to that project.

---

## 2) Turn on billing and add budget protection

1. Go to **Billing** and connect a billing account.
2. Go to **Billing -> Budgets & alerts**.
3. Create a budget (example: `$5` or `$10`).
4. Add alerts at 50%, 90%, and 100%.
5. Optional: add quota limits for Vision API calls.

---

## 3) Enable Cloud Vision API only

1. Go to **APIs & Services -> Library**.
2. Search for **Cloud Vision API**.
3. Click **Enable**.

Do not enable extra APIs unless needed.

---

## 4) Create a service account

1. Go to **IAM & Admin -> Service Accounts**.
2. Click **Create Service Account**.
3. Name: `mtg-vision-runner` (or any clear name).
4. Click **Create and Continue**.
5. Give role:
   - `Cloud Vision API User` (or your org's smallest Vision invoke role)
6. Finish.

---

## 5) Create and download JSON key

1. Open the service account.
2. Go to **Keys** tab.
3. Click **Add Key -> Create new key -> JSON**.
4. Download the file.
5. Save it to this repo path on your machine:
   - `credentials/google-vision-key.json`

Important:
- Do not send this file to anyone.
- Do not upload this file to GitHub.
- Do not paste this file in chat.

---

## 6) Clone and install project

```bash
git clone <repo-url>
cd SCHOOL_PROJECT
python -m venv venv
```

Windows:

```bash
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

## 7) Confirm key is local only

Run:

```bash
git status
```

You should NOT see `credentials/google-vision-key.json` listed.

---

## 8) Run a quick test

Single image:

```bash
.\venv\Scripts\python.exe scripts/bin_from_path.py "data/Magic the gathering Iphone/Screenshot 2026-04-13 185409.png" --mode type
```

Folder:

```bash
.\venv\Scripts\python.exe scripts/bin_from_path.py "data/Magic the gathering Iphone" --mode type
```

Expected output includes:
- card name
- bin name
- timing in seconds and milliseconds

---

## 9) Team safety rules

- Never commit files in `credentials/`
- Never share key file in any chat
- Never screenshot key content
- If exposed, revoke and replace immediately

---

## 10) If key leaks (emergency)

1. Go to **IAM & Admin -> Service Accounts -> Keys**.
2. Delete the leaked key now.
3. Create a new key.
4. Replace local file in `credentials/google-vision-key.json`.
5. If key was pushed to git, rotate key first, then clean history if needed.
