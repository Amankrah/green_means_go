# African Environmental Sustainability Assessment Tool

A comprehensive Life Cycle Assessment (LCA) tool designed specifically for food companies and farmers in Africa, starting with Ghana and Nigeria. The system uses Rust for high-performance calculations and FastAPI for the web interface.

## Features

- **Country-Specific Data**: Tailored impact factors for Ghana and Nigeria
- **Global Fallbacks**: Uses global averages when local data unavailable  
- **Multiple Impact Categories**: 8 midpoint and 3 endpoint impact categories
- **Data Quality Tracking**: Confidence levels and source documentation
- **Flexible Food Categories**: Supports 9 major food categories relevant to African agriculture
- **RESTful API**: Easy integration with existing systems

## Architecture

```
┌─────────────────┐    HTTP/JSON    ┌──────────────────┐
│   FastAPI       │ ──────────────> │   Rust Backend   │
│   (Python)      │ <────────────── │   (LCA Engine)   │
└─────────────────┘                 └──────────────────┘
│                                   │
│ • REST API                       │ • LCA Calculations
│ • Data Validation               │ • Impact Factors
│ • Response Formatting          │ • Data Processing
│ • Development UI               │ • Performance
```

## Quick Start

### Prerequisites
- **Rust** (latest stable version)
- **Python 3.8+**
- **Windows PowerShell** (for batch scripts)

### 1. Install Dependencies

Run the dependency installation script:
```cmd
install_deps.bat
```

Or manually:
```cmd
# Create and activate Python virtual environment
python -m venv african_lca_api
african_lca_api\Scripts\activate

# Install Python dependencies  
pip install -r requirements.txt
```

### 2. Build Rust Backend

```cmd
build_rust.bat
```

Or manually:
```cmd
cd african_lca_backend
cargo build --release
```

### 3. Start the API

```cmd
run_api.bat
```

Or manually:
```cmd
african_lca_api\Scripts\activate
cd app
python main.py
```

The API will be available at:
- **API Base**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

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

### Response

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

## Supported Food Categories

1. **Cereals** - Rice, maize, millet, sorghum
2. **Legumes** - Cowpea, groundnuts, soybean
3. **Vegetables** - Tomato, okra, pepper, leafy greens
4. **Fruits** - Plantain, banana, mango, citrus
5. **MeatPoultry** - Cattle, goat, chicken, sheep
6. **Fish** - Tilapia, catfish, tuna, sardines
7. **DairyEggs** - Milk, cheese, eggs
8. **OilsNuts** - Palm oil, shea nuts, coconut
9. **RootsOther** - Yam, cassava, sweet potato

## Supported Countries

- **Ghana** - Country-specific impact factors
- **Nigeria** - Country-specific impact factors  
- **Global** - Global averages as fallback

## Impact Categories

### Midpoint (8 categories)
- Global warming (kg CO2-eq)
- Water consumption (m³)
- Land use (m²a)
- Terrestrial acidification (kg SO2-eq)
- Freshwater eutrophication (kg P-eq)
- Marine eutrophication (kg N-eq)
- Biodiversity loss (species.yr)
- Soil degradation (quality points)

### Endpoint (3 categories)
- Human Health (DALY)
- Ecosystem Quality (species.yr)
- Resource Scarcity (USD)

## Data Sources

The system integrates data from:

- **Government Sources**: Ghana EPA, Nigeria Federal Ministry of Environment
- **Research Institutions**: IITA, CSIR-Ghana, Nigerian universities
- **International Organizations**: FAO, World Bank, IPCC
- **Academic Literature**: Peer-reviewed LCA studies

See [data_sources.md](data_sources.md) for detailed source information.

## Configuration

### Environment Variables
- `RUST_LOG` - Logging level (debug, info, warn, error)
- `API_HOST` - API host (default: 0.0.0.0)
- `API_PORT` - API port (default: 8000)

### Data Updates
Impact factors can be updated by:
1. Modifying the Rust backend data structures
2. Loading from CSV files using the data loader
3. Integrating with external databases

## Development

### Project Structure
```
african_lca_backend/          # Rust LCA engine
├── src/
│   ├── models.rs            # Data structures
│   ├── lca.rs              # LCA calculations  
│   ├── data.rs             # Impact factors
│   ├── utils.rs            # Utilities
│   └── main.rs             # CLI interface
└── Cargo.toml              # Rust dependencies

app/                         # Python FastAPI
├── main.py                 # API routes and logic
└── requirements.txt        # Python dependencies

data_sources.md             # Documentation
README.md                   # This file
```

### Testing
```cmd
# Test Rust backend
cd african_lca_backend
cargo test

# Test API endpoints
# (Start API first, then use tools like Postman or curl)
```

### Adding New Countries
1. Add country to `Country` enum in `models.rs`
2. Add impact factors in `data.rs`
3. Update API documentation

### Adding New Food Categories
1. Add category to `FoodCategory` enum in `models.rs`
2. Add impact factors for each supported country
3. Update API endpoint documentation

## Contributing

1. Follow Rust and Python best practices
2. Add tests for new functionality
3. Update documentation
4. Ensure data sources are credible and documented

## License

[Add appropriate license]

## Support

For technical support or questions about the methodology, please refer to:
- API documentation at `/docs` endpoint
- Data sources documentation
- Academic literature cited in impact factors