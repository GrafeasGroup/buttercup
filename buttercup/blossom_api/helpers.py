from typing import Optional, Dict, Any

from blossom_wrapper import BlossomResponse, BlossomStatus


def try_get_first(response: BlossomResponse) -> Optional[Dict[str, Any]]:
    """Tries to get the first result of the response."""
    if response is None or response.status != BlossomStatus.ok or response.data is None or len(response.data) == 0:
        return None

    return response.data[0]
