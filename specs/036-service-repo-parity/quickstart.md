# Quickstart: Running Parity Tests

## Run all parity tests (all backends)

```bash
pytest tests/service/test_service_categories.py \
       tests/service/test_service_items.py \
       tests/service/test_service_tags.py \
       tests/service/test_service_graph.py \
       tests/service/test_service_slug.py \
       tests/service/test_service_item_relations.py \
       tests/service/test_service_reorder_reparent.py \
       tests/service/test_service_search.py \
       -v
```

## Run parity tests for a single backend

```bash
# JSON backend only
pytest tests/service/ -v -k "json"

# YAML backend only
pytest tests/service/ -v -k "yaml"

# In-memory backend only (original behavior)
pytest tests/service/ -v -k "in_memory"
```

## Run the full test suite including parity

```bash
pytest --cov=taxomesh --cov-fail-under=80
```

## Expected parity test count

With three backends, the total parametrized test count equals:
```
(original test count) × 3
```

For example, if `test_service_categories.py` had 37 tests, after parity it will
report 111 tests (37 × 3 backends).

## Backend-specific tests (unchanged)

These tests are not affected by the parity change and continue to run as before:

```bash
pytest tests/service/test_json_repository.py       # JSON-specific
pytest tests/service/test_yaml_repository.py       # YAML-specific
pytest tests/service/test_service_config.py        # config/auto-discovery
pytest tests/service/test_service_cache.py         # memoization with mocks
```
