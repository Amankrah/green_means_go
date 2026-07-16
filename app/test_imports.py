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
    print("\nTesting results grounding import...")
    from services.report_grounding import format_grounding_for_prompt
    print("[OK] Results grounding module imported successfully")
except Exception as e:
    print(f"[FAIL] Results grounding import failed: {e}")

try:
    print("\nTesting chat routes import...")
    from chat.routes import router as chat_router
    print("[OK] Chat routes imported successfully")
except Exception as e:
    print(f"[FAIL] Chat routes import failed: {e}")

print("\n" + "="*60)
print("Import test complete!")
print("="*60)
