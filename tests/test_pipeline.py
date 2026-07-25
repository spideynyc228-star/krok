import json
import tempfile
import unittest
from pathlib import Path

from economics import EconomicsConfig, build_economics
from main import run_pipeline


class PipelineTest(unittest.TestCase):
    def test_economics_allocates_the_full_period_tco(self):
        rows = [{"request_id": "a", "agent_id": "x", "user_id": "u", "created_at": "2026-01-05", "total_tokens_est": 100, "estimated_minutes_saved": 20, "agent_failed": False}]
        result = build_economics(rows, EconomicsConfig(server_capex_rub=1200, amortization_years=1, server_power_kw=0, monthly_license_per_active_user_rub=0, value_realisation_rate=1))
        self.assertAlmostEqual(result["summary"]["period_tco_rub"], result["by_request"]["a"]["allocated_cost_rub"], places=2)

    def test_pipeline_writes_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dialogs = root / "dialogs"
            dialogs.mkdir()
            (dialogs / "one.json").write_text(json.dumps({"user_id": "u", "session_id": "s", "agent_id": "a", "created_at": "2026-01-01T00:00:00Z", "scenario_type": "Планирование и календарь", "scenario": "Встречи", "messages": [{"role": "user", "content": "Найди время для встречи"}, {"role": "tool", "tool_name": "calendar.find", "result": {"status": "ok"}}]}), encoding="utf-8")
            config = root / "economics.json"
            config.write_text(json.dumps({"server_capex_rub": 1200, "amortization_years": 1, "server_power_kw": 0, "monthly_license_per_active_user_rub": 0}), encoding="utf-8")
            output = root / "outputs"
            result = run_pipeline(dialogs, output, config)
            self.assertEqual(result["dialogs"], 1)
            self.assertTrue((output / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
