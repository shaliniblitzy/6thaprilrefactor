"""Validators package for centralized validation utilities.

This package provides reusable validation functions that enforce data integrity
rules across the Blitzy Platform API endpoints.  The primary export is
:func:`validate_percent_complete`, which ensures the ``percent_complete``
metering field conforms to its contract (``float`` in ``[0.0, 100.0]`` or
``None``) for all three target endpoints:

- ``GET /runs/metering``
- ``GET /runs/metering/current``
- ``GET /project``

Convenience re-export
---------------------
Instead of the fully qualified import path::

    from src.validators.percent_complete import validate_percent_complete

consumers may use the shorter package-level import::

    from src.validators import validate_percent_complete
"""

from src.validators.percent_complete import validate_percent_complete

__all__: list[str] = ["validate_percent_complete"]
