from ares_console.diagnostics import RouteDiagnosticsRunner


def test_diagnostics_builds_every_route_without_live_network() -> None:
    runner = RouteDiagnosticsRunner()
    try:
        report = runner.run(live=False)
    finally:
        runner.close()

    assert report["total"] == 82
    assert report["summary"] == {
        "skipped_stream": 2,
        "validated_build_only": 80,
    }
    assert not [
        item for item in report["results"] if item["status"].startswith("failed")
    ]
