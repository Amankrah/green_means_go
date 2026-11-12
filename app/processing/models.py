from pydantic import BaseModel, field_validator
from typing import ClassVar, List, Optional, Dict, Union, Any

# Same strict request base as the farm side: unknown keys are a 422, removed keys listed in
# `_legacy` are discarded so archived requests still re-run.
try:
    from production.models import StrictModel  # app/ on sys.path (uvicorn, tests)
except ImportError:  # imported as a package (app.processing.models)
    from app.production.models import StrictModel
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

class AllocationBasis(str, Enum):
    # How the facility's total impact is split between co-products (ISO 14044 requires this
    # be stated). MASS needs no extra data (uses annual_production); ECONOMIC needs a per-kg
    # value per product and, when values are missing, falls back to mass with a note.
    MASS = "mass"
    ECONOMIC = "economic"

# Processing facility profile
class ProcessingFacilityProfile(StrictModel):
    facility_name: str
    company_name: str
    # facility_type: selects the default raw material / conversion ratio when a product has
    # no raw-material input (engine/conversion_ratios.py).
    facility_type: ProcessingFacilityType
    # processing_capacity / operational_hours_per_day / location_type: report-only metadata
    # (echoed in the ISO report goal & scope; capacity also drives the utilisation check in
    # the data-quality section). They do not change the numbers.
    processing_capacity: float  # tonnes per day
    operational_hours_per_day: float = 8.0
    operational_days_per_year: int = 250   # live: scales solid waste kg/day to a year
    established_year: Optional[int] = None
    certifications: List[str] = []
    employee_count: Optional[int] = None
    facility_size: Optional[float] = None  # m2
    location_type: LocationType = LocationType.RURAL
    # Free-text province/state from the wizard (not an engine region code).
    admin_region: Optional[str] = None

    @field_validator('processing_capacity')
    @classmethod
    def validate_capacity(cls, v):
        if v <= 0:
            raise ValueError("Processing capacity must be positive")
        return v

# Energy management
class FuelStream(StrictModel):
    """One fuel burned on site. A facility may have several (boiler wood + generator diesel)."""
    # Diesel | Diesel generator | Petrol | Kerosene | LPG | Natural gas | Biodiesel |
    # Firewood | Charcoal | Palm kernel shell | Palm fibre | Biogas
    fuel_type: str
    monthly_consumption: float
    unit: Optional[str] = None         # L | kg | m3 | MJ; blank -> carrier's natural unit
    use: Optional[str] = None          # report-only label (e.g. "boiler", "backup generator")


class EnergyManagement(StrictModel):
    # Removed: secondary_energy_sources (no amounts; use fuel_streams), backup_generator
    # (enter the generator's diesel as a fuel stream), energy_efficiency_measures (free text).
    _legacy: ClassVar[frozenset] = frozenset({
        "secondary_energy_sources", "backup_generator", "energy_efficiency_measures"})
    # Selects the electricity dataset: grid market, PV, hydro, wind, or a diesel genset
    # (kWh -> diesel via specific fuel consumption). Mixed/Biomass/LPG/NaturalGas -> grid.
    primary_energy_source: EnergySource = EnergySource.GRID_ELECTRICITY
    monthly_electricity_consumption: Optional[float] = None  # kWh
    # Legacy single fuel stream; merged into fuel_streams by the engine.
    monthly_fuel_consumption: Optional[float] = None  # liters
    fuel_type: Optional[str] = None
    fuel_streams: List[FuelStream] = []
    # Share of electricity from on-site solar PV (modelled with the ecoinvent PV dataset).
    renewable_energy_percentage: float = 0.0

# Water management for processing
class ProcessingWaterManagement(StrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"water_conservation_measures"})
    # water_source: Municipal -> tap-water dataset; Borehole/Well/River/... -> withdrawal
    # elementary flow (groundwater / surface water) characterised by the water-use method.
    water_source: List[str] = []
    monthly_water_consumption: Optional[float] = None  # m3
    # On-site treatment of the intake: Chemical -> decarbonised water dataset, Reverse
    # osmosis / Comprehensive -> deionised water dataset, None / Basic -> as sourced.
    water_treatment: WaterTreatment = WaterTreatment.BASIC_FILTRATION
    # None -> no treatment dataset and an explicit data-gap warning (untreated effluent);
    # any treatment -> average wastewater treatment dataset.
    wastewater_treatment: WastewaterTreatment = WastewaterTreatment.BASIC_SEDIMENTATION

# Byproduct utilization
class ByproductUtilization(StrictModel):
    # The utilised share of the solid-waste stream leaves the system burden-free (cut-off:
    # it is a valorised by-product, not waste) instead of going to waste treatment.
    byproduct_name: str
    utilization_method: str
    percentage_utilized: float = 0.0

# Waste management
class ProcessingWasteManagement(StrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"recycling_programs"})
    solid_waste_generation: Optional[float] = None  # kg/day
    # Splits the waste: the organic share goes to the disposal method's biowaste dataset,
    # the rest to the inert / mixed-waste dataset (engine/process_inputs.py).
    organic_waste_percentage: float = 70.0
    waste_disposal_method: WasteDisposalMethod = WasteDisposalMethod.LANDFILL
    byproduct_utilization: List[ByproductUtilization] = []

# Storage practices
class StoragePractices(StrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"storage_type", "climate_control", "pest_control_methods"})
    # Raw-material loss in storage: applied to DEFAULT conversion ratios only (a measured
    # kg-per-tonne-output figure already includes the facility's own losses).
    storage_loss_percentage: float = 5.0

# Raw material sourcing
class RawMaterialSourcing(StrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"supplier_sustainability_practices", "seasonal_variation"})
    # Used only when average_transport_distance is blank: the default distance is a
    # local/non-local weighted mean (engine/process_inputs.py, cited).
    local_sourcing_percentage: float = 80.0
    average_transport_distance: Optional[float] = None  # km; blank -> default from local share
    transport_mode: TransportMode = TransportMode.TRUCK
    storage_practices: StoragePractices = StoragePractices()

# Refrigerant / F-gas use (cold storage, chilling). Leakage is a direct on-site climate
# emission (leaked mass x GWP100), separate from purchased energy.
class RefrigerantManagement(StrictModel):
    refrigerant_type: Optional[str] = None       # e.g. R-134a, R-404A, Ammonia
    annual_leakage_kg: Optional[float] = None     # kg of refrigerant lost per year

# Processing operations
class ProcessingOperations(StrictModel):
    energy_management: EnergyManagement = EnergyManagement()
    water_management: ProcessingWaterManagement = ProcessingWaterManagement()
    waste_management: ProcessingWasteManagement = ProcessingWasteManagement()
    raw_material_sourcing: RawMaterialSourcing = RawMaterialSourcing()
    refrigerant_management: RefrigerantManagement = RefrigerantManagement()
    # equipment_efficiency (age, maintenance, automation, utilisation) carried no flow; the
    # metered energy already reflects it. Removed; archived requests are still accepted.
    _legacy: ClassVar[frozenset] = frozenset({"equipment_efficiency"})

# Raw material input
class RawMaterialInput(StrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"quality_requirements", "seasonal_availability"})
    material_name: str
    quantity_per_tonne_output: float  # kg
    source_location: Optional[str] = None   # report-only metadata (ISO report)

# Processing step
class ProcessingStep(StrictModel):
    # duration / yield_efficiency / emissions_factor removed: duration has no power to
    # multiply, the mass balance comes from raw-material inputs or default conversion ratios,
    # and a single CO2-eq number cannot be characterised across categories (and would double
    # count the metered fuel).
    _legacy: ClassVar[frozenset] = frozenset({"duration", "yield_efficiency", "emissions_factor"})
    step_name: str
    energy_intensity: float  # kWh per tonne (used when there is no facility meter)
    water_usage: float  # liters per tonne (used when there is no facility meter)

    @field_validator('energy_intensity', 'water_usage')
    @classmethod
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Energy intensity and water usage must be non-negative")
        return v

# Packaging info
class PackagingInfo(StrictModel):
    packaging_material: PackagingMaterial = PackagingMaterial.PLASTIC_BAG
    package_size: float = 50.0  # kg
    packaging_weight_per_unit: float = 0.1  # kg
    # Report-only metadata: end-of-life of the packaging is outside a cradle-to-gate boundary.
    recyclable: bool = False

# Processed product
class ProcessedProduct(StrictModel):
    id: str
    name: str
    product_type: ProductType
    annual_production: float  # tonnes
    raw_material_inputs: List[RawMaterialInput] = []
    processing_steps: List[ProcessingStep] = []
    packaging: PackagingInfo = PackagingInfo()
    # quality_grade / market_destination: report-only metadata (ISO report goal & scope).
    quality_grade: QualityGrade = QualityGrade.STANDARD
    market_destination: MarketDestination = MarketDestination.LOCAL
    economic_value: Optional[float] = None  # price per kg, used only for economic allocation

    @field_validator('annual_production')
    @classmethod
    def validate_production(cls, v):
        if v <= 0:
            raise ValueError("Annual production must be positive")
        return v

# Processing assessment request
class ProcessingAssessmentRequest(StrictModel):
    country: str  # one of the supported countries below
    region: Optional[str] = None
    facility_profile: ProcessingFacilityProfile
    processing_operations: ProcessingOperations = ProcessingOperations()
    processed_products: List[ProcessedProduct]
    allocation_basis: AllocationBasis = AllocationBasis.MASS  # how co-products split the total

    # When true, run pedigree screening Monte Carlo and attach percentiles. Defaults on for
    # parity with the farm path: real pedigree-driven p5/p95 bands are the deliverable, and the
    # MC scales category totals rather than re-solving the LCI, so the cost is small. Pass False
    # for the fast flat-band screening path.
    run_uncertainty: bool = True

    # Optional linkage/labelling for saving under a user's account.
    facility_id: Optional[str] = None  # attach to a Facility the user owns
    title: Optional[str] = None        # human label for the saved assessment

    # Opaque client form snapshot for edit/re-run UX (not used by the engine).
    form_snapshot: Optional[Dict[str, Any]] = None

    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        # Country is the coarse dataset bucket the kernel understands; finer geography
        # (e.g. Canada) is carried by `region` (engine/regions.py: GH/NG/CA).
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
    # Enriched fields from the validated engine (parity with the farm response), so the ISO
    # report renderer and the results chat work for processors too.
    allocation: Optional[Dict[str, Any]] = None
    input_matches: Optional[List[Dict[str, Any]]] = None
    inventory: Optional[Dict[str, Any]] = None
    contribution_by_source: Optional[Dict[str, Any]] = None
    iso_report: Optional[Dict[str, Any]] = None
    uncertainty: Optional[Dict[str, Any]] = None  # pedigree screening Monte Carlo percentiles
