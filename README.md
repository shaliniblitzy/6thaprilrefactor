# 6thaprilrefactor

API response schema enhancements for the Blitzy Platform. This project introduces the `percent_complete` field to track code generation run progress across three API endpoints: `GET /runs/metering`, `GET /runs/metering/current`, and `GET /project`. All changes are purely additive — existing response fields and behavior are fully preserved.

## API Endpoints

### `GET /runs/metering?projectId=xxx`

Fetches metering data for multiple runs in a project's run history.

The response includes the `percent_complete` field at the top level of the response body, representing the overall completion percentage of the queried runs.

**Example response:**

```json
{
  "runs": [],
  "percent_complete": 85.5
}
```

### `GET /runs/metering/current`

Returns live run status for the currently active code generation run. Designed for auto-refresh polling during active code generation.

The response includes the `percent_complete` field at the top level, reflecting the real-time progress of the current run.

**Example response:**

```json
{
  "currentRun": {},
  "percent_complete": 42.0
}
```

### `GET /project?id=xxx`

Returns project details including inline metering data. Used when opening a project page.

The response includes `percent_complete` nested within the `metering` object inside the `project` payload.

**Example response:**

```json
{
  "project": {
    "metering": {
      "percent_complete": 100.0
    }
  }
}
```

## percent_complete Field Specification

| Property | Detail |
|----------|--------|
| **Data type** | `float` or `null` |
| **Valid range** | `0.0 <= value <= 100.0` |
| **Null semantics** | Returned when no metering data is available or the field is not applicable |
| **Presence** | MANDATORY in all three API responses — omission is a defect |
| **Naming** | Consistently `percent_complete` across all endpoints |

- The field must always be a number (`float` / `int` coerced to float) or `null`. It must never be a string, boolean, array, object, or any other type.
- Values outside the 0.0–100.0 range are classified as bugs and must be rejected by validation.
- Wrong data types are classified as bugs and must be rejected by validation.
- The field name `percent_complete` is used uniformly across all three endpoints. Mixing naming conventions (e.g., `percentComplete` in one endpoint and `percent_complete` in another) is a defect.

## Validation Matrix

| Scenario | Expected Value | Valid |
|----------|---------------|-------|
| Completed run | 0.0–100.0 | ✅ Yes |
| In-progress run | Less than 100.0 | ✅ Yes |
| No data available | `null` | ✅ Yes |
| Field missing entirely | N/A | ❌ Bug |
| Value greater than 100 | N/A | ❌ Bug |
| Value less than 0 | N/A | ❌ Bug |
| String instead of number | N/A | ❌ Bug |
| Inconsistent field name across APIs | N/A | ❌ Bug |
| Present in one API but missing in others | N/A | ❌ Bug |

## Setup

### Prerequisites

- Python 3.12+

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Tests

```bash
pytest
```

## Project Structure

```
├── src/
│   ├── api/          # API route handlers
│   ├── models/       # Pydantic response models
│   ├── services/     # Business logic layer
│   └── validators/   # Validation utilities
├── tests/
│   ├── api/          # API endpoint tests
│   ├── models/       # Model validation tests
│   └── edge_cases/   # Boundary and type tests
├── conftest.py       # Pytest fixtures
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Verification

Use browser DevTools to verify the `percent_complete` field is present in API responses:

1. **Open DevTools** — Right-click the page → Inspect → navigate to the **Network** tab.
2. **Enable filters** — Select **XHR / Fetch** and enable **Preserve log** before performing actions.
3. **Trigger API calls** — Open a project, start or view a code generation run, refresh the project dashboard, or check run progress.
4. **Filter requests** — In the Network tab filter bar, search for `metering`, `runs`, or `project`.
5. **Inspect response** — Click the API request → go to the **Response** or **Preview** tab.
6. **Search for field** — Press `Ctrl+F` (or `Cmd+F` on macOS) and search for `percent_complete`.
7. **Validate value** — Confirm the field value is a number in the range 0.0–100.0 or `null`.
