"""Process-wide stdio defaults for local CLI/task entry points.

Python imports this module automatically when the app directory is on sys.path.
Keeping stdout/stderr on UTF-8 prevents Windows code pages from crashing when
book text or model output contains Unicode punctuation.
"""

from stdio_utils import configure_utf8_stdio


configure_utf8_stdio()
