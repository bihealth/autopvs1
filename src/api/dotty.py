"""Dotty API client."""

import requests

from src.core.config import settings
from src.genome_builds import GenomeRelease
from src.models.dotty import DottyResponse

#: Dotty API base URL
DOTTI_API_BASE_URL = f"{settings.API_REEV_URL}/dotty"


class DottyClient:
    def __init__(self, api_base_url: str = DOTTI_API_BASE_URL):
        self.api_base_url = api_base_url

    def to_spdi(self, query: str, assembly: GenomeRelease = GenomeRelease.GRCh38) -> DottyResponse:
        """
        Converts a variant to SPDI format.

        :param query: Variant query
        :type query: str
        :param assembly: Genome assembly
        :type assembly: GRChAssemblyType
        :return: SPDI format
        :rtype: dict | None
        """
        url = f"{self.api_base_url}/api/v1/to-spdi?q={query}&assembly={assembly.name}"
        response = requests.get(url)
        response.raise_for_status()
        return DottyResponse.model_validate(response.json())
