# African Environmental Sustainability Assessment Tool

**African Environmental Sustainability Assessment Tool** is a comprehensive Life Cycle Assessment (LCA) platform tailored for food companies and farmers in Africa, with an initial focus on Ghana and Nigeria. The system leverages Rust for high-performance calculations and FastAPI for a robust web interface.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Usage](#api-usage)
- [Supported Food Categories](#supported-food-categories)
- [Supported Countries](#supported-countries)
- [Impact Categories](#impact-categories)
- [Data Sources](#data-sources)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Features

- **Country-Specific Data:** Impact factors customized for Ghana and Nigeria.
- **Global Fallbacks:** Utilizes global averages when local data is unavailable.
- **Comprehensive Impact Categories:** Includes 8 midpoint and 3 endpoint categories.
- **Data Quality Tracking:** Confidence levels and source documentation for transparency.
- **Flexible Food Categories:** Supports 9 major food categories relevant to African agriculture.
- **RESTful API:** Seamless integration with existing systems.

---

## Architecture

```
┌─────────────────┐    HTTP/JSON    ┌──────────────────┐
│   FastAPI       │ ──────────────> │   Rust Backend   │
│   (Python)      │ <────────────── │   (LCA Engine)   │
└─────────────────┘                 └──────────────────┘
│                                   │
│ • REST API                        │ • LCA Calculations
│ • Data Validation                 │ • Impact Factors
│ • Response Formatting             │ • Data Processing
│ • Development UI                  │ • Performance
```

---

## Quick Start

### Prerequisites

- [Rust](https://www.rust-lang.org/) (latest stable)
- [Python 3.8+](https://www.python.org/)
- Windows PowerShell (for batch scripts)

### 1. Install Dependencies

Run the installation script:

```powershell
install_deps.bat
```

Or manually:

```powershell
python -m venv african_lca_api
african_lca_api\Scripts\activate
pip install -r requirements.txt
```

### 2. Build Rust Backend

```powershell
build_rust.bat
```

Or manually:

```powershell
cd african_lca_backend
cargo build --release
```

### 3. Start the API

```powershell
run_api.bat
```

Or manually:

```powershell
african_lca_api\Scripts\activate
cd app
python main.py
```

The API will be available at:

- **Base URL:** http://localhost:8000
- **Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## API Usage

### Create Assessment

```bash
curl -X POST "http://localhost:8000/assess" \
-H "Content-Type: application/json" \
-d '{
  "company_name": "Ghana Farms Co.",
  "country": "Ghana",
  "foods": [
    {
      "id": "rice001",
      "name": "Rice",
      "quantity_kg": 1000,
      "category": "Cereals",
      "origin_country": "Ghana"
    },
    {
      "id": "cowpea001",
      "name": "Cowpea",
      "quantity_kg": 500,
      "category": "Legumes"
    }
  ]
}'
```

#### Example Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "company_name": "Ghana Farms Co.",
  "country": "Ghana",
  "assessment_date": "2024-01-15T10:30:00Z",
  "midpoint_impacts": {
    "Global warming": 3250.0,
    "Water consumption": 2800.0,
    "Land use": 4200.0,
    "Terrestrial acidification": 750.0
  },
  "endpoint_impacts": {
    "Human Health": 0.000683,
    "Ecosystem Quality": 3.9e-11,
    "Resource Scarcity": 178.75
  },
  "single_score": 68.25,
  "data_quality": {
    "confidence_level": "Medium",
    "data_source": "CountrySpecific(Ghana)",
    "regional_adaptation": true,
    "completeness_score": 0.75,
    "warnings": ["Using global averages for some impact categories"]
  }
}
```

---

## Supported Food Categories

1. **Cereals:** Rice, maize, millet, sorghum
2. **Legumes:** Cowpea, groundnuts, soybean
3. **Vegetables:** Tomato, okra, pepper, leafy greens
4. **Fruits:** Plantain, banana, mango, citrus
5. **Meat & Poultry:** Cattle, goat, chicken, sheep
6. **Fish:** Tilapia, catfish, tuna, sardines
7. **Dairy & Eggs:** Milk, cheese, eggs
8. **Oils & Nuts:** Palm oil, shea nuts, coconut
9. **Roots & Others:** Yam, cassava, sweet potato

---

## Supported Countries

- **Ghana:** Country-specific impact factors
- **Nigeria:** Country-specific impact factors
- **Global:** Global averages as fallback

---

## Impact Categories

### Midpoint (8 categories)

- Global warming (kg CO₂-eq)
- Water consumption (m³)
- Land use (m²a)
- Terrestrial acidification (kg SO₂-eq)
- Freshwater eutrophication (kg P-eq)
- Marine eutrophication (kg N-eq)
- Biodiversity loss (species·yr)
- Soil degradation (quality points)

### Endpoint (3 categories)

- Human Health (DALY)
- Ecosystem Quality (species·yr)
- Resource Scarcity (USD)

---

## Data Sources

The system integrates data from:

- **Government Agencies:** Ghana EPA, Nigeria Federal Ministry of Environment
- **Research Institutions:** IITA, CSIR-Ghana, Nigerian universities
- **International Organizations:** FAO, World Bank, IPCC
- **Academic Literature:** Peer-reviewed LCA studies

For detailed source information, see [data_sources.md](data_sources.md).

---

## Configuration

### Environment Variables

- `RUST_LOG` — Logging level (`debug`, `info`, `warn`, `error`)
- `API_HOST` — API host (default: `0.0.0.0`)
- `API_PORT` — API port (default: `8000`)

### Data Updates

Impact factors can be updated by:

1. Modifying Rust backend data structures
2. Loading from CSV files via the data loader
3. Integrating with external databases

---

## Development

### Project Structure

```
african_lca_backend/          # Rust LCA engine
├── src/
│   ├── models.rs             # Data structures
│   ├── lca.rs                # LCA calculations
│   ├── data.rs               # Impact factors
│   ├── utils.rs              # Utilities
│   └── main.rs               # CLI interface
└── Cargo.toml                # Rust dependencies

app/                          # Python FastAPI
├── main.py                   # API routes and logic
└── requirements.txt          # Python dependencies

data_sources.md               # Documentation
README.md                     # This file
```

### Testing

```powershell
# Test Rust backend
cd african_lca_backend
cargo test

# Test API endpoints
# (Start API first, then use tools like Postman or curl)
```

### Adding New Countries

1. Add the country to the `Country` enum in `models.rs`
2. Add impact factors in `data.rs`
3. Update API documentation

### Adding New Food Categories

1. Add the category to the `FoodCategory` enum in `models.rs`
2. Add impact factors for each supported country
3. Update API endpoint documentation

---

## Contributing

- Follow Rust and Python best practices
- Add tests for new functionality
- Update documentation
- Ensure all data sources are credible and documented

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

---

## Support

For technical support or questions regarding methodology:

- API documentation at `/docs` endpoint
- Data sources documentation
- Academic literature cited in impact factors

---