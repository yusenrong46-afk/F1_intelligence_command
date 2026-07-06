from burnaby_prototype.m8.extraction.rule_schema import SourceSpan
from burnaby_prototype.m8.retrieval.evidence_bundle import build_evidence_bundle
from burnaby_prototype.m8.retrieval.hybrid_index import HybridM8Index
from burnaby_prototype.m8.retrieval.query_planner import plan_query


def spans():
    return [
        SourceSpan(
            city="burnaby_r1",
            document_id="source.pdf",
            page=1,
            section_id="101.3",
            block_type="clause",
            text="In R1 the maximum height for a front principal building is 10 m.",
            metadata={"evidence_id": "ev_height", "rule_family": "height"},
        ),
        SourceSpan(
            city="burnaby_r1",
            document_id="source.pdf",
            page=2,
            section_id="101.4",
            block_type="clause",
            text="Minimum lot area is 281 m2.",
            metadata={"evidence_id": "ev_area", "rule_family": "lot_area"},
        ),
    ]


def test_hybrid_retrieval_finds_height_and_preserves_metadata():
    index = HybridM8Index(spans())
    planned = plan_query("maximum height R1", city="burnaby_r1", rule_family="height")
    hits = index.search(planned, top_k=3)

    assert hits
    assert hits[0].span.metadata["evidence_id"] == "ev_height"
    assert hits[0].span.page == 1


def test_metadata_filter_narrows_results():
    index = HybridM8Index(spans())

    hits = index.search("maximum height", filters={"page": 2}, top_k=3)

    assert hits == []


def test_evidence_bundle_preserves_source_provenance():
    index = HybridM8Index(spans())
    hits = index.search("maximum height", top_k=1)
    bundle = build_evidence_bundle("maximum height", hits)

    assert bundle.spans[0].section_id == "101.3"
    assert bundle.pointers[0].evidence_id == "ev_height"
    assert bundle.pointers[0].source_span is not None
