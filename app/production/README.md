# Production Assessment Module

> **Farm-Level Environmental Sustainability Assessments**  
> Comprehensive LCA analysis for agricultural production systems in Africa

## Overview

The Production module provides specialized environmental sustainability assessments for farm-level operations, supporting both simple and comprehensive evaluations of agricultural systems across Ghana, Nigeria, and global contexts.

---

## Features

### 🌾 **Farm Assessment Types**
- **Simple Assessment:** Basic environmental impact analysis
- **Comprehensive Assessment:** Detailed farm management and sustainability analysis

### 📊 **Assessment Capabilities**
- **Multi-crop Analysis:** Support for 13+ food categories
- **Management Practices:** Soil, water, fertilizer, and pest management
- **Production Systems:** Intensive, extensive, smallholder, organic, etc.
- **Farm Profiling:** Complete farmer and farm characterization

### 🎯 **Impact Categories**
- **8 Midpoint Categories:** GWP, water consumption, land use, acidification, eutrophication, biodiversity loss, soil degradation
- **3 Endpoint Categories:** Human health, ecosystem quality, resource scarcity
- **Single Score:** Weighted sustainability indicator

---

## Tech Stack

### **Backend Architecture**
```
┌─────────────────┐    JSON    ┌──────────────────┐
│   FastAPI       │ ────────── │   Rust Engine    │
│   Production    │            │   LCA Core       │
│   Routes        │ ────────── │   Calculations   │
└─────────────────┘            └──────────────────┘
```

- **FastAPI Router:** Modular endpoint management
- **Pydantic Models:** Type-safe data validation
- **Rust Integration:** High-performance LCA calculations
- **Async Processing:** Non-blocking assessment workflows

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/assess` | Create simple/comprehensive assessment |
| `POST` | `/assess/comprehensive` | Create comprehensive assessment (required farm profile) |
| `GET` | `/assess/{id}` | Retrieve assessment by ID |
| `GET` | `/assessments` | List all assessments |
| `GET` | `/food-categories` | Get supported food categories |
| `GET` | `/countries` | Get supported countries |
| `GET` | `/impact-categories` | Get impact category definitions |
| `GET` | `/farm-types` | Get farm type options |
| `GET` | `/management-options` | Get management practice options |

---

## Data Models

### **Core Models**

#### `AssessmentRequest`
```python
class AssessmentRequest(BaseModel):
    company_name: str
    country: str  # "Ghana", "Nigeria", "Global"
    foods: List[FoodItem]
    region: Optional[str] = None
    
    # Comprehensive assessment fields
    farm_profile: Optional[FarmProfile] = None
    management_practices: Optional[ManagementPractices] = None
```

#### `FarmProfile`
```python
class FarmProfile(BaseModel):
    farmer_name: str
    farm_name: str
    total_farm_size: float  # hectares
    farming_experience: int  # years
    farm_type: FarmType
    primary_farming_system: FarmingSystem
    certifications: List[str] = []
    participates_in_programs: List[str] = []
```

#### `ManagementPractices`
```python
class ManagementPractices(BaseModel):
    soil_management: SoilManagement
    fertilization: FertilizationPractices
    water_management: WaterManagement
    pest_management: PestManagement
```

### **Enums & Categories**

- **Farm Types:** Smallholder, SmallScale, MediumScale, Commercial, Cooperative, MixedLivestock
- **Farming Systems:** Subsistence, SemiCommercial, Commercial, Organic, Agroecological, Conventional, IntegratedFarming
- **Production Systems:** Intensive, Extensive, Smallholder, Agroforestry, Irrigated, Rainfed, Organic, Conventional
- **Soil Types:** Sandy, Clay, Loam, SandyLoam, ClayLoam, SiltLoam, Lateritic, Volcanic
- **Cropping Patterns:** Monoculture, Intercropping, RelayCropping, Agroforestry, CropRotation

---

## Assessment Response

### **Simple Assessment Output**
```json
{
  "id": "uuid-string",
  "company_name": "Ghana Farms Co.",
  "country": "Ghana",
  "assessment_date": "2024-01-15T10:30:00Z",
  "midpoint_impacts": {
    "Global warming": 3250.0,
    "Water consumption": 2800.0,
    "Land use": 4200.0
  },
  "endpoint_impacts": {
    "Human Health": 0.000683,
    "Ecosystem Quality": 3.9e-11,
    "Resource Scarcity": 178.75
  },
  "single_score": 68.25,
  "data_quality": {
    "confidence_level": "Medium",
    "completeness_score": 0.75
  },
  "breakdown_by_food": { /* per-crop impacts */ }
}
```

### **Comprehensive Assessment Output**
Includes additional analysis:
- `management_analysis`: Soil health, fertilizer efficiency, water use efficiency scores
- `benchmarking`: Performance comparison with similar farms
- `recommendations`: Actionable sustainability improvements
- `sensitivity_analysis`: Impact factor uncertainty analysis
- `comparative_analysis`: Alternative scenario comparisons

---

## Usage Examples

### **Simple Assessment**
```bash
curl -X POST "http://localhost:8000/assess" \
-H "Content-Type: application/json" \
-d '{
  "company_name": "Ghana Farms Co.",
  "country": "Ghana",
  "foods": [
    {
      "id": "maize001",
      "name": "Maize",
      "quantity_kg": 1000,
      "category": "Cereals"
    }
  ]
}'
```

### **Comprehensive Assessment**
```bash
curl -X POST "http://localhost:8000/assess/comprehensive" \
-H "Content-Type: application/json" \
-d '{
  "company_name": "Advanced Farm Ltd.",
  "country": "Ghana",
  "foods": [...],
  "farm_profile": {
    "farmer_name": "Kwame Asante",
    "farm_name": "Asante Organic Farm",
    "total_farm_size": 25.5,
    "farming_experience": 12,
    "farm_type": "SmallScale",
    "primary_farming_system": "Organic"
  },
  "management_practices": {
    "soil_management": {
      "soil_type": "Loam",
      "uses_compost": true,
      "conservation_practices": ["CoverCropping", "Terracing"]
    },
    "fertilization": {
      "uses_fertilizers": true,
      "soil_test_based": true
    },
    "water_management": {
      "water_source": ["Borehole", "Rainwater"],
      "irrigation_system": "Drip"
    },
    "pest_management": {
      "management_approach": "IntegratedIPM",
      "uses_ipm": true
    }
  }
}'
```

---

## Integration

### **With Frontend**
```typescript
// TypeScript client integration
import { AssessmentRequest, AssessmentResponse } from '../types/production'

const createAssessment = async (data: AssessmentRequest): Promise<AssessmentResponse> => {
  const response = await fetch('/assess', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  return response.json()
}
```

### **With Other Modules**
```python
# Cross-module integration
from production.models import AssessmentRequest
from processing.models import ProcessingAssessmentRequest

# Farm-to-fork analysis combining production and processing
```

---

## Data Quality

### **Confidence Levels**
- **High:** Country-specific, validated data sources
- **Medium:** Regional averages with local adaptations  
- **Low:** Global averages with high uncertainty

### **Source Mix**
- Government agricultural statistics
- Research institution studies
- Farmer survey data
- International databases (FAO, World Bank)

### **Regional Adaptation**
- Climate factor adjustments
- Soil type considerations
- Agricultural practice variations
- Economic context integration

---

## Performance

- **Response Time:** < 2 seconds for simple assessments
- **Throughput:** 100+ concurrent assessments
- **Data Processing:** Rust-powered calculations
- **Memory Efficient:** Stateless request processing

---

## Validation

### **Input Validation**
- Pydantic schema enforcement
- Business rule validation
- Data range checking
- Cross-field consistency

### **Output Validation**
- Impact category completeness
- Uncertainty range validation
- Data quality scoring
- Result consistency checks

---

## Future Enhancements

- [ ] Machine learning impact factor optimization
- [ ] Real-time satellite data integration
- [ ] Blockchain-based certification tracking
- [ ] Mobile app synchronization
- [ ] Multi-language support
- [ ] Advanced benchmark analytics

---

*For technical support or methodology questions, refer to the main project documentation.*
