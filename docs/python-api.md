# Python API Reference

`TaxomeshService` is the only class you construct. You reach everything else through it: three
collections (`svc.categories`, `svc.items`, `svc.tags`), a graph snapshot (`svc.graph(...)`), and two
properties (`svc.info`, `svc.repository`). One law covers the three collections and the graph:

> **Subscript raises. Anything named `get*` never does.**

Every parameter that names a category, an item or a tag takes the row itself or its `UUID`, as a
path parameter takes a `str` or an `os.PathLike`: `svc.items.place_in(song, jazz)` and
`svc.items.place_in(song.item_id, jazz.category_id)` are one call. The parameters are typed
`CategoryRef`, `ItemRef` and `TagRef`. Only a row's identifier is read, so a row you hold that has
since been updated still addresses the stored one. Anything else, a row of another kind included,
raises `TypeError` before storage is read. A batch lookup takes one key or a collection of them, as
`str.startswith` takes one prefix or a tuple: `svc.items.get_many(song)` is
`svc.items.get_many([song])`.

The tables below give each signature once, without types; [`llms.txt`](../llms.txt) has every
signature with its types, and `help()` shows each member's docstring. The models are Pydantic v2
models, and the package passes `mypy --strict` and ships `py.typed`, so your type checker reads its
annotations. Every example on this page runs, in order, in the test suite.

## The worked example

Every example below runs against the taxonomy built here.

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()  # the taxomesh.toml in the working directory, else a YAML file in ./data/

music = svc.categories.create(name="Music", slug="music", external_id="cat:music")
jazz = svc.categories.create(name="Jazz", slug="jazz", external_id="cat:jazz")
blues = svc.categories.create(name="Blues", slug="blues", external_id=7)
svc.categories.add_parent(jazz, music, sort_index=10)
svc.categories.add_parent(blues, music, sort_index=20)

kob = svc.items.create(name="Kind of Blue", external_id=42, slug="kind-of-blue")
steps = svc.items.create(name="Giant Steps", external_id="catalog:99", slug="giant-steps")
birth = svc.items.create(name="Birth of the Cool", slug="birth-of-the-cool")
svc.items.place_in(kob, jazz, sort_index=0)
svc.items.place_in(steps, jazz, sort_index=1)
svc.items.place_in(birth, blues, sort_index=0)

assert [c.name for c in svc.categories.list(parent=music)] == ["Jazz", "Blues"]
assert [i.name for i in svc.items.list(category=jazz)] == ["Kind of Blue", "Giant Steps"]
```

## The container law

The forms below are shared by the three collections. Only the error differs:
`TaxomeshCategoryNotFoundError`, `TaxomeshItemNotFoundError` or `TaxomeshTagNotFoundError`, each a
`KeyError`.

| Form | Returns | On a miss |
|---|---|---|
| `coll[key]` | the row | raises `Taxomesh<X>NotFoundError` |
| `coll.get(key, default=None, /)` | the row | `default` |
| `key in coll` | `bool` | `False` |
| `len(coll)` | `int`, every stored row | `0` |
| `del coll[key]` | `None` | raises |

A member named `list*` or `search` returns a `Sequence`, which is a tuple, and one named
`get_many*` a `Mapping`, which is a new dict on every call; a key that finds nothing is left out of
it. `get_by_slug` and `get_by_external_id` return the row or `None`.

A collection does not iterate ([why](design.md#the-law-subscript-raises-get-never-does)): `iter()`
and `reversed()` raise `TypeError`, and `coll.list(...)` enumerates. `len()` is the one form that
reads every row: it counts disabled rows too, so it is not `len(coll.list())`.

```python
from uuid import uuid4

missing = uuid4()  # no row has this identifier; reused below

assert svc.categories[music.category_id] == svc.categories[music]
assert svc.categories.get(missing) is None
assert svc.categories.get(missing, "no such category") == "no such category"
assert music in svc.categories and missing not in svc.categories
try:
    svc.categories[missing]
except KeyError:  # TaxomeshCategoryNotFoundError
    pass
else:
    raise AssertionError("subscript must raise")

retired = svc.categories.create(name="Retired")
svc.categories.update(retired, enabled=False)
assert len(svc.categories) == 4  # every stored row
assert len(svc.categories.list()) == 3  # a listing keeps the enabled rows by default

for builtin in (iter, reversed):
    try:
        builtin(svc.categories)
    except TypeError:
        pass
    else:
        raise AssertionError("a collection does not iterate")
```

## Rows are values

A row never changes in place. The seven models are frozen: assigning to a field raises pydantic's
`ValidationError`, a `ValueError`. `metadata` is frozen all the way down: its dicts and lists raise
`TypeError` on any change. `update` stores a new row and returns it, one `version` higher, and a
row read before it keeps the values it was read with. A row carrying `metadata` is not hashable.

```python
held = svc.categories[music]
try:
    held.name = "Musica"
except ValueError:
    pass
else:
    raise AssertionError("a row refuses assignment")
try:
    held.metadata["era"] = "any"
except TypeError:
    pass
else:
    raise AssertionError("metadata refuses a change in place")

tagged = svc.categories.update(music, metadata={**held.metadata, "era": "any"})
assert (held.metadata, tagged.metadata) == ({}, {"era": "any"})
assert tagged.version == held.version + 1
svc.categories.update(music, metadata={})
```

A row carries data and no behaviour. What you do with it is a member of its collection,
`svc.categories.update(row, …)`; what it is connected to is on the graph's node,
`svc.graph()[row].parents`. `help(Category)` says what this table does, under `Attributes:`.

| Field | Type | Of | Meaning | Set by |
|---|---|---|---|---|
| `category_id` · `item_id` · `tag_id` | `UUID` | each its own | the identifier | `create` |
| `name` | `str` | all three | at most 256 characters (`MAX_CATEGORY_NAME_LENGTH`, `MAX_ITEM_NAME_LENGTH`), a tag's 25 (`MAX_TAG_NAME_LENGTH`); `__root__` is reserved | you |
| `description` | `str` | Category | free text, `""` unless given | you |
| `slug` | `str` | Category, Item | a URL-friendly key, unique within its kind; `""` is no slug | you |
| `external_id` | `str \| None` | Category, Item | your system's key, unique within its kind | you |
| `enabled` | `bool` | Category, Item | `False` leaves the row out of what a member finds, by default | you |
| `metadata` | `dict` | all three | plain JSON, frozen | you |
| `created_at` · `updated_at` | `datetime` | Category, Item | stamped by `create`; `update` moves `updated_at`; 1970 on a row stored without them | `create`, `update` |
| `version` | `int` | Category, Item | 0 at `create`, one higher per `update` | storage |

A link joins two entities, and the member named beside it stores it. `sort_index` is a position,
lower first: among a parent's children or a category's items, as `reorder` and `move` set it, and
among an item's relations.

| Link | Fields | Stored by |
|---|---|---|
| `CategoryParentLink` | `category_id`, `parent_category_id`, `sort_index` | `categories.add_parent` |
| `ItemParentLink` | `item_id`, `category_id`, `sort_index` | `items.place_in` |
| `ItemRelationLink` | `source_item_id`, `target_item_id`, `relation_type`, `sort_index`, `metadata` | `items.relate` |
| `ItemTagLink` | `tag_id`, `item_id` | `items.tag` |

## External ids

An external id binds a category or an item to the record it stands for in your system. It is
given as `ExternalId`, `str | int | UUID | None`, and stored as its `str()`, by one rule shared by
writes and lookups. So what comes back is a `str`; values with one string form, such as `42` and
`"42"`, are one external id; and since external ids are unique within a kind, creating both raises
`TaxomeshExternalIdConflictError`. `None` means no external id, and a lookup for it reads nothing.
Nothing else is cleaned: whitespace, case and the empty string are part of the external id.

```python
from uuid import UUID

from taxomesh import TaxomeshExternalIdConflictError

assert blues.external_id == "7"
assert svc.categories.get_by_external_id(7).category_id == blues.category_id  # no str() needed

release = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
keyed = svc.items.create(name="UUID keyed", external_id=release)
assert keyed.external_id == "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
assert svc.items.get_by_external_id(str(release)).item_id == keyed.item_id  # one row, not two
assert svc.items.get_by_external_id("6BA7B810-9DAD-11D1-80B4-00C04FD430C8") is None  # another external id
try:
    svc.items.create(name="Same row", external_id=str(release))
except TaxomeshExternalIdConflictError:
    pass
else:
    raise AssertionError("a UUID and its text are one external id")
del svc.items[keyed]
```

## The enabled filter

`enabled` is `True` (enabled rows only), `False` (disabled only) or `None` (all). A member that
finds rows, `list`, `roots`, `search`, `list_related`, `get_many_related` and `svc.graph()`,
defaults to `True`. A member handed the keys, `get_many` and `get_many_by_external_id`, defaults to
`None`, as subscript, `get`, `in` and `len` do not filter at all. `update(enabled=…)` sets the field
and is not a filter. `Tag` has no `enabled` field, so no tag member takes one.

```python
assert sorted(c.name for c in svc.categories.list(enabled=None)) == ["Blues", "Jazz", "Music", "Retired"]
assert [c.name for c in svc.categories.list(enabled=False)] == ["Retired"]
assert set(svc.categories.get_many([retired])) == {retired.category_id}
assert svc.categories.get_many([retired], enabled=True) == {}
assert svc.categories[retired].name == "Retired"
```

## The top level

A category is at the top level exactly when it has no parent. `roots()` lists the top level, in
the same order as `svc.graph().roots`, and `None` stands for it in `move` and `reorder`. `create`
puts a category there, `add_parent` takes it off, and losing its last parent puts it back. Storage
holds the top level as links to the implicit root, which no signature needs: its identifier answers
not-found wherever a member takes a category.

```python
assert [c.name for c in svc.categories.roots()] == ["Music"]
assert [n.category.name for n in svc.graph().roots] == ["Music"]
```

---

# `svc.categories`

| Member | Returns | Does |
|---|---|---|
| `create(name, *, description="", slug="", external_id=None, metadata=None)` | `Category` | Creates a category at the top level |
| `update(category, *, name, description, slug, external_id, enabled, metadata, expected_version=None)` | `Category` | Stores a new row with the fields given |
| `delete(key, /)` | `None` | Deletes it, and every link that names it |
| `get_by_slug(slug, /)` | `Category \| None` | The category with that slug; `""` is no slug |
| `get_by_external_id(external_id, /)` | `Category \| None` | The category with that external id |
| `get_many(categories, /, *, enabled=None)` | `Mapping[UUID, Category]` | The categories found, in one read |
| `get_many_by_external_id(external_ids, /, *, enabled=None)` | `Mapping[str, Category]` | The same, keyed by stored external id |
| `list(*, parent=None, item=None, enabled=True)` | `Sequence[Category]` | Every category; or a parent's children; or an item's categories |
| `roots(*, enabled=True)` | `Sequence[Category]` | The top level |
| `search(query, *, limit=20, parent=None, enabled=True, fuzzy=True)` | `Sequence[Category]` | Ranked matches: see [Search](#search) |
| `add_parent(category, parent, *, sort_index=0)` | `CategoryParentLink` | Adds a parent, keeping the others |
| `remove_parent(category, parent)` | `None` | Removes one parent |
| `move(category, *, from_parent, to_parent, before=None)` | `None` | Moves it from one parent to another |
| `reorder(parent, categories)` | `None` | Orders a parent's children, or the top level |

## Writing

`create` refuses a slug or an external id another category holds
(`TaxomeshDuplicateSlugError`, `TaxomeshExternalIdConflictError`), and the reserved name
`__root__` (`TaxomeshRootCategoryError`). `taxomesh.domain.constants` names each limit: a name is at
most `MAX_CATEGORY_NAME_LENGTH` (256) characters, a description `MAX_DESCRIPTION_LENGTH` (100,000).

`update` leaves every field it is not given: each defaults to `UNSET`. It builds on the row as
stored, never on a cached copy, so it keeps a change another service made. `external_id=None` clears
the external id; `None` for any other field is the wrong type and raises `TypeError`. `metadata` is
replaced, never merged, and it is plain JSON: dicts with text keys, lists or tuples, text, finite
numbers, booleans and `None`; a tuple is taken as a list, and an enum member as its value. Anything
else, such as a `datetime` or a `UUID`, raises `TaxomeshValidationError`. Every check comes before
the save, so a refused update stores nothing. `expected_version` makes the update conditional: pass
the `version` of the row you read, and if a write has stored a newer row since, the update raises
`TaxomeshVersionConflictError` and stores nothing. The repository compares and writes in one step,
so two writers holding one version cannot both succeed, through one repository on a file or across
processes on Django; read the row again and retry with its version.

`delete` takes the category's links with it, in the same write, on every backend: its links to
its parents and children, and the placements of the items in it. The items and child categories
stay stored.

```python
from taxomesh import TaxomeshValidationError, TaxomeshVersionConflictError

soul = svc.categories.create(name="Soul", slug="soul", external_id="cat:soul", description="Soul music")
renamed = svc.categories.update(soul, name="Soul Music")
assert renamed.description == "Soul music"  # not given, so left as it is
assert svc.categories.update(soul, external_id=None).external_id is None  # None clears it
try:
    svc.categories.update(soul, name=None)
except TypeError:
    pass
else:
    raise AssertionError("None is not a name")
try:
    svc.categories.update(soul, name="Soul", expected_version=renamed.version)
except TaxomeshVersionConflictError:
    pass  # the external id was cleared since
else:
    raise AssertionError("a stale version is refused")
svc.categories.update(soul, enabled=False)  # disabled from here on

doomed = svc.categories.create(name="Doomed")
svc.items.place_in(kob, doomed)
del svc.categories[doomed]  # svc.categories.delete(doomed) is the same
assert [c.name for c in svc.categories.list(item=kob)] == ["Jazz"]  # the placement went too
```

## Reading

`list(parent=…)` orders the children by their sort index under that parent, and `list(item=…)`
the item's categories by the sort index of each placement. Unfiltered, `list()` holds every
category `enabled` keeps, in no promised order, since a sort index orders a category within one
parent only. The two filters reach different reads, so passing both raises
`TaxomeshValidationError`. A filter naming an entity that is not stored raises the not-found error
of that entity: it is a wrong address, not a miss. `roots()` orders the top level by sort index,
then by identifier.

```python
from taxomesh import TaxomeshCategoryNotFoundError

assert svc.categories.get_by_slug("jazz").category_id == jazz.category_id
assert svc.categories.get_by_slug("") is None
assert set(svc.categories.get_many([jazz, blues.category_id, missing])) == {jazz.category_id, blues.category_id}
assert sorted(svc.categories.get_many_by_external_id([7, "cat:music", None, "cat:404"])) == ["7", "cat:music"]
assert [c.name for c in svc.categories.list(item=kob)] == ["Jazz"]

for wrong, error in ((dict(parent=missing), TaxomeshCategoryNotFoundError), (dict(parent=music, item=kob), ValueError)):
    try:
        svc.categories.list(**wrong)
    except error:
        pass
    else:
        raise AssertionError(f"list({wrong}) must raise")
```

## Parents and order

`add_parent` adds: the category keeps the parents it had. A link that would close a cycle raises
`TaxomeshCyclicDependencyError`. `remove_parent` removes one link and is a no-op when there is
none. `move` removes the link to `from_parent`, when there is one, and adds `to_parent`, before the
sibling `before` or last; `to_parent=None` raises `TaxomeshValidationError` while the category keeps
another parent. Every check runs before the first write, so a refused move changes nothing.

`reorder` gives the categories passed positions 0, 1, 2… in that order. Pass every child: one left
out keeps its position, which another may then share. A category that is not a child of that
parent raises `TaxomeshValidationError`.

```python
from taxomesh import TaxomeshCyclicDependencyError

svc.categories.add_parent(blues, jazz, sort_index=5)
assert [c.name for c in svc.categories.list(parent=jazz)] == ["Blues"]
assert [c.name for c in svc.categories.list(parent=music)] == ["Jazz", "Blues"]  # both parents
try:
    svc.categories.add_parent(music, jazz)
except TaxomeshCyclicDependencyError:
    pass
else:
    raise AssertionError("a cycle is refused")
svc.categories.remove_parent(blues, jazz)
svc.categories.remove_parent(blues, jazz)  # no such link: a no-op

svc.categories.move(blues, from_parent=music, to_parent=None)
assert {c.name for c in svc.categories.roots()} == {"Music", "Blues"}
svc.categories.move(blues, from_parent=None, to_parent=music)
assert [c.name for c in svc.categories.list(parent=music)] == ["Jazz", "Blues"]

svc.categories.reorder(music, [blues, jazz])
assert [c.name for c in svc.categories.list(parent=music)] == ["Blues", "Jazz"]
svc.categories.reorder(music, [jazz, blues])
try:
    svc.categories.reorder(music, [soul])
except TaxomeshValidationError:
    pass
else:
    raise AssertionError("Soul is not a child of Music")
```

---

# `svc.items`

| Member | Returns | Does |
|---|---|---|
| `create(name, *, slug="", external_id=None, metadata=None)` | `Item` | Creates an item |
| `update(item, *, name, slug, external_id, enabled, metadata, expected_version=None)` | `Item` | Stores a new row with the fields given, as `categories.update` |
| `delete(key, /)` | `None` | Deletes it, with its placements, tags and relations |
| `get_by_slug(slug, /)` | `Item \| None` | The item with that slug; `""` is no slug |
| `get_by_external_id(external_id, /)` | `Item \| None` | The item with that external id |
| `get_many(items, /, *, enabled=None)` | `Mapping[UUID, Item]` | The items found, in one read |
| `get_many_by_external_id(external_ids, /, *, enabled=None)` | `Mapping[str, Item]` | The same, keyed by stored external id |
| `list(*, category=None, recursive=False, tag=None, enabled=True)` | `Sequence[Item]` | Every item; or a category's; or a tag's; or both |
| `search(query, *, limit=20, category=None, recursive=False, enabled=True, fuzzy=True)` | `Sequence[Item]` | Ranked matches: see [Search](#search) |
| `place_in(item, category, *, sort_index=0)` | `ItemParentLink` | Places it in a category, or sets the sort index of that placement |
| `remove_from(item, category)` | `None` | Removes one placement |
| `move(item, *, from_category, to_category, before=None)` | `ItemParentLink` | Moves one placement |
| `reorder(category, items)` | `None` | Orders the items placed in a category |
| `tag(item, tag)` · `untag(item, tag)` | `None` | Tags an item, or removes a tag from it |
| `relate(source, target, relation_type, *, sort_index=0, metadata=None)` | `ItemRelationLink` | Stores a directed, typed relation, or updates that one |
| `unrelate(source, target, relation_type)` | `None` | Removes one relation |
| `list_relations(item, *, relation_types=None, direction="outgoing")` | `Sequence[ItemRelationLink]` | The item's relation links |
| `list_related(item, *, relation_types=None, direction="outgoing", enabled=True)` | `Sequence[Item]` | The items at the other end, in link order |
| `get_many_related(items, /, *, relation_types=None, direction="outgoing", enabled=True)` | `Mapping[UUID, RelatedItems]` | The same for many items, in two storage reads |

## Writing and reading

`create`, `update` and `delete` keep the rules of their category namesakes. Unfiltered, `list()`
orders the items by name, then by identifier. `list(category=…)` orders them by the sort index of
their placement; with `recursive=True` it takes the category's descendants in too, each item once,
in depth-first order. `list(tag=…)` orders the tagged items by name, then by identifier; beside
`category`, it keeps the category listing's order and only the tagged items. A filter naming an
entity that is not stored raises its not-found error.

```python
blue_train = svc.items.create(name="Blue Train", external_id=7001, metadata={"year": 1958})
assert svc.items.update(blue_train, name="Blue Train (mono)").external_id == "7001"
del svc.items[blue_train]
assert blue_train not in svc.items

assert svc.items.get_by_slug("kind-of-blue").item_id == kob.item_id
assert svc.items.get_by_external_id(42).item_id == kob.item_id
assert set(svc.items.get_many([kob, missing])) == {kob.item_id}
assert sorted(svc.items.get_many_by_external_id([42, "catalog:99", None, " 42"])) == ["42", "catalog:99"]

assert svc.items.list(category=music) == ()  # nothing is placed in Music itself
recursive = svc.items.list(category=music, recursive=True)
assert [i.name for i in recursive] == ["Kind of Blue", "Giant Steps", "Birth of the Cool"]
```

## Placement, order and tags

An item may be placed in any number of categories. `place_in` again sets the sort index of that
placement rather than adding a second one; `remove_from`, `untag` and `unrelate` are no-ops when
there is nothing to remove, and `tag` when the tag is already there. `reorder` works as it does for
categories, and refuses an item not placed in that category.

```python
svc.items.place_in(kob, blues, sort_index=9)
assert sorted(c.name for c in svc.categories.list(item=kob)) == ["Blues", "Jazz"]
svc.items.remove_from(kob, blues)
svc.items.remove_from(kob, blues)  # a no-op the second time

svc.items.move(steps, from_category=jazz, to_category=blues)
assert [i.name for i in svc.items.list(category=blues)] == ["Birth of the Cool", "Giant Steps"]
svc.items.move(steps, from_category=blues, to_category=jazz)
svc.items.reorder(jazz, [steps, kob])
assert [i.name for i in svc.items.list(category=jazz)] == ["Giant Steps", "Kind of Blue"]
svc.items.reorder(jazz, [kob, steps])

live = svc.tags.create(name="live")
svc.items.tag(steps, live)
svc.items.tag(birth, live)
svc.items.tag(birth, live)  # already tagged: a no-op
assert [i.name for i in svc.items.list(tag=live)] == ["Birth of the Cool", "Giant Steps"]
assert [i.name for i in svc.items.list(category=music, recursive=True, tag=live)] == ["Giant Steps", "Birth of the Cool"]
svc.items.untag(steps, live)
del svc.tags[live]  # removed from Birth of the Cool too
```

## Relations

A relation is directed and typed: `relate(source, target, relation_type)`. Its type is your own
label, stripped and lowercased on write and on lookup alike, so a filter on `["COVERS"]` matches
`"covers"`; a blank type or a self-relation raises `TaxomeshRelationError`. Each read takes a
`direction`: `"outgoing"` (the default) where the item is the source, `"incoming"` where it is the
target, or `"both"`, which returns each stored link once. `Direction.BOTH` and `"both"` are the same
argument. When an item can be at either end of a relation, read its relations with `"both"`:
`"outgoing"` leaves out the links that point at the item. A relation stored in both directions is
two links, and `"both"` returns the two. `relation_types` takes one type or a collection of them,
and `None`, or an empty one, reads every type.

`list_related` and `get_many_related` filter the related items by `enabled`, and skip, with one
`WARNING` from the `taxomesh.application.collections.items` logger, a relation whose other end is
not stored. In `get_many_related` the queried items are keys: one with no matching relation, or not
stored, is left out. Each value is a `RelatedItems`:

| Member | Returns |
|---|---|
| `item_id` · `by_type` | the queried item's `UUID` · its related items per relation type, each a tuple |
| `of_type(t)` | that type's items, `()` for a type not present; `t` is stripped and lowercased |
| `relation_types` | the types present, sorted |
| `iter(related)` · `len(related)` | each related item once, by type · how many that is |

```python
from taxomesh import Direction

svc.items.relate(kob, birth, "version_of")
assert svc.items.relate(steps, kob, "  Covers  ").relation_type == "covers"

assert [link.target_item_id for link in svc.items.list_relations(kob)] == [birth.item_id]
assert len(svc.items.list_relations(kob, direction=Direction.BOTH)) == 2
assert len(svc.items.list_relations(kob, relation_types=["COVERS"], direction="incoming")) == 1
assert [i.name for i in svc.items.list_related(kob)] == ["Birth of the Cool"]
assert [i.name for i in svc.items.list_related(kob, direction="incoming")] == ["Giant Steps"]

related = svc.items.get_many_related([kob, birth], direction="both")[kob.item_id]
assert related.relation_types == ("covers", "version_of")
assert [i.name for i in related.of_type("VERSION_OF")] == ["Birth of the Cool"]
assert [i.name for i in related] == ["Giant Steps", "Birth of the Cool"]
assert svc.items.get_many_related([birth]) == {}  # its one relation is incoming

svc.items.unrelate(kob, birth, "VERSION_OF")
svc.items.unrelate(steps, kob, "covers")
svc.items.unrelate(steps, kob, "covers")  # already gone: a no-op
assert svc.items.list_relations(kob, direction="both") == ()
```

---

# `svc.tags`

| Member | Returns | Does |
|---|---|---|
| `create(name, *, metadata=None)` | `Tag` | Creates a tag; a name is at most `MAX_TAG_NAME_LENGTH` (25) characters |
| `update(tag, *, name, metadata)` | `Tag` | Stores a new row with the fields given; neither takes `None` |
| `delete(key, /)` | `None` | Deletes it, and its links to items |
| `get_many(tags, /)` | `Mapping[UUID, Tag]` | The tags found, in one read |
| `list(*, item=None)` | `Sequence[Tag]` | Every tag, or an item's tags by name, then identifier |

```python
featured = svc.tags.create(name="featured", metadata={"colour": "gold"})
assert svc.tags.update(featured, metadata={"colour": "silver"}).name == "featured"
svc.items.tag(kob, featured)
assert [t.name for t in svc.tags.list(item=kob)] == ["featured"]
assert set(svc.tags.get_many([featured, missing])) == {featured.tag_id}
del svc.tags[featured]
assert svc.tags.list(item=kob) == () and len(svc.tags) == 0
```

---

# Search

`items.search` and `categories.search` rank matches on name, slug and external id, typo-tolerant
and accent-insensitive, using [rapidfuzz](https://github.com/maxbachmann/RapidFuzz). The query and
each field are normalised first: accents stripped, the characters `'`, `-`, `.`, `_` and `\`
turned into spaces, lowercased, whitespace collapsed. From best to worst, a match is exact on name
or slug, a prefix of the name, a prefix of the slug, a word prefix in the name, a substring of the
name, of the slug, or of the external id, and last a fuzzy match scoring 70 or more out of 100;
`fuzzy=False` stops before it. Ties go alphabetically by normalised name.

`limit` below 1 raises `TaxomeshValidationError`. `items.search(category=…)` searches the items
placed there, and with `recursive=True` its descendants' too; `categories.search(parent=…)` searches
that parent's children. A blank query returns `()` once the filter is checked.

An unfiltered search ranks a corpus that the service builds once, at the first search, and holds
for `cache_ttl`. A create, update or delete of a category drops the category corpus, and one of an
item drops the item corpus; a write to a link drops neither. A search with `category` or `parent`
ranks the rows of that listing instead.

```python
assert [i.name for i in svc.items.search("kind of blue")] == ["Kind of Blue"]
assert "Kind of Blue" in {i.name for i in svc.items.search("kind of bleu")}  # typo-tolerant
assert [i.name for i in svc.items.search("giant", category=jazz)] == ["Giant Steps"]
assert [c.name for c in svc.categories.search("jazz", parent=music)] == ["Jazz"]
assert "Soul Music" in {c.name for c in svc.categories.search("soul", enabled=False)}
assert svc.items.search("nothing remotely like this") == ()

magaldi = svc.items.create(name="Agustín Magaldi")
assert "Agustín Magaldi" in {i.name for i in svc.items.search("agustin magaldi")}  # accents ignored
del svc.items[magaldi]
```

---

# The graph

`svc.graph(*, root=None, enabled=True, include_items=True)` returns a `TaxomeshGraph`: a read-only
snapshot, which a later write does not change. It holds one `CategoryNode` per category, however
many paths reach it, and costs a constant number of storage reads at any size. `root` limits it to
that category and its descendants; `include_items=False` reads no items at all.

| Form | Returns | On a miss |
|---|---|---|
| `graph[key]` | `CategoryNode` | raises `TaxomeshCategoryNotFoundError` |
| `graph.get(key, default=None, /)` | `CategoryNode` | `default` |
| `key in graph` · `len(graph)` | `bool` · `int` | `False` · `0` |
| `graph.roots` | `Sequence[CategoryNode]`, the top level | empty |
| `graph.walk()` | `Iterator[CategoryNode]` | — |

| Node member | Returns |
|---|---|
| `node.category` | the `Category` row |
| `node.children` · `node.parents` | `Sequence[CategoryNode]`, one level: children by sort index, parents as stored |
| `node.items` | `Sequence[Item]`, by sort index; `()` in a graph built with `include_items=False` |
| `node.descendants()` · `node.ancestors()` | `Sequence[CategoryNode]`, every level down or up, depth-first in stored order, each once, the node left out |

`walk()` is the graph's only enumerator: it yields every node once, a category no top-level
category reaches included. It and both node walks end on a cycle in stored data. The graph itself
does not iterate.

```python
graph = svc.graph()
assert len(graph) == 3  # Retired and Soul are disabled
assert [n.category.name for n in graph[music].children] == ["Jazz", "Blues"]
assert [n.category.name for n in graph[jazz].parents] == ["Music"]
assert [i.name for i in graph[jazz].items] == ["Kind of Blue", "Giant Steps"]
assert graph[jazz] is graph[jazz.category_id]
assert graph.get(missing) is None and missing not in graph
assert [n.category.name for n in graph[music].descendants()] == ["Jazz", "Blues"]
assert [n.category.name for n in graph[jazz].ancestors()] == ["Music"]
assert len(list(graph.walk())) == len(graph)

assert len(svc.graph(root=jazz)) == 1
assert svc.graph(include_items=False)[jazz].items == ()
assert len(svc.graph(enabled=None)) == 5
```

---

# `svc.info` and `svc.repository`

`svc.info` is a frozen `TaxomeshInfo`, a snapshot of the moment it is read:

| Field | Holds |
|---|---|
| `version` | the installed taxomesh version |
| `config_name` | the name the `taxomesh.toml` that configured the service declares, else `None` |
| `item_corpus_size` · `category_corpus_size` | the held search corpus's size; `None` while none is held |
| `repository` | a `RepositoryInfo`: `backend`, the repository's class name; `path`, its file or `None`; `diagnostics`, its other facts, such as Django's database alias |

`svc.repository` is the repository, the object that implements the port.
[Repositories](repositories.md) says how to choose a storage backend and how to write one.

```python
svc.categories.search("jazz")
assert svc.info.category_corpus_size == len(svc.categories)
assert svc.info.repository.backend == svc.repository.describe().backend == "YamlRepository"
```

---

# Caching

Each service caches its reads in memory for `cache_ttl` seconds, 5 unless it is built with
another; `0` caches nothing, and a negative or NaN lifetime raises `TaxomeshValidationError`. A
write through a service clears that service's cache, and no other's: another service over the same
repository, or over the same Django database from another process, sees the write once its own
entries expire. A write reads what it changes from storage, never from the cache, so a service may
be shared across threads: its writes are never stale, and its reads may be stale within
`cache_ttl`. A YAML or JSON file is read when its repository is built, so it has one writer:
see [Storage](repositories.md). The [design notes](design.md#the-per-service-cache) say why.

```python
uncached = TaxomeshService(svc.repository, cache_ttl=0)
assert uncached.categories[music].name == "Music"  # read from storage every time
```

---

# Errors

The members raise these errors, and one more: `TypeError`, for an argument of the wrong type, as
`int(None)` raises it. A value of the right type that is refused is a `TaxomeshValidationError`, as
`int("sarasa")` raises `ValueError`.

```
TaxomeshError
├── TaxomeshNotFoundError               also a KeyError
│   ├── TaxomeshCategoryNotFoundError
│   ├── TaxomeshItemNotFoundError
│   └── TaxomeshTagNotFoundError
├── TaxomeshValidationError             also a ValueError
│   ├── TaxomeshCyclicDependencyError
│   ├── TaxomeshDuplicateSlugError
│   ├── TaxomeshExternalIdConflictError
│   ├── TaxomeshRelationError
│   └── TaxomeshRootCategoryError
├── TaxomeshVersionConflictError
├── TaxomeshRepositoryError
└── TaxomeshConfigError
```

All of them are importable from `taxomesh`. `TaxomeshGraphTooLargeError`, which only the HTTP
serializer raises, is a `TaxomeshError` too, in `taxomesh.contrib.api.errors`. A storage failure
raises `TaxomeshRepositoryError` from any write. A value the model refuses raises
`TaxomeshValidationError`, with pydantic's error chained as its cause, so no
`pydantic.ValidationError` leaves a member. A field takes what pydantic's lax mode takes, so
`sort_index="5"` is 5, `name=b"Jazz"` is `"Jazz"` and `sort_index="sarasa"` is refused; a filter
takes only its own type, so `enabled="yes"` raises `TypeError`, which is not a `TaxomeshError`.

```python
for call, error in (
    (lambda: svc.items[missing], KeyError),
    (lambda: svc.items.create(name="x" * 300), ValueError),
    (lambda: svc.items["Kind of Blue"], TypeError),
    (lambda: svc.items.list(enabled="yes"), TypeError),
):
    try:
        call()
    except error:
        pass
    else:
        raise AssertionError(f"expected {error.__name__}")
```

The library logs with the standard `logging` module, on loggers whose names start with `taxomesh`.
`list_related` and `get_many_related` log a `WARNING`, the HTTP error mapping an `ERROR`, and the
Django admin a `WARNING` when it cannot link an external id. The `taxomesh` logger has a
`NullHandler`, so no log record is written until your application configures logging. To read the
log records, attach a handler:

```python notest
import logging

logging.getLogger("taxomesh").addHandler(logging.StreamHandler())  # WARNING and above, to stderr
```

← [Back to README](../README.md)
