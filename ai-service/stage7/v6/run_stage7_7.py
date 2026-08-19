"""Stage 7.7 -- V6 Dataset Redesign Orchestrator.

Execute the main V6 redesign pipeline and print the final summary.
No production writes. Fully reproducible (seed=42).
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "stage7_7_v6_dataset_redesign.py"


def main():
    print("=" * 60)
    print("STAGE 7.7 -- V6 DATASET REDESIGN")
    print("Running full pipeline...")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=False,
        text=True,
        cwd=str(SCRIPT.resolve().parents[2]),
    )

    if result.returncode != 0:
        print(f"\nPIPELINE FAILED (exit code {result.returncode})")
        sys.exit(result.returncode)

    # Read and print final metadata
    meta_path = SCRIPT.parent / "stage7_7_metadata.json"
    if meta_path.exists():
        import json
        meta = json.loads(meta_path.read_text())
        print("\n" + "=" * 60)
        print("ORCHESTRATOR -- FINAL SUMMARY")
        print("=" * 60)
        print(f"Decision: {meta.get('decision', 'UNKNOWN')}")
        print(f"Outputs:  {len(meta.get('outputs', []))} files")
        print(f"Production integrity: {meta.get('production_integrity', 'UNKNOWN')}")
        print("=" * 60)


if __name__ == "__main__":
    main()
