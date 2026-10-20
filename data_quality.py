"""Cobertura, anomalias e proveniência local; importar este módulo não grava arquivos."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match


@lru_cache(maxsize=2048)
def _file_hash(path, size, mtime_ns):
    # As chaves stat invalidam a memoização quando o arquivo muda.
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_signature(data_dir=DEFAULT_DATA_DIR):
    """SHA256 de conteúdo, tamanho e mtime dos JSONs, incluindo metadados de mapas.

    O hash de cada conteúdo é memoizado pelo caminho/tamanho/mtime_ns. Assim,
    reruns normais só fazem stat, e mudanças nos arquivos invalidam os caches.
    """
    root = Path(data_dir)
    records = []
    for path in sorted(root.rglob("*.json")):
        stat = path.stat()
        records.append((str(path.relative_to(root)), stat.st_size, stat.st_mtime_ns,
                        _file_hash(str(path.resolve()), stat.st_size, stat.st_mtime_ns)))
    return hashlib.sha256(json.dumps(records, ensure_ascii=False).encode()).hexdigest()


def iter_selected_matches(data_dir=DEFAULT_DATA_DIR, match_ids=None):
    """Itera (caminho, partida), sem recalibrar referências em partidas excluídas."""
    selected = None if match_ids is None else set(match_ids)
    for path in find_match_files(Path(data_dir)):
        match = load_match(path)
        if selected is None or match["matchInfo"]["matchId"] in selected:
            yield path, match


def _empty_timer_prefix(match):
    count = 0
    for result in match.get("roundResults", []):
        deaths = [k for s in result.get("playerStats", []) for k in s.get("kills", [])]
        if result.get("roundResult") == "Round timer expired" and not deaths and not result.get("bombPlanter"):
            count += 1
        else:
            break
    return count


def inspect_quality(match, source=None):
    """Sinais observáveis de qualidade, sem atribuir causa a registros anômalos."""
    info = match["matchInfo"]
    rounds = match.get("roundResults", [])
    players = match.get("players", [])
    teams = {p["puuid"]: p.get("teamId") for p in players}
    participants = {s["puuid"] for r in rounds for s in r.get("playerStats", [])}
    kills = [k for r in rounds for s in r.get("playerStats", []) for k in s.get("kills", [])]
    initial_empty_timers = _empty_timer_prefix(match)
    anomalies = []
    if initial_empty_timers >= 12:
        anomalies.append(f"{initial_empty_timers} rounds iniciais por tempo, sem mortes nem plant; causa não determinada")
    raw_plants = [r for r in rounds if r.get("bombPlanter")]
    invalid_timer = sum(r.get("roundResult") == "Round timer expired" for r in raw_plants)
    plants_without_defenders = sum(
        bool(r.get("plantPlayerLocations"))
        and not any(teams.get(p["puuid"]) not in {teams.get(r["bombPlanter"]), None, "Neutral"}
                    for p in r.get("plantPlayerLocations") or [])
        for r in raw_plants)
    after_defuse = sum(k["timeSinceRoundStartMillis"] > r.get("defuseRoundTime", 0)
                       for r in rounds if r.get("bombDefuser")
                       for s in r.get("playerStats", []) for k in s.get("kills", []))
    same_team = sum(teams.get(k.get("killer")) == teams.get(k.get("victim")) for k in kills)
    killer_positions = sum(any(p["puuid"] == k.get("killer") for p in k.get("playerLocations") or []) for k in kills)
    duplicates = sum(len(s.get("damage", [])) - len({h["receiver"] for h in s.get("damage", [])})
                     for r in rounds for s in r.get("playerStats", []))
    from match_events import round_events
    event_coverage = Counter()
    for result in rounds:
        events = round_events(result, teams)
        for event in events:
            if event["kind"] == "plant":
                event_coverage["valid_tactical_plants"] += bool(event.get("plant_valid"))
                continue
            if event["kind"] != "kill":
                continue
            event_coverage["deaths_after_observed_decision"] += event["after_decision"]
            if not event["tactical_valid"]:
                continue
            event_coverage["tactical_deaths"] += 1
            event_coverage["tactical_deaths_with_snapshot"] += event["snapshot_available"]
            event_coverage["tactical_deaths_with_killer_position"] += any(p["puuid"] == event["actor"] for p in event["locations"])
            if result.get("bombPlanter") and result.get("plantRoundTime") is not None and event["time_ms"] > result["plantRoundTime"] + 45000:
                event_coverage["tactical_deaths_over_45s_after_plant_without_observed_decision"] += 1
    return {
        "match_id": info["matchId"], "source": str(source) if source is not None else None,
        "map_id": info.get("mapId"), "game_version": info.get("gameVersion"),
        "game_start_millis": info.get("gameStartMillis"), "rounds": len(rounds),
        "deaths": len(kills), "participants": len(participants),
        "participant_ids": sorted(participants),
        "observer_ids": sorted({p["puuid"] for p in players if p.get("isObserver") and p["puuid"] not in participants}),
        "anomalous": bool(anomalies), "anomalies": anomalies,
        "initial_empty_timer_rounds": initial_empty_timers,
        "coverage": {"deaths_with_killer_position": killer_positions,
                     "deaths_with_snapshot": sum(bool(k.get("playerLocations")) for k in kills),
                     "plants_with_snapshot": sum(bool(r.get("plantPlayerLocations")) for r in raw_plants),
                     "round_player_stats": sum(len(r.get("playerStats", [])) for r in rounds),
                     "round_player_stats_without_initial_weapon": sum(not s.get("economy", {}).get("weapon") for r in rounds for s in r.get("playerStats", [])),
                     "raw_plants": len(raw_plants), "raw_defuses": sum(bool(r.get("bombDefuser")) for r in rounds),
                     **dict(event_coverage)},
        "exclusions": {"plants_timer_expired": invalid_timer,
                       "plants_without_defenders": plants_without_defenders,
                       "deaths_after_defuse": after_defuse,
                       "same_team_deaths": same_team,
                       "suicides": sum(k.get("killer") == k.get("victim") for k in kills)},
        "repeated_damage_entries": duplicates,
    }


def dataset_quality(data_dir=DEFAULT_DATA_DIR, match_ids=None):
    """Resumo reutilizável pela UI, incluindo denominadores e exclusões explícitas."""
    records = [inspect_quality(match, path.name) for path, match in iter_selected_matches(data_dir, match_ids)]
    participants = {p for row in records for p in row.pop("participant_ids")}
    observers = {p for row in records for p in row.pop("observer_ids")}
    observers -= participants  # Observador exclusivo, não participante em outra partida.
    coverage = Counter()
    exclusions = Counter()
    map_rounds = Counter()
    version_rounds = Counter()
    for row in records:
        coverage.update(row["coverage"])
        exclusions.update(row["exclusions"])
        map_rounds[row["map_id"]] += row["rounds"]
        version_rounds[row["game_version"]] += row["rounds"]
    return {"totals": {"matches": len(records), "rounds": sum(r["rounds"] for r in records),
                       "deaths": sum(r["deaths"] for r in records),
                       "participants": len(participants), "observers": len(observers)},
            "coverage": dict(coverage), "exclusions": dict(exclusions),
            "anomalies": [r for r in records if r["anomalous"]],
            "map_rounds": dict(map_rounds), "version_rounds": dict(version_rounds), "matches": records,
            "source_note": "Arquivos locais; completude em relação à pasta remota não verificada."}


def eligible_match_ids(data_dir=DEFAULT_DATA_DIR, include_anomalous=False):
    return {match["matchInfo"]["matchId"] for _, match in iter_selected_matches(data_dir)
            if include_anomalous or _empty_timer_prefix(match) < 12}


def write_manifest(output_path, data_dir=DEFAULT_DATA_DIR, origins=None):
    """Grava somente no caminho explicitamente solicitado; não inclui PUUIDs."""
    root = Path(data_dir)
    output = Path(output_path)
    previous = {}
    if output.exists():
        try:
            previous = {row["path"]: row for row in json.loads(output.read_text(encoding="utf-8")).get("files", [])}
        except (ValueError, KeyError):
            pass
    files = []
    for path in sorted(root.rglob("*.json")):
        stat = path.stat()
        relative = str(path.relative_to(root))
        file_hash = _file_hash(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
        record = {"path": relative, "bytes": stat.st_size, "sha256": file_hash}
        origin = (origins or {}).get(relative)
        old = previous.get(relative, {})
        if isinstance(origin, dict):
            record.update(origin)
        elif origin:
            record["origin"] = origin
        elif old.get("sha256") == file_hash:
            record.update({key: old[key] for key in ("origin", "downloaded_at_utc") if key in old})
        record.setdefault("origin", "arquivo local; origem remota não verificada")
        files.append(record)
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "signature": data_signature(root), "files": files, "quality": dataset_quality(root)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--manifest", type=Path, help="Gravar manifesto neste caminho explícito")
    args = parser.parse_args()
    report = write_manifest(args.manifest, args.data_dir)["quality"] if args.manifest else dataset_quality(args.data_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
