from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dart_xbrl_pipeline.analyzer import run_analysis
from dart_xbrl_pipeline.reporter import save_outputs

result = run_analysis(
    corp_name="하나마이크론",
    corp_code=None,
    date="2026-03-19",
    report_type="annual",
    output_root=Path(__file__).resolve().parent / "data",
)
paths = save_outputs(result, Path(__file__).resolve().parent / "reports")
print(paths)
