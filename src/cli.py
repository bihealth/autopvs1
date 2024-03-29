"""Entry point for the command line interface."""

import typer
from typing_extensions import Annotated

from src.autoPVS1 import AutoPVS1
from src.genome_builds import GenomeRelease

app = typer.Typer()

#: Allowed genome releases
ALLOWED_GENOME_RELEASES = ["GRCh37", "GRCh38", "hg19", "hg38", "grch37", "grch38"]
#: Allowed sequence variant formats
ALLOWED_SEQVAR_FORMATS = ["Canonical SPDI", "gnomAD", "relaxed SPDI", "dbSNP", "ClinVar"]


@app.command()
def classify(
    variant: Annotated[
        str,
        typer.Argument(
            help=f"Variant to be classified, e.g., 'NM_000038.3:c.797G>A'. Accepted formats: {', '.join(ALLOWED_SEQVAR_FORMATS)}"
        ),
    ],
    genome_release: Annotated[
        str,
        typer.Option(
            "--genome-release",
            "-g",
            help=f"Accepted genome Releases: {', '.join(ALLOWED_GENOME_RELEASES)}",
        ),
    ] = "GRCh38",
):
    """
    Classify a variant using the specified genome release.
    """
    try:
        genome_release_enum = GenomeRelease.from_string(genome_release)
        if not genome_release_enum:
            raise ValueError(
                f"Invalid genome release: {genome_release}. Please use one of {', '.join(ALLOWED_GENOME_RELEASES)}."
            )

        auto_pvs1 = AutoPVS1(variant, genome_release_enum)
        auto_pvs1.predict()
    except Exception as e:
        typer.secho(f"Error: {e}", err=True, fg=typer.colors.RED)


if __name__ == "__main__":
    app()
