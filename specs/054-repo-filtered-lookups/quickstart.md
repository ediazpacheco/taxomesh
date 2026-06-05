# Quickstart: Repository-Level Filtered Lookups (054)

## What changes for library consumers

Nothing in observable behavior — this is a pure performance release. The four
hot read paths stop materializing full tables:

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()  # any backend

# All of these now issue filtered repository queries instead of full scans:
svc.list_related_items_for_sources([album.item_id])     # only referenced items fetched
svc.list_categories_by_item(album.item_id)              # only that item's links fetched
svc.list_items(category_id=jazz.category_id)            # only that category's links fetched
svc.search_items("tango", category_id=root, recursive=True)  # subtree links + matched items only
```

## What changes for custom-backend authors

`TaxomeshRepositoryBase` (structural Protocol) grew — custom repositories
need two updates to stay compliant:

```python
def get_items_by_ids(
    self, item_ids: Collection[UUID], *, enabled: bool | None = None
) -> dict[UUID, Item]:
    """Bulk fetch by internal ID. Missing IDs silently absent."""

def list_item_parent_links(
    self, *, item_id: UUID | None = None, category_ids: Collection[UUID] | None = None
) -> list[ItemParentLink]:
    """Existing method — now accepts optional filters (None = unfiltered, as before).
    Empty category_ids collection returns [] (NOT a full listing)."""
```

mypy --strict flags non-compliant repositories at the `TaxomeshService(...)`
construction site.

## Verifying locally

```bash
# Contract tests, 4 backends. test_parity_fixture.py must be included: running a
# django-param file standalone hits a pre-existing pytest-django quirk where
# getfixturevalue("db") alone does not create the test database — a
# @pytest.mark.django_db test (the parity smoke) must run first.
pytest tests/service/test_parity_fixture.py tests/service/test_repo_filtered_lookups.py

pytest tests/service/test_service_no_full_scan.py    # spy-repo: no full scans in the 4 paths (InMemory-backed, standalone-safe)
pytest                                                # full parity suite
ruff check . && ruff format --check . && mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

## Upgrading (letrastango)

```toml
# pyproject.toml
taxomesh == 0.1.0a42   # was 0.1.0a40
```

No code changes required in the consumer.
