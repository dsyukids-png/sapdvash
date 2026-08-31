import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(ROOT, "project_root")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.chdir(PROJECT_ROOT)
runpy.run_path(os.path.join(PROJECT_ROOT, "main.py"), run_name="__main__")
