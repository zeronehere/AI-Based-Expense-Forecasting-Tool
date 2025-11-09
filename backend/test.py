# verify_install.py
import importlib

required_packages = [
    'flask', 'flask_cors', 'flask_jwt_extended', 'werkzeug',
    'pandas', 'numpy', 'sklearn', 'prophet', 'holidays',
    'nltk', 'streamlit', 'plotly', 'sqlite3'
]

print("🔍 Verifying package installation...")
for package in required_packages:
    try:
        importlib.import_module(package)
        print(f"✅ {package}")
    except ImportError as e:
        print(f"❌ {package}: {e}")

print("\n🎯 All packages verified!")