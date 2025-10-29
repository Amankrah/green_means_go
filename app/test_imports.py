"""
Quick test to verify all imports work correctly
"""
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

print("Python version:", sys.version)
print("Python path:", sys.executable)
print()

try:
    print("Testing FastAPI import...")
    from fastapi import FastAPI
    print("[OK] FastAPI imported successfully")
except Exception as e:
    print(f"[FAIL] FastAPI import failed: {e}")

try:
    print("\nTesting Anthropic import...")
    import anthropic
    print("[OK] Anthropic imported successfully")
except Exception as e:
    print(f"[FAIL] Anthropic import failed: {e}")

try:
    print("\nTesting production routes import...")
    from production.routes import router as production_router
    print("[OK] Production routes imported successfully")
except Exception as e:
    print(f"[FAIL] Production routes import failed: {e}")

try:
    print("\nTesting processing routes import...")
    from processing.routes import router as processing_router
    print("[OK] Processing routes imported successfully")
except Exception as e:
    print(f"[FAIL] Processing routes import failed: {e}")

try:
    print("\nTesting AI report generator import...")
    from services.ai_report_generator import AIReportGenerator
    print("[OK] AI report generator module imported successfully")
    print("  Note: AIReportGenerator requires ANTHROPIC_API_KEY to initialize")
except Exception as e:
    print(f"[FAIL] AI report generator import failed: {e}")

try:
    print("\nTesting reports routes import...")
    from reports.routes import router as reports_router
    print("[OK] Reports routes imported successfully")
except Exception as e:
    print(f"[FAIL] Reports routes import failed: {e}")

print("\n" + "="*60)
print("Import test complete!")
print("="*60)
