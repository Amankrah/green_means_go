# African Environmental Sustainability Assessment Platform

> **Enterprise-Grade LCA Platform for African Food Systems**  
> Modern full-stack application delivering comprehensive environmental sustainability assessments for food companies, farmers, and processing facilities across Africa.

[![License](https://img.shields.io/badge/license-Proprietary-red.svg)]()
[![Rust](https://img.shields.io/badge/rust-1.75%2B-orange.svg)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/next.js-15.5-black.svg)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0%2B-blue.svg)](https://www.typescriptlang.org/)

---

## Table of Contents

- [🚀 Tech Stack](#-tech-stack)
- [🏗️ Architecture](#️-architecture)
- [✨ Features](#-features)
- [📊 Assessment Types](#-assessment-types)
- [🔧 Quick Start](#-quick-start)
- [📖 API Documentation](#-api-documentation)
- [🌍 Supported Categories](#-supported-categories)
- [📈 Data Sources](#-data-sources)
- [⚙️ Configuration](#️-configuration)
- [🛠️ Development](#️-development)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🚀 Tech Stack

### **Frontend** - Modern React Application
```typescript
┌─────────────────────────────────────┐
│             Frontend Stack          │
├─────────────────────────────────────┤
│ • Next.js 15.5 (App Router)        │
│ • React 19.1 (Latest)              │
│ • TypeScript 5.0+                  │
│ • Tailwind CSS 4 (Styling)         │
│ • React Hook Form (Forms)          │
│ • Zod (Validation)                 │
│ • Recharts (Visualization)         │
│ • Framer Motion (Animations)       │
│ • Headless UI (Components)         │
│ • Turbopack (Build Optimization)   │
└─────────────────────────────────────┘
```

### **Backend** - High-Performance API Services
```rust
┌─────────────────────────────────────┐
│             Backend Stack           │
├─────────────────────────────────────┤
│ • FastAPI (Python 3.8+)           │
│   ├── Production Module            │
│   ├── Processing Module            │
│   └── Modular Architecture         │
│                                     │
│ • Rust (High-Performance Core)     │
│   ├── LCA Calculation Engine       │
│   ├── Impact Factor Database       │
│   └── Data Processing Pipeline     │
│                                     │
│ • Pydantic (Data Validation)       │
│ • Uvicorn (ASGI Server)           │
│ • JSON Processing & REST APIs      │
└─────────────────────────────────────┘
```

---

## 🏗️ Architecture

### **Full-Stack Application Architecture**
```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   Next.js   │  │   React     │  │ TypeScript  │           │
│  │   App       │  │ Components  │  │   Types     │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP/REST API
┌─────────────────────▼───────────────────────────────────────────┐
│                     API Gateway Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   FastAPI   │  │  Production │  │ Processing  │           │
│  │    Main     │  │   Module    │  │   Module    │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────┬───────────────────────────────────────────┘
                      │ JSON Processing
┌─────────────────────▼───────────────────────────────────────────┐
│                   Computation Layer                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Rust LCA Engine                         │   │
│  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │   │
│  │ │ Impact      │ │ Production  │ │ Processing  │       │   │
│  │ │ Factors     │ │ Algorithms  │ │ Algorithms  │       │   │
│  │ └─────────────┘ └─────────────┘ └─────────────┘       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### **Modular Backend Architecture**
```
app/
├── main.py                    # 🚀 FastAPI Application Entry
├── production/                # 🌾 Farm Assessment Module
│   ├── routes.py             #   └── Production Endpoints
│   ├── models.py             #   └── Farm & Crop Models
│   └── README.md             #   └── Module Documentation
├── processing/                # 🏭 Processing Assessment Module
│   ├── routes.py             #   └── Processing Endpoints
│   ├── models.py             #   └── Facility & Equipment Models
│   └── README.md             #   └── Module Documentation
└── [shared utilities]

african_lca_backend/           # ⚡ Rust Computation Core
├── src/
│   ├── production/           #   └── Farm LCA Algorithms
│   ├── processing/           #   └── Processing LCA Algorithms
│   └── lib.rs               #   └── Core LCA Engine
└── Cargo.toml               #   └── Rust Dependencies
```

---

## ✨ Features

### **🎯 Comprehensive Assessment Types**
- **Farm-Level Assessments:** Crop production, farm management, sustainability analysis
- **Processing Facility Assessments:** Equipment efficiency, energy optimization, waste management
- **Full Value Chain:** Farm-to-fork environmental impact analysis

### **🚀 Advanced Technology Integration**
- **High-Performance Computing:** Rust-powered LCA calculations (1000x faster than Python)
- **Modern UI/UX:** React 19 with responsive design and real-time feedback
- **Type Safety:** End-to-end TypeScript coverage with Zod validation
- **Modular Architecture:** Microservice-style backend with specialized modules

### **📊 Rich Data Analysis**
- **8 Midpoint Impact Categories:** Carbon footprint, water use, land use, biodiversity, and more
- **3 Endpoint Categories:** Human health, ecosystem quality, resource scarcity
- **Data Quality Scoring:** Confidence levels, uncertainty ranges, source tracking
- **Benchmarking:** Performance comparison with similar operations

### **🌍 African-Focused Capabilities**
- **Country-Specific Data:** Customized impact factors for Ghana and Nigeria
- **Local Context:** Climate, soil, agricultural practice adaptations
- **Global Fallbacks:** International data when local data unavailable
- **Scalable Design:** Ready for expansion to additional African countries

---

## 📊 Assessment Types

### **🌾 Production Assessments** - Farm Operations Analysis
```typescript
// Simple farm assessment
POST /assess
{
  company_name: "Ghana Farms Co.",
  country: "Ghana",
  foods: [
    { id: "maize001", name: "Maize", quantity_kg: 1000, category: "Cereals" }
  ]
}

// Comprehensive farm assessment with management analysis
POST /assess/comprehensive
{
  // ... basic assessment data ...
  farm_profile: {
    farmer_name: "Kwame Asante",
    farm_name: "Asante Organic Farm",
    farm_type: "SmallScale",
    farming_system: "Organic"
  },
  management_practices: {
    soil_management: { soil_type: "Loam", uses_compost: true },
    fertilization: { uses_fertilizers: true, soil_test_based: true },
    water_management: { irrigation_system: "Drip" },
    pest_management: { uses_ipm: true }
  }
}
```

### **🏭 Processing Assessments** - Facility Operations Analysis
```typescript
// Processing facility assessment
POST /processing/assess
{
  country: "Ghana",
  facility_profile: {
    facility_name: "Accra Rice Mill",
    facility_type: "RiceProcessing",
    processing_capacity: 75.0,
    location_type: "PeriUrban"
  },
  processing_operations: {
    energy_management: { primary_energy_source: "GridElectricity" },
    water_management: { water_treatment: "BasicFiltration" },
    waste_management: { waste_disposal_method: "Composting" }
  },
  processed_products: [
    {
      name: "White Rice",
      product_type: "RiceProcessed",
      annual_production: 18000.0,
      processing_steps: [
        { step_name: "Cleaning", energy_intensity: 15.0 },
        { step_name: "Hulling", energy_intensity: 35.0 }
      ]
    }
  ]
}
```

---

## 🔧 Quick Start

### **Prerequisites**

- [Node.js 18+](https://nodejs.org/) (for frontend)
- [Rust](https://www.rust-lang.org/) (latest stable)
- [Python 3.8+](https://www.python.org/)
- Windows PowerShell (for batch scripts)

### **1. Install Dependencies**

**Backend Setup:**
```powershell
install_deps.bat
```

**Frontend Setup:**
```powershell
cd african-lca-frontend
npm install
```

**Manual Backend Setup:**
```powershell
python -m venv african_lca_api
african_lca_api\Scripts\activate
pip install -r requirements.txt
```

### **2. Build Rust Backend**

```powershell
build_rust.bat
```

**Or manually:**
```powershell
cd african_lca_backend
cargo build --release
```

### **3. Start the Application**

**Start Backend API:**
```powershell
run_api.bat
```

**Start Frontend Development Server:**
```powershell
cd african-lca-frontend
npm run dev
```

**Manual API Start:**
```powershell
african_lca_api\Scripts\activate
cd app
python main.py
```

### **4. Access the Application**

- **Frontend UI:** http://localhost:3000
- **API Base:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## 📖 API Documentation

### **🌾 Production Assessment Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/assess` | Simple farm assessment |
| `POST` | `/assess/comprehensive` | Comprehensive farm assessment |
| `GET` | `/assess/{id}` | Retrieve assessment by ID |
| `GET` | `/assessments` | List all assessments |
| `GET` | `/food-categories` | Supported food categories |
| `GET` | `/countries` | Supported countries |
| `GET` | `/farm-types` | Farm type options |
| `GET` | `/management-options` | Management practice options |

### **🏭 Processing Assessment Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/processing/assess` | Processing facility assessment |
| `GET` | `/processing/assess/{id}` | Retrieve processing assessment |
| `GET` | `/processing/assessments` | List processing assessments |
| `GET` | `/processing/facility-types` | Supported facility types |
| `GET` | `/processing/product-types` | Supported product types |
| `GET` | `/processing/energy-sources` | Energy source options |

### **📊 Example API Calls**

#### **Simple Farm Assessment**
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
    }
  ]
}'
```

#### **Processing Facility Assessment**
```bash
curl -X POST "http://localhost:8000/processing/assess" \
-H "Content-Type: application/json" \
-d '{
  "country": "Ghana",
  "facility_profile": {
    "facility_name": "Ghana Rice Mill",
    "company_name": "Ghana Processing Ltd",
    "facility_type": "RiceProcessing",
    "processing_capacity": 50.0
  },
  "processed_products": [
    {
      "id": "rice001",
      "name": "Processed Rice",
      "product_type": "RiceProcessed",
      "annual_production": 15000.0
    }
  ]
}'
```

#### **Assessment Response Structure**
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
    "completeness_score": 0.75
  }
}
```

---

## 🌍 Supported Categories

### **🌾 Food Categories** (Production Module)
| Category | Examples | Supported Systems |
|----------|----------|-------------------|
| **Cereals** | Rice, maize, millet, sorghum | Intensive, Organic, Smallholder |
| **Legumes** | Cowpea, groundnuts, soybean | Intercropping, Monoculture |
| **Vegetables** | Tomato, okra, pepper, leafy greens | Irrigated, Rainfed |
| **Fruits** | Plantain, banana, mango, citrus | Agroforestry, Commercial |
| **Meat & Poultry** | Cattle, goat, chicken, sheep | Mixed-Livestock, Pastoral |
| **Fish** | Tilapia, catfish, tuna, sardines | Aquaculture, Wild-catch |
| **Dairy & Eggs** | Milk, cheese, eggs | Small-scale, Commercial |
| **Oils & Nuts** | Palm oil, shea nuts, coconut | Traditional, Industrial |
| **Roots & Tubers** | Yam, cassava, sweet potato | Subsistence, Commercial |

### **🏭 Facility Types** (Processing Module)
| Type | Products | Capacity Range |
|------|----------|----------------|
| **Mills** | Flour (maize, wheat, cassava) | 1-500 tonnes/day |
| **Rice Processing** | Processed rice, rice bran | 10-200 tonnes/day |
| **Palm Oil Mills** | Crude palm oil, palm kernel | 5-100 tonnes/day |
| **Cocoa Processing** | Cocoa powder, butter | 2-50 tonnes/day |
| **Fish Processing** | Dried fish, fish meal | 1-25 tonnes/day |
| **Bakeries** | Bread, baked goods | 0.5-10 tonnes/day |
| **Dairy Processing** | Pasteurized milk, cheese | 1-20 tonnes/day |

### **🌍 Supported Countries**
- **🇬🇭 Ghana:** Comprehensive country-specific data
- **🇳🇬 Nigeria:** Localized impact factors and practices
- **🌐 Global:** International averages as fallback

### **📊 Impact Categories**

#### **Midpoint Categories (8)**
- **Global Warming** (kg CO₂-eq) - Climate change potential
- **Water Consumption** (m³) - Freshwater use
- **Land Use** (m²a) - Agricultural land occupation
- **Terrestrial Acidification** (kg SO₂-eq) - Soil acidification
- **Freshwater Eutrophication** (kg P-eq) - Phosphorus pollution
- **Marine Eutrophication** (kg N-eq) - Nitrogen pollution
- **Biodiversity Loss** (species·yr) - Ecosystem impact
- **Soil Degradation** (quality points) - Soil health impact

#### **Endpoint Categories (3)**
- **Human Health** (DALY) - Disability-adjusted life years
- **Ecosystem Quality** (species·yr) - Biodiversity impact
- **Resource Scarcity** (USD) - Economic cost of resource depletion

---

## 📈 Data Sources

The platform integrates comprehensive data from trusted sources:

### **🏛️ Government & Regulatory**
- **Ghana EPA** - Environmental standards and local factors
- **Nigeria Federal Ministry of Environment** - Country-specific regulations
- **National Statistical Services** - Agricultural production data

### **🎓 Research & Academic**
- **IITA (International Institute of Tropical Agriculture)** - Crop research
- **CSIR-Ghana** - Scientific research and validation
- **Nigerian Universities** - Local agricultural studies
- **Peer-reviewed LCA Studies** - Academic literature validation

### **🌍 International Organizations**
- **FAO** - Global agricultural statistics
- **World Bank** - Economic and development data
- **IPCC** - Climate impact factors
- **Ecoinvent** - Background LCA databases

For detailed methodology, see [data_sources.md](data_sources.md) and [tech_explain.md](tech_explain.md).

---

## ⚙️ Configuration

### **Environment Variables**

```bash
# Rust Backend
RUST_LOG=info                 # Logging: debug, info, warn, error
RUST_BACKTRACE=1             # Error debugging

# Python API
API_HOST=0.0.0.0             # API host binding
API_PORT=8000                # API port
PYTHONPATH=./app             # Python path

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000  # API endpoint
NODE_ENV=development         # Environment mode
```

### **Data Configuration**
- **Impact Factors:** Editable in Rust `data.rs` modules
- **Regional Adaptations:** Country-specific adjustment factors
- **Validation Rules:** Configurable in Pydantic models

---

## 🛠️ Development

### **Full-Stack Project Structure**
```
📁 green_means_go/                 # 🏠 Project Root
├── 📁 african-lca-frontend/        # 🎨 Next.js Frontend
│   ├── 📁 src/
│   │   ├── 📁 app/                # App Router pages
│   │   ├── 📁 components/         # React components
│   │   ├── 📁 lib/               # Utilities & API client
│   │   └── 📁 types/             # TypeScript definitions
│   ├── package.json              # Frontend dependencies
│   └── tailwind.config.js        # Styling configuration
│
├── 📁 app/                        # 🐍 Python FastAPI Backend
│   ├── main.py                   # API entry point
│   ├── 📁 production/            # 🌾 Farm assessment module
│   │   ├── routes.py            # Production endpoints
│   │   ├── models.py            # Farm/crop data models
│   │   └── README.md            # Module documentation
│   ├── 📁 processing/            # 🏭 Processing assessment module
│   │   ├── routes.py            # Processing endpoints
│   │   ├── models.py            # Facility data models
│   │   └── README.md            # Module documentation
│   └── requirements.txt          # Python dependencies
│
├── 📁 african_lca_backend/         # ⚡ Rust Computation Core
│   ├── 📁 src/
│   │   ├── 📁 production/        # Farm LCA algorithms
│   │   ├── 📁 processing/        # Processing LCA algorithms
│   │   ├── lib.rs               # Core LCA library
│   │   └── main.rs              # CLI interface
│   └── Cargo.toml               # Rust dependencies
│
└── 📄 Documentation files         # 📚 Project docs
```

### **Development Workflow**

#### **🎨 Frontend Development**
```bash
cd african-lca-frontend
npm run dev          # Start development server
npm run build        # Production build
npm run lint         # Code linting
npm run type-check   # TypeScript validation
```

#### **🐍 Backend Development**
```bash
# Start API server
cd app
python main.py

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Module testing
python -m pytest tests/
```

#### **⚡ Rust Development**
```bash
cd african_lca_backend

# Development build
cargo build

# Production build  
cargo build --release

# Run tests
cargo test

# Performance benchmarks
cargo bench
```

### **🧪 Testing Strategy**

#### **Frontend Tests**
- **Unit Tests:** Jest + React Testing Library
- **E2E Tests:** Playwright automation
- **Visual Tests:** Storybook component testing

#### **Backend Tests**
- **API Tests:** FastAPI TestClient
- **Integration Tests:** Full workflow validation
- **Performance Tests:** Load testing with locust

#### **Rust Tests**
- **Unit Tests:** Built-in Rust testing
- **Benchmark Tests:** Criterion performance testing
- **Property Tests:** QuickCheck fuzzing

### **🔄 Adding New Features**

#### **New Assessment Types**
1. **Add Models:** Define Pydantic models in respective module
2. **Add Routes:** Implement endpoints in `routes.py`
3. **Add Rust Logic:** Implement calculations in Rust backend
4. **Add Frontend:** Create UI components and forms
5. **Update Documentation:** Module and API documentation

#### **New Countries**
1. **Rust:** Add to `Country` enum in `models.rs`
2. **Data:** Add impact factors in respective data modules
3. **Validation:** Update country validation rules
4. **Frontend:** Add country options to UI components

#### **New Impact Categories**
1. **Rust:** Add to impact category enums
2. **Calculations:** Implement calculation algorithms
3. **API:** Update response models
4. **Frontend:** Add visualization components

---

## 🤝 Contributing

We welcome contributions to improve the platform! Please follow these guidelines:

### **🔧 Technical Standards**
- **Frontend:** Follow React/Next.js best practices, use TypeScript strictly
- **Backend:** Adhere to FastAPI patterns, maintain Pydantic model integrity  
- **Rust:** Follow Rust coding conventions, ensure memory safety
- **Testing:** Add comprehensive tests for all new functionality

### **📚 Documentation**
- Update module READMEs for new features
- Add API documentation with examples
- Document data sources and methodology changes
- Include performance impact analysis

### **🔍 Code Review Process**
1. **Fork Repository:** Create feature branch from main
2. **Implement Changes:** Follow coding standards and add tests
3. **Update Documentation:** Ensure all docs reflect changes
4. **Submit PR:** Include detailed description and test results

### **📊 Data Quality Requirements**
- **Source Validation:** All data sources must be credible and documented
- **Regional Accuracy:** Ensure country-specific data is validated
- **Uncertainty Analysis:** Include confidence intervals and data quality metrics
- **Academic Review:** Technical changes require peer review

---

## 📄 License

**Proprietary Software - All Rights Reserved**

This software is proprietary and all rights are reserved by the author.  
Unauthorized copying, modification, or distribution is strictly prohibited.  

For commercial licensing, integration, or usage permissions, please contact the development team.

---

## 🚀 Performance & Scale

### **⚡ Performance Metrics**
- **Rust Calculations:** < 100ms for complex assessments
- **API Response Times:** < 2s for comprehensive assessments  
- **Frontend Load Time:** < 3s initial page load
- **Concurrent Users:** 100+ simultaneous assessments

### **📈 Scalability**
- **Horizontal Scaling:** Stateless API design enables load balancing
- **Database Ready:** Easy integration with PostgreSQL/MongoDB
- **Cloud Deployment:** Docker containers for AWS/Azure/GCP
- **CDN Integration:** Frontend optimized for global delivery

---

## 📞 Support & Resources

### **📖 Documentation**
- **API Documentation:** http://localhost:8000/docs (interactive)
- **Module Documentation:** See individual module README files
- **Technical Methodology:** [tech_explain.md](tech_explain.md)
- **Data Sources:** [data_sources.md](data_sources.md)

### **🛠️ Technical Support**
- **GitHub Issues:** Bug reports and feature requests
- **Academic Consultation:** Methodology and validation questions
- **Commercial Support:** Integration and deployment assistance

### **🎓 Research & Methodology**
- **Peer-reviewed Publications:** Academic literature validation
- **International Standards:** ISO 14040/14044 LCA compliance  
- **Regional Adaptation:** Local expert consultation and validation

---

*Built with ❤️ for sustainable African food systems*