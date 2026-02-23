from pathlib import Path
import os

ROOT = Path(r"C:\Fireant\Fireant Data")

def head_bytes(p: Path, n=256):
    with open(p, "rb") as f:
        return f.read(n)

def main():
    if not ROOT.exists():
        print("Path not found:", ROOT)
        return

    files = [p for p in ROOT.rglob("*") if p.is_file()]
    print("Total files:", len(files))

    # top extensions
    ext_count = {}
    for p in files:
        ext = p.suffix.lower()
        ext_count[ext] = ext_count.get(ext, 0) + 1
    print("\nTop extensions:")
    for ext, cnt in sorted(ext_count.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"{cnt:>8}  {ext or '(no ext)'}")

    # latest 10 files
    files_sorted = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    print("\nLatest 10 files:")
    for p in files_sorted[:10]:
        st = p.stat()
        print(f"{p} | {st.st_size} bytes")

    # probe first 3 latest files
    print("\nProbe latest files (first 64 bytes hex + ascii hint):")
    for p in files_sorted[:3]:
        b = head_bytes(p, 64)
        hexs = b.hex()
        if len(hexs) > 200:
            hexs = hexs[:200] + "..."
        asci = "".join(chr(x) if 32 <= x <= 126 else "." for x in b)
        print("\nFILE:", p)
        print("HEX :", hexs)
        print("ASCII:", asci)

if __name__ == "__main__":
    main()
