"""The HTTP modules of taxomesh, for an application that has its own web framework.

It has four modules:

- ``schemas``: the pydantic request models, which validate the input;
- ``handlers``: functions that each call one member of the service;
- ``errors``: the mapping from a taxomesh error to an HTTP status and a body;
- ``serializers``: the conversion of rows and graph snapshots to values that JSON can hold.
"""

from taxomesh.contrib.api import errors, handlers, schemas, serializers

__all__ = ["errors", "handlers", "schemas", "serializers"]
