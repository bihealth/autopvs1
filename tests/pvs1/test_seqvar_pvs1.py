from unittest.mock import MagicMock, patch

import pytest

from src.api.annonars import AnnonarsClient
from src.api.mehari import MehariClient
from src.defs.annonars_range import AnnonarsRangeResponse
from src.defs.auto_pvs1 import (
    GenomicStrand,
    PVS1Prediction,
    PVS1PredictionSeqVarPath,
    SeqVarConsequence,
)
from src.defs.exceptions import AlgorithmError, MissingDataError
from src.defs.genome_builds import GenomeRelease
from src.defs.mehari import Exon, GeneTranscripts, TranscriptsSeqVar
from src.defs.seqvar import SeqVar
from src.pvs1.seqvar_pvs1 import SeqVarPVS1, SeqVarPVS1Helper, SeqVarTranscriptsHelper
from src.utils import SplicingPrediction
from tests.utils import get_json_object


@pytest.fixture
def seqvar():
    return SeqVar(GenomeRelease.GRCh38, "1", 1000, "A", "T", "1:1000A>T")


@pytest.fixture
def ts_helper(seqvar):
    return SeqVarTranscriptsHelper(seqvar)


@pytest.fixture
def seqvar_transcripts(file_name: str = "mehari/mehari_seqvar_success.json"):
    return TranscriptsSeqVar.model_validate(get_json_object(file_name)).result


@pytest.fixture
def gene_transcripts(file_name: str = "mehari/mehari_genes_success.json"):
    return GeneTranscripts.model_validate(get_json_object(file_name)).transcripts


#: Mock the Exon class
class MockExon:
    def __init__(self, altStartI, altEndI, altCdsStartI=None, altCdsEndI=None, cigar="", ord=None):
        self.altStartI = altStartI
        self.altEndI = altEndI
        self.altCdsStartI = altCdsStartI if altCdsStartI is not None else altStartI
        self.altCdsEndI = altCdsEndI if altCdsEndI is not None else altEndI
        self.cigar = cigar
        self.ord = ord


#: Mock the CdsInfo class
class MockCdsInfo:
    def __init__(
        self, start_codon, stop_codon, cds_start, cds_end, exons, cds_strand=GenomicStrand.Plus
    ):
        self.start_codon = start_codon
        self.stop_codon = stop_codon
        self.cds_start = cds_start
        self.cds_end = cds_end
        self.cds_strand = cds_strand
        self.exons = exons


# === SeqVarPVS1Helper ===


@pytest.mark.parametrize(
    "var_pos,exons,strand,expected_result",
    [
        (
            100,
            [MockExon(0, 100, 0, 100)],
            GenomicStrand.Plus,
            (100, 100),
        ),
        (100, [MockExon(0, 100, 0, 100)], GenomicStrand.Plus, (100, 100)),
        (
            150,
            [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200), MockExon(200, 300, 200, 300)],
            GenomicStrand.Plus,
            (150, 300),
        ),
        (
            150,
            [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200), MockExon(200, 300, 200, 300)],
            GenomicStrand.Plus,
            (150, 300),
        ),
    ],
)
def test_calc_alt_reg(var_pos, exons, strand, expected_result):
    """Test the _calc_alt_reg method."""
    result = SeqVarPVS1Helper()._calc_alt_reg(var_pos, exons, strand)
    assert result == expected_result


@pytest.mark.parametrize(
    "gene_transcripts_file,transcript_id,var_pos,expected_result",
    [
        (
            "mehari/HAL_gene.json",
            "NM_002108.4",
            96370184,
            (96366439, 96370184),
        ),  # Strand minus
        (
            "mehari/F10_gene_NM_000504.4.json",
            "NM_000504.4",
            113139456,
            (113139456, 113149529),
        ),  # Strand plus
        (
            "mehari/PCID2_gene.json",
            "NM_001127202.4",
            113184385,
            (113177535, 113184385),
        ),  # Strand minus
    ],
)
def test_calc_alt_reg_real_data(gene_transcripts_file, transcript_id, var_pos, expected_result):
    """Test the _calc_alt_reg method."""
    gene_transcripts = GeneTranscripts.model_validate(
        get_json_object(gene_transcripts_file)
    ).transcripts
    tsx = None
    for transcript in gene_transcripts:
        if transcript.id == transcript_id:
            tsx = transcript
    if tsx is None:  # Should never happen
        raise ValueError(f"Transcript {transcript_id} not found in the gene transcripts")

    exons = tsx.genomeAlignments[0].exons
    strand = GenomicStrand.from_string(tsx.genomeAlignments[0].strand)
    start_pos, end_pos = SeqVarPVS1Helper()._calc_alt_reg(var_pos, exons, strand)
    assert start_pos == expected_result[0]
    assert end_pos == expected_result[1]


@pytest.mark.parametrize(
    "annonars_range_response, expected_result",
    [
        ("annonars/GAA_range.json", (535, 2606)),
        ("annonars/CDH1_range.json", (0, 2)),
    ],
)
def test_count_pathogenic_vars(annonars_range_response, expected_result, seqvar):
    """Test the _count_pathogenic_vars method."""
    with patch.object(AnnonarsClient, "get_variant_from_range") as mock_get_variant_from_range:
        mock_get_variant_from_range.return_value = AnnonarsRangeResponse.model_validate(
            get_json_object(annonars_range_response)
        )
        result = SeqVarPVS1Helper()._count_pathogenic_vars(seqvar, 1, 1000)  # Real range is mocked
        assert result == expected_result


@pytest.mark.parametrize(
    "var_pos,exons,expected_result",
    [
        (100, [MockExon(0, 100, 0, 100)], (0, 100)),
        (150, [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200)], (100, 200)),
        (150, [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200)], (100, 200)),
    ],
)
def test_find_aff_exon_pos(var_pos, exons, expected_result):
    """Test the _find_aff_exon_pos method."""
    result = SeqVarPVS1Helper()._find_aff_exon_pos(var_pos, exons)
    assert result == expected_result


@pytest.mark.parametrize(
    "value,expected_result",
    [
        (
            SeqVarConsequence.NonsenseFrameshift,
            [
                "3_prime_utr_variant",
                "3_prime_UTR_variant",
                "frameshift_variant",
                "stop_gained",
            ],
        ),
        (
            SeqVarConsequence.InitiationCodon,
            [
                "upstream_gene_variant",
                "downstream_gene_variant",
                "start_lost",
                "initiator_codon_variant",
                "start_retained_variant",
            ],
        ),
        (
            SeqVarConsequence.SpliceSites,
            [
                "splice_region_variant",
                "splice_donor_variant",
                "splice_donor_5th_base_variant",
                "splice_donor_region_variant",
                "splice_polypyrimidine_tract_variant",
                "splice_acceptor_variant",
            ],
        ),
        (SeqVarConsequence.Missense, ["missense_variant"]),
    ],
)
def test_get_conseq(value, expected_result):
    """Test the _get_conseq method."""
    result = SeqVarPVS1Helper()._get_conseq(value)
    assert result == expected_result


@pytest.mark.parametrize(
    "annonars_range_response, expected_result",
    [
        ("annonars/GAA_range.json", (56, 158)),
        ("annonars/CDH1_range.json", (0, 0)),
    ],
)
def test_count_lof_vars(annonars_range_response, expected_result, seqvar):
    """Test the _count_lof_vars method."""
    with patch.object(AnnonarsClient, "get_variant_from_range") as mock_get_variant_from_range:
        mock_get_variant_from_range.return_value = AnnonarsRangeResponse.model_validate(
            get_json_object(annonars_range_response)
        )
        result = SeqVarPVS1Helper()._count_lof_vars(seqvar, 1, 1000)  # Real range is mocked
        assert result == expected_result


@pytest.mark.parametrize(
    "hgvs, cds_info, expected_result",
    [
        # Test no alternative start codon is found
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
            },
            None,
        ),
        # Test an alternative start codon is found
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=150, stop_codon=1000, cds_start=150, cds_end=1000, exons=[]
                ),
            },
            150,
        ),
        # Test multiple transcripts, one with an alternative start
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000003": MockCdsInfo(
                    start_codon=200, stop_codon=1000, cds_start=200, cds_end=1000, exons=[]
                ),
            },
            200,
        ),
        # Test multiple transcripts, none with an alternative start
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000003": MockCdsInfo(
                    start_codon=100, stop_codon=2000, cds_start=100, cds_end=1000, exons=[]
                ),
            },
            None,
        ),
    ],
)
def test_closest_alt_start_cdn(hgvs, cds_info, expected_result):
    """Test the _closest_alt_start_cdn method."""
    result = SeqVarPVS1Helper()._closest_alt_start_cdn(cds_info, hgvs)
    assert result == expected_result


def test_closest_alt_start_cdn_invalid():
    """Test the _closest_alt_start_cdn method."""
    hgvs = "NM_000"
    cds_info = {
        "NM_000001": MockCdsInfo(
            start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
        ),
        "NM_000002": MockCdsInfo(
            start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
        ),
        "NM_000003": MockCdsInfo(
            start_codon=200, stop_codon=1000, cds_start=200, cds_end=1000, exons=[]
        ),
    }
    with pytest.raises(MissingDataError):
        SeqVarPVS1Helper()._closest_alt_start_cdn(cds_info, hgvs)  # type: ignore


@pytest.mark.parametrize(
    "seqvar, exons, expected_result",
    [
        (
            SeqVar(GenomeRelease.GRCh38, "1", 50, "A", "T"),
            [MockExon(2, 100, 0, 100)],
            (2, 100),
        ),  # One exon
        (
            SeqVar(GenomeRelease.GRCh38, "1", 150, "A", "T"),
            [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200)],
            (100, 200),
        ),  # Multiple exons
        (
            SeqVar(GenomeRelease.GRCh38, "1", 98, "A", "T"),
            [MockExon(100, 200, 100, 200)],
            (100, 200),
        ),  # Upstream intron
        (
            SeqVar(GenomeRelease.GRCh38, "1", 220, "A", "T"),
            [MockExon(100, 200, 100, 200)],
            (100, 200),
        ),  # Downstream intron
    ],
)
def test_skipping_exon_pos(seqvar, exons, expected_result):
    """Test the _skipping_exon_pos method."""
    result = SeqVarPVS1Helper()._skipping_exon_pos(seqvar, exons)
    assert result == expected_result


def test_skipping_exon_pos_invalid():
    """Test the _skipping_exon_pos method."""
    seqvar = SeqVar(GenomeRelease.GRCh38, "1", 50, "A", "T")
    exons = [MockExon(100, 200, 100, 200)]
    with pytest.raises(AlgorithmError):
        SeqVarPVS1Helper()._skipping_exon_pos(seqvar, exons)  # type: ignore


@pytest.mark.parametrize(
    "gene_transcripts_file,transcript_id,hgnc_id,var_pos,expected_result",
    [
        (
            "mehari/F10_gene_NM_000504.4.json",
            "NM_000504.4",
            "HGNC:3528",
            500,
            True,
        ),  # Strand plus
        (
            "mehari/F10_gene_NM_000504.4.json",
            "NM_000504.4",
            "HGNC:3528",
            1000,
            False,
        ),  # Strand plus
        (
            "mehari/PCID2_gene.json",
            "NM_001127202.4",
            "HGNC:25653",
            900,
            True,
        ),  # Strand minus. Not a frameshift!
        (
            "mehari/PCID2_gene.json",
            "NM_001127202.4",
            "HGNC:25653",
            1100,
            False,
        ),  # Strand minus. Not a real variant
    ],
)
def test_undergo_nmd(gene_transcripts_file, transcript_id, hgnc_id, var_pos, expected_result):
    """
    Test the _undergo_nmd method. Note, that we don't mock the `_get_variant_position` and
    `_calculate_5_prime_UTR_length` methods.
    """
    gene_transcripts = GeneTranscripts.model_validate(
        get_json_object(gene_transcripts_file)
    ).transcripts
    tsx = None
    for transcript in gene_transcripts:
        if transcript.id == transcript_id:
            tsx = transcript
    if tsx is None:  # Should never happen
        raise ValueError(f"Transcript {transcript_id} not found in the gene transcripts")
    exons = tsx.genomeAlignments[0].exons
    strand = GenomicStrand.from_string(tsx.genomeAlignments[0].strand)
    result = SeqVarPVS1Helper().undergo_nmd(var_pos, hgnc_id, strand, exons)
    assert result == expected_result


@pytest.mark.parametrize(
    "transcript_tags,expected_result",
    [
        ([], False),
        (["NonRelevantTag"], False),
        (["ManeSelect"], True),
        (["SomeOtherTag", "ManeSelect"], True),
        (["maneselect"], False),  # Case-sensitive check
        (["MANESELECT"], False),  # Case-sensitive check
        (["SomeTag", "AnotherTag"], False),
    ],
)
def test_in_bio_relevant_tsx(transcript_tags, expected_result):
    """Test the _in_bio_relevant_tsx method."""
    result = SeqVarPVS1Helper().in_bio_relevant_tsx(transcript_tags)
    assert result == expected_result, f"Failed for transcript_tags: {transcript_tags}"


@pytest.mark.parametrize(
    "pathogenic_variants, total_variants, strand, expected_result",
    [
        (6, 100, GenomicStrand.Plus, True),  # Test pathogenic variants exceed the threshold
        (3, 100, GenomicStrand.Plus, False),  # Test pathogenic variants do not exceed the threshold
        (0, 0, GenomicStrand.Plus, False),  # Test no variants are found
        (0, 100, GenomicStrand.Plus, False),  # Test no pathogenic variants are found
        (100, 0, GenomicStrand.Plus, False),  # Test more pathogenic variants than total variants
    ],
)
def test_crit4prot_func(
    seqvar, pathogenic_variants, total_variants, strand, expected_result, monkeypatch
):
    """Test the _crit4prot_func method."""
    # Mock exons, since they won't affect the outcome
    exons = [MagicMock(spec=Exon)]
    # Mocking _calc_alt_reg to return a mocked range
    mock_calculate = MagicMock(return_value=(1, 1000))
    monkeypatch.setattr(SeqVarPVS1Helper, "_calc_alt_reg", mock_calculate)
    # Mocking _count_pathogenic_vars to return controlled counts of pathogenic and total variants
    mock_count_pathogenic = MagicMock(return_value=(pathogenic_variants, total_variants))
    monkeypatch.setattr(SeqVarPVS1Helper, "_count_pathogenic_vars", mock_count_pathogenic)

    result = SeqVarPVS1Helper().crit4prot_func(seqvar, exons, strand)  # type: ignore
    assert result == expected_result


@pytest.mark.parametrize(
    "frequent_lof_variants, lof_variants, strand, expected_result",
    [
        (
            11,
            100,
            GenomicStrand.Plus,
            True,
        ),  # Test case where frequent LoF variants exceed the 10% threshold
        (
            5,
            100,
            GenomicStrand.Plus,
            False,
        ),  # Test case where frequent LoF variants do not exceed the 10% threshold
        (0, 0, GenomicStrand.Plus, False),  # Test case where no LoF variants are found
        (
            0,
            100,
            GenomicStrand.Plus,
            False,
        ),  # Test case where no frequent LoF variants are found
        (0, 0, GenomicStrand.Plus, False),  # Test case where no LoF variants are found
    ],
)
def test_lof_freq_in_pop(
    seqvar, frequent_lof_variants, lof_variants, strand, expected_result, monkeypatch
):
    """Test the _lof_freq_in_pop method."""
    # Mocking exons, since they won't affect the outcome
    exons = [MagicMock(spec=Exon)]
    # Mocking _calc_alt_reg to return a mocked range
    mock_calculate = MagicMock(return_value=(1, 1000))
    monkeypatch.setattr(SeqVarPVS1Helper, "_find_aff_exon_pos", mock_calculate)
    # Mocking _count_lof_vars to return controlled counts of frequent and total LoF variants
    mock_count_lof_vars = MagicMock(return_value=(frequent_lof_variants, lof_variants))
    monkeypatch.setattr(SeqVarPVS1Helper, "_count_lof_vars", mock_count_lof_vars)

    result = SeqVarPVS1Helper().lof_freq_in_pop(seqvar, exons, strand)  # type: ignore
    assert result == expected_result


@pytest.mark.parametrize(
    "prot_pos, prot_length, expected_result",
    [
        (
            4,
            100,
            False,
        ),  # Test case where the variant remove less than 10% of the protein
        (
            99,
            100,
            True,
        ),  # Test case where the variant removes more than 10% of the protein
    ],
)
def test_lof_rm_gt_10pct_of_prot(prot_pos, prot_length, expected_result):
    """Test the _lof_rm_gt_10pct_of_prot method."""
    result = SeqVarPVS1Helper().lof_rm_gt_10pct_of_prot(prot_pos, prot_length)
    assert result == expected_result


# @pytest.mark.parametrize(
#     "skipping_exon_pos_output, consequences, strand, cryptic_ss_output, expected",
#     [
#         (
#             (90, 120),  # _skipping_exon_pos output
#             ["splice_donor_variant"],  # consequences
#             GenomicStrand.Plus,  # strand
#             [(95, "some_seq", 5.0)],  # get_cryptic_ss output
#             True,
#         ),
#         (
#             (90, 123),
#             ["splice_acceptor_variant"],
#             GenomicStrand.Plus,
#             [],
#             False,
#         ),
#         (
#             (90, 120),
#             ["splice_donor_variant"],
#             GenomicStrand.Minus,
#             [(101, "some_seq", 5.0)],
#             True,
#         ),
#         (
#             (90, 120),
#             ["splice_donor_variant"],
#             GenomicStrand.Minus,
#             [(103, "some_seq", 5.0)],
#             False,
#         ),
#     ],
# )
# def test_exon_skip_or_cryptic_ss_disrupt(
#     seqvar, skipping_exon_pos_output, consequences, strand, cryptic_ss_output, expected
# ):
#     """Test the _exon_skip_or_cryptic_ss_disrupt method."""
#     exons = [MockExon(90, 120, 90, 120)]

#     # Mock the SplicingPrediction class
#     sp_mock = MagicMock()
#     sp_mock.get_sequence.return_value = "some_sequence"
#     sp_mock.get_cryptic_ss.return_value = cryptic_ss_output

#     with patch.object(
#         SeqVarPVS1Helper, "_skipping_exon_pos", return_value=skipping_exon_pos_output
#     ):
#         with patch("src.utils.SplicingPrediction", return_value=sp_mock):
#             result = SeqVarPVS1Helper()._exon_skip_or_cryptic_ss_disrupt(
#                 seqvar, exons, consequences, strand  # type: ignore
#             )
#             assert result == expected, f"Expected {expected}, but got {result}"


@pytest.mark.parametrize(
    "hgvs, cds_info, expected_result",
    [
        # Test no alternative start codon is found
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
            },
            False,
        ),
        # Test an alternative start codon is found
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=150, stop_codon=1000, cds_start=150, cds_end=1000, exons=[]
                ),
            },
            True,
        ),
        # Test multiple transcripts, one with an alternative start
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000003": MockCdsInfo(
                    start_codon=200, stop_codon=1000, cds_start=200, cds_end=1000, exons=[]
                ),
            },
            True,
        ),
        # Test multiple transcripts, none with an alternative start
        (
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000003": MockCdsInfo(
                    start_codon=100, stop_codon=2000, cds_start=100, cds_end=1000, exons=[]
                ),
            },
            False,
        ),
    ],
)
def test_alt_start_cdn(hgvs, cds_info, expected_result):
    """Test the _alt_start_cdn method."""
    result = SeqVarPVS1Helper().alt_start_cdn(cds_info, hgvs)
    assert result == expected_result


@pytest.mark.parametrize(
    "exons, strand, pathogenic_variants, hgvs, cds_info, expected_result",
    [
        (
            [MagicMock(altStartI=1, altEndI=200, altCdsStartI=1, altCdsEndI=200)],
            GenomicStrand.Plus,
            1,
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=150, stop_codon=1000, cds_start=150, cds_end=1000, exons=[]
                ),
            },
            True,
        ),  # Test pathogenic variant is found
        (
            [MagicMock(altStartI=1, altEndI=200, altCdsStartI=1, altCdsEndI=200)],
            GenomicStrand.Plus,
            0,
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=150, stop_codon=1000, cds_start=150, cds_end=1000, exons=[]
                ),
            },
            False,
        ),  # Test no pathogenic variants found
        (
            [MagicMock(altStartI=1, altEndI=200, altCdsStartI=1, altCdsEndI=200)],
            GenomicStrand.Minus,
            1,
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=150, stop_codon=1000, cds_start=150, cds_end=1000, exons=[]
                ),
            },
            True,
        ),  # Test pathogenic variants found on minus strand
        (
            [MagicMock(altStartI=1, altEndI=200, altCdsStartI=1, altCdsEndI=200)],
            GenomicStrand.Minus,
            0,
            "NM_000001",
            {
                "NM_000001": MockCdsInfo(
                    start_codon=100, stop_codon=1000, cds_start=100, cds_end=1000, exons=[]
                ),
                "NM_000002": MockCdsInfo(
                    start_codon=150, stop_codon=1000, cds_start=150, cds_end=1000, exons=[]
                ),
            },
            False,
        ),  # Test no pathogenic variants found on minus strand
    ],
)
def test_up_pathogenic_vars(
    seqvar, exons, strand, pathogenic_variants, hgvs, cds_info, expected_result, monkeypatch
):
    """Test the _up_pathogenic_vars method."""
    # Mocking _count_pathogenic_vars to return a controlled number of pathogenic variants
    mock_count_pathogenic = MagicMock(return_value=(pathogenic_variants, 10))
    monkeypatch.setattr(SeqVarPVS1Helper, "_count_pathogenic_vars", mock_count_pathogenic)

    result = SeqVarPVS1Helper().up_pathogenic_vars(seqvar, exons, strand, cds_info, hgvs)
    assert result == expected_result


# === SeqVarPVS1 ===


def test_init(seqvar):
    """Test the initialization of SeqVarPVS1."""
    pvs1 = SeqVarPVS1(seqvar)
    assert pvs1.config is not None
    assert pvs1.annonars_client is not None
    assert pvs1.seqvar == seqvar
    assert pvs1._seqvar_transcript is None
    assert pvs1._gene_transcript is None
    assert pvs1._consequence == SeqVarConsequence.NotSet
    assert pvs1.HGVS == ""
    assert pvs1.HGNC_id == ""
    assert len(pvs1.transcript_tags) == 0
    assert len(pvs1.exons) == 0
    assert pvs1.tx_pos_utr == -1
    assert pvs1.prot_pos == -1
    assert pvs1.prot_length == -1
    assert pvs1.cds_info == {}
    assert pvs1.strand == None
    assert pvs1.prediction == PVS1Prediction.NotPVS1
    assert pvs1.prediction_path == PVS1PredictionSeqVarPath.NotSet
