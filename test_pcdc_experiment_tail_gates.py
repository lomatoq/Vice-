import unittest

from vice_compiler.experiment1b_pricing_recall import _pricing_machine_gate
from vice_compiler.experiment2_oracle_extraction import _oracle_machine_gate
from vice_compiler.experiment3_certificate_discrimination import (
    _certificate_machine_gate,
)


class ExperimentTailGateTests(unittest.TestCase):
    def test_pricing_gate_rejects_hidden_semantic_class_failure(self) -> None:
        common = {
            "acceptable_recall": 0.99,
            "p95_pricing": 20.0,
            "column_ratio": 0.10,
            "no_manual": True,
            "feasible": True,
        }
        self.assertTrue(_pricing_machine_gate(class_floor=0.95, **common))
        self.assertFalse(_pricing_machine_gate(class_floor=0.20, **common))

    def test_oracle_gate_rejects_hidden_semantic_class_failure(self) -> None:
        common = {
            "acceptable_rate": 0.99,
            "catastrophes": 0,
            "median_ms": 10.0,
            "p95_ms": 50.0,
            "fallback_feasible": True,
        }
        self.assertTrue(_oracle_machine_gate(class_floor=0.95, **common))
        self.assertFalse(_oracle_machine_gate(class_floor=0.20, **common))

    def test_certificate_gate_rejects_hidden_pair_type_failure(self) -> None:
        common = {
            "correct_rate": 0.99,
            "micro_recall": 0.99,
            "catastrophe_rate": 0.0,
            "ece": 0.01,
        }
        self.assertTrue(_certificate_machine_gate(type_floor=0.90, **common))
        self.assertFalse(_certificate_machine_gate(type_floor=0.20, **common))


if __name__ == "__main__":
    unittest.main()
