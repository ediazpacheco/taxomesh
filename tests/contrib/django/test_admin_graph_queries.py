"""Query-count gates for the admin's two reading graph views.

The point is not that the views are *fast* but that their cost is **constant**: the same
number of queries for 3 top-level categories as for 12, and for 3 items as for 9. A query per
top-level category, or a relation query per item plus one lookup per relation, would make the
cost grow with the page, and no other test would notice: every other test asserts what renders,
never what it cost.

Nothing else gates the admin's query count. ``test_django_placement_queries.py`` gates three
*service* methods against its own corpus and cannot see this file's subject.

The views are called through ``RequestFactory`` rather than ``admin_client`` deliberately:
the figure is then the view's own cost, with no login, session or permission queries folded
in. Every measurement is taken cold: each view builds its own service for the request, and with
it an empty cache, so a second call pays what the first did.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.contrib import admin as dj_admin  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.db import connection  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.template.response import TemplateResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel  # noqa: E402

pytestmark = pytest.mark.django_db

# Two sizes far enough apart that any per-row term is unmissable.
CORPUS_SIZES = (3, 12)

# _ensure_root, the graph loader's four reads, and one scoped link read for the stored
# sort_index values the admin renders.
EXPECTED_GRAPH_QUERIES = 6

# _ensure_root; the scoped child-category and item listings (two reads apiece); the two
# scoped link reads behind the sort maps and the has-descendants flags; and the batched
# relation read (one link query, one bulk item lookup).
EXPECTED_CHILDREN_QUERIES = 10


@dataclass(frozen=True)
class Corpus:
    """A populated store plus what the two views are expected to render from it."""

    holder_id: UUID
    """A top-level category holding ``size`` items, each carrying two outgoing relations."""
    root_names: tuple[str, ...]
    item_names: tuple[str, ...]
    size: int


@pytest.fixture(params=CORPUS_SIZES, ids=lambda n: f"n{n}")
def corpus(request: pytest.FixtureRequest) -> Corpus:
    """Build a corpus of the parametrised size covering both views."""
    size = int(request.param)
    service = TaxomeshService(repository=DjangoRepository())
    root_names: list[str] = []
    holder_id: UUID | None = None

    for i in range(size):
        root = service.categories.create(f"root-{size}-{i}", slug=f"root-{size}-{i}")
        root_names.append(root.name)
        child = service.categories.create(f"child-{size}-{i}", slug=f"child-{size}-{i}")
        service.categories.add_parent(child.category_id, root.category_id)
        if holder_id is None:
            holder_id = root.category_id

    assert holder_id is not None
    item_names: list[str] = []
    for i in range(size):
        item = service.items.create(name=f"item-{size}-{i}")
        item_names.append(item.name)
        service.items.place_in(item.item_id, holder_id, sort_index=i)
        # Distinct targets per item: shared ones would be served from the per-item cache and
        # would hide a per-relation resolution behind it.
        for t in range(2):
            target = service.items.create(name=f"target-{size}-{i}-{t}")
            service.items.relate(item.item_id, target.item_id, "covers")

    return Corpus(
        holder_id=holder_id,
        root_names=tuple(root_names),
        item_names=tuple(item_names),
        size=size,
    )


@pytest.fixture
def admin_user() -> User:
    """A superuser to hang on the request; the views read ``request.user`` for context."""
    return User.objects.create_superuser("graph-queries", "graph-queries@example.com", "x")


def _model_admin() -> CategoryModelAdmin:
    """Return the registered admin carrying the graph views."""
    model_admin = dj_admin.site.get_model_admin(CategoryModel)
    assert isinstance(model_admin, CategoryModelAdmin)
    return model_admin


def render_graph(admin_user: User) -> str:
    """Call ``graph_view`` and return its rendered HTML."""
    request = RequestFactory().get("/graph/")
    request.user = admin_user
    response = _model_admin().graph_view(request)
    assert isinstance(response, TemplateResponse)
    return response.rendered_content


def render_children(admin_user: User, parent_id: UUID) -> str:
    """Call ``graph_children_view`` for one parent and return its HTML fragment."""
    request = RequestFactory().get("/graph/children/", {"parent_uuid": str(parent_id), "depth": "1"})
    request.user = admin_user
    response: HttpResponse = _model_admin().graph_children_view(request)
    return response.content.decode()


def count_queries(call: Callable[[], object]) -> int:
    """Return the number of queries *call* issues.

    Each view builds its own service, and with it an empty cache, so every call is measured cold.
    """
    with CaptureQueriesContext(connection) as ctx:
        call()
    return len(ctx.captured_queries)


# ---------------------------------------------------------------------------
# graph_view
# ---------------------------------------------------------------------------


def test_graph_view_costs_a_constant_number_of_queries(corpus: Corpus, admin_user: User) -> None:
    """The initial graph page must not cost a query for each top-level category."""
    render_graph(admin_user)  # warm Django's own permission cache, outside the measurement
    count = count_queries(lambda: render_graph(admin_user))
    assert count == EXPECTED_GRAPH_QUERIES, (
        f"graph_view issued {count} queries for {corpus.size} top-level categories; expected a constant "
        f"{EXPECTED_GRAPH_QUERIES}. A count near {corpus.size + 4} means one subscript per top-level category."
    )


def test_graph_view_renders_every_display_root(corpus: Corpus, admin_user: User) -> None:
    """Guard against a query count that is constant only because rows went missing."""
    html = render_graph(admin_user)
    missing = [name for name in corpus.root_names if name not in html]
    assert not missing, f"top-level categories absent from the graph page: {missing}"


def test_graph_view_hides_subcategories(corpus: Corpus, admin_user: User) -> None:
    """Only top-level categories are rendered; children arrive through the lazy-load endpoint."""
    html = render_graph(admin_user)
    assert f"child-{corpus.size}-0" not in html, "a subcategory leaked into the initial graph page"


# ---------------------------------------------------------------------------
# graph_children_view
# ---------------------------------------------------------------------------


def test_graph_children_view_costs_a_constant_number_of_queries(corpus: Corpus, admin_user: User) -> None:
    """Expanding a node must not pay per item, nor per relation of each item."""
    render_children(admin_user, corpus.holder_id)  # warm, outside the measurement
    count = count_queries(lambda: render_children(admin_user, corpus.holder_id))
    assert count == EXPECTED_CHILDREN_QUERIES, (
        f"graph_children_view issued {count} queries for {corpus.size} items with 2 relations each; "
        f"expected a constant {EXPECTED_CHILDREN_QUERIES}. A count near {8 + corpus.size * 3} means "
        "per-item relation reads and per-relation subscripts are back."
    )


def test_graph_children_view_renders_every_item(corpus: Corpus, admin_user: User) -> None:
    """Guard against a query count that is constant only because rows went missing."""
    html = render_children(admin_user, corpus.holder_id)
    missing = [name for name in corpus.item_names if name not in html]
    assert not missing, f"items absent from the children fragment: {missing}"


def test_graph_children_view_renders_relation_targets(corpus: Corpus, admin_user: User) -> None:
    """The batched relation read must still produce the rows the fragment renders."""
    html = render_children(admin_user, corpus.holder_id)
    assert "covers" in html, "the relation type must appear in the fragment"
    assert f"target-{corpus.size}-0-0" in html, "the relation target's name must appear in the fragment"
