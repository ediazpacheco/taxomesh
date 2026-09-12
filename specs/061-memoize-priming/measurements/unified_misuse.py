from unified_proto import Service, mosaic, paths_from_main, tree
svc = Service()
svc.get_category.prime(123, 7)      # E: value type
svc.get_category("x")               # E: arg type
n: int = svc.get_category(7)        # E: return type
paths_from_main(1)                  # E: too many args
mosaic(3)                           # E: count is keyword-only
tree("x")                           # E: arg type
