"""Framework-agnostic HTTP handler modules for taxomesh.

Exposes four modules:
- schemas: Pydantic request models for input validation
- handlers: Pure functions that delegate to TaxomeshService
- errors: Exception-to-HTTP-status mapping utilities
- serializers: Graph-to-dict serialization utilities for HTTP responses
"""

from taxomesh.contrib.api import errors, handlers, schemas, serializers

__all__ = ["errors", "handlers", "schemas", "serializers"]
