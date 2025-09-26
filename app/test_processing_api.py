#!/usr/bin/env python3
"""
Test script for the Processing Facility LCA Assessment API
Validates that the processing endpoints work correctly with the Rust backend
"""

import requests
import json
import sys
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8000"

def test_processing_facility_types():
    """Test facility types endpoint"""
    print("Testing /processing/facility-types...")
    response = requests.get(f"{BASE_URL}/processing/facility-types")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Found {len(data['facility_types'])} facility types")
        print(f"  Examples: {data['facility_types'][:3]}")
        return True
    else:
        print(f"✗ Failed: {response.status_code} - {response.text}")
        return False

def test_processing_assessment():
    """Test processing assessment with example data"""
    print("\nTesting /processing/assess...")
    
    # Load example assessment
    example_file = Path(__file__).parent / "processing" / "example_assessment.json"
    if not example_file.exists():
        print(f"✗ Example file not found: {example_file}")
        return False
    
    with open(example_file, 'r') as f:
        assessment_data = json.load(f)
    
    response = requests.post(
        f"{BASE_URL}/processing/assess",
        json=assessment_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✓ Processing assessment successful!")
        print(f"  Assessment ID: {result.get('id', 'N/A')}")
        print(f"  Facility: {result.get('facility_profile', {}).get('facility_name', 'N/A')}")
        
        # Check key results
        midpoint = result.get('midpoint_impacts', {})
        if 'Global warming' in midpoint:
            gwp_value = midpoint['Global warming']
            if isinstance(gwp_value, dict):
                gwp_value = gwp_value.get('value', 'N/A')
            print(f"  Global warming: {gwp_value} kg CO2-eq")
        
        if 'Energy consumption' in midpoint:
            energy_value = midpoint['Energy consumption']
            if isinstance(energy_value, dict):
                energy_value = energy_value.get('value', 'N/A')
            print(f"  Energy consumption: {energy_value} kWh")
        
        # Check recommendations
        recommendations = result.get('recommendations', [])
        if recommendations:
            print(f"  Recommendations: {len(recommendations)} items")
            for i, rec in enumerate(recommendations[:2]):  # Show first 2
                print(f"    {i+1}. {rec.get('title', 'N/A')}")
        
        return True
        
    else:
        print(f"✗ Failed: {response.status_code}")
        print(f"  Error: {response.text}")
        return False

def test_cassava_processing():
    """Test cassava processing assessment"""
    print("\nTesting cassava processing assessment...")
    
    # Load cassava example
    example_file = Path(__file__).parent / "processing" / "example_cassava_processing.json"
    if not example_file.exists():
        print(f"✗ Cassava example file not found: {example_file}")
        return False
    
    with open(example_file, 'r') as f:
        assessment_data = json.load(f)
    
    response = requests.post(
        f"{BASE_URL}/processing/assess",
        json=assessment_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✓ Cassava processing assessment successful!")
        print(f"  Facility: {result.get('facility_profile', {}).get('facility_name', 'N/A')}")
        print(f"  Country: {result.get('country', 'N/A')}")
        
        # Show processing-specific impacts
        midpoint = result.get('midpoint_impacts', {})
        processing_impacts = ['Energy consumption', 'Water consumption', 'Solid waste generation']
        
        for impact in processing_impacts:
            if impact in midpoint:
                value = midpoint[impact]
                if isinstance(value, dict):
                    value = value.get('value', 'N/A')
                print(f"  {impact}: {value}")
        
        return True
        
    else:
        print(f"✗ Failed: {response.status_code}")
        print(f"  Error: {response.text}")
        return False

def test_benchmarks():
    """Test benchmarks endpoint"""
    print("\nTesting /processing/benchmarks...")
    
    facility_types = ["Mill", "RiceProcessing", "PalmOilMill"]
    
    for facility_type in facility_types:
        response = requests.get(f"{BASE_URL}/processing/benchmarks/{facility_type}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {facility_type} benchmarks available")
            if 'benchmarks' in data:
                benchmarks = data['benchmarks']
                if 'energy_consumption' in benchmarks:
                    energy = benchmarks['energy_consumption']
                    print(f"    Energy: {energy.get('best', 'N/A')}-{energy.get('poor', 'N/A')} {energy.get('unit', '')}")
        else:
            print(f"⚠ {facility_type} benchmarks: {response.status_code}")

def test_api_health():
    """Test basic API health"""
    print("Testing API health...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✓ API is healthy")
            return True
        else:
            print(f"✗ API health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API. Is it running on localhost:8000?")
        return False

def main():
    """Run all tests"""
    print("=== Processing Facility LCA API Test Suite ===\n")
    
    # Test API health first
    if not test_api_health():
        print("\n❌ API not available. Please start the API server first:")
        print("   python app/main.py")
        sys.exit(1)
    
    # Test endpoints
    tests = [
        test_processing_facility_types,
        test_processing_assessment,
        test_cassava_processing,
        test_benchmarks,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    print(f"Success rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 All tests passed! Processing API is working correctly.")
        sys.exit(0)
    else:
        print("⚠ Some tests failed. Check the Rust backend compilation and API server.")
        sys.exit(1)

if __name__ == "__main__":
    main()
