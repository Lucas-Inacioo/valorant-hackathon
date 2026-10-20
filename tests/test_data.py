import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from valorant.data.quality import (
    data_signature,
    dataset_quality,
    eligible_match_ids,
    write_manifest,
)
from valorant.data.download import download_dataset, download_file
from valorant.analysis.fights import (
    aggregate_damage,
    fight_rows,
    MULTIPLE_DAMAGE,
    TRADE_POSSIBLE,
    rounds_with_next,
)
from valorant.analysis.plants import build_plants_table, cells_for_map, plant_rows
from valorant.analysis.setups import setup_rows


def location(puuid, x=0, y=0):
    return {"puuid": puuid, "location": {"x": x, "y": y}, "viewRadians": 0}


def sample_match(match_id="sample", won=True):
    participants = [("a", "Red"), ("b", "Red"), ("c", "Blue"), ("d", "Blue")]
    stats = [
        {"puuid": p, "damage": [], "kills": [], "economy": {"weapon": "", "loadoutValue": 1000}}
        for p, _ in participants
    ]
    result = {
        "roundNum": 0,
        "roundResult": "Bomb detonated",
        "roundResultCode": "Detonate",
        "bombPlanter": "a",
        "plantRoundTime": 30000,
        "plantSite": "A",
        "plantLocation": {"x": 0, "y": 0},
        "plantPlayerLocations": [
            location("a"),
            location("b", 500),
            location("c", 1000),
            location("d", 3000),
        ],
        "bombDefuser": None,
        "defuseRoundTime": None,
        "defusePlayerLocations": [],
        "winningTeam": "Red" if won else "Blue",
        "winningTeamRole": "Attacker" if won else "Defender",
        "playerStats": stats,
    }
    return {
        "matchInfo": {"matchId": match_id, "mapId": "/Test", "gameVersion": "test"},
        "players": [{"puuid": p, "teamId": t} for p, t in participants],
        "roundResults": [result],
    }


class DataRegressionTests(unittest.TestCase):
    def test_even_defender_median_is_average_of_middle_values(self):
        row = setup_rows(sample_match(), None)[0]
        self.assertEqual(row["defesa_dist_mediana"], 2000)
        self.assertEqual(row["raio_medio_aliados_ate_spike"], 500)

    def test_invalid_plants_are_kept_only_when_requested_with_reason(self):
        match = sample_match()
        match["roundResults"][0]["roundResult"] = "Round timer expired"
        self.assertEqual(plant_rows(match), [])
        raw = plant_rows(match, include_invalid=True)[0]
        self.assertFalse(raw["plant_valido"])
        self.assertIn("tempo", raw["exclusao_plant"])
        match = sample_match()
        match["roundResults"][0]["plantPlayerLocations"] = [location("a")]
        self.assertEqual(plant_rows(match), [])

    def test_damage_is_summed_and_assistance_does_not_define_class(self):
        match = sample_match()
        result = match["roundResults"][0]
        result["playerStats"][0]["damage"] = [
            {"receiver": "c", "damage": 25},
            {"receiver": "c", "damage": 35},
        ]
        result["playerStats"][1]["damage"] = [{"receiver": "c", "damage": 20}]
        result["playerStats"][2]["damage"] = [
            {"receiver": "a", "damage": 10},
            {"receiver": "a", "damage": 15},
        ]
        result["playerStats"][0]["kills"] = [
            {
                "killer": "a",
                "victim": "c",
                "timeSinceRoundStartMillis": 10000,
                "victimLocation": {"x": 1000, "y": 0},
                "playerLocations": [location("a"), location("b"), location("d")],
                "assistants": [],
                "finishingDamage": {"damageType": "Weapon", "damageItem": ""},
            }
        ]
        self.assertEqual(aggregate_damage(result)["a", "c"], 60)
        row = fight_rows(match, {})[0]
        self.assertEqual(row["dano_no_killer"], 25)
        self.assertEqual(row["fontes_dano_adversario_round"], 2)
        self.assertEqual(row["classe_luta"], MULTIPLE_DAMAGE)
        self.assertEqual(row["assistencias"], 0)
        self.assertEqual(row["troca_possivel"], TRADE_POSSIBLE)

    def test_selected_matches_recompute_references_and_empty_cells_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for match in [sample_match("won", True), sample_match("lost", False)]:
                (root / f"{match['matchInfo']['matchId']}.json").write_text(json.dumps(match))
            both = build_plants_table(root)
            one = build_plants_table(root, match_ids={"won"})
            self.assertTrue(both["esperado_vitoria_vivos"].eq(0.5).all())
            self.assertEqual(one.iloc[0]["esperado_vitoria_vivos"], 1)
            self.assertTrue(cells_for_map(one, "Test", min_plants=5).empty)
            self.assertTrue(build_plants_table(root, match_ids=[]).empty)

    def test_anomalies_are_flagged_without_inventing_cause(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            normal = sample_match()
            anomalous = sample_match("anomalous")
            empty_round = copy.deepcopy(anomalous["roundResults"][0])
            empty_round.update(roundResult="Round timer expired", bombPlanter=None)
            anomalous["roundResults"] = [dict(empty_round, roundNum=i) for i in range(24)]
            anomalous["roundResults"].append(dict(sample_match()["roundResults"][0], roundNum=24))
            (root / "normal.json").write_text(json.dumps(normal))
            (root / "anomalous.json").write_text(json.dumps(anomalous))
            self.assertEqual(eligible_match_ids(root), {"sample"})
            self.assertEqual(len(eligible_match_ids(root, include_anomalous=True)), 2)
            quality = dataset_quality(root)
            self.assertEqual(quality["anomalies"][0]["initial_empty_timer_rounds"], 24)
            self.assertIn("causa não determinada", quality["anomalies"][0]["anomalies"][0])
            self.assertEqual(len(build_plants_table(root)), 1)
            self.assertEqual(
                len(
                    build_plants_table(
                        root, match_ids=eligible_match_ids(root, include_anomalous=True)
                    )
                ),
                2,
            )

    def test_signature_tracks_metadata_and_manifest_is_explicit_without_player_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data"
            root.mkdir()
            match = sample_match()
            marker = "private-player-marker-231"
            match["players"][0]["puuid"] = marker
            match["roundResults"][0]["playerStats"][0]["puuid"] = marker
            (root / "match.json").write_text(json.dumps(match))
            first = data_signature(root)
            self.assertFalse((root.parent / "manifest.json").exists())
            (root / "maps").mkdir()
            (root / "maps" / "valorant.data.metadata.json").write_text('{"data": []}')
            self.assertNotEqual(first, data_signature(root))
            manifest = root.parent / "manifest.json"
            write_manifest(manifest, root)
            self.assertNotIn(marker, manifest.read_text())

    def test_continuity_uses_alive_count_and_excludes_resets_and_overtime(self):
        rows = pd.DataFrame(
            [
                {
                    "match_id": "m",
                    "time": "Red",
                    "round": r,
                    "loadout": 1000,
                    "venceu": False,
                    "sobreviventes": 1,
                }
                for r in range(1, 28)
            ]
        )
        result = rounds_with_next(rows)
        self.assertTrue(result["sobreviventes"].eq(1).all())
        self.assertNotIn(12, set(result["round"]))
        self.assertTrue(result["round"].lt(24).all())

    def test_observers_who_participate_elsewhere_are_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = sample_match("first")
            first["players"] += [
                {"puuid": "occasional-player", "teamId": "Neutral", "isObserver": True},
                {"puuid": "exclusive-observer", "teamId": "Neutral", "isObserver": True},
            ]
            second = sample_match("second")
            second["roundResults"][0]["playerStats"].append(
                {"puuid": "occasional-player", "kills": [], "damage": []}
            )
            (root / "first.json").write_text(json.dumps(first))
            (root / "second.json").write_text(json.dumps(second))
            self.assertEqual(dataset_quality(root)["totals"]["observers"], 1)

    def test_invalid_download_never_replaces_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "match.json"
            target.write_text("invalid existing file")
            with patch("valorant.data.download.fetch", return_value=b"<html>error</html>"):
                with self.assertRaises(ValueError):
                    download_file("id", target)
            self.assertEqual(target.read_text(), "invalid existing file")

    def test_parallel_download_failures_propagate(self):
        def discover(folder_id, parent, executor, futures):
            def fail():
                raise ValueError("synthetic download failure")

            futures.append(executor.submit(fail))
            return futures

        with tempfile.TemporaryDirectory() as directory, patch(
            "valorant.data.download.download_folder", side_effect=discover
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic download failure"):
                download_dataset(Path(directory))


if __name__ == "__main__":
    unittest.main()
