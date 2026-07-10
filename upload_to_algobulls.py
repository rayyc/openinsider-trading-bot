# upload_to_algobulls.py
# ============================================================
# UPLOAD SCRIPT FOR ALGOBULLS STRATEGY CREATOR PROGRAM
# ============================================================
# This script uploads your OpenInsider strategy to AlgoBulls
# and starts the monetization process.
# ============================================================

import os
import sys
from pyalgotrading.algobulls import AlgoBullsConnection

# ============================================================
# CONFIGURATION
# ============================================================
# Get your API token from AlgoBulls dashboard
ALGOBULLS_API_TOKEN = os.getenv('ALGOBULLS_API_TOKEN', 'YOUR_API_TOKEN_HERE')
STRATEGY_FILE = 'strategy_openinsider_bot.py'

# ============================================================
# MAIN
# ============================================================
def main():
    print("\n" + "="*60)
    print("UPLOADING STRATEGY TO ALGOBULLS")
    print("="*60 + "\n")
    
    # Step 1: Connect to AlgoBulls
    print("Step 1: Connecting to AlgoBulls...")
    connection = AlgoBullsConnection()
    
    if not ALGOBULLS_API_TOKEN or ALGOBULLS_API_TOKEN == 'YOUR_API_TOKEN_HERE':
        print("\n❌ ERROR: Please set your ALGOBULLS_API_TOKEN")
        print("   Get it from: https://algobulls.com/dashboard")
        print("\n   Set it as environment variable or edit this file.")
        sys.exit(1)
    
    connection.set_access_token(ALGOBULLS_API_TOKEN)
    print("✓ Connected successfully\n")
    
    # Step 2: Upload the strategy file
    print(f"Step 2: Uploading {STRATEGY_FILE}...")
    
    if not os.path.exists(STRATEGY_FILE):
        print(f"❌ ERROR: {STRATEGY_FILE} not found in current directory")
        print("   Make sure the strategy file is in the same folder.")
        sys.exit(1)
    
    with open(STRATEGY_FILE, 'r') as f:
        strategy_code = f.read()
    
    # Upload using AlgoBulls API
    try:
        strategy_id = connection.upload_strategy(strategy_code)
        print(f"✓ Strategy uploaded successfully!")
        print(f"   Strategy ID: {strategy_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        sys.exit(1)
    
    # Step 3: Verify upload
    print("\nStep 3: Verifying upload...")
    try:
        strategies = connection.get_strategies()
        print(f"✓ Found {len(strategies)} strategies in your account")
        for s in strategies:
            print(f"   - {s.get('name', 'Unnamed')} (ID: {s.get('id', 'N/A')})")
    except Exception as e:
        print(f"⚠️  Could not verify: {e}")
    
    # Step 4: Apply for Strategy Creator Program
    print("\n" + "="*60)
    print("✅ STRATEGY UPLOAD COMPLETE!")
    print("="*60)
    print("\nNEXT STEPS FOR MONETIZATION:")
    print("1. Log in to https://algobulls.com")
    print("2. Go to 'My Coded Strategies'")
    print("3. Find your 'OpenInsider Multi-Layer Bot'")
    print("4. Run backtests and paper trading to validate")
    print("5. Apply for the 'Strategy Creator Program'")
    print("6. Sign NDA and MSA agreements")
    print("7. Your strategy will be listed on Odyssey marketplace")
    print("8. Start earning up to 70% revenue share!")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()