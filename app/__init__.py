"""App package init — runs before any submodule import.

pydub probes the system PATH for ffmpeg at import time and warns if not found.
We point it at the bundled ffmpeg later (app.core.media), so that warning is
noise — silence it before anything imports pydub.
"""

import warnings

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")
