"""
Convenience runner — executes the full trading system pipeline.

Usage:
    python run.py
    python run.py --symbols "RELIANCE.NS,TCS.NS" --start 2020-01-01
"""
from trading_system.main import main

if __name__ == "__main__":
    main()
