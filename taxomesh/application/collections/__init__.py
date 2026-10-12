"""taxomesh.application.collections: the collection of each kind of entity.

The three collections are reached as ``service.categories``, ``service.items`` and
``service.tags``, and are **never constructed directly**. This package re-exports nothing, for that
reason: an import for convenience would offer a way to construct a collection, and that way is
wrong, not only discouraged. The memoized reads are in the service's cache, which the service gives
to each collection that it builds. A collection built in another way has a cache of its own, and
finds no entry that the service's collections primed.
"""
