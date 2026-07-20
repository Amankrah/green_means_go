from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Union, Any
from datetime import datetime
from enum import Enum

# Country is the coarse dataset bucket the LCI kernel understands (Ghana / Nigeria /
# Global). Finer geography — including new demonstration regions like Canada — is
# carried by `region` (engine/regions.py: GH / NG / CA), so onboarding a country means
# adding a region, not a new country bucket. The platform is global; "Global" is the
# region-agnostic default and the bucket Canada (region "CA") resolves through.
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
    compost_application_rate: Optional[float] = None  # tonnes/ha/year (organic N -> field N2O)
    conservation_practices: List[str] = []
    soil_testing_frequency: Optional[str] = None

class FertilizerApplication(BaseModel):
    fertilizer_type: str
    npk_ratio: Optional[str] = None  # e.g., "15-15-15"
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

# Equipment and Energy models
class FarmEquipment(BaseModel):
    equipment_type: str
    power_source: str
    age: int  # years
    hours_per_year: float
    fuel_efficiency: Optional[float] = None  # liters per hour

class EnergyUsage(BaseModel):
    energy_type: str
    monthly_consumption: float  # kWh or equivalent
    primary_use: str
    cost: Optional[float] = None
    currency: Optional[str] = None

class FuelUsage(BaseModel):
    fuel_type: str
    monthly_consumption: float  # liters
    primary_use: str
    cost: Optional[float] = None

class EquipmentEnergy(BaseModel):
    equipment: List[FarmEquipment] = []
    energy_sources: List[EnergyUsage] = []
    fuel_consumption: List[FuelUsage] = []

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

# LCIA methods exposed for researcher method toggle (must exist in the CF store).
SUPPORTED_LCIA_METHODS = (
    "ReCiPe 2016 v1.03, midpoint (H)",
    "EF v3.1",
)


class StudyMeta(BaseModel):
    """Temporal and spatial metadata for research export and cohort analysis."""

    crop_year: Optional[int] = None
    season: Optional[str] = None
    admin_region: Optional[str] = None


class AssessmentRequest(BaseModel):
    company_name: str
    country: str  # one of VALID_COUNTRIES
    foods: List[FoodItem]
    region: Optional[str] = None

    # Optional linkage/labelling for saving under a user's account.
    farm_id: Optional[str] = None  # attach this assessment to a Farm the user owns
    title: Optional[str] = None    # human label for the saved assessment

    # Enhanced fields for comprehensive assessments
    farm_profile: Optional[FarmProfile] = None
    management_practices: Optional[ManagementPractices] = None
    equipment_energy: Optional[EquipmentEnergy] = None

    # Opaque client wizard snapshot for edit/re-run UX (not used by the engine).
    form_snapshot: Optional[Dict[str, Any]] = None

    # Optional LCIA method override (region default used when omitted).
    lcia_method: Optional[str] = None

    # When true, run pedigree screening Monte Carlo and attach percentiles.
    run_uncertainty: bool = False

    # Optional study metadata (crop year / season / admin region) for research export.
    study_meta: Optional[StudyMeta] = None

    # Optional IPCC EF1 scale for N2O (literature-linked toggle; 1.0 = region default).
    ipcc_ef1_scale: Optional[float] = None
    
    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        if v not in VALID_COUNTRIES:
            raise ValueError(f"Invalid country: {v}. Must be one of {VALID_COUNTRIES}")
        return v

    @field_validator('lcia_method')
    @classmethod
    def validate_lcia_method(cls, v):
        if v is None:
            return v
        if v not in SUPPORTED_LCIA_METHODS:
            raise ValueError(
                f"Unsupported lcia_method: {v}. Must be one of {list(SUPPORTED_LCIA_METHODS)}"
            )
        return v

class ScenarioPatchBody(BaseModel):
    """Body for POST /assess/{id}/scenarios."""
    name: Optional[str] = None
    yield_scale: Optional[float] = None
    n_rate_scale: Optional[float] = None
    diesel_scale: Optional[float] = None


class RecharacterizeBody(BaseModel):
    """Body for POST /assess/{id}/recharacterize."""
    lcia_method: str
    apply_as_primary: bool = False


class ReviewStatusBody(BaseModel):
    """Body for POST /assess/{id}/review."""
    review_status: str


# Enhanced result models to match Rust backend output
class MidpointResult(BaseModel):
    value: float
    unit: str
    uncertainty_range: Optional[List[float]] = None  # [min, max]
    data_quality_score: Optional[float] = None
    contributing_sources: Optional[List[str]] = None

class EndpointResult(BaseModel):
    value: float
    unit: str
    uncertainty_range: Optional[List[float]] = None  # [min, max]
    normalization_factor: Optional[float] = None
    regional_adaptation_factor: Optional[float] = None

class SingleScoreResult(BaseModel):
    value: float
    unit: str
    band: Optional[str] = None  # qualitative band: Low | Moderate | High
    band_basis: Optional[str] = None  # what the band is relative to (benchmark basket)
    uncertainty_range: Optional[List[float]] = None  # [min, max]
    weighting_factors: Optional[Dict[str, float]] = None
    contributions: Optional[Dict[str, float]] = None  # each category's share of the single score
    methodology: Optional[str] = None

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

    # Echoed from the request so results/reports show the farmer's own names
    farm_profile: Optional[FarmProfile] = None
    
    # Enhanced analysis results
    sensitivity_analysis: Optional[Dict[str, Any]] = None
    comparative_analysis: Optional[Dict[str, Any]] = None
    management_analysis: Optional[ManagementAnalysis] = None
    benchmarking: Optional[BenchmarkingResults] = None
    recommendations: Optional[List[Recommendation]] = None

    # Purchased-input match report (name -> matched background process, location, score);
    # kept for transparency so users can audit which datasets were used.
    input_matches: Optional[List[Dict[str, Any]]] = None

    # Auditable LCI: dominant merged elementary flows (per kg), and the per-source
    # contribution breakdown (which input/stage drove each impact category, per kg).
    inventory: Optional[Dict[str, Any]] = None
    contribution_by_source: Optional[Dict[str, Any]] = None

    # Deterministic, data-backed ISO 14040/14044 report structure (four phases + review)
    iso_report: Optional[Dict[str, Any]] = None

    # Researcher dual FU / method / uncertainty / scenario metadata (engine-optional).
    functional_units: Optional[Dict[str, Any]] = None
    lcia_method: Optional[str] = None
    engine_inventory: Optional[Dict[str, Any]] = None
    method_variants: Optional[Dict[str, Any]] = None
    uncertainty: Optional[Dict[str, Any]] = None
    baseline_assessment_id: Optional[str] = None
    study_meta: Optional[StudyMeta] = None
    review_status: Optional[str] = None
    regional_benchmark: Optional[Dict[str, Any]] = None
    contribution_sankey: Optional[Dict[str, Any]] = None