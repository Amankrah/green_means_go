use std::error::Error;
use std::fmt;

#[derive(Debug)]
pub struct LCAError {
    pub message: String,
}

impl fmt::Display for LCAError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "LCA Error: {}", self.message)
    }
}

impl Error for LCAError {}

impl LCAError {
    pub fn new(message: &str) -> Self {
        Self {
            message: message.to_string(),
        }
    }
}

pub fn validate_food_quantity(quantity: f64) -> Result<(), LCAError> {
    if quantity <= 0.0 {
        return Err(LCAError::new("Food quantity must be positive"));
    }
    if quantity > 10000.0 {
        return Err(LCAError::new("Food quantity seems unusually high (>10 tons)"));
    }
    Ok(())
}

pub fn validate_company_name(name: &str) -> Result<(), LCAError> {
    if name.trim().is_empty() {
        return Err(LCAError::new("Company name cannot be empty"));
    }
    if name.len() > 200 {
        return Err(LCAError::new("Company name too long (max 200 characters)"));
    }
    Ok(())
}