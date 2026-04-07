"""Services package for business logic and computation.

This package encapsulates all service-layer modules responsible for
metering calculations and run-progress tracking across the Blitzy
Platform API.  It re-exports the primary public functions from
:mod:`src.services.metering_service` so that consumers can use the
shorter import path::

    from src.services import get_percent_complete
    from src.services import compute_percent_from_metering_data

instead of the fully-qualified module path.
"""

from src.services.metering_service import (
    compute_percent_from_metering_data,
    get_percent_complete,
)

__all__ = [
    "get_percent_complete",
    "compute_percent_from_metering_data",
]
