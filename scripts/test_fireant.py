from datetime import date, timedelta
from src.intake.fireant_historical import fetch_historical, latest_close

def main():
    end = date.today()
    start = end - timedelta(days=60)
    s, e = start.isoformat(), end.isoformat()

    # Test 1: HOSTC (the sample symbol in public examples)
    print("HOSTC latest close:", latest_close("HOSTC", s, e))

    # Test 2: try VNINDEX-like symbols you use in Ami (you may need to discover the right one)
    for sym in ["VNINDEX", "VNI", "^VNINDEX", "VN-INDEX"]:
        try:
            v = latest_close(sym, s, e)
            print(sym, "=>", v)
        except Exception as ex:
            print(sym, "=> ERROR:", type(ex).__name__)

if __name__ == "__main__":
    main()
