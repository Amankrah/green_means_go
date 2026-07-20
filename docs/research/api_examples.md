# Research API examples

Examples for researcher workflows: export saved assessments, run scenarios, and manage study cohorts. Replace placeholders with your values.

**Base URL (local dev):** `http://localhost:8000`  
**Auth:** Sign up or log in, then pass `Authorization: Bearer <access_token>` on protected routes.

## Authentication

```bash
curl -s -X POST "$BASE/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "researcher@example.com",
    "password": "password123",
    "full_name": "Ada Researcher",
    "role": "researcher"
  }'
```

Save `access_token` from the response:

```bash
export TOKEN="<access_token>"
export BASE="http://localhost:8000"
```

## Run a farm assessment with study metadata

`study_meta` carries temporal/spatial fields for export and cohort analysis.

```bash
curl -s -X POST "$BASE/assess" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Tamale Agro",
    "country": "Ghana",
    "region": "GH",
    "title": "Maize 2025 wet season",
    "study_meta": {
      "crop_year": 2025,
      "season": "WetSeason",
      "admin_region": "Northern Region"
    },
    "foods": [{
      "id": "1",
      "name": "Maize",
      "quantity_kg": 3500,
      "category": "Cereals",
      "area_allocated": 2.5
    }]
  }'
```

Save `id` from the response as `ASSESSMENT_ID`.

## Export JSON (SI-ready slice)

OpenAPI tag: **research-export**

```bash
curl -s "$BASE/me/assessments/$ASSESSMENT_ID/export.json" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Includes `contribution_by_source`, `contribution_sankey`, `study_meta`, `uncertainty`, and `method_variants` when present.

## Export CSV

```bash
curl -s "$BASE/me/assessments/$ASSESSMENT_ID/export.csv" \
  -H "Authorization: Bearer $TOKEN" \
  -o assessment_export.csv
```

Sections: `# midpoints`, `# input_matches`, `# contribution_by_source`.

## Scenario compare

OpenAPI tag: **research-scenarios**

Clone the archived request, apply a patch, re-solve, and return midpoint deltas:

```bash
curl -s -X POST "$BASE/assess/$ASSESSMENT_ID/scenarios" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Yield +20%", "yield_scale": 1.2}'
```

Other patches: `n_rate_scale`, `diesel_scale`.

## Recharacterize (method lab)

```bash
curl -s -X POST "$BASE/assess/$ASSESSMENT_ID/recharacterize" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lcia_method": "EF v3.1",
    "apply_as_primary": false
  }'
```

## Uncertainty (pedigree screening MC)

```bash
curl -s -X POST "$BASE/assess/$ASSESSMENT_ID/uncertainty" \
  -H "Authorization: Bearer $TOKEN"
```

## Study cohorts

OpenAPI tag: **research-studies** (researcher role required)

```bash
curl -s -X POST "$BASE/studies" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Northern Ghana maize 2025",
    "assessment_ids": ["'"$ASSESSMENT_ID"'"]
  }'
```

List studies:

```bash
curl -s "$BASE/studies" -H "Authorization: Bearer $TOKEN"
```

## Read-only share link

OpenAPI tag: **research-share**

Generate a token (owner only):

```bash
curl -s -X POST "$BASE/me/assessments/$ASSESSMENT_ID/share" \
  -H "Authorization: Bearer $TOKEN"
```

Fetch results without auth:

```bash
curl -s "$BASE/share/$SHARE_TOKEN"
```

The share route is read-only; it does not accept POST/PATCH/DELETE.

## OpenAPI

In development, browse grouped tags at `$BASE/docs`:

| Tag | Endpoints |
|-----|-----------|
| `research-export` | `GET /me/assessments/{id}/export.json`, `export.csv` |
| `research-scenarios` | `POST /assess/{id}/scenarios`, `recharacterize`, `uncertainty` |
| `research-studies` | `CRUD /studies` |
| `research-share` | `POST /me/assessments/{id}/share`, `GET /share/{token}` |
