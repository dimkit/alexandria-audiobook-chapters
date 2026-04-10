import json
import os
import sys

from stdio_utils import configure_utf8_stdio
from script_repair import repair_chapter_headings_only

configure_utf8_stdio()

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        result = repair_chapter_headings_only(root_dir)
    except Exception as e:
        print(json.dumps({"status": "error", "detail": str(e)}, ensure_ascii=False))
        return 1

    print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
