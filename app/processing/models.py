from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Union, Any
from datetime import datetime
from enum import Enum

# Processing-specific enums to match Rust backend
class ProcessingFacilityType(str, Enum):
    MILL = "Mill"
    BAKERY = "Bakery"
    CASSIVA_PROCESSING = "CassivaProcessing"
    RICE_PROCESSING = "RiceProcessing"
    PALM_OIL_MILL = "PalmOilMill"
    COCOA_PROCESSING = "CocoaProcessing"
    FISH_PROCESSING = "FishProcessing"
    MEAT_PROCESSING = "MeatProcessing"
    DAIRY_PROCESSING = "DairyProcessing"
    FRUIT_PROCESSING = "FruitProcessing"
    VEGETABLE_PROCESSING = "VegetableProcessing"
    GENERAL = "General"

class LocationType(str, Enum):
    URBAN = "Urban"
    PERI_URBAN = "PeriUrban"
    RURAL = "Rural"
    INDUSTRIAL = "Industrial"

class ProductType(str, Enum):
    FLOUR_MAIZE = "FlourMaize"
    FLOUR_WHEAT = "FlourWheat"
    FLOUR_CASSAVA = "FlourCassava"
    FLOUR_PLANTAIN = "FlourPlantain"
    RICE_PROCESSED = "RiceProcessed"
    PALM_OIL = "PalmOil"
    COCOA_POWDER = "CocoaPowder"
    COCOA_BUTTER = "CocoaButter"
    BAKED_GOODS = "BakedGoods"
    PROCESSED_FISH = "ProcessedFish"
    PROCESSED_MEAT = "ProcessedMeat"
    DAIRY = "Dairy"
    FRUIT_JUICE = "FruitJuice"
    DRIED_FRUITS = "DriedFruits"
    OTHER = "Other"

class EnergySource(str, Enum):
    GRID_ELECTRICITY = "GridElectricity"
    DIESEL_GENERATOR = "DieselGenerator"
    SOLAR_POWER = "SolarPower"
    BIOMASS = "Biomass"
    LPG = "LPG"
    NATURAL_GAS = "NaturalGas"
    HYDRO_ELECTRICITY = "HydroElectricity"
    WIND_POWER = "WindPower"
    MIXED = "Mixed"

class WaterTreatment(str, Enum):
    NONE = "None"
    BASIC_FILTRATION = "BasicFiltration"
    CHEMICAL_TREATMENT = "ChemicalTreatment"
    REVERSE_OSMOSIS = "ReverseOsmosis"
    COMPREHENSIVE = "Comprehensive"

class WastewaterTreatment(str, Enum):
    NONE = "None"
    BASIC_SEDIMENTATION = "BasicSedimentation"
    BIOLOGICAL_TREATMENT = "BiologicalTreatment"
    CHEMICAL_TREATMENT = "ChemicalTreatment"
    ADVANCED = "Advanced"

class WasteDisposalMethod(str, Enum):
    LANDFILL = "Landfill"
    INCINERATION = "Incineration"
    COMPOSTING = "Composting"
    ANAEROBIC_DIGESTION = "AnaerobicDigestion"
    RECYCLING = "Recycling"
    MIXED = "Mixed"

class EquipmentAge(str, Enum):
    NEW = "New"  # < 2 years
    RECENT = "Recent"  # 2-5 years
    MATURE = "Mature"  # 5-10 years
    OLD = "Old"  # 10-20 years
    VERY_OLD = "VeryOld"  # > 20 years

class MaintenanceFrequency(str, Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    BIANNUAL = "Biannual"
    ANNUAL = "Annual"
    IRREGULAR = "Irregular"

class AutomationLevel(str, Enum):
    MANUAL = "Manual"
    SEMI_AUTOMATED = "SemiAutomated"
    HIGHLY_AUTOMATED = "HighlyAutomated"
    FULLY_AUTOMATED = "FullyAutomated"

class TransportMode(str, Enum):
    TRUCK = "Truck"
    RAIL = "Rail"
    SHIP = "Ship"
    MIXED = "Mixed"

class PackagingMaterial(str, Enum):
    PLASTIC_BAG = "PlasticBag"
    PAPER_BAG = "PaperBag"
    JUTE = "Jute"
    POLYPROPYLENE = "Polypropylene"
    CARDBOARD = "Cardboard"
    METAL = "Metal"
    GLASS = "Glass"
    COMPOSITE = "Composite"

class QualityGrade(str, Enum):
    PREMIUM = "Premium"
    STANDARD = "Standard"
    BASIC = "Basic"
    INDUSTRIAL = "Industrial"

class MarketDestination(str, Enum):
    LOCAL = "Local"
    REGIONAL = "Regional"
    NATIONAL = "National"
    EXPORT = "Export"
    MIXED = "Mixed"

# Processing facility profile
class ProcessingFacilityProfile(BaseModel):
    facility_name: str
    company_name: str
    facility_type: ProcessingFacilityType
    processing_capacity: float  # tonnes per day
    operational_hours_per_day: float = 8.0
    operational_days_per_year: int = 250
    established_year: Optional[int] = None
    certifications: List[str] = []
    employee_count: Optional[int] = None
    facility_size: Optional[float] = None  # m2
    location_type: LocationType = LocationType.RURAL

    @field_validator('processing_capacity')
    @classmethod
    def validate_capacity(cls, v):
        if v <= 0:
            raise ValueError("Processing capacity must be positive")
        return v

# Energy management
class EnergyManagement(BaseModel):
    primary_energy_source: EnergySource = EnergySource.GRID_ELECTRICITY
    secondary_energy_sources: List[EnergySource] = []
    monthly_electricity_consumption: Optional[float] = None  # kWh
    monthly_fuel_consumption: Optional[float] = None  # liters
    fuel_type: Optional[str] = None
    renewable_energy_percentage: float = 0.0
    energy_efficiency_measures: List[str] = []
    backup_generator: bool = False

# Water management for processing
class ProcessingWaterManagement(BaseModel):
    water_source: List[str] = []
    monthly_water_consumption: Optional[float] = None  # m3
    water_treatment: WaterTreatment = WaterTreatment.BASIC_FILTRATION
    water_conservation_measures: List[str] = []
    wastewater_treatment: WastewaterTreatment = WastewaterTreatment.BASIC_SEDIMENTATION

# Byproduct utilization
class ByproductUtilization(BaseModel):
    byproduct_name: str
    utilization_method: str
    percentage_utilized: float = 0.0

# Waste management
class ProcessingWasteManagement(BaseModel):
    solid_waste_generation: Optional[float] = None  # kg/day
    organic_waste_percentage: float = 70.0
    waste_disposal_method: WasteDisposalMethod = WasteDisposalMethod.LANDFILL
    recycling_programs: List[str] = []
    byproduct_utilization: List[ByproductUtilization] = []

# Storage practices
class StoragePractices(BaseModel):
    storage_type: str = "Warehouse"
    climate_control: bool = False
    pest_control_methods: List[str] = []
    storage_loss_percentage: float = 5.0

# Raw material sourcing
class RawMaterialSourcing(BaseModel):
    local_sourcing_percentage: float = 80.0
    average_transport_distance: float = 50.0  # km
    transport_mode: TransportMode = TransportMode.TRUCK
    supplier_sustainability_practices: List[str] = []
    seasonal_variation: bool = True
    storage_practices: StoragePractices = StoragePractices()

# Equipment efficiency
class EquipmentEfficiency(BaseModel):
    equipment_age: EquipmentAge = EquipmentAge.MATURE
    maintenance_frequency: MaintenanceFrequency = MaintenanceFrequency.MONTHLY
    automation_level: AutomationLevel = AutomationLevel.SEMI_AUTOMATED
    equipment_utilization_rate: float = 75.0  # percentage
    modernization_investments: List[str] = []

# Processing operations
class ProcessingOperations(BaseModel):
    energy_management: EnergyManagement = EnergyManagement()
    water_management: ProcessingWaterManagement = ProcessingWaterManagement()
    waste_management: ProcessingWasteManagement = ProcessingWasteManagement()
    raw_material_sourcing: RawMaterialSourcing = RawMaterialSourcing()
    equipment_efficiency: EquipmentEfficiency = EquipmentEfficiency()

# Raw material input
class RawMaterialInput(BaseModel):
    material_name: str
    quantity_per_tonne_output: float  # kg
    source_location: Optional[str] = None
    quality_requirements: List[str] = []
    seasonal_availability: bool = True

# Processing step
class ProcessingStep(BaseModel):
    step_name: str
    energy_intensity: float  # kWh per tonne
    water_usage: float  # liters per tonne
    duration: float = 1.0  # hours
    yield_efficiency: float = 95.0  # percentage
    emissions_factor: Optional[float] = None  # kg CO2-eq per tonne

    @field_validator('energy_intensity', 'water_usage')
    @classmethod
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Energy intensity and water usage must be non-negative")
        return v

# Packaging info
class PackagingInfo(BaseModel):
    packaging_material: PackagingMaterial = PackagingMaterial.PLASTIC_BAG
    package_size: float = 50.0  # kg
    packaging_weight_per_unit: float = 0.1  # kg
    recyclable: bool = False

# Processed product
class ProcessedProduct(BaseModel):
    id: str
    name: str
    product_type: ProductType
    annual_production: float  # tonnes
    raw_material_inputs: List[RawMaterialInput] = []
    processing_steps: List[ProcessingStep] = []
    packaging: PackagingInfo = PackagingInfo()
    quality_grade: QualityGrade = QualityGrade.STANDARD
    market_destination: MarketDestination = MarketDestination.LOCAL

    @field_validator('annual_production')
    @classmethod
    def validate_production(cls, v):
        if v <= 0:
            raise ValueError("Annual production must be positive")
        return v

# Processing assessment request
class ProcessingAssessmentRequest(BaseModel):
    country: str  # "Ghana", "Nigeria", or "Global"
    region: Optional[str] = None
    facility_profile: ProcessingFacilityProfile
    processing_operations: ProcessingOperations = ProcessingOperations()
    processed_products: List[ProcessedProduct]

    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        valid_countries = ["Ghana", "Nigeria", "Global"]
        if v not in valid_countries:
            raise ValueError(f"Invalid country: {v}. Must be one of {valid_countries}")
        return v

    @field_validator('processed_products')
    @classmethod
    def validate_products(cls, v):
        if not v:
            raise ValueError("At least one processed product must be specified")
        return v

# Processing assessment response (reusing assessment response structure from main models)
class ProcessingAssessmentResponse(BaseModel):
    id: str
    facility_profile: ProcessingFacilityProfile
    country: str
    assessment_date: datetime
    midpoint_impacts: Dict[str, Union[float, Dict[str, Any]]]
    endpoint_impacts: Dict[str, Union[float, Dict[str, Any]]]
    single_score: Union[float, Dict[str, Any]]
    data_quality: Dict[str, Any]
    breakdown_by_product: Dict[str, Dict[str, Union[float, Dict[str, Any]]]]
    recommendations: Optional[List[Dict[str, Any]]] = None
