"""Chapter 27: list the app's callbacks — what each one listens to and what it changes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warnings  # noqa: E402
warnings.simplefilter("ignore", DeprecationWarning)
import app  # noqa: E402

for spec in app.app.callback_map.values():
    name = spec["callback"].__name__
    inputs = ", ".join(f"{i['id']}.{i['property']}" for i in spec["inputs"])
    states = ", ".join(f"{s['id']}.{s['property']}" for s in spec["state"])
    outs = spec["output"] if isinstance(spec["output"], list) else [spec["output"]]
    outputs = ", ".join(f"{o.component_id}.{o.component_property}" for o in outs)
    print(f"{name}")
    print(f"  listens to: {inputs}")
    if states:
        print(f"  reads:      {states}")
    print(f"  changes:    {outputs}")
