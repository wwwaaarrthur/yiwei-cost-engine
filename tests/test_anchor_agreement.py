import csv

from scripts.compute_anchor_agreement import cohen_kappa, compute


def test_cohen_kappa_matches_known_fixture():
    pairs = [
        ("approve", "approve"),
        ("approve", "revise"),
        ("revise", "revise"),
        ("reject", "reject"),
    ]
    assert cohen_kappa(pairs) == 0.636364


def test_compute_reports_pending_when_yi_labels_are_empty(tmp_path):
    path = tmp_path / "anchors.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "input_summary",
                "critic_verdict",
                "critic_reason_summary",
                "yi_verdict",
                "yi_note",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "case_id": "case-01",
            "input_summary": "BC export sample",
            "critic_verdict": "revise",
            "critic_reason_summary": "Missing lamination.",
            "yi_verdict": "",
            "yi_note": "",
        })

    report = compute(path)
    assert report["status"] == "pending-labels"
    assert report["total_rows"] == 1
    assert report["labeled_rows"] == 0
    assert report["cohen_kappa"] is None
