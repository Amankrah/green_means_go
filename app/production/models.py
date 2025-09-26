from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Union, Any
from datetime import datetime
from enum import Enum

# Valid values
VALID_COUNTRIES = ["Ghana", "Nigeria", "Global"]
VALID_FOOD_CATEGORIES = [
    "Cereals", "Legumes", "Vegetables", "Fruits", "Meat", "Poultry", 
    "Fish", "Dairy", "Eggs", "Oils", "Nuts", "Roots", "Other"
]

# Enhanced enums to match Rust backend
class ProductionSystem(str, Enum):
    INTENSIVE = "Intensive"
    EXTENSIVE = "Extensive"
    SMALLHOLDER = "Smallholder"
    AGROFORESTRY = "Agroforestry"
    IRRIGATED = "Irrigated"
    RAINFED = "Rainfed"
    ORGANIC = "Organic"
    CONVENTIONAL = "Conventional"

class FarmType(str, Enum):
    SMALLHOLDER = "Smallholder"
    SMALL_SCALE = "SmallScale"
    MEDIUM_SCALE = "MediumScale"
    COMMERCIAL = "Commercial"
    COOPERATIVE = "Cooperative"
    MIXED_LIVESTOCK = "MixedLivestock"

class FarmingSystem(str, Enum):
    SUBSISTENCE = "Subsistence"
    SEMI_COMMERCIAL = "SemiCommercial"
    COMMERCIAL = "Commercial"
    ORGANIC = "Organic"
    AGROECOLOGICAL = "Agroecological"
    CONVENTIONAL = "Conventional"
    INTEGRATED_FARMING = "IntegratedFarming"

class SoilType(str, Enum):
    SANDY = "Sandy"
    CLAY = "Clay"
    LOAM = "Loam"
    SANDY_LOAM = "SandyLoam"
    CLAY_LOAM = "ClayLoam"
    SILT_LOAM = "SiltLoam"
    LATERITIC = "Lateritic"
    VOLCANIC = "Volcanic"

class CroppingPattern(str, Enum):
    MONOCULTURE = "Monoculture"
    INTERCROPPING = "Intercropping"
    RELAY_CROPPING = "RelayCropping"
    AGROFORESTRY = "Agroforestry"
    CROP_ROTATION = "CropRotation"

class SeasonalFactor(str, Enum):
    WET_SEASON = "WetSeason"
    DRY_SEASON = "DrySeason"
    YEAR_ROUND = "YearRound"

# Enhanced models for comprehensive assessments
class FarmProfile(BaseModel):
    farmer_name: str
    farm_name: str
    total_farm_size: float  # hectares
    farming_experience: int  # years
    farm_type: FarmType
    primary_farming_system: FarmingSystem
    certifications: List[str] = []
    participates_in_programs: List[str] = []

class SoilManagement(BaseModel):
    soil_type: Optional[SoilType] = None
    uses_compost: bool = False
    compost_source: Optional[str] = None
    conservation_practices: List[str] = []
    soil_testing_frequency: Optional[str] = None

class FertilizerApplication(BaseModel):
    fertilizer_type: str
    application_rate: float  # kg/hectare/season
    applications_per_season: int
    cost: Optional[float] = None

class FertilizationPractices(BaseModel):
    uses_fertilizers: bool = False
    fertilizer_applications: List[FertilizerApplication] = []
    soil_test_based: bool = False
    follows_nutrient_plan: bool = False

class WaterManagement(BaseModel):
    water_source: List[str] = []
    irrigation_system: Optional[str] = None
    water_conservation_practices: List[str] = []

class PesticideApplication(BaseModel):
    pesticide_type: str
    active_ingredient: str
    application_rate: float
    applications_per_season: int
    target_pests: List[str] = []

class PestManagement(BaseModel):
    management_approach: str = "IntegratedIPM"
    uses_ipm: bool = False
    pesticides: List[PesticideApplication] = []
    pest_monitoring_frequency: Optional[str] = None

class ManagementPractices(BaseModel):
    soil_management: SoilManagement
    fertilization: FertilizationPractices
    water_management: WaterManagement
    pest_management: PestManagement

class FoodItem(BaseModel):
    id: str
    name: str
    quantity_kg: float
    category: str
    crop_type: Optional[str] = None
    origin_country: Optional[str] = None
    production_system: Optional[ProductionSystem] = None
    seasonal_factor: Optional[SeasonalFactor] = None
    
    # Enhanced fields for comprehensive assessments
    variety: Optional[str] = None
    area_allocated: Optional[float] = None  # hectares
    cropping_pattern: Optional[CroppingPattern] = None
    intercropping_partners: Optional[List[str]] = None
    post_harvest_losses: Optional[float] = None  # percentage
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v not in VALID_FOOD_CATEGORIES:
            raise ValueError(f"Invalid food category: {v}. Must be one of {VALID_FOOD_CATEGORIES}")
        return v
    
    @field_validator('quantity_kg')
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

class AssessmentRequest(BaseModel):
    company_name: str
    country: str  # "Ghana", "Nigeria", or "Global"
    foods: List[FoodItem]
    region: Optional[str] = None
    
    # Enhanced fields for comprehensive assessments
    farm_profile: Optional[FarmProfile] = None
    management_practices: Optional[ManagementPractices] = None
    
    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        if v not in VALID_COUNTRIES:
            raise ValueError(f"Invalid country: {v}. Must be one of {VALID_COUNTRIES}")
        return v

# Enhanced result models to match Rust backend output
class MidpointResult(BaseModel):
    value: float
    unit: str
    uncertainty_range: List[float]  # [min, max]
    data_quality_score: float
    contributing_sources: List[str]

class EndpointResult(BaseModel):
    value: float
    unit: str
    uncertainty_range: List[float]  # [min, max]
    normalization_factor: Optional[float] = None
    regional_adaptation_factor: Optional[float] = None

class SingleScoreResult(BaseModel):
    value: float
    unit: str
    uncertainty_range: List[float]  # [min, max]
    weighting_factors: Dict[str, float]
    methodology: str

class DataQuality(BaseModel):
    overall_confidence: str
    data_source_mix: List[Dict[str, Any]] = []
    regional_adaptation: bool
    completeness_score: float
    temporal_representativeness: float = 0.0
    geographical_representativeness: float = 0.0
    technological_representativeness: float = 0.0
    warnings: List[str] = []
    recommendations: List[str] = []

class ManagementAnalysis(BaseModel):
    soil_health_score: float = 0.0  # 0-100
    fertilizer_efficiency: float = 0.0
    water_use_efficiency: float = 0.0
    pest_management_score: float = 0.0
    sustainability_indicators: Dict[str, float] = {}

class BenchmarkingResults(BaseModel):
    farm_type_comparison: Dict[str, float] = {}
    regional_comparison: Dict[str, float] = {}
    performance_percentile: float = 0.0  # 0-100
    best_practices_identified: List[str] = []

class Recommendation(BaseModel):
    category: str
    title: str
    description: str
    potential_impact_reduction: Dict[str, float] = {}
    implementation_difficulty: str
    cost_category: str
    priority: str

class AssessmentResponse(BaseModel):
    id: str
    company_name: str
    country: str
    assessment_date: datetime
    midpoint_impacts: Dict[str, Union[float, MidpointResult]]
    endpoint_impacts: Dict[str, Union[float, EndpointResult]]
    single_score: Union[float, SingleScoreResult]
    data_quality: Union[Dict, DataQuality]
    breakdown_by_food: Dict[str, Dict[str, Union[float, MidpointResult]]]
    
    # Enhanced analysis results
    sensitivity_analysis: Optional[Dict[str, Any]] = None
    comparative_analysis: Optional[Dict[str, Any]] = None
    management_analysis: Optional[ManagementAnalysis] = None
    benchmarking: Optional[BenchmarkingResults] = None
    recommendations: Optional[List[Recommendation]] = None