# app package
import sys
from pathlib import Path

# Auto-detect project virtual environments and inject their site-packages
# into sys.path so the application runs seamlessly even if invoked from
# an un-activated shell or system python interpreter.
_ROOT = Path(__file__).resolve().parent.parent
_CANDIDATE_SITE_PACKAGES = [
    _ROOT / "venv" / "Lib" / "site-packages",
    _ROOT / ".venv" / "Lib" / "site-packages",
    _ROOT.parent / "venv" / "Lib" / "site-packages",
    _ROOT.parent / ".venv" / "Lib" / "site-packages",
]

for _site in _CANDIDATE_SITE_PACKAGES:
    if _site.exists() and str(_site) not in sys.path:
        sys.path.insert(0, str(_site))

