from typing import Any, Dict, List, Optional

from blossom_wrapper import BlossomResponse, BlossomStatus


def try_get_all(response: BlossomResponse) -> Optional[List[Dict[str, Any]]]:
    """Try to get all results of the response."""
    if (
        response is None
        or response.status != BlossomStatus.ok
        or response.data is None
        or len(response.data) == 0
    ):
        return None

    return response.data


def try_get_first(response: BlossomResponse) -> Optional[Dict[str, Any]]:
    """Try to get the first result of the response."""
    all_results = try_get_all(response)

    if all is None:
        return None

    return all_results[0]


def get_id_from_url(grafeas_url: str) -> int:
    """Extract the API from a Grafeas URL."""
    return int(grafeas_url.split("/")[-2])


def get_url_from_id(grafeas_type: str, grafeas_id: int) -> str:
    """Get the full Grafeas URL from the ID and type."""
    return f"https://grafeas.org/api/{grafeas_type}/{grafeas_id}/"


def limit_str(text: str, limit: Optional[int] = None) -> str:
    """Limit the string to the given length."""
    if limit is None or len(text) <= limit:
        return text

    return f"{text[:(limit - 3)]}..."
