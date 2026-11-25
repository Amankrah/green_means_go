from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import ClassVar, List, Literal, Optional, Dict, Union, Any
from datetime import datetime
from enum import Enum

# Country is the coarse dataset bucket the LCI kernel understands (Ghana / Nigeria /
# Global). Finer geography, including new demonstration regions like Canada, is
# carried by `region` (engine/regions.py: GH / NG / CA), so onboarding a country means
# adding a region, not a new country bucket. The platform is global; "Global" is the
# region-agnostic default and the bucket Canada (region "CA") resolves through.
VALID_COUNTRIES = ["Ghana", "Nigeria", "Global"]
VALID_FOOD_CATEGORIES = [
    "Cereals", "Legumes", "Vegetables", "Fruits", "Meat", "Poultry", 
    "Fish", "Dairy", "Eggs", "Oils", "Nuts", "Roots", "Other"
]


class StrictModel(BaseModel):
    """Request-model base: unknown keys are a 422, never silently dropped.

    Silent dropping is how the wizard's `pesticides_used` key lost every pesticide burden
    (the model expected `pesticides`). `_aliases` maps a legacy key to its current name;
    `_legacy` lists keys that were deliberately removed from the contract (they carried no
    inventory meaning) and are discarded so archived requests can still be re-run. Anything
    else is rejected.
    """
    # allow_inf_nan=False: NaN / inf used to pass pydantic and crash the kernel's JSON parse
    # (a 500 instead of a 422).
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    _aliases: ClassVar[Dict[str, str]] = {}
    _legacy: ClassVar[frozenset] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_keys(cls, data):
        if not isinstance(data, dict):
            return data
        if not cls._aliases and not cls._legacy:
            return data
        out = {}
        for k, v in data.items():
            if k in cls._legacy:
                continue
            nk = cls._aliases.get(k, k)
            if nk in out and nk != k:
                continue        # the current key wins over its legacy alias
            out[nk] = v
        return out

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


# ---------------------------------------------------------------------------------------
# Closed vocabularies for fields the engine keys numbers on. The wizard offers exactly
# these options (african-lca-frontend/src/types/enhanced-assessment.ts); the API used to
# accept any string, and a bogus irrigation system was silently modelled as surface
# irrigation with invented water and pumping energy. Matching is case-insensitive and
# keyword based so archived requests ("Sprinkler", "Drip irrigation") and the wizard's
# labels ("Sprinkler System") both resolve to one canonical value; anything else is a 422.
# fertilizer_type and fuel_type stay free text on purpose: the intelligence layer
# (engine/llm) classifies trade names such as "white prills" or "gas oil".
# ---------------------------------------------------------------------------------------
class IrrigationSystem(str, Enum):
    NONE = "None (Rainfed)"
    FLOOD = "Flood Irrigation"
    FURROW = "Furrow Irrigation"
    SPRINKLER = "Sprinkler System"
    DRIP = "Drip Irrigation"
    BUCKET = "Bucket/Manual Irrigation"


class WaterSource(str, Enum):
    RAINFALL = "Rainfall only"
    BOREHOLE = "Borehole"
    RIVER = "River/Stream"
    DAM = "Dam/Reservoir"
    WELL = "Well"
    MUNICIPAL = "Municipal Water Supply"


class PesticideType(str, Enum):
    INSECTICIDE = "Insecticide"
    HERBICIDE = "Herbicide"
    FUNGICIDE = "Fungicide"
    NEMATICIDE = "Nematicide"
    RODENTICIDE = "Rodenticide"
    BIO_PESTICIDE = "Bio-pesticide"
    ORGANIC_APPROVED = "Organic-approved pesticide"


class CompostSource(str, Enum):
    FARM_MADE = "Farm-made compost"
    PURCHASED = "Purchased compost"
    ANIMAL_MANURE = "Animal manure"
    GREEN_WASTE = "Green waste/crop residues"
    MIXED = "Mixed sources"
    NONE = "Not used"


class PowerSource(str, Enum):
    MANUAL = "Manual/Human power"
    ANIMAL = "Animal power"
    DIESEL = "Diesel engine"
    PETROL = "Petrol engine"
    ELECTRIC = "Electric"
    SOLAR = "Solar powered"


class EnergyType(str, Enum):
    GRID = "Grid Electricity"
    DIESEL_GENERATOR = "Diesel Generator"
    SOLAR = "Solar Panels"
    BIOGAS = "Biogas"
    FIREWOOD = "Firewood"
    CHARCOAL = "Charcoal"


def _norm_text(v) -> str:
    return " ".join(str(v or "").lower().replace("_", " ").replace("-", " ").split())


def _resolve_vocab(field: str, value, rules, enum_cls):
    """Map free text to a canonical enum value by exact match, then by keyword rules
    (first rule whose every keyword appears, in order). Unknown -> ValueError (422)."""
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    text = str(value).strip()
    if not text:
        return None
    low = _norm_text(text)
    for member in enum_cls:
        if _norm_text(member.value) == low:
            return member
    for keywords, member in rules:
        if any(k in low for k in keywords):
            return member
    allowed = ", ".join(m.value for m in enum_cls)
    raise ValueError(f"{field} '{text}' is not recognised. Use one of: {allowed}")


_IRRIGATION_RULES = [
    (("none", "rainfed", "rain fed", "no irrigation"), IrrigationSystem.NONE),
    (("drip",), IrrigationSystem.DRIP),
    (("sprinkler", "pivot"), IrrigationSystem.SPRINKLER),
    (("furrow",), IrrigationSystem.FURROW),
    (("flood", "basin"), IrrigationSystem.FLOOD),
    (("bucket", "manual", "watering can"), IrrigationSystem.BUCKET),
]
_WATER_SOURCE_RULES = [
    (("rain",), WaterSource.RAINFALL),
    (("borehole", "bore hole"), WaterSource.BOREHOLE),
    (("river", "stream"), WaterSource.RIVER),
    (("dam", "reservoir", "lake", "pond"), WaterSource.DAM),
    (("well",), WaterSource.WELL),
    (("municipal", "tap", "piped", "mains"), WaterSource.MUNICIPAL),
]
_PESTICIDE_TYPE_RULES = [
    (("insect",), PesticideType.INSECTICIDE),
    (("herbic", "weed"), PesticideType.HERBICIDE),
    (("fungic",), PesticideType.FUNGICIDE),
    (("nematic",), PesticideType.NEMATICIDE),
    (("rodent", "rat"), PesticideType.RODENTICIDE),
    (("bio", "biological"), PesticideType.BIO_PESTICIDE),
    (("organic",), PesticideType.ORGANIC_APPROVED),
]
_COMPOST_SOURCE_RULES = [
    (("not used", "none", "no compost"), CompostSource.NONE),
    (("purchas", "bought", "commercial"), CompostSource.PURCHASED),
    (("manure", "dung", "poultry", "litter"), CompostSource.ANIMAL_MANURE),
    (("farm made", "fosse", "homemade", "home made", "on farm"), CompostSource.FARM_MADE),
    (("green", "residue", "crop waste"), CompostSource.GREEN_WASTE),
    (("mixed",), CompostSource.MIXED),
]
_POWER_SOURCE_RULES = [
    (("manual", "human", "hand"), PowerSource.MANUAL),
    (("animal", "ox", "bullock", "donkey"), PowerSource.ANIMAL),
    (("solar",), PowerSource.SOLAR),
    (("electric", "grid", "battery"), PowerSource.ELECTRIC),
    (("petrol", "gasoline"), PowerSource.PETROL),
    (("diesel", "engine", "motor"), PowerSource.DIESEL),
]
_ENERGY_TYPE_RULES = [
    (("generator", "genset"), EnergyType.DIESEL_GENERATOR),
    (("solar", "pv"), EnergyType.SOLAR),
    (("grid", "electric", "mains"), EnergyType.GRID),
    (("biogas",), EnergyType.BIOGAS),
    (("firewood", "fire wood", "wood", "fuelwood"), EnergyType.FIREWOOD),
    (("charcoal",), EnergyType.CHARCOAL),
]

# Plausibility ceilings mirror the wizard's zod caps so a direct API call cannot send
# 1e9 kg/ha. They are generous for real farms and only stop obvious garbage.
MAX_FARM_SIZE_HA = 1_000_000.0
MAX_FERTILISER_RATE_KG_HA = 5_000.0
MAX_APPLICATIONS_PER_SEASON = 12
MAX_PESTICIDE_APPLICATIONS_PER_SEASON = 30
MAX_PESTICIDE_RATE_PER_HA = 100.0
MAX_COMPOST_RATE_T_HA = 200.0
MAX_IRRIGATION_M3 = 1e9
MAX_MONTHLY_CONSUMPTION = 1e6
MAX_QUANTITY_KG = 1e9
MAX_TEXT = 120


# Enhanced models for comprehensive assessments
class FarmProfile(StrictModel):
    farmer_name: str = Field(min_length=1, max_length=MAX_TEXT)
    farm_name: str = Field(min_length=1, max_length=MAX_TEXT)
    total_farm_size: float = Field(gt=0, le=MAX_FARM_SIZE_HA)  # hectares
    farming_experience: int = Field(ge=0, le=100)  # years
    farm_type: FarmType
    primary_farming_system: FarmingSystem
    certifications: List[str] = []
    participates_in_programs: List[str] = []

class SoilManagement(StrictModel):
    soil_type: Optional[SoilType] = None
    uses_compost: bool = False
    compost_source: Optional[CompostSource] = None
    # tonnes/ha/year (organic N -> field N2O). Read only when uses_compost is true.
    compost_application_rate: Optional[float] = Field(default=None, ge=0, le=MAX_COMPOST_RATE_T_HA)
    conservation_practices: List[str] = []
    soil_testing_frequency: Optional[str] = Field(default=None, max_length=MAX_TEXT)

    @field_validator("compost_source", mode="before")
    @classmethod
    def _compost_source_vocab(cls, v):
        return _resolve_vocab("compost_source", v, _COMPOST_SOURCE_RULES, CompostSource)

    @model_validator(mode="after")
    def _compost_consistency(self):
        if self.uses_compost:
            if not self.compost_application_rate or self.compost_application_rate <= 0:
                raise ValueError("uses_compost is true but compost_application_rate (t/ha/year) "
                                 "is missing or zero; enter the rate or set uses_compost to false")
            if self.compost_source in (None, CompostSource.NONE):
                raise ValueError("uses_compost is true but compost_source is 'Not used' or blank")
        return self

class FertilizerApplication(StrictModel):
    # Free text by design: trade names are classified by the intelligence layer.
    fertilizer_type: str = Field(min_length=1, max_length=MAX_TEXT)
    npk_ratio: Optional[str] = Field(default=None, max_length=20)  # e.g., "15-15-15"
    application_rate: float = Field(ge=0, le=MAX_FERTILISER_RATE_KG_HA)  # kg/hectare/season
    applications_per_season: int = Field(ge=0, le=MAX_APPLICATIONS_PER_SEASON)
    cost: Optional[float] = Field(default=None, ge=0)

    @field_validator("fertilizer_type", "npk_ratio", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

class FertilizationPractices(StrictModel):
    uses_fertilizers: bool = False
    fertilizer_applications: List[FertilizerApplication] = []
    soil_test_based: bool = False
    follows_nutrient_plan: bool = False

    @model_validator(mode="after")
    def _flag_matches_rows(self):
        real = [a for a in self.fertilizer_applications
                if a.application_rate > 0 and a.applications_per_season > 0]
        if not self.uses_fertilizers and real:
            # The Python extractor counted these while the kernel skipped their field N2O:
            # two layers disagreed. Make the caller say which it is.
            raise ValueError("uses_fertilizers is false but fertilizer_applications contains "
                             f"{len(real)} application(s) with a positive rate; set "
                             "uses_fertilizers to true or remove the rows")
        if self.uses_fertilizers and not real:
            raise ValueError("uses_fertilizers is true but no fertilizer application has a "
                             "positive rate and at least one application per season")
        return self

class WaterManagement(StrictModel):
    # water_source selects the withdrawal flow (groundwater vs surface vs municipal) for
    # irrigation water, which is what AWARE / water-use CFs are keyed on.
    water_source: List[WaterSource] = []
    irrigation_system: Optional[IrrigationSystem] = None
    # Annual irrigation water applied to the whole farm (m3/yr). When blank and the farm is
    # irrigated, engine/crop_defaults.py estimates it (FAO crop water need / application
    # efficiency) and flags it as estimated.
    irrigation_water_m3: Optional[float] = Field(default=None, ge=0, le=MAX_IRRIGATION_M3)
    # Report-only metadata (echoed in the ISO report; does not change the numbers).
    water_conservation_practices: List[str] = []

    @field_validator("water_source", mode="before")
    @classmethod
    def _water_source_vocab(cls, v):
        if v is None:
            return []
        if isinstance(v, (str, WaterSource)):
            v = [v]
        out = []
        for item in v:
            r = _resolve_vocab("water_source", item, _WATER_SOURCE_RULES, WaterSource)
            if r is not None and r not in out:
                out.append(r)
        return out

    @field_validator("irrigation_system", mode="before")
    @classmethod
    def _irrigation_vocab(cls, v):
        return _resolve_vocab("irrigation_system", v, _IRRIGATION_RULES, IrrigationSystem)

class PesticideApplication(StrictModel):
    pesticide_type: PesticideType    # selects the production dataset class if the AI is unknown
    active_ingredient: str = Field(min_length=1, max_length=MAX_TEXT)  # AI dataset + soil flow
    application_rate: float = Field(ge=0, le=MAX_PESTICIDE_RATE_PER_HA)  # kg or L product/ha/app
    applications_per_season: int = Field(ge=0, le=MAX_PESTICIDE_APPLICATIONS_PER_SEASON)
    # kg active ingredient per kg (or L) of product. Blank -> typical formulation strength
    # for the AI (engine/pesticides.py) or, if unknown, 1.0 (conservative upper bound).
    active_ingredient_content: Optional[float] = Field(default=None, gt=0, le=1.0)
    target_pests: List[str] = []     # report-only metadata

    @field_validator("pesticide_type", mode="before")
    @classmethod
    def _pesticide_type_vocab(cls, v):
        return _resolve_vocab("pesticide_type", v, _PESTICIDE_TYPE_RULES, PesticideType)

    @field_validator("active_ingredient", mode="before")
    @classmethod
    def _strip_ai(cls, v):
        return v.strip() if isinstance(v, str) else v

class PestManagement(StrictModel):
    # The wizard historically posted `pesticides_used` / `monitoring_frequency` (the Rust
    # field names); pydantic dropped them and no pesticide was ever counted. Accept both.
    _aliases: ClassVar[Dict[str, str]] = {
        "pesticides_used": "pesticides",
        "monitoring_frequency": "pest_monitoring_frequency",
    }
    # management_approach / uses_ipm / pest_monitoring_frequency: report-only metadata.
    management_approach: str = "IntegratedIPM"
    uses_ipm: bool = False
    pesticides: List[PesticideApplication] = []
    pest_monitoring_frequency: Optional[str] = None

class ManagementPractices(StrictModel):
    soil_management: SoilManagement
    fertilization: FertilizationPractices
    water_management: WaterManagement
    pest_management: PestManagement

# Equipment and Energy models
class FarmEquipment(StrictModel):
    # equipment_type + power_source + hours_per_year + fuel_efficiency estimate the fuel of
    # any carrier not metered in fuel_consumption (engine/inputs.py). age is report-only.
    equipment_type: str = Field(min_length=1, max_length=MAX_TEXT)
    power_source: PowerSource
    age: int = Field(ge=0, le=100)  # years (report-only metadata)
    hours_per_year: float = Field(ge=0, le=8760)
    fuel_efficiency: Optional[float] = Field(default=None, ge=0, le=1000)  # litres per hour

    @field_validator("power_source", mode="before")
    @classmethod
    def _power_source_vocab(cls, v):
        return _resolve_vocab("power_source", v, _POWER_SOURCE_RULES, PowerSource)


_UNIT_ALIASES = {
    "l": "L", "litre": "L", "litres": "L", "liter": "L", "liters": "L", "lt": "L",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "kwh": "kWh", "m3": "m3", "m³": "m3", "cubic metre": "m3", "cubic meter": "m3",
}


def _normalise_unit(v, allowed: tuple[str, ...], field: str):
    if v is None:
        return None
    text = str(v).strip()
    if not text:
        return None
    unit = _UNIT_ALIASES.get(text.lower(), text)
    if unit not in allowed:
        raise ValueError(f"{field} unit '{text}' is not supported. Use one of: {', '.join(allowed)}")
    return unit


class EnergyUsage(StrictModel):
    # monthly_consumption is in `unit`; when unit is blank the engine uses the carrier's
    # natural unit (kWh electricity/solar, L diesel, m3 biogas, kg wood/charcoal).
    energy_type: EnergyType
    monthly_consumption: float = Field(ge=0, le=MAX_MONTHLY_CONSUMPTION)
    unit: Optional[str] = None
    primary_use: str = Field(min_length=1, max_length=MAX_TEXT)
    cost: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=10)

    @field_validator("energy_type", mode="before")
    @classmethod
    def _energy_type_vocab(cls, v):
        return _resolve_vocab("energy_type", v, _ENERGY_TYPE_RULES, EnergyType)

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v):
        return _normalise_unit(v, ("kWh", "L", "kg", "m3"), "energy")

class FuelUsage(StrictModel):
    # Free text by design (Diesel | Petrol | Kerosene | LPG | Biodiesel and local trade
    # names): engine/energy_carriers.py maps it, the intelligence layer classifies the rest.
    fuel_type: str = Field(min_length=1, max_length=MAX_TEXT)
    monthly_consumption: float = Field(ge=0, le=MAX_MONTHLY_CONSUMPTION)  # litres, or `unit`
    unit: Optional[str] = None          # L (default) or kg (LPG cylinders)
    primary_use: str = Field(min_length=1, max_length=MAX_TEXT)
    cost: Optional[float] = Field(default=None, ge=0)

    @field_validator("fuel_type", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v):
        return _normalise_unit(v, ("L", "kg"), "fuel")

class EquipmentEnergy(StrictModel):
    equipment: List[FarmEquipment] = []
    energy_sources: List[EnergyUsage] = []
    fuel_consumption: List[FuelUsage] = []


class FarmLogistics(StrictModel):
    """Packaging and transport around the farm gate (engine/inputs.py)."""
    # Packaging of the harvested product (e.g. PP woven sacks, jute bags, crates).
    packaging_material: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    packaging_kg_per_tonne: Optional[float] = Field(default=None, ge=0, le=1000)  # blank -> default
    # Delivery of the harvest to the first point of sale. Given -> included (boundary is
    # then cradle-to-first-point-of-sale); blank -> outside the farm-gate boundary.
    distance_to_market_km: Optional[float] = Field(default=None, ge=0, le=20000)
    market_transport_mode: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    # Transport of purchased inputs (fertiliser, pesticides, seed, compost) to the farm.
    # Blank -> default distance (engine/inputs.py, cited).
    input_transport_km: Optional[float] = Field(default=None, ge=0, le=20000)

class LandUseChange(StrictModel):
    """Read by WS1's field model: IPCC stock-change LUC carbon, 20-year amortisation."""
    previous_land_use: Literal["forest", "grassland", "annual_cropland", "perennial_cropland"]
    years_since_conversion: int = Field(ge=0)


class ResidueManagement(StrictModel):
    """Read by WS1's field model: crop-residue N2O and burning."""
    fraction_removed: float = Field(default=0.0, ge=0.0, le=1.0)
    fraction_burnt: float = Field(default=0.0, ge=0.0, le=1.0)


class Establishment(StrictModel):
    """Perennials (cocoa, oil palm): establishment phase amortised over productive years."""
    immature_years: Optional[float] = Field(default=None, ge=0)
    productive_years: Optional[float] = Field(default=None, gt=0)
    input_share: Optional[float] = Field(default=None, ge=0)


class FoodItem(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=MAX_TEXT)
    quantity_kg: float = Field(gt=0, le=MAX_QUANTITY_KG)
    category: str
    crop_type: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    origin_country: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    production_system: Optional[ProductionSystem] = None
    seasonal_factor: Optional[SeasonalFactor] = None

    # Enhanced fields for comprehensive assessments
    variety: Optional[str] = Field(default=None, max_length=MAX_TEXT)
    # hectares. Optional for a bare product assessment; required (> 0) on every crop as
    # soon as any area-scaled input (fertiliser, pesticide, compost) is declared, see
    # AssessmentRequest._area_required_for_inputs.
    area_allocated: Optional[float] = Field(default=None, gt=0, le=MAX_FARM_SIZE_HA)
    cropping_pattern: Optional[CroppingPattern] = None
    intercropping_partners: Optional[List[str]] = None
    post_harvest_losses: Optional[float] = Field(default=None, ge=0, le=100)  # percentage
    # Seed / planting material sown (kg per ha per season). Blank -> crop default
    # (engine/crop_defaults.py, FAO seed rates), chosen by crop name, else by category.
    seed_rate_kg_per_ha: Optional[float] = Field(default=None, ge=0, le=10000)
    # Advanced field-model inputs (engine field model, WS1).
    land_use_change: Optional[LandUseChange] = None
    residue_management: Optional[ResidueManagement] = None
    establishment: Optional[Establishment] = None

    # The wizard used to nest a copy of farm_profile / management_practices inside every
    # food; they were never read. Discard them so cached clients keep working.
    _legacy: ClassVar[frozenset] = frozenset({"farm_profile", "management_practices"})

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v not in VALID_FOOD_CATEGORIES:
            raise ValueError(f"Invalid food category: {v}. Must be one of {VALID_FOOD_CATEGORIES}")
        return v

# LCIA methods exposed for researcher method toggle (must exist in the CF store).
SUPPORTED_LCIA_METHODS = (
    "ReCiPe 2016 v1.03, midpoint (H)",
    "EF v3.1",
)


class StudyMeta(StrictModel):
    """Temporal and spatial metadata for research export and cohort analysis."""

    crop_year: Optional[int] = None
    season: Optional[str] = None
    admin_region: Optional[str] = None


def _known_region_code(value: str) -> str:
    """Resolve a region code or alias through the engine registry (single source of truth).
    Raises ValueError for anything the engine does not know, so the API answers 422 instead
    of the KeyError 500 the service used to raise."""
    try:
        from engine.regions import get_region
    except ImportError:  # app/ imported without the repo root on sys.path
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from engine.regions import get_region
    try:
        return get_region(value).code
    except KeyError as e:
        raise ValueError(str(e)) from e


class AssessmentRequest(StrictModel):
    company_name: str = Field(min_length=1, max_length=2 * MAX_TEXT)
    country: str  # one of VALID_COUNTRIES
    foods: List[FoodItem] = Field(min_length=1)
    region: Optional[str] = None

    # Optional linkage/labelling for saving under a user's account.
    farm_id: Optional[str] = None  # attach this assessment to a Farm the user owns
    title: Optional[str] = None    # human label for the saved assessment

    # Enhanced fields for comprehensive assessments
    farm_profile: Optional[FarmProfile] = None
    management_practices: Optional[ManagementPractices] = None
    equipment_energy: Optional[EquipmentEnergy] = None
    logistics: Optional[FarmLogistics] = None

    # Opaque client wizard snapshot for edit/re-run UX (not used by the engine).
    form_snapshot: Optional[Dict[str, Any]] = None

    # Optional LCIA method override (region default used when omitted).
    lcia_method: Optional[str] = None

    # When true, run pedigree screening Monte Carlo and attach percentiles.
    # Defaults on: real pedigree-driven p5/p95 bands are the deliverable, and the MC
    # scales category totals rather than re-solving the LCI, so the cost is small.
    # Explicitly pass False for the fast flat-band screening path.
    run_uncertainty: bool = True

    # Optional study metadata (crop year / season / admin region) for research export.
    study_meta: Optional[StudyMeta] = None

    # Optional IPCC EF1 scale for N2O (literature-linked toggle; 1.0 = region default).
    ipcc_ef1_scale: Optional[float] = Field(default=None, gt=0, le=10)

    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        if v not in VALID_COUNTRIES:
            raise ValueError(f"Invalid country: {v}. Must be one of {VALID_COUNTRIES}")
        return v

    @field_validator("region", mode="before")
    @classmethod
    def validate_region(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        if not text:
            return None
        return _known_region_code(text)

    # Inputs that the engine scales by crop area. If any is declared, every crop needs an
    # area, otherwise fertiliser, pesticide, compost and seed inputs and all fertiliser
    # field N2O silently vanish and a fertilised farm gets a clean per-kg score.
    def _area_scaled_inputs(self) -> List[str]:
        mp = self.management_practices
        if mp is None:
            return []
        declared = []
        fert = mp.fertilization
        if fert.uses_fertilizers or any(a.application_rate > 0 and a.applications_per_season > 0
                                        for a in fert.fertilizer_applications):
            declared.append("fertiliser")
        if any(p.application_rate > 0 and p.applications_per_season > 0
               for p in mp.pest_management.pesticides):
            declared.append("pesticide")
        if mp.soil_management.uses_compost:
            declared.append("compost")
        return declared

    @model_validator(mode="after")
    def _area_required_for_inputs(self):
        declared = self._area_scaled_inputs()
        if declared:
            missing = [f.name for f in self.foods if not f.area_allocated]
            if missing:
                raise ValueError(
                    f"area_allocated (ha) is required on every crop when {', '.join(declared)} "
                    f"inputs are declared, because those inputs are scaled by area; missing on: "
                    f"{', '.join(missing)}")
        return self

    @model_validator(mode="after")
    def _area_within_farm(self):
        if self.farm_profile is None:
            return self
        areas = [f.area_allocated for f in self.foods if f.area_allocated]
        total = sum(areas)
        # Intercropped partners share the same field, so allow a small tolerance only.
        if total > self.farm_profile.total_farm_size * 1.001:
            raise ValueError(
                f"the crop areas add up to {total:g} ha but total_farm_size is "
                f"{self.farm_profile.total_farm_size:g} ha")
        return self

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

class ScenarioPatchBody(StrictModel):
    """Body for POST /assess/{id}/scenarios."""
    name: Optional[str] = None
    yield_scale: Optional[float] = None
    n_rate_scale: Optional[float] = None
    diesel_scale: Optional[float] = None


class RecharacterizeBody(StrictModel):
    """Body for POST /assess/{id}/recharacterize."""
    lcia_method: str
    apply_as_primary: bool = False


class ReviewStatusBody(StrictModel):
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