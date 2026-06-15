# What Taxomesh Solves

`taxomesh` is a reusable taxonomy layer for Python applications.

Use it when your real entities already exist in your system, but you need a robust way
to organize them with categories, tags, placement rules, and item relationships.

In practice, that often means:

- products in an ecommerce catalog
- articles or pages in a CMS
- tracks, albums, or videos in a media library
- internal documents, assets, or knowledge-base entries

## The Short Version

`taxomesh` stores and validates taxonomy structure so your application does not have to
rebuild it from scratch.

It gives you:

- categories with more than one parent
- items placed in multiple branches
- per-parent ordering
- tags and typed item-to-item relations (relation type names are defined by
  your application; taxomesh treats them as opaque strings)
- slugs, metadata, and external IDs
- one consistent service layer with optional CLI, Django, and HTTP integrations

## Why This Gets Complex Quickly

A taxonomy is rarely just "a categories table."

Real applications often need:

- navigation paths that are not a strict tree
- the same item shown in several parts of the catalog
- different ordering depending on where the item appears
- taxonomy records linked to existing application models
- validation and error handling reused across scripts, admin tools, and APIs

That is the gap `taxomesh` is meant to fill.

## A Good Fit

`taxomesh` is a good fit when:

- taxonomy is important enough to deserve its own component
- the same taxonomy needs to be edited and consumed in multiple places
- you want to keep taxonomy logic separate from your core domain models
- you need to start with file-backed storage and possibly move to Django later

## Probably Not A Good Fit

You may not need `taxomesh` if:

- you only need a flat dropdown or a single-parent tree
- taxonomy is a tiny, fixed part of one application screen
- there is no need for reusable validation, traversal, or integrations

## Relationship To Your Existing Models

`taxomesh` does not need to own your business entities.

The common pattern is to keep your real models where they already live and connect them
through `external_id`. That makes `taxomesh` useful as a taxonomy layer rather than as a
full content or product database.

## Where To Go Next

- Start with the [README](../README.md) for installation and a quick example
- See the [Python API](python-api.md) for service-level usage
- See [Django integration](django-integration.md) if taxonomy lives in a Django project
- See [HTTP API integration](http-api-integration.md) to expose taxonomy through your app

← [Back to README](../README.md)
