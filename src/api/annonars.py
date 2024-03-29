"""Annonars API client."""

import requests
from pydantic import ValidationError

from src.core.config import settings
from src.seqvar import SeqVar
from src.types.annonars import AnnonarsRangeResponse

#: Annonars API base URL
ANNONARS_API_BASE_URL = f"{settings.API_REEV_URL}/annonars"


class AnnonarsClient:
    def __init__(self, api_base_url: str = ANNONARS_API_BASE_URL):
        self.api_base_url = api_base_url

    def get_variant_from_range(
        self, seqvar: SeqVar, start: int, stop: int
    ) -> AnnonarsRangeResponse | None:
        """
        Pull all variants within a range.

        :param seqvar: Sequence variant
        :type seqvar: SeqVar
        :param start: Start position
        :type start: int
        :param stop: End position
        :type stop: int
        :return: Variants
        :rtype: dict | None
        """
        url = (
            f"{self.api_base_url}/annos/range?"
            f"genome_release={seqvar.genome_release.name.lower()}"
            f"&chromosome={seqvar.chrom}"
            f"&start={start}"
            f"&stop={stop}"
        )
        response = requests.get(url)
        try:
            response.raise_for_status()
            return AnnonarsRangeResponse.model_validate(response.json())
        except requests.RequestException:
            return None
        except ValidationError as e:
            return None
