"""python -m sloth_ledger [--model gemma4:12b] [--ollama URL] [--port 8765]"""

import argparse

from . import web

parser = argparse.ArgumentParser(prog="sloth_ledger")
parser.add_argument("--model", default=web.CONFIG["model"])
parser.add_argument("--ollama", default=web.CONFIG["host"])
parser.add_argument("--port", type=int, default=8765)
args = parser.parse_args()
web.CONFIG.update(model=args.model, host=args.ollama)
web.serve(args.port)
