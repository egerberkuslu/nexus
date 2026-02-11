# Frontend E2E Tests

This folder contains Playwright tests that verify UI and API integration.

Specs:

- `e2e/smoke.spec.ts`: quick sanity checks.
- `e2e/f1-f19.spec.ts`: full feature validation flow for claims F1-F19.

## Prerequisites

- Caduceus-Flux stack is running (`frontend` on `http://localhost:3000`, API under `/api`)
- Node dependencies installed in `frontend/`

## Install browser

```bash
cd frontend
npm run e2e:install
```

## Run tests

```bash
cd frontend
npm run e2e
```

Run only smoke tests:

```bash
npm run e2e:smoke
```

Run only F1-F19 validation:

```bash
npm run e2e:f1f19
```

## Useful variants

```bash
npm run e2e:headed
npm run e2e:ui
npm run e2e:report
```

## Target URL

By default tests run against:

- `http://localhost:3000`

To run against another URL:

```bash
E2E_BASE_URL=http://127.0.0.1:3000 npm run e2e
```
