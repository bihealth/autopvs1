# generated by datamodel-codegen:
#   filename:  LPA_var_info.json
#   timestamp: 2024-05-02T12:23:07+00:00

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class VariantQuery(BaseModel):
    genome_release: str
    chromosome: str
    pos: int
    reference: str
    alternative: str


class Cadd(BaseModel):
    ConsDetail: Optional[str] = None
    PolyPhenVal: Optional[float] = None
    SpliceAI_acc_gain: Optional[int] = Field(..., alias="SpliceAI-acc-gain")
    SpliceAI_acc_loss: Optional[int] = Field(..., alias="SpliceAI-acc-loss")
    SpliceAI_don_gain: Optional[int] = Field(..., alias="SpliceAI-don-gain")
    SpliceAI_don_loss: Optional[int] = Field(..., alias="SpliceAI-don-loss")


class GnomadExomes(BaseModel):
    alleleCounts: List[AlleleCount]


class Dbnsfp(BaseModel):
    HGVSc_ANNOVAR: Optional[str] = None
    HGVSp_ANNOVAR: Optional[str] = None
    HGVSc_snpEff: Optional[str] = None
    HGVSp_snpEff: Optional[str] = None
    HGVSc_VEP: Optional[str] = None
    HGVSp_VEP: Optional[str] = None


class Overall(BaseModel):
    ac: Optional[int] = None
    an: Optional[int] = None
    nhomalt: Optional[int] = None
    af: Optional[float] = None


class Xx(BaseModel):
    ac: Optional[int] = None
    an: Optional[int] = None
    nhomalt: Optional[int] = None
    af: Optional[float] = None


class Xy(BaseModel):
    ac: Optional[int] = None
    an: Optional[int] = None
    nhomalt: Optional[int] = None
    af: Optional[float] = None


class Counts(BaseModel):
    overall: Optional[Overall] = None
    xx: Optional[Xx] = None
    xy: Optional[Xy] = None


class ByAncestryGroupItem(BaseModel):
    ancestryGroup: Optional[str] = None
    counts: Optional[Counts] = None
    faf95: Optional[float] = None
    faf99: Optional[float] = None


class BySex(BaseModel):
    overall: Optional[Overall] = None
    xx: Optional[Xx] = None
    xy: Optional[Xy] = None


class Raw(BaseModel):
    ac: Optional[int] = None
    an: Optional[int] = None
    nhomalt: Optional[int] = None
    af: Optional[float] = None


class AlleleCount(BaseModel):
    cohort: Optional[str] = None
    byAncestryGroup: Optional[List[ByAncestryGroupItem]] = None
    bySex: Optional[BySex] = None
    raw: Optional[Raw] = None
    grpmax: Optional[str] = None
    afGrpmax: Optional[float] = None
    acGrpmax: Optional[int] = None
    anGrpmax: Optional[int] = None
    nhomaltGrpmax: Optional[int] = None


class GnomadGenomes(BaseModel):
    chrom: Optional[str] = None
    pos: Optional[int] = None
    refAllele: Optional[str] = None
    altAllele: Optional[str] = None
    alleleCounts: Optional[List[AlleleCount]] = None
    effectInfo: Optional[Any] = None
    variantInfo: Optional[Any] = None
    qualityInfo: Optional[Any] = None
    ageInfo: Optional[Any] = None
    vrsInfo: Optional[Any] = None


class ReferenceAssertion(BaseModel):
    rcv: Optional[str] = None
    title: Optional[str] = None
    clinicalSignificance: Optional[str] = None
    reviewStatus: Optional[str] = None


class ClinvarItem(BaseModel):
    release: Optional[str] = None
    chromosome: Optional[str] = None
    start: Optional[int] = None
    stop: Optional[int] = None
    reference: Optional[str] = None
    alternative: Optional[str] = None
    vcv: Optional[str] = None
    referenceAssertions: Optional[List[ReferenceAssertion]] = None


class VariantResult(BaseModel):
    cadd: Optional[Cadd] = None
    dbsnp: Optional[Any] = None
    dbnsfp: Optional[Dbnsfp] = None
    dbscsnv: Optional[Any] = None
    gnomad_mtdna: Optional[Any] = None
    gnomad_exomes: Optional[GnomadExomes] = None
    gnomad_genomes: Optional[GnomadGenomes] = None
    helixmtdb: Optional[Any] = None
    ucsc_conservation: Optional[Any] = None
    clinvar: Optional[ClinvarItem] = None


class AnnonarsVariantResponse(BaseModel):
    server_version: str
    query: VariantQuery
    result: VariantResult
