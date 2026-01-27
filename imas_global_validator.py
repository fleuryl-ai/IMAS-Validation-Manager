import os
import re
import json
import csv
import argparse
from collections import defaultdict

def parse_validation_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Shot ID extraction
    shot_match = re.search(r'Tested URI : .*/(\d+)/\d+$', content, re.MULTILINE)
    shot_id = shot_match.group(1) if shot_match else os.path.basename(file_path).split('.')[0]

    if "FAILED IDSs:" not in content:
        return shot_id, []

    failed_section = content.split("FAILED IDSs:")[1]
    ids_blocks = re.split(r'\n- IDS ', failed_section)
    
    results = []
    for block in ids_blocks:
        if not block.strip(): continue
        
        ids_header = re.match(r'^(\w+) occurrence (\d+)', block.strip())
        if not ids_header: continue
        
        ids_name = ids_header.group(1)
        occ = ids_header.group(2)

        rule_blocks = re.split(r'\n\s+RULE: ', block)
        for r_block in rule_blocks[1:]:
            rule_name = re.search(r'^([^\n]+)', r_block).group(1).strip()
            message = re.search(r'MESSAGE:\s*(.*)', r_block).group(1).strip()
            nodes_count = re.search(r'NODES COUNT:\s*(\d+)', r_block).group(1).strip()
            
            nodes_match = re.search(r'NODES:\s*\[(.*?)\]', r_block, re.DOTALL)
            nodes = [n.strip().replace("'", "") for n in nodes_match.group(1).split(',')] if nodes_match else []

            results.append({
                'ids': ids_name,
                'occurrence': occ,
                'rule': rule_name,
                'message': message,
                'nodes_count': int(nodes_count),
                'nodes': nodes
            })
    return shot_id, results

def save_json(data, directory):
    path = os.path.join(directory, "global_report.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"JSON generated : {path}")

def save_csv(data, directory):
    path = os.path.join(directory, "global_report.csv")
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['IDS', 'Occurrence', 'Rule', 'Message', 'Shot', 'Nodes_Count', 'Nodes'])
        for ids_key, rules in data.items():
            ids_name, occ = ids_key.split(" (occ ")
            occ = occ.replace(")", "")
            for (rule, msg), shots in rules.items():
                for s in shots:
                    writer.writerow([ids_name, occ, rule, msg, s['shot'], s['nodes_count'], "|".join(s['nodes'])])
    print(f"CSV generated : {path}")

def process_directory(directory):
    # Structure for aggregation : data[ids_key][(rule, msg)] = list of shots
    aggregated = defaultdict(lambda: defaultdict(list))
    
    files = [f for f in os.listdir(directory) if f.endswith('.txt') and "global_report" not in f]
    
    for filename in files:
        shot_id, violations = parse_validation_file(os.path.join(directory, filename))
        for v in violations:
            ids_key = f"{v['ids']} (occ {v['occurrence']})"
            rule_key = (v['rule'], v['message'])
            aggregated[ids_key][rule_key].append({
                'shot': shot_id,
                'nodes_count': v['nodes_count'],
                'nodes': v['nodes']
            })

    # Export CSV
    save_csv(aggregated, directory)

    # Conversion to simple dictionary for JSON (dict keys cannot be tuples)
    json_ready = {}
    for ids_key, rules in aggregated.items():
        json_ready[ids_key] = []
        for (rule, msg), shots in rules.items():
            json_ready[ids_key].append({
                'rule': rule,
                'message': msg,
                'impacted_shots': shots
            })
    
    save_json(json_ready, directory)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregates IMAS validation reports.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to analyze (default: current)")
    args = parser.parse_args()
    process_directory(args.directory)