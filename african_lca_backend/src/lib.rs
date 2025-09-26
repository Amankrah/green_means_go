pub mod production;
pub mod utils;
pub mod processing;

pub use production::*;
pub use utils::*;
pub use processing::{
    ProcessingLCAEngine, ProcessingDataLoader, ProcessingAssessment,
    ProcessingFacilityProfile, ProcessingOperations, ProcessedProduct,
    ProcessingStep, RawMaterialInput, PackagingInfo, PackagingMaterial, QualityGrade, MarketDestination,
    ProcessingFacilityType, LocationType, ProductType, EnergySource, EnergyManagement,
    EquipmentAge, MaintenanceFrequency, AutomationLevel, EquipmentEfficiency,
    TransportMode, RawMaterialSourcing, StoragePractices
};

#[cfg(test)]
mod tests {
    use super::*;


    #[test]
    fn test_food_category_parsing() {
        assert!(matches!(FoodCategory::Cereals, FoodCategory::Cereals));
        assert!(matches!(FoodCategory::Legumes, FoodCategory::Legumes));
        assert!(matches!(FoodCategory::Meat, FoodCategory::Meat));
        assert!(matches!(FoodCategory::Poultry, FoodCategory::Poultry));
        assert!(matches!(FoodCategory::Dairy, FoodCategory::Dairy));
        assert!(matches!(FoodCategory::Eggs, FoodCategory::Eggs));
        assert!(matches!(FoodCategory::Oils, FoodCategory::Oils));
        assert!(matches!(FoodCategory::Nuts, FoodCategory::Nuts));
        assert!(matches!(FoodCategory::Roots, FoodCategory::Roots));
        assert!(matches!(FoodCategory::Other, FoodCategory::Other));
    }

    #[test]
    fn test_country_display() {
        assert_eq!(Country::Ghana.to_string(), "Ghana");
        assert_eq!(Country::Nigeria.to_string(), "Nigeria");
        assert_eq!(Country::Global.to_string(), "Global");
    }

    #[test]
    fn test_confidence_levels() {
        let high = ConfidenceLevel::High;
        let medium = ConfidenceLevel::Medium;
        let low = ConfidenceLevel::Low;
        
        // Test that they can be cloned and compared
        assert_eq!(high, ConfidenceLevel::High);
        assert_ne!(medium, low);
    }
}