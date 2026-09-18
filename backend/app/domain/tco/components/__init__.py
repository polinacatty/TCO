"""TCO components — one module per cost line in the methodology.

Each module exposes a single ``*Component`` class with a ``compute(...)``
method that takes the user profile + the relevant slice of
:class:`~app.domain.tco.inputs.TcoContext` and returns either:

* an integer in rubles, or
* a tuple ``(rubles, breakdown_dict)`` for components whose explanation is
  worth surfacing in the API response.
"""
