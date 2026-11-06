---
name: app-scaffold
description: Scaffold web apps, Capacitor APKs, Node/Python backends with SQLite.
---
# App scaffolding

## Web frontend
`npm create vite@latest my-app -- --template react-ts` then Tailwind + the ui-design skill.

## Capacitor APK (needs setup-android-sdk first)
In the web app: `npm i @capacitor/core @capacitor/cli @capacitor/android && npx cap init && npx cap add android && npx cap sync && cd android && ./gradlew assembleDebug`.

## Node backend
`mkdir api && cd api && npm init -y && npm i express better-sqlite3 cors` — SQLite file at `./data.db`.

## Python backend
`python3 -m venv .venv && . .venv/bin/activate && pip install fastapi uvicorn sqlalchemy` — SQLite via SQLAlchemy.
