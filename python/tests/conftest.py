"""Test settings for the working repository.

Volume 1 is published, and its companion repository (learning-ai-from-zero-volume1) keeps the deal pack
the printed book describes: the 9-page prospectus and the simple CSV and JSON files. Its tests run there.
This repository now holds Volume 2's deal pack (the full prospectuses and the files in the formats the
parties send), so the Volume 1 tests are not collected here.
"""

collect_ignore_glob = ["test_vol1_*.py"]
