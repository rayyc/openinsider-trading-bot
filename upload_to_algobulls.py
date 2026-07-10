# upload_to_algobulls_correct.py
# ============================================================
# CORRECT UPLOAD METHOD FOR ALGOBULLS
# ============================================================

import os
import sys
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('ALGOBULLS_API_TOKEN')
STRATEGY_FILE = 'strategy_openinsider_bot.py'


def main():
    print("\n" + "=" * 60)
    print("🚀 UPLOADING STRATEGY TO ALGOBULLS (CORRECT METHOD)")
    print("=" * 60 + "\n")

    # Step 1: Import the strategy class
    print("Step 1: Loading strategy class...")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("strategy_openinsider_bot", STRATEGY_FILE)
        module = importlib.util.module_from_spec(spec)
        # Register in sys.modules BEFORE executing it. AlgoBulls' create_strategy()
        # calls inspect.getsource() internally, which looks the module up in
        # sys.modules to find its file on disk. Without this line, inspect can't
        # find it and raises a misleading "<class ...> is a built-in class" error.
        sys.modules["strategy_openinsider_bot"] = module
        spec.loader.exec_module(module)

        strategy_class = getattr(module, 'StrategyOpenInsiderBot', None)

        if not strategy_class:
            print("❌ Could not find StrategyOpenInsiderBot class in the file")
            return False

        print(f"✓ Found strategy class: {strategy_class.__name__}")
        print(f"   Strategy name (from class attribute): {getattr(strategy_class, 'name', 'NOT SET')}\n")

    except Exception as e:
        print(f"❌ Failed to load strategy: {e}")
        return False

    # Step 2: Connect to AlgoBulls
    print("Step 2: Connecting to AlgoBulls...")
    try:
        from pyalgotrading.algobulls import AlgoBullsConnection
        connection = AlgoBullsConnection()
        connection.set_access_token(API_TOKEN)
        print("✓ Connected successfully\n")

    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

    # Step 3: Create the strategy on AlgoBulls
    # NOTE: create_strategy() only accepts (strategy_cls, overwrite=True).
    # The strategy's display name/description come from the `name` class
    # attribute inside strategy_openinsider_bot.py itself, NOT from kwargs here.
    print("Step 3: Creating strategy on AlgoBulls...")
    try:
        response = connection.create_strategy(strategy_class, overwrite=True)
        strategy_id = response['strategyId']
        print(f"✓ Strategy created successfully!")
        print(f"   Strategy ID: {strategy_id}\n")

    except Exception as e:
        print(f"❌ Create strategy failed: {e}")
        print("\n⚠️  Falling back to web interface method...")
        return web_interface_fallback()

    # Step 4: Verify
    # get_all_strategies() returns a pandas DataFrame, not a list of dicts.
    print("Step 4: Verifying upload...")
    try:
        strategies = connection.get_all_strategies()
        print(f"✓ Found {len(strategies)} strategies in your account")

        # Handle both possible return types defensively, since pyalgotrading's
        # exact return shape has changed across versions.
        if hasattr(strategies, "iterrows"):  # pandas DataFrame
            cols = strategies.columns.tolist()
            name_col = next((c for c in ('name', 'strategyName') if c in cols), None)
            id_col = next((c for c in ('strategyCode', 'strategyId', 'id') if c in cols), None)
            for idx, (_, row) in enumerate(strategies.head(5).iterrows(), 1):
                name = row[name_col] if name_col else 'Unnamed'
                sid = row[id_col] if id_col else 'N/A'
                print(f"   {idx}. {name} (ID: {sid})")
        else:  # list of dicts fallback
            for idx, s in enumerate(strategies[:5], 1):
                name = s.get('name', 'Unnamed')
                sid = s.get('id', s.get('strategyId', 'N/A'))
                print(f"   {idx}. {name} (ID: {sid})")

    except Exception as e:
        print(f"⚠️  Could not verify (upload itself likely still succeeded): {e}")

    print("\n" + "=" * 60)
    print("✅ UPLOAD COMPLETE!")
    print("=" * 60)
    return True


def web_interface_fallback():
    """Fallback instructions for web interface upload."""
    print("\n" + "=" * 60)
    print("📋 MANUAL UPLOAD INSTRUCTIONS")
    print("=" * 60)
    print("\nPlease upload your strategy using the web interface:")
    print("1. Go to https://algobulls.com")
    print("2. Log in to your account")
    print("3. Navigate to 'My Coded Strategies'")
    print("4. Click 'Create New Strategy'")
    print("5. Fill in the details:")
    print("   - Name: OpenInsider Multi-Layer Bot")
    print("   - Type: Python Strategy")
    print("6. Copy and paste the code from strategy_openinsider_bot.py")
    print("7. Click 'Save'")
    print("8. Run backtest to validate")
    print("9. Apply for Strategy Creator Program")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)