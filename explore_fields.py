"""Análise exploratória dos JSONs de partidas: quais campos existem, o tipo de cada um e a frequência dos valores.

Uso: python explore_fields.py [pasta_com_jsons]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).parent / "data"
TOP_VALUES_SHOWN = 5


def find_match_files(data_dir):
    return sorted(data_dir.rglob("*.json"))


def load_match(match_file):
    return json.loads(match_file.read_text(encoding="utf-8"))


def walk_fields(value, field_path=""):
    """Gera (caminho_do_campo, valor_folha) para cada folha do JSON. Itens de lista viram 'campo[]'."""
    if isinstance(value, dict) and value:
        for key, child in value.items():
            child_path = f"{field_path}.{key}" if field_path else key
            yield from walk_fields(child, child_path)
    elif isinstance(value, list) and value:
        for item in value:
            yield from walk_fields(item, f"{field_path}[]")
    else:
        yield field_path, value


def as_countable(leaf_value):
    # Dicionários e listas vazios chegam aqui como folhas e não podem ser chaves de Counter
    if isinstance(leaf_value, (dict, list)):
        return json.dumps(leaf_value)
    return leaf_value


def collect_field_stats(match_files):
    types_by_field = defaultdict(Counter)
    values_by_field = defaultdict(Counter)
    for match_file in match_files:
        for field_path, leaf_value in walk_fields(load_match(match_file)):
            types_by_field[field_path][type(leaf_value).__name__] += 1
            values_by_field[field_path][as_countable(leaf_value)] += 1
    return types_by_field, values_by_field


def summarize_fields(types_by_field, values_by_field):
    """Uma linha por campo com tipos, ocorrências, valores distintos e os mais frequentes."""
    field_rows = []
    for field_path in sorted(types_by_field):
        type_counts = types_by_field[field_path]
        value_counts = values_by_field[field_path]
        field_rows.append({
            "campo": field_path,
            "tipos": ", ".join(f"{type_name} ({count})" for type_name, count in type_counts.most_common()),
            "ocorrencias": sum(type_counts.values()),
            "distintos": len(value_counts),
            "mais_frequentes": ", ".join(f"{value!r}: {count}" for value, count in value_counts.most_common(TOP_VALUES_SHOWN)),
        })
    return field_rows


def print_files_summary(match_files, data_dir):
    files_by_folder = Counter(str(match_file.parent.relative_to(data_dir)) for match_file in match_files)
    print(f"Arquivos encontrados: {len(match_files)}")
    for folder, file_count in sorted(files_by_folder.items()):
        print(f"  {folder}: {file_count}")
    print()


def print_field_report(field_rows):
    print(f"Campos encontrados: {len(field_rows)}\n")
    for row in field_rows:
        print(row["campo"])
        print(f"  tipos: {row['tipos']}")
        print(f"  ocorrências: {row['ocorrencias']} | valores distintos: {row['distintos']}")
        print(f"  mais frequentes: {row['mais_frequentes']}")
        print()


def check_walk_fields():
    sample = {"a": [1, {"b": 2}], "c": {}, "d": []}
    assert list(walk_fields(sample)) == [("a[]", 1), ("a[].b", 2), ("c", {}), ("d", [])]


def main():
    check_walk_fields()
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_DIR
    match_files = find_match_files(data_dir)
    print_files_summary(match_files, data_dir)
    types_by_field, values_by_field = collect_field_stats(match_files)
    print_field_report(summarize_fields(types_by_field, values_by_field))


if __name__ == "__main__":
    main()
