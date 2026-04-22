import sys
from pathlib import Path

_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tests.fake_hermes import install as _install_hermes_stubs

_install_hermes_stubs()
