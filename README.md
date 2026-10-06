# Expense Management System

## Overview

A small production-structured REST API for tracking personal expenses and category budgets. Every financial record is owner-scoped.

## Features

- Registration, login, database-backed JWT logout, and admin/user roles
- Admin-managed expense categories
- Owner-protected expense CRUD with search, date/category filters, sorting, and pagination
- Monthly category budgets, dashboard totals, remaining-budget reports, and activity logs
- Structured errors, audit fields, validation, Docker, PostgreSQL migrations, seed data, and CI

## Technology Stack

Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, PostgreSQL 17 (SQLite in unit tests), PyJWT, Argon2, pytest, Ruff, pip-audit, Docker.

## Requirements

Python 3.12+ and PostgreSQL 15+, or Docker with Compose.

## Installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env
```

## Environment Variables

`DATABASE_URL` is required. `JWT_SECRET` must contain at least 32 random characters. Optional variables are `JWT_EXPIRY_MINUTES` and comma-separated `ALLOWED_ORIGINS`. Never use the example secret in production.

## Database Setup

```bash
python -m app.migrate
python -m app.seed
```

Docker alternative: `docker compose up -d db`, then `docker compose --profile tools run --rm migrate` and `docker compose --profile tools run --rm seed`.

## Running the Application

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs`. For Docker, run `docker compose up --build api` after migration.

## Running Tests

```bash
ruff check .
pytest -q
pip-audit
```

## Default Development Accounts

Created only by the seed command:

- Admin: `admin@example.com` / `AdminPassword123!`
- User: `user@example.com` / `UserPassword123!`

Change these development-only passwords outside a disposable local environment.

## API Endpoints

Authentication: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`. Categories: `GET/POST /api/categories`. Expenses: `GET/POST /api/expenses`, `GET/PUT/DELETE /api/expenses/{id}`. Budgets: `GET/PUT /api/budgets`. Reports: `GET /api/reports/monthly` and `GET /api/dashboard`. Health: `GET /health`.

## Folder Structure

`app/` contains API, schemas, models, services, repositories, auth, and configuration. `migrations/` owns PostgreSQL schema changes. `tests/` contains isolated service tests. `.github/workflows/` runs PostgreSQL CI.

## Architecture

Routes handle HTTP concerns, services enforce ownership and business rules, repositories build data queries, schemas whitelist request/response fields, and SQLAlchemy models map persistence.

## Security Notes

Passwords use Argon2. Short-lived JWTs map to revocable server-side sessions. Login is rate-limited and performs dummy-hash verification for unknown users. Authorization and ownership are enforced server-side. Queries are parameterized, inputs and page sizes are bounded, CORS is allow-listed, errors do not expose stack traces, and responses exclude password hashes and secrets.

## Known Limitations

The in-memory login limiter is per process; distributed deployment needs Redis or a gateway limiter. Currency conversion, recurring expenses, receipt uploads, email verification, password reset, and immutable external audit storage are intentionally outside this portfolio scope.
