from __future__ import annotations

from pathlib import Path

import pytest

from scripts.dev.export_run_viewer import export_run_viewer
from scripts.dev.run_experiment import run_experiment_from_seed


def test_export_run_viewer_writes_static_html_from_run_artifacts(tmp_path: Path) -> None:
    """Protects INV-X-004."""
    run_dir = tmp_path / "editable_run"
    run_experiment_from_seed(
        seed_path=Path("seeds/editable-marketing-demo.json"),
        output_dir=run_dir,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'editable.db'}",
        reset_db=True,
    )

    viewer_path = export_run_viewer(run_dir=run_dir)

    html = viewer_path.read_text(encoding="utf-8")
    assert viewer_path == run_dir / "viewer.html"
    assert "Net Working Platform Run Viewer" in html
    assert "https://unpkg.com/cytoscape" in html
    assert '<script id="run-summary" type="application/json">' in html
    assert '<script id="initial-graph" type="application/json">' in html
    assert '<script id="final-graph" type="application/json">' in html
    assert '<script id="graph-events" type="application/json">' in html
    assert "editable-marketing-demo" in html
    assert "negotiation_editable_alpha_beta" in html
    assert "Client Alpha has lifecycle marketing experience" in html
    assert "Initial Graph" in html
    assert "Final Graph" in html
    assert "Selected Turn State" in html
    assert "Timeline" in html
    assert "Legend" in html
    assert "Principal / Principal Agent" in html
    assert "Client / Client Agent" in html
    assert "Turn Details" in html
    assert "◀" in html
    assert "▶" in html
    assert "Auto-play" in html
    assert "turn-slider" in html
    assert "turn-position" in html
    assert "function graphAtTurn" in html
    assert "function applyGraphDelta" in html
    assert "function nodeClasses" in html
    assert "function roleMaps" in html
    assert "function selectTurn" in html
    assert "function toggleAutoplay" in html
    assert "function inspectNode" in html
    assert "function inspectEdge" in html
    assert "function relatedRecordsForNode" in html
    assert "function relatedRecordsForEdge" in html
    assert "Related Protocol Timeline" in html
    assert "Raw JSON" in html
    assert "function protocolSignalRows" in html
    assert "function renderInspection" in html
    assert "function renderSelectedTurnDetails" in html
    assert "function subjectMentionsNode" in html
    assert "represented_party_id" in html
    assert "cy.on('tap', 'node'" in html
    assert "cy.on('tap', 'edge'" in html
    assert "const stablePositions" in html
    assert "layout: { name: 'preset'" in html
    assert "#dc2626" in html


def test_export_run_viewer_can_write_custom_output_file(tmp_path: Path) -> None:
    """Protects INV-X-004."""
    run_dir = tmp_path / "editable_run"
    output_file = tmp_path / "demo-viewer.html"
    run_experiment_from_seed(
        seed_path=Path("seeds/editable-marketing-demo.json"),
        output_dir=run_dir,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'editable.db'}",
        reset_db=True,
    )

    viewer_path = export_run_viewer(run_dir=run_dir, output_file=output_file)

    assert viewer_path == output_file
    assert output_file.exists()


def test_export_run_viewer_reports_missing_run_artifacts(tmp_path: Path) -> None:
    """Protects INV-X-004."""
    run_dir = tmp_path / "missing_run"
    run_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="Run artifact not found"):
        export_run_viewer(run_dir=run_dir)
