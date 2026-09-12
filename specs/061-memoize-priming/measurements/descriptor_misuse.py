"""Deliberate misuse: every line below must be a mypy error."""

from descriptor_proto import Service

svc = Service()
svc.get_category.prime(123, 7)          # wrong value type: int where str expected
svc.get_category.prime("x", "seven")    # wrong key type: str where int expected
svc.get_category("seven")               # wrong argument type on the call itself
n: int = svc.get_category(7)            # wrong return type
