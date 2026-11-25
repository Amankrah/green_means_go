from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import ClassVar, List, Optional, Dict, Union, Any

# Same strict request base as the farm side: unknown keys are a 422, removed keys listed in
# `_legacy` are discarded so archived requests still re-run.
try:
    from production.models import StrictModel  # app/ on sys.path (uvicorn, tests)
except ImportError:  # imported as a package (app.processing.models)
    from app.production.models import StrictModel
from datetime import datetime
from enum import Enum
import sys
from pathlib import Path


def _engine_module(name: str):
    """Import an engine module whether app/ or the repo root is on sys.path."""
    try:
        return __import__(f"engine.{name}", fromlist=[name])
    except ImportError:
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        return __import__(f"engine.{name}", fromlist=[name])


class ProcessingStrictModel(StrictModel):
    """Processing request base: unknown keys are a 422 and NaN / infinity are rejected, so a
    quantity can never pass through as a non-number (the engine would otherwise divide by it
    or emit it as an inventory amount)."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# Upper bounds are plausibility caps for a single facility, not physical limits. They stop a
# typo (or a direct API call) from producing a billion-tonne inventory with no warning.
MAX_ANNUAL_PRODUCTION_T = 1.0e7       # tonnes per year, per product
MAX_CAPACITY_T_PER_DAY = 1.0e6        # tonnes per day
MAX_MONTHLY_KWH = 1.0e9               # kWh per month
MAX_MONTHLY_FUEL = 1.0e8              # litres, kg or m3 per month
MAX_MONTHLY_WATER_M3 = 1.0e8          # m3 per month
MAX_EFFLUENT_MG_PER_L = 1.0e6         # physical ceiling (1 kg/L); real effluents are far lower
MAX_WASTE_KG_PER_DAY = 1.0e7          # kg per day
MAX_RAW_KG_PER_TONNE = 1.0e6          # kg of raw material per tonne of output
MAX_PACKAGE_SIZE_KG = 1.0e5           # kg of product per package
MAX_PACKAGING_WEIGHT_KG = 1.0e4       # kg of packaging per package
MAX_TRANSPORT_KM = 5.0e4              # km, one way
MAX_REFRIGERANT_KG = 1.0e6            # kg leaked per year
MAX_STEP_KWH_PER_T = 1.0e6            # kWh per tonne
MAX_STEP_L_PER_T = 1.0e7              # litres per tonne
MAX_PRICE_PER_KG = 1.0e6              # price per kg in local currency
_TEXT = 120

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


class FuelType(str, Enum):
    """Fuels the wizard offers (processing-assessment-schema.ts FUEL_TYPES). Each maps to a
    carrier in engine/energy_carriers.py; an unknown fuel is a 422, never 'modelled as diesel'."""
    DIESEL = "Diesel"
    DIESEL_GENERATOR = "Diesel generator"
    PETROL = "Petrol"
    LPG = "LPG"
    NATURAL_GAS = "Natural gas"
    KEROSENE = "Kerosene"
    BIODIESEL = "Biodiesel"
    FIREWOOD = "Firewood"
    CHARCOAL = "Charcoal"
    PALM_KERNEL_SHELL = "Palm kernel shell"
    PALM_FIBRE = "Palm fibre"
    BIOGAS = "Biogas"


class FuelUnit(str, Enum):
    LITRE = "L"
    KILOGRAM = "kg"
    CUBIC_METRE = "m3"
    MEGAJOULE = "MJ"


class WaterSource(str, Enum):
    """Wizard WATER_SOURCES. Municipal is a purchased tap-water supply; the others are
    elementary withdrawals (engine/process_inputs.py _NATURAL_WATER); rainwater is excluded."""
    MUNICIPAL = "Municipal"
    BOREHOLE = "Borehole"
    WELL = "Well"
    RIVER = "River"
    DAM_RESERVOIR = "Dam/Reservoir"
    RAINWATER = "Rainwater"


_FUEL_SYNONYMS = {
    "diesel": "Diesel", "gasoil": "Diesel", "diesel generator": "Diesel generator",
    "generator diesel": "Diesel generator", "genset": "Diesel generator",
    "petrol": "Petrol", "gasoline": "Petrol",
    "lpg": "LPG", "liquefied petroleum gas": "LPG", "liquefied petroleum gas (lpg)": "LPG",
    "propane": "LPG", "butane": "LPG",
    "natural gas": "Natural gas", "naturalgas": "Natural gas", "ng": "Natural gas",
    "kerosene": "Kerosene", "paraffin": "Kerosene",
    "biodiesel": "Biodiesel",
    "firewood": "Firewood", "fuelwood": "Firewood", "wood": "Firewood",
    "charcoal": "Charcoal",
    "palm kernel shell": "Palm kernel shell", "pks": "Palm kernel shell",
    "palm fibre": "Palm fibre", "palm fiber": "Palm fibre",
    "biogas": "Biogas",
}
_UNIT_SYNONYMS = {
    "l": "L", "litre": "L", "liter": "L", "litres": "L", "liters": "L",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
    "m3": "m3", "m^3": "m3", "m³": "m3", "cubic metre": "m3", "cubic meter": "m3",
    "mj": "MJ",
}
_WATER_SYNONYMS = {
    "municipal": "Municipal", "municipal water supply": "Municipal", "tap": "Municipal",
    "tap water": "Municipal", "public supply": "Municipal", "tanker": "Municipal",
    "borehole": "Borehole", "groundwater": "Borehole",
    "well": "Well", "river": "River", "river/stream": "River", "stream": "River",
    "dam": "Dam/Reservoir", "reservoir": "Dam/Reservoir", "dam/reservoir": "Dam/Reservoir",
    "lake": "Dam/Reservoir",
    "rainwater": "Rainwater", "rain": "Rainwater", "rainwater harvesting": "Rainwater",
}


def _canon(value, table: dict):
    """Case-insensitive lookup of a free-text value in a synonym table. Unknown text is
    returned unchanged so the enum raises the 422."""
    if isinstance(value, str):
        key = " ".join(value.strip().lower().split())
        return table.get(key, value.strip())
    return value


def _canon_refrigerant(value):
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text.lower() == "none":
        return "None"
    found = _engine_module("refrigerants").canonical_name(text)
    return found or text

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
    # value on every product (enforced on the request, never silently degraded to mass).
    MASS = "mass"
    ECONOMIC = "economic"

# Processing facility profile
class ProcessingFacilityProfile(ProcessingStrictModel):
    facility_name: str = Field(min_length=1, max_length=_TEXT)
    company_name: str = Field(min_length=1, max_length=_TEXT)
    # facility_type: selects the default raw material / conversion ratio when a product has
    # no raw-material input (engine/conversion_ratios.py).
    facility_type: ProcessingFacilityType
    # processing_capacity / operational_hours_per_day / location_type: report-only metadata
    # (echoed in the ISO report goal & scope; capacity also drives the utilisation check in
    # the data-quality section). They do not change the numbers.
    processing_capacity: float = Field(gt=0, le=MAX_CAPACITY_T_PER_DAY)  # tonnes per day
    operational_hours_per_day: float = Field(default=8.0, ge=0, le=24)
    operational_days_per_year: int = Field(default=250, ge=1, le=366)   # live: scales solid waste kg/day to a year
    established_year: Optional[int] = Field(default=None, ge=1800, le=2100)
    certifications: List[str] = []
    employee_count: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    facility_size: Optional[float] = Field(default=None, ge=0, le=1.0e7)  # m2
    location_type: LocationType = LocationType.RURAL
    # Free-text province/state from the wizard (not an engine region code).
    admin_region: Optional[str] = Field(default=None, max_length=100)

    @field_validator("facility_name", "company_name", mode="before")
    @classmethod
    def _strip_names(cls, v):
        return v.strip() if isinstance(v, str) else v

# Energy management
class FuelStream(ProcessingStrictModel):
    """One fuel burned on site. A facility may have several (boiler wood + generator diesel)."""
    fuel_type: FuelType
    monthly_consumption: float = Field(gt=0, le=MAX_MONTHLY_FUEL)
    unit: Optional[FuelUnit] = None     # blank -> carrier's natural unit
    use: Optional[str] = Field(default=None, max_length=_TEXT)  # report-only label

    @field_validator("fuel_type", mode="before")
    @classmethod
    def _canon_fuel(cls, v):
        return _canon(v, _FUEL_SYNONYMS)

    @field_validator("unit", mode="before")
    @classmethod
    def _canon_unit(cls, v):
        if v in (None, ""):
            return None
        if isinstance(v, str):
            # engine/energy_carriers.py owns the unit vocabulary; unknown text stays as typed
            # so the enum raises the 422.
            return _engine_module("energy_carriers").normalise_fuel_unit(v) or _canon(v, _UNIT_SYNONYMS)
        return v


class EnergyManagement(ProcessingStrictModel):
    # Removed: secondary_energy_sources (no amounts; use fuel_streams), backup_generator
    # (enter the generator's diesel as a fuel stream), energy_efficiency_measures (free text).
    _legacy: ClassVar[frozenset] = frozenset({
        "secondary_energy_sources", "backup_generator", "energy_efficiency_measures"})
    # Selects the electricity dataset: grid market, PV, hydro, wind, or a diesel genset
    # (kWh -> diesel via specific fuel consumption). Mixed/Biomass/LPG/NaturalGas -> grid.
    primary_energy_source: EnergySource = EnergySource.GRID_ELECTRICITY
    monthly_electricity_consumption: Optional[float] = Field(default=None, ge=0, le=MAX_MONTHLY_KWH)  # kWh
    # Legacy single fuel stream (archived requests); merged into fuel_streams by the engine.
    monthly_fuel_consumption: Optional[float] = Field(default=None, ge=0, le=MAX_MONTHLY_FUEL)  # liters
    fuel_type: Optional[FuelType] = None
    fuel_streams: List[FuelStream] = []
    # Share of electricity from on-site solar PV (modelled with the ecoinvent PV dataset).
    renewable_energy_percentage: float = Field(default=0.0, ge=0, le=100)

    @field_validator("fuel_type", mode="before")
    @classmethod
    def _canon_fuel(cls, v):
        return _canon(v, _FUEL_SYNONYMS) if v not in (None, "") else None

    def declares_energy(self) -> bool:
        return bool((self.monthly_electricity_consumption or 0) > 0 or self.fuel_streams
                    or (self.monthly_fuel_consumption or 0) > 0)

# Water management for processing
class ProcessingWaterManagement(ProcessingStrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"water_conservation_measures"})
    # water_source: Municipal -> tap-water dataset; Borehole/Well/River/... -> withdrawal
    # elementary flow (groundwater / surface water) characterised by the water-use method.
    water_source: List[WaterSource] = []
    monthly_water_consumption: Optional[float] = Field(default=None, ge=0, le=MAX_MONTHLY_WATER_M3)  # m3
    # On-site treatment of the intake: Chemical -> decarbonised water dataset, Reverse
    # osmosis / Comprehensive -> deionised water dataset, None / Basic -> as sourced.
    water_treatment: WaterTreatment = WaterTreatment.BASIC_FILTRATION
    # None -> no treatment dataset and an explicit data-gap warning (untreated effluent);
    # any treatment -> average wastewater treatment dataset.
    wastewater_treatment: WastewaterTreatment = WastewaterTreatment.BASIC_SEDIMENTATION
    # Measured effluent concentrations (mg/L). Read only when wastewater_treatment is "None":
    # the untreated discharge is emitted to surface water (engine/process_inputs.py
    # EFFLUENT_FIELDS). Blank -> load not quantified (disclosed), no default is assumed.
    effluent_cod_mg_per_l: Optional[float] = Field(default=None, ge=0, le=MAX_EFFLUENT_MG_PER_L)
    effluent_bod5_mg_per_l: Optional[float] = Field(default=None, ge=0, le=MAX_EFFLUENT_MG_PER_L)
    effluent_total_n_mg_per_l: Optional[float] = Field(default=None, ge=0, le=MAX_EFFLUENT_MG_PER_L)
    effluent_total_p_mg_per_l: Optional[float] = Field(default=None, ge=0, le=MAX_EFFLUENT_MG_PER_L)

    @field_validator("water_source", mode="before")
    @classmethod
    def _canon_sources(cls, v):
        if isinstance(v, list):
            return [_canon(s, _WATER_SYNONYMS) for s in v]
        return v

# Byproduct utilization
class ByproductUtilization(ProcessingStrictModel):
    # The utilised share of the solid-waste stream leaves the system burden-free (cut-off:
    # it is a valorised by-product, not waste) instead of going to waste treatment.
    byproduct_name: str = Field(min_length=1, max_length=_TEXT)
    utilization_method: str = Field(min_length=1, max_length=_TEXT)
    percentage_utilized: float = Field(default=0.0, ge=0, le=100)

# Waste management
class ProcessingWasteManagement(ProcessingStrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"recycling_programs"})
    solid_waste_generation: Optional[float] = Field(default=None, ge=0, le=MAX_WASTE_KG_PER_DAY)  # kg/day
    # Splits the waste: the organic share goes to the disposal method's biowaste dataset,
    # the rest to the inert / mixed-waste dataset (engine/process_inputs.py).
    organic_waste_percentage: float = Field(default=70.0, ge=0, le=100)
    waste_disposal_method: WasteDisposalMethod = WasteDisposalMethod.LANDFILL
    byproduct_utilization: List[ByproductUtilization] = []

    @model_validator(mode="after")
    def _byproducts_within_the_stream(self):
        total = sum(b.percentage_utilized for b in self.byproduct_utilization)
        if total > 100.0 + 1e-9:
            raise ValueError(
                f"by-product utilisation adds up to {total:g}% of the solid-waste stream; "
                "the shares must total 100% or less")
        return self

# Storage practices
class StoragePractices(ProcessingStrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"storage_type", "climate_control", "pest_control_methods"})
    # Raw-material loss in storage: applied to DEFAULT conversion ratios only (a measured
    # kg-per-tonne-output figure already includes the facility's own losses).
    storage_loss_percentage: float = Field(default=5.0, ge=0, le=50)

# Raw material sourcing
class RawMaterialSourcing(ProcessingStrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"supplier_sustainability_practices", "seasonal_variation"})
    # Used only when average_transport_distance is blank: the default distance is a
    # local/non-local weighted mean (engine/process_inputs.py, cited).
    local_sourcing_percentage: float = Field(default=80.0, ge=0, le=100)
    # km; blank -> default from local share; an explicit 0 means no inbound transport.
    average_transport_distance: Optional[float] = Field(default=None, ge=0, le=MAX_TRANSPORT_KM)
    transport_mode: TransportMode = TransportMode.TRUCK
    storage_practices: StoragePractices = StoragePractices()

# Refrigerant / F-gas use (cold storage, chilling). Leakage is a direct on-site climate
# emission (leaked mass x GWP100), separate from purchased energy.
class RefrigerantManagement(ProcessingStrictModel):
    # A standard designation from engine/refrigerants.py (R-134a, R-404A, Ammonia, ...) or
    # "None". Unknown gases are a 422: there is no default GWP any more.
    refrigerant_type: Optional[str] = Field(default=None, max_length=40)
    annual_leakage_kg: Optional[float] = Field(default=None, ge=0, le=MAX_REFRIGERANT_KG)

    @field_validator("refrigerant_type", mode="before")
    @classmethod
    def _canon_gas(cls, v):
        return _canon_refrigerant(v) if v not in (None, "") else None

    @field_validator("refrigerant_type")
    @classmethod
    def _known_gas(cls, v):
        if v is None or v == "None":
            return v
        known = _engine_module("refrigerants").KNOWN_REFRIGERANTS
        if v not in known:
            raise ValueError(
                f"refrigerant '{v}' is not a known designation. Use one of: "
                + ", ".join(known) + ", or None")
        return v

    @model_validator(mode="after")
    def _leak_needs_a_gas(self):
        if (self.annual_leakage_kg or 0) > 0 and (self.refrigerant_type in (None, "None")):
            raise ValueError("annual_leakage_kg is given but refrigerant_type is missing; "
                             "name the gas (e.g. R-134a, R-404A, Ammonia)")
        return self

# Processing operations
class ProcessingOperations(ProcessingStrictModel):
    energy_management: EnergyManagement = EnergyManagement()
    water_management: ProcessingWaterManagement = ProcessingWaterManagement()
    waste_management: ProcessingWasteManagement = ProcessingWasteManagement()
    raw_material_sourcing: RawMaterialSourcing = RawMaterialSourcing()
    refrigerant_management: RefrigerantManagement = RefrigerantManagement()
    # equipment_efficiency (age, maintenance, automation, utilisation) carried no flow; the
    # metered energy already reflects it. Removed; archived requests are still accepted.
    _legacy: ClassVar[frozenset] = frozenset({"equipment_efficiency"})

# Raw material input
class RawMaterialInput(ProcessingStrictModel):
    _legacy: ClassVar[frozenset] = frozenset({"quality_requirements", "seasonal_availability"})
    material_name: str = Field(min_length=1, max_length=_TEXT)
    quantity_per_tonne_output: float = Field(gt=0, le=MAX_RAW_KG_PER_TONNE)  # kg
    source_location: Optional[str] = Field(default=None, max_length=_TEXT)   # report-only metadata (ISO report)

    @field_validator("material_name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

# Processing step
class ProcessingStep(ProcessingStrictModel):
    # duration / yield_efficiency / emissions_factor removed: duration has no power to
    # multiply, the mass balance comes from raw-material inputs or default conversion ratios,
    # and a single CO2-eq number cannot be characterised across categories (and would double
    # count the metered fuel).
    _legacy: ClassVar[frozenset] = frozenset({"duration", "yield_efficiency", "emissions_factor"})
    step_name: str = Field(min_length=1, max_length=_TEXT)
    energy_intensity: float = Field(ge=0, le=MAX_STEP_KWH_PER_T)  # kWh per tonne (used when there is no facility meter)
    water_usage: float = Field(ge=0, le=MAX_STEP_L_PER_T)         # liters per tonne (used when there is no facility meter)

# Packaging info
class PackagingInfo(ProcessingStrictModel):
    packaging_material: PackagingMaterial = PackagingMaterial.PLASTIC_BAG
    package_size: float = Field(gt=0, le=MAX_PACKAGE_SIZE_KG)                 # kg of product per package
    packaging_weight_per_unit: float = Field(gt=0, le=MAX_PACKAGING_WEIGHT_KG)  # kg of packaging per package
    # Report-only metadata: end-of-life of the packaging is outside a cradle-to-gate boundary.
    recyclable: bool = False

# Processed product
class ProcessedProduct(ProcessingStrictModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=_TEXT)
    product_type: ProductType
    annual_production: float = Field(gt=0, le=MAX_ANNUAL_PRODUCTION_T)  # tonnes
    raw_material_inputs: List[RawMaterialInput] = []
    processing_steps: List[ProcessingStep] = []
    # Packaging must be declared to be counted. There is no fabricated default: a product
    # sent without packaging is modelled as unpackaged, and the engine says so in its notes.
    packaging: Optional[PackagingInfo] = None
    # quality_grade / market_destination: report-only metadata (ISO report goal & scope).
    quality_grade: QualityGrade = QualityGrade.STANDARD
    market_destination: MarketDestination = MarketDestination.LOCAL
    economic_value: Optional[float] = Field(default=None, ge=0, le=MAX_PRICE_PER_KG)  # price per kg, economic allocation only

    @field_validator("name", "id", mode="before")
    @classmethod
    def _strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v

    def has_mass_balance(self, facility_type: Optional[str]) -> bool:
        """True when the cradle burden of this product's ingredients can be counted: a
        declared raw material, or a cited default conversion ratio for its type."""
        if self.raw_material_inputs:
            return True
        default_raw_input = _engine_module("conversion_ratios").default_raw_input
        return default_raw_input({"product_type": self.product_type.value}, facility_type) is not None

# Processing assessment request
class ProcessingAssessmentRequest(ProcessingStrictModel):
    country: str  # one of the supported countries below
    region: Optional[str] = Field(default=None, max_length=100)
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
    facility_id: Optional[str] = Field(default=None, max_length=64)  # attach to a Facility the user owns
    title: Optional[str] = Field(default=None, max_length=200)       # human label for the saved assessment

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

    @model_validator(mode="after")
    def _region_resolves(self):
        """The engine region must resolve from `region` (code, name or alias). A region that
        does not resolve is tolerated only as a province of a named country (Ghana, Nigeria:
        'Greater Accra', 'Ogun State'), where the country settles it. Under country
        'Global' the region IS the geography, so it must resolve. Nothing is defaulted."""
        regions = _engine_module("regions")

        def resolves(cand) -> bool:
            try:
                regions.get_region(str(cand))
                return True
            except KeyError:
                return False

        if self.region and resolves(self.region):
            return self
        if self.country != "Global" and resolves(self.country):
            return self
        raise ValueError(
            f"region '{self.region}' / country '{self.country}' do not resolve to a supported "
            f"engine region ({', '.join(regions.REGIONS)}); with country 'Global' the region "
            "must be a code or a known name")

    @model_validator(mode="after")
    def _products_are_distinct(self):
        seen: Dict[str, str] = {}
        for p in self.processed_products:
            key = p.name.strip().lower()
            if key in seen:
                raise ValueError(
                    f"duplicate product name '{p.name}': co-products are allocated by name, "
                    "so each product needs a distinct name")
            seen[key] = p.name
        return self

    @model_validator(mode="after")
    def _economic_allocation_needs_prices(self):
        if self.allocation_basis == AllocationBasis.ECONOMIC:
            missing = [p.name for p in self.processed_products if not (p.economic_value or 0) > 0]
            if missing:
                raise ValueError(
                    "economic allocation requires a price per kg (economic_value) greater than "
                    "zero on every product; missing for: " + ", ".join(missing))
        return self

    @model_validator(mode="after")
    def _complete_enough_to_assess(self):
        """Completeness gate: a result needs the cradle burden of every product's ingredients
        and at least one energy input. Anything less is not a facility footprint."""
        ftype = self.facility_profile.facility_type.value
        no_mass = [p.name for p in self.processed_products if not p.has_mass_balance(ftype)]
        if no_mass:
            raise ValueError(
                "no raw material declared and no default conversion ratio exists for: "
                + ", ".join(no_mass)
                + ". Add a raw_material_inputs entry (material name and kg per tonne of "
                "output) or choose a product type with a known conversion ratio")
        em = self.processing_operations.energy_management
        step_energy = any(s.energy_intensity > 0 for p in self.processed_products
                          for s in p.processing_steps)
        if not (em.declares_energy() or step_energy):
            raise ValueError(
                "no energy input declared: give monthly_electricity_consumption, at least one "
                "fuel stream, or per-step energy intensities")
        return self

# Processing assessment response (reusing assessment response structure from main models)
class ProcessingAssessmentResponse(BaseModel):
    id: str
    # Echoed from the saved result as-is: the request-side bounds above must never make an
    # archived assessment unreadable.
    facility_profile: Dict[str, Any]
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
    region: Optional[str] = None
    lcia_method: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    review_required: Optional[bool] = None
    review_items: Optional[List[Dict[str, Any]]] = None
