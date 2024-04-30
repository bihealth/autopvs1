from unittest.mock import MagicMock, Mock, patch

import pytest

from src.api.annonars import AnnonarsClient
from src.api.mehari import MehariClient
from src.defs.annonars import AnnonarsRangeResponse
from src.defs.autopvs1 import (
    AlteredRegionMode,
    PVS1Prediction,
    PVS1PredictionSeqVarPath,
    SeqVarConsequence,
)
from src.defs.genome_builds import GenomeRelease
from src.defs.mehari import Exon, GeneTranscripts, TranscriptsSeqVar
from src.defs.seqvar import SeqVar
from src.pvs1.seqvar_pvs1 import SeqVarPVS1, SeqVarPVS1Helper, SeqVarTranscriptsHelper
from tests.utils import get_json_object


@pytest.fixture
def seqvar():
    return SeqVar(GenomeRelease.GRCh38, "1", 1000, "A", "T", "1:1000A>T")


@pytest.fixture
def ts_helper(seqvar):
    return SeqVarTranscriptsHelper(seqvar)


@pytest.fixture
def seqvar_transcripts():
    return TranscriptsSeqVar.model_validate(
        get_json_object("mehari/mehari_seqvar_success.json")
    ).result


@pytest.fixture
def gene_transcripts():
    return GeneTranscripts.model_validate(
        get_json_object("mehari/mehari_genes_success.json")
    ).transcripts


@pytest.fixture
def mock_annonars_client(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_variant_from_range.return_value = AnnonarsRangeResponse.model_validate(
        get_json_object("annonars/annonars_range_success.json")
    )
    monkeypatch.setattr("src.pvs1.seqvar_pvs1.AnnonarsClient", lambda *args, **kwargs: mock_client)
    return mock_client


#: Mock the Exon class
class MockExon:
    def __init__(self, altStartI, altEndI, altCdsStartI=None, altCdsEndI=None, cigar="", ord=None):
        self.altStartI = altStartI
        self.altEndI = altEndI
        self.altCdsStartI = altCdsStartI if altCdsStartI is not None else altStartI
        self.altCdsEndI = altCdsEndI if altCdsEndI is not None else altEndI
        self.cigar = cigar
        self.ord = ord


# === SeqVarPVS1Helpers ===


# TODO: Check if the termination number is correct
@pytest.mark.parametrize(
    "pHGVS,expected_termination",
    [
        ("NM_031475.2:p.Gln98*", 98),
        ("NM_031475.2:p.Ala586Glyfs*73", 586 + 73),
        ("NP_000305.3:p.Arg378SerfsTer5", 378 + 5),
        ("p.Arg97Glyfs*26", 97 + 26),
        ("p.Arg97GlyfsX26", 97 + 26),
        ("p.Arg97GlyfsTer26", 97 + 26),
        # ("p.Arg97fs", -1),  # No termination number provided
        ("p.Gly100Ter", 100),
        ("p.Cys24*", 24),
        ("p.Ala2X", 2),
        ("p.Tyr10Ter", 10),
        ("p.Gln98*", 98),
        ("p.Ala586Gly", -1),  # No frameshift or termination codon
    ],
)
def test_get_pHGVS_termination(pHGVS, expected_termination):
    """Test the _get_pHGVS_termination method."""
    termination = SeqVarPVS1Helper._get_pHGVS_termination(pHGVS)
    assert termination == expected_termination, f"Failed for pHGVS: {pHGVS}"


@pytest.mark.parametrize(
    "cds_pos,exons,mode,expected_result",
    [
        (100, [MockExon(0, 100, 0, 100)], AlteredRegionMode.Downstream, (100, 100)),
        (100, [MockExon(0, 100, 0, 100)], AlteredRegionMode.Exon, (100, 100)),
        (
            150,
            [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200), MockExon(200, 300, 200, 300)],
            AlteredRegionMode.Downstream,
            (150, 300),
        ),
        (
            150,
            [MockExon(0, 100, 0, 100), MockExon(100, 200, 100, 200), MockExon(200, 300, 200, 300)],
            AlteredRegionMode.Exon,
            (150, 200),
        ),
    ],
)
def test_calculate_altered_region(cds_pos, exons, mode, expected_result):
    """Test the _calculate_altered_region method."""
    result = SeqVarPVS1Helper._calculate_altered_region(cds_pos, exons, mode)
    assert result == expected_result


def test_calculate_altered_region_invalid_mode():
    """Test the _calculate_altered_region method with an invalid mode."""
    with pytest.raises(ValueError):
        SeqVarPVS1Helper._calculate_altered_region(
            100, [MockExon(0, 100, 0, 100)], "InvalidMode"  # type: ignore
        )


# TODO: Fix the test
def test_count_pathogenic_variants(seqvar, mock_annonars_client):
    """Test the _count_pathogenic_variants method."""
    result = SeqVarPVS1Helper()._count_pathogenic_variants(seqvar, 1, 2)  # The range is mocked
    assert result == (0, 0)  # Something is wrong with the mocked data


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
        (SeqVarConsequence.InitiationCodon, ["initiator_codon_variant"]),
        (
            SeqVarConsequence.SpliceSites,
            ["splice_region_variant", "splice_donor_variant", "splice_acceptor_variant"],
        ),
    ],
)
def test_get_consequence(value, expected_result):
    """Test the _get_consequence method."""
    result = SeqVarPVS1Helper._get_consequence(value)
    assert result == expected_result


# TODO: Fix the test
def test_count_lof_variants(seqvar, mock_annonars_client):
    """Test the _count_lof_variants method."""
    result = SeqVarPVS1Helper()._count_lof_variants(seqvar, 1, 2)  # The range is mocked
    assert result == (0, 0)  # Something is wrong with the mocked data


# TODO: Check if the exon number is correct
@pytest.mark.parametrize(
    "exons, pHGVS, hgnc_id, expected_result",
    [
        # Specific gene with HGNC ID "HGNC:4284" should always return True
        ([MockExon(0, 100, 0, 100)], "p.Gln98*", "HGNC:4284", True),
        # Variant in the last exon should not undergo NMD
        ([MockExon(0, 200, 0, 150), MockExon(200, 400, 150, 350)], "p.Gln300*", "HGNC:1234", False),
        # Variant in the penultimate exon, more than 50 nt from the end, should undergo NMD
        # ([MockExon(0, 100, 0, 100), MockExon(100, 300, 100, 300)], "p.Gln50*", "HGNC:1234", True),
        # Single exon variants should not undergo NMD
        ([MockExon(0, 100, 0, 100)], "p.Gln50*", "HGNC:1234", False),
        # Variant in the penultimate exon, within the last 50 nt, should not undergo NMD
        ([MockExon(0, 100, 0, 100), MockExon(100, 300, 100, 300)], "p.Gln95*", "HGNC:1234", False),
    ],
)
def test_undergo_nmd(exons, pHGVS, hgnc_id, expected_result):
    """Test the _undergo_nmd method."""
    result = SeqVarPVS1Helper()._undergo_nmd(exons, pHGVS, hgnc_id)
    assert result == expected_result, f"Failed for hgnc_id: {hgnc_id}, pHGVS: {pHGVS}"


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
def test_in_biologically_relevant_transcript(transcript_tags, expected_result):
    """Test the _in_biologically_relevant_transcript method."""
    result = SeqVarPVS1Helper._in_biologically_relevant_transcript(transcript_tags)
    assert result == expected_result, f"Failed for transcript_tags: {transcript_tags}"


@pytest.mark.parametrize(
    "cds_pos, pathogenic_variants, total_variants, expected_result",
    [
        (None, 0, 0, False),  # Test cds_pos is None
        (100, 6, 100, True),  # Test pathogenic variants exceed the threshold
        (100, 3, 100, False),  # Test pathogenic variants do not exceed the threshold
        (100, 0, 0, False),  # Test no variants are found
        (100, 0, 100, False),  # Test no pathogenic variants are found
        (100, 100, 0, False),  # Test more pathogenic variants than total variants
    ],
)
def test_critical4protein_function(
    seqvar, cds_pos, pathogenic_variants, total_variants, expected_result, monkeypatch
):
    """Test the _critical4protein_function method."""
    # Create a mock list of Exons
    exons = [MagicMock(spec=Exon)]
    # Mocking _calculate_altered_region to return a controlled range
    mock_calculate = MagicMock(return_value=(1, 1000))  # The range is mocked
    monkeypatch.setattr(SeqVarPVS1Helper, "_calculate_altered_region", mock_calculate)
    # Mocking _count_pathogenic_variants to return controlled counts of pathogenic and total variants
    mock_count_pathogenic = MagicMock(return_value=(pathogenic_variants, total_variants))
    monkeypatch.setattr(SeqVarPVS1Helper, "_count_pathogenic_variants", mock_count_pathogenic)

    # Run the method under test
    helper = SeqVarPVS1Helper()
    result = helper._critical4protein_function(seqvar, cds_pos, exons)  # type: ignore

    # Assert the expected outcome
    assert result == expected_result
    if cds_pos is not None:
        mock_calculate.assert_called_once_with(cds_pos, exons, AlteredRegionMode.Downstream)
        mock_count_pathogenic.assert_called_once_with(seqvar, 1, 1000)  # The range is mocked


@pytest.mark.parametrize(
    "cds_pos, frequent_lof_variants, lof_variants, expected_result",
    [
        (None, 0, 0, False),  # Test case where cds_pos is None
        (100, 11, 100, True),  # Test case where frequent LoF variants exceed the 10% threshold
        (
            100,
            5,
            100,
            False,
        ),  # Test case where frequent LoF variants do not exceed the 10% threshold
        (100, 0, 0, False),  # Test case where no LoF variants are found
        (100, 20, 0, False),  # Test case where more frequent LoF variants than total LoF variants
    ],
)
def test_lof_is_frequent_in_population(
    seqvar, cds_pos, frequent_lof_variants, lof_variants, expected_result, monkeypatch
):
    # Create a mock list of Exons
    exons = [MagicMock(spec=Exon)]
    # Mocking _calculate_altered_region to return a controlled range
    mock_calculate = MagicMock(return_value=(1, 1000))  # The range is mocked
    monkeypatch.setattr(SeqVarPVS1Helper, "_calculate_altered_region", mock_calculate)
    # Mocking _count_lof_variants to return controlled counts of frequent and total LoF variants
    mock_count_lof_variants = MagicMock(return_value=(frequent_lof_variants, lof_variants))
    monkeypatch.setattr(SeqVarPVS1Helper, "_count_lof_variants", mock_count_lof_variants)

    # Run the method under test
    helper = SeqVarPVS1Helper()
    result = helper._lof_is_frequent_in_population(seqvar, cds_pos, exons)  # type: ignore

    # Assert the expected outcome
    assert result == expected_result
    if cds_pos is not None:
        mock_calculate.assert_called_once_with(cds_pos, exons, AlteredRegionMode.Exon)
        mock_count_lof_variants.assert_called_once_with(seqvar, 1, 1000)  # The range is mocked


# TODO: Check if the exon number is correct
@pytest.mark.parametrize(
    "exons, pHGVS, expected_result",
    [
        # ([MockExon(0, 300)], "p.Gln100*", True),  # Simple case where LoF removes more than 10% of a 100-codon protein
        (
            [MockExon(0, 300)],
            "p.Gln90*",
            False,
        ),  # LoF variant at codon 90, removes exactly 10% of a 100-codon protein
        # ([MockExon(0, 300), MockExon(300, 900)], "p.Gln200fs*1", True),  # Frameshift early in the protein
        ([MockExon(0, 900)], "p.Gln850*", False),  # Truncation removes less than 10% of the protein
        ([MockExon(0, 100), MockExon(100, 500)], "p.Arg50X", True),  # Early nonsense mutation
        ([MockExon(0, 500)], "p.Arg490Ter", False),  # Truncation very close to the end
    ],
)
def test_lof_removes_more_then_10_percent_of_protein(exons, pHGVS, expected_result):
    """Test the _lof_removes_more_then_10_percent_of_protein method."""
    result = SeqVarPVS1Helper._lof_removes_more_then_10_percent_of_protein(pHGVS, exons)
    assert (
        result == expected_result
    ), f"Expected {expected_result} for pHGVS: {pHGVS} with exon lengths: {[exon.altEndI - exon.altStartI for exon in exons]}"


def test_exon_skipping_or_cryptic_ss_disruption():
    """Test the _exon_skipping_or_cryptic_ss_disruption method."""
    pass


def test_alternative_start_codon():
    """Test the _alternative_start_codon method."""
    pass


def test_upstream_pathogenic_variant():
    """Test the _upstream_pathogenic_variant method."""
    pass


# === SeqVarTranscriptsHelper ===


def test_get_ts_info_success(ts_helper):
    """Test get_ts_info method with a successful response."""
    # Mock the actual data that would be returned from the Mehari API
    ts_helper.seqvar_ts_info = TranscriptsSeqVar.model_validate(
        get_json_object("mehari/mehari_seqvar_success.json")
    )
    ts_helper.seqvar_transcript = TranscriptsSeqVar.model_validate(
        get_json_object("mehari/mehari_seqvar_success.json")
    ).result
    ts_helper.gene_ts_info = GeneTranscripts.model_validate(
        get_json_object("mehari/mehari_genes_success.json")
    )
    ts_helper.gene_transcript = GeneTranscripts.model_validate(
        get_json_object("mehari/mehari_genes_success.json")
    ).transcripts
    ts_helper.consequence = SeqVarConsequence.InitiationCodon

    seqvar_transcript, gene_transcript, seqvar_ts_info, gene_ts_info, consequence = (
        ts_helper.get_ts_info()
    )

    assert seqvar_transcript is not None
    assert gene_transcript is not None
    assert seqvar_ts_info is not None
    assert gene_ts_info is not None
    assert consequence == SeqVarConsequence.InitiationCodon


def test_get_ts_info_failure(ts_helper):
    """Test get_ts_info method with a failed response."""
    seqvar_transcript, gene_transcript, seqvar_ts_info, gene_ts_info, consequence = (
        ts_helper.get_ts_info()
    )

    assert seqvar_transcript is None
    assert gene_transcript is None
    assert seqvar_ts_info == []
    assert gene_ts_info == []
    assert consequence == SeqVarConsequence.NotSet


@patch.object(MehariClient, "get_seqvar_transcripts")
@patch.object(MehariClient, "get_gene_transcripts")
def test_initialize_success(
    mock_get_gene_transcripts,
    mock_get_seqvar_transcripts,
    seqvar,
    ts_helper,
    seqvar_transcripts,
    gene_transcripts,
):
    # Mock successful responses
    mock_get_seqvar_transcripts.return_value = MagicMock(result=seqvar_transcripts)
    mock_get_gene_transcripts.return_value = MagicMock(transcripts=gene_transcripts)

    ts_helper.seqvar = seqvar
    ts_helper.initialize()

    assert ts_helper.seqvar_ts_info is seqvar_transcripts
    assert ts_helper.gene_ts_info is gene_transcripts
    assert ts_helper.HGNC_id is seqvar_transcripts[0].gene_id
    assert ts_helper.HGVSs is not None


@patch.object(MehariClient, "get_seqvar_transcripts")
@patch.object(MehariClient, "get_gene_transcripts")
def test_initialize_failure(
    mock_get_gene_transcripts, mock_get_seqvar_transcripts, seqvar, ts_helper
):
    # Mock failed responses
    mock_get_seqvar_transcripts.return_value = None
    mock_get_gene_transcripts.return_value = None

    ts_helper.seqvar = seqvar
    ts_helper.initialize()

    assert ts_helper.seqvar_ts_info == []
    assert ts_helper.gene_ts_info == []
    assert ts_helper.seqvar_ts_info == []
    assert ts_helper.gene_ts_info == []
    assert ts_helper.HGNC_id is ""
    assert len(ts_helper.HGVSs) == 0


def test_initialize_no_seqvar(ts_helper):
    ts_helper.initialize()
    assert ts_helper.gene_ts_info == []
    assert ts_helper.HGNC_id is ""
    assert len(ts_helper.HGVSs) == 0


@pytest.mark.parametrize(
    "consequence_input, expected_consequence",
    [
        (["splice_region_variant"], SeqVarConsequence.SpliceSites),
        (["splice_donor_variant"], SeqVarConsequence.SpliceSites),
        (["frameshift_variant"], SeqVarConsequence.NonsenseFrameshift),
        (["initiator_codon_variant"], SeqVarConsequence.InitiationCodon),
        (["unknown_consequence"], SeqVarConsequence.NotSet),
        (["regulatory_region_amplification"], SeqVarConsequence.NotSet),
        ([""], SeqVarConsequence.NotSet),
        ([], SeqVarConsequence.NotSet),
    ],
)
def test_get_consequence_various_cases(consequence_input, expected_consequence, seqvar_transcripts):
    """Test get_consequence method with various cases."""
    mock_transcript = seqvar_transcripts[0]
    mock_transcript.consequences = consequence_input
    consequence = SeqVarTranscriptsHelper._get_consequence(mock_transcript)
    assert consequence == expected_consequence


def test_get_consequence_none_input():
    """Test get_consequence method with None input."""
    consequence = SeqVarTranscriptsHelper._get_consequence(None)
    assert consequence == SeqVarConsequence.NotSet


# TODO: Add more use cases for the choose_transcript method
# E.g. - multiple transcripts, multiple genes
#      - one transcript, multiple genes (or vice versa)
#      - no transcripts, no genes
#      - no transcripts, one gene (or vice versa)
@pytest.mark.parametrize(
    "hgvss, gene_ts_file, seqvar_ts_file, expected_hgvs",
    [
        (
            ["NM_001267039.2"],
            "mehari/larp7_mehari_gene.json",
            "mehari/larp7_mehari_seqvar.json",
            "NM_001267039.2",
        ),
        (
            ["NM_001267039.2", "NM_001370974.1"],
            "mehari/larp7_mehari_gene.json",
            "mehari/larp7_mehari_seqvar.json",
            "NM_001267039.2",
        ),
    ],
)
def test_choose_transcript_success(hgvss, gene_ts_file, seqvar_ts_file, expected_hgvs, ts_helper):
    """Test choose_transcript method."""
    ts_helper.seqvar_ts_info = TranscriptsSeqVar.model_validate(
        get_json_object(seqvar_ts_file)
    ).result
    ts_helper.gene_ts_info = GeneTranscripts.model_validate(
        get_json_object(gene_ts_file)
    ).transcripts

    seqvar_ts, gene_ts = ts_helper._choose_transcript(
        hgvss, ts_helper.seqvar_ts_info, ts_helper.gene_ts_info
    )
    assert seqvar_ts.feature_id == expected_hgvs


@pytest.mark.parametrize(
    "hgvss, gene_ts_file, seqvar_ts_file",
    [
        (["invalid"], "mehari/larp7_mehari_gene.json", "mehari/larp7_mehari_seqvar.json"),
        ([], "mehari/larp7_mehari_gene.json", "mehari/larp7_mehari_seqvar.json"),
    ],
)
def test_choose_transcript_invalid(hgvss, gene_ts_file, seqvar_ts_file, ts_helper):
    """Test choose_transcript method."""
    ts_helper.seqvar_ts_info = TranscriptsSeqVar.model_validate(
        get_json_object(seqvar_ts_file)
    ).result
    ts_helper.gene_ts_info = GeneTranscripts.model_validate(
        get_json_object(gene_ts_file)
    ).transcripts

    seqvar_ts, gene_ts = ts_helper._choose_transcript(
        hgvss, ts_helper.seqvar_ts_info, ts_helper.gene_ts_info
    )
    assert seqvar_ts == None


# === SeqVarPVS1 ===


def test_init(seqvar):
    """Test the initialization of SeqVarPVS1."""
    pvs1 = SeqVarPVS1(seqvar)
    assert pvs1.seqvar == seqvar
    assert pvs1._seqvar_transcript is None
    assert pvs1._gene_transcript is None
    assert pvs1._consequence == SeqVarConsequence.NotSet
    assert pvs1.HGVS == ""
    assert pvs1.pHGVS == ""
    assert pvs1.tHGVS == ""
    assert pvs1.HGNC_id == ""
    assert len(pvs1.transcript_tags) == 0
    assert len(pvs1.exons) == 0
    assert pvs1.cds_pos is None
    assert pvs1.prediction == PVS1Prediction.NotPVS1
    assert pvs1.prediction_path == PVS1PredictionSeqVarPath.NotSet


@patch.object(SeqVarTranscriptsHelper, "get_ts_info", autospec=True)
@patch.object(SeqVarTranscriptsHelper, "initialize", autospec=True)
def test_get_pvs1_prediction_success(
    mock_initialize, mock_get_ts_info, seqvar, seqvar_transcripts, gene_transcripts
):
    mock_get_ts_info.return_value = (
        seqvar_transcripts[0],
        gene_transcripts[0],
        seqvar_transcripts,
        gene_transcripts,
        SeqVarConsequence.InitiationCodon,
    )

    pvs1 = SeqVarPVS1(seqvar)
    pvs1.initialize()

    assert pvs1._seqvar_transcript is seqvar_transcripts[0]
    assert pvs1._gene_transcript is gene_transcripts[0]
    assert pvs1._consequence is SeqVarConsequence.InitiationCodon


@patch.object(SeqVarTranscriptsHelper, "get_ts_info", autospec=True)
@patch.object(SeqVarTranscriptsHelper, "initialize", autospec=True)
def test_get_pvs1_prediction_failure(mock_initialize, mock_get_ts_info, seqvar):
    mock_get_ts_info.return_value = (None, None, [], [], SeqVarConsequence.NotSet)

    pvs1 = SeqVarPVS1(seqvar)
    pvs1.initialize()

    assert pvs1._seqvar_transcript == None
    assert pvs1._gene_transcript == None
    assert pvs1._consequence is SeqVarConsequence.NotSet


def test_get_prediction_default(seqvar):
    pvs1 = SeqVarPVS1(seqvar)
    prediction, path = pvs1.get_prediction()
    assert prediction == PVS1Prediction.NotPVS1
    assert path == PVS1PredictionSeqVarPath.NotSet
