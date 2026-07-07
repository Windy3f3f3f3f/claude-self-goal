import importlib.util
import os
from importlib.machinery import SourceFileLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "claude-self-goal")


def load_module():
    loader = SourceFileLoader("csg", TOOL)
    spec = importlib.util.spec_from_loader("csg", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod
