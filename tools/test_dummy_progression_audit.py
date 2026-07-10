#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from tools.dummy_progression_audit import (
        EconomyLedger,
        ProgressionAnomaly,
        ProgressionSnapshot,
        ProgressionSpecialization,
        audit_progression_checkpoint,
        compact_anomaly_payload,
        parse_progression_hunt_request,
        parse_progression_service_request,
        parse_progression_snapshot,
        write_compact_anomaly_summary,
    )
except ModuleNotFoundError:
    from dummy_progression_audit import (
        EconomyLedger,
        ProgressionAnomaly,
        ProgressionSnapshot,
        ProgressionSpecialization,
        audit_progression_checkpoint,
        compact_anomaly_payload,
        parse_progression_hunt_request,
        parse_progression_service_request,
        parse_progression_snapshot,
        write_compact_anomaly_summary,
    )


class ProgressionSnapshotTests(unittest.TestCase):
    def test_parse_progression_snapshot_keeps_economy_specs_inventory_and_skills(self) -> None:
        snapshot = parse_progression_snapshot(
            {
                "player": {
                    "name": "GrowthAlb",
                    "account": "growthalb001",
                    "level": 6,
                    "class": "Armsman",
                    "classId": 2,
                    "realm": "Albion",
                    "experience": 12345,
                    "experienceForCurrentLevel": 12000,
                    "experienceForNextLevel": 15000,
                    "experienceIntoLevel": 345,
                    "experienceNeededForLevel": 3000,
                    "moneyCopper": 890,
                    "specialtyPoints": 4,
                    "specializations": [
                        {"name": "Slash", "keyName": "Slash", "level": 5, "trainable": True}
                    ],
                    "inventory": [
                        {
                            "slot": 40,
                            "iTemplate_Id": "loot_sword",
                            "name": "Sword",
                            "count": 2,
                            "sellPrice": 12,
                            "backpack": True,
                        }
                    ],
                },
                "skills": [{"name": "Shield Bash", "level": 5}],
                "spellLines": [{"entries": [{"name": "Guard", "level": 4}]}],
            }
        )

        self.assertEqual(snapshot.level, 6)
        self.assertEqual(snapshot.money_copper, 890)
        self.assertEqual(snapshot.specialization_levels, {"Slash": 5})
        self.assertEqual(snapshot.backpack_sell_value, 24)
        self.assertEqual(snapshot.usable_skills, ("Shield Bash|5",))
        self.assertEqual(snapshot.usable_spells, ("Guard|4",))

    def test_training_without_spec_gain_is_an_error(self) -> None:
        before = ProgressionSnapshot(
            level=6,
            specializations=(ProgressionSpecialization("Slash", "Slash", 4, True),),
        )
        after = ProgressionSnapshot(
            level=6,
            specializations=(ProgressionSpecialization("Slash", "Slash", 4, True),),
        )

        anomalies = audit_progression_checkpoint(before, after, expected_level=6, training_requested=True)

        self.assertIn("training_no_spec_gain", {row.code for row in anomalies})

    def test_training_skill_rank_upgrade_is_not_a_catalog_regression(self) -> None:
        before = ProgressionSnapshot(
            level=1,
            usable_skills=("Slash|1", "Shield|1"),
        )
        after = ProgressionSnapshot(
            level=2,
            usable_skills=("Slash|2", "Shield|1", "Parry|2"),
            specializations=(ProgressionSpecialization("Slash", "Slash", 2, True),),
        )

        anomalies = audit_progression_checkpoint(
            before,
            after,
            expected_level=2,
            training_requested=True,
        )

        self.assertNotIn("usable_catalog_regression", {row.code for row in anomalies})

    def test_economy_ledger_separates_hunt_coin_and_service_net(self) -> None:
        ledger = EconomyLedger(
            hunt_start_copper=100,
            service_start_copper=175,
            service_end_copper=145,
            expected_sale_copper=20,
            expected_purchase_copper=50,
        )

        self.assertEqual(ledger.mob_coin_copper, 75)
        self.assertEqual(ledger.service_net_copper, -30)
        self.assertEqual(ledger.unexplained_service_copper, 0)

    def test_compact_summary_routes_green_runs_without_a_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "anomaly-summary.json"
            write_compact_anomaly_summary(path, [], run_id="run-1", checkpoints=49)

            text = path.read_text(encoding="utf-8")

        self.assertIn('"anomalyCount": 0', text)
        self.assertIn('"default": "none"', text)

    def test_compact_summary_groups_repeated_deterministic_anomalies(self) -> None:
        anomalies = [
            ProgressionAnomaly(
                "training_no_spec_gain",
                "error",
                "Training did not increase a specialization.",
                {"level": level},
            )
            for level in range(2, 32)
        ]

        payload = compact_anomaly_payload(anomalies, run_id="run-2", checkpoints=30)

        self.assertEqual(payload["anomalyCount"], 30)
        self.assertEqual(payload["anomalyGroups"][0]["count"], 30)
        self.assertEqual(payload["anomaliesTruncated"], 10)
        self.assertEqual(payload["modelRouting"]["decision"], "none")

    def test_service_request_selects_only_the_current_account_plan(self) -> None:
        payload = {
            "progressionService": {
                "requestId": "alb-l6",
                "level": 6,
                "serviceLocation": {"region": 1, "x": 100, "y": 200, "z": 300},
                "huntLocation": {"region": 1, "x": 400, "y": 500, "z": 600},
                "statusDirectory": "status",
                "serviceNpcName": "Brother Penric",
                "members": {
                    "growthalb001": {
                        "specs": "Slash|6;Shields|5",
                        "sellSlots": [40, 41],
                        "buySlots": [3],
                        "equipSlots": [42],
                    }
                },
            }
        }

        request = parse_progression_service_request(payload, account="GrowthAlb001")
        skipped = parse_progression_service_request(payload, account="GrowthAlb002")

        self.assertIsNotNone(request)
        self.assertEqual(request.sell_slots, (40, 41))
        self.assertEqual(request.buy_slots, (3,))
        self.assertEqual(request.equip_slots, (42,))
        self.assertIsNone(skipped)

    def test_service_request_requires_both_locations(self) -> None:
        request = parse_progression_service_request(
            {
                "progression_service": {
                    "request_id": "bad",
                    "level": 7,
                    "service_location": {"region": 1, "x": 100, "y": 200},
                }
            },
            account="growthalb001",
        )

        self.assertIsNone(request)

    def test_hunt_request_parses_dynamic_quest_target_route(self) -> None:
        request = parse_progression_hunt_request(
            {
                "progressionHunt": {
                    "requestId": "quest-route-1",
                    "level": 8,
                    "huntLocation": {"region": 100, "x": 700, "y": 800, "z": 900},
                    "requireTargetName": "young grendelorm",
                    "minTargetLevel": 7,
                    "maxTargetLevel": 9,
                }
            },
            account="growthmid001",
        )

        self.assertIsNotNone(request)
        self.assertEqual(request.require_target_name, "young grendelorm")
        self.assertEqual(request.hunt_location.region, 100)
        self.assertEqual(request.max_target_level, 9)


if __name__ == "__main__":
    unittest.main()
