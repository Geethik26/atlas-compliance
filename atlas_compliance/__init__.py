"""Atlas deterministic compliance engine."""
from .engine import evaluate_employee
from .rules import load_rules

def load_employees(path):
    from .loader import load_employees as load
    return load(path)

__all__ = ["evaluate_employee", "load_employees", "load_rules"]
