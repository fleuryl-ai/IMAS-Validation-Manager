import json
import re
import sys
import pandas as pd
from pathlib import Path

def parse_category_string(cat_str):
    """Extrait le nom du système et l'occurrence d'une chaîne type 'camera_ir (occ 0)'."""
    cat_str = str(cat_str).strip()
    match = re.search(r'^(.*?) \(occ (\d+)\)$', cat_str, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower(), int(match.group(2))
    return cat_str.lower(), 0

def generate_markdown_synthesis(json_path):
    input_path = Path(json_path)
    if not input_path.exists():
        return f"Error: File {json_path} not found."

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return f"Error parsing JSON: {e}"

    # Configuration des catégories de rapport
    categories_config = {
        "Diagnostics": [
            "camera_ir", "bolometer", "calorimetry", "ece", "interferometer", 
            "reflectometer_profile", "spectrometer_visible", 
            "spectrometer_x_ray_crystal", "hard_x_rays"
        ],
        "Profiles and Equilibrium": [
            "core_profiles", "equilibrium"
        ],
        "Magnetics and Antennas": [
            "magnetics", "pf_active", "pf_passive", "lh_antennas"
        ],
        "Summary": [
            "summary"
        ]
    }

    # Extraction des données du JSON
    rows = []
    all_found_systems = set()

    for raw_category, items in data.items():
        if not isinstance(items, list):
            continue
            
        system_base, occ = parse_category_string(raw_category)
        all_found_systems.add(system_base)
        
        for item in items:
            if not isinstance(item, dict) or "rule" not in item:
                continue
            
            # Nettoyage du nom de la règle (identique à votre export_report.py)
            full_rule = item.get("rule", "")
            rule_name = full_rule.split(":")[-1] if ":" in full_rule else full_rule
            
            # Récupération du compte (nombre de chocs impactés)
            shots = item.get("impacted_shots", [])
            count = len(shots)
            
            if count > 0:
                rows.append({
                    "system": system_base,
                    "occ": occ,
                    "rule": rule_name,
                    "value": count
                })

    if not rows:
        return f"No validation errors found in {json_path}."

    processed_df = pd.DataFrame(rows)
    
    # Construction du rapport Markdown
    md = "# IDS Validation Rules Summary\n\n"
    md += "Here is the summary of unsatisfied validation rules. For each rule, the numbers in parentheses represent the number of impacted items (shocks) for each occurrence (`occ`) within the specified range.\n\n"

    consumed_systems = set()

    # 1. Traitement des catégories définies
    for cat_header, systems in categories_config.items():
        systems_lower = [s.lower() for s in systems]
        cat_df = processed_df[processed_df['system'].isin(systems_lower)]
        
        if cat_df.empty:
            continue
            
        md += f"### {cat_header}\n\n"
        
        # Tri selon l'ordre défini dans le dictionnaire de config
        for sys_template in systems:
            sys_df = cat_df[cat_df['system'] == sys_template.lower()]
            if sys_df.empty:
                continue
            
            consumed_systems.add(sys_template.lower())
            
            min_occ = sys_df['occ'].min()
            max_occ = sys_df['occ'].max()
            range_str = f"occ {min_occ}" if min_occ == max_occ else f"occ {min_occ} to {max_occ}"
            
            md += f"* **{sys_template}** ({range_str})\n\n"
            
            # Groupement par règle pour lister les valeurs par occurrence
            for rule in sys_df['rule'].unique():
                rule_df = sys_df[sys_df['rule'] == rule].sort_values('occ')
                all_possible_occs = list(range(min_occ, max_occ + 1))
                is_continuous = len(rule_df) == len(all_possible_occs) and len(rule_df) > 1
                
                if is_continuous:
                    vals = ", ".join(map(str, rule_df['value'].tolist()))
                    md += f"  * `{rule}` ({vals})\n\n"
                elif len(rule_df) == 1:
                    row_data = rule_df.iloc[0]
                    if min_occ != max_occ:
                        md += f"  * `{rule}` (occ {row_data['occ']}: {row_data['value']})\n\n"
                    else:
                        md += f"  * `{rule}` ({row_data['value']})\n\n"
                else:
                    parts = [f"occ {r['occ']}: {r['value']}" for _, r in rule_df.iterrows()]
                    md += f"  * `{rule}` ({', '.join(parts)})\n\n"

    # 2. Gestion des systèmes non catégorisés
    uncategorized_df = processed_df[~processed_df['system'].isin(consumed_systems)]
    
    if not uncategorized_df.empty:
        md += "### Other / Uncategorized\n\n"
        for system in sorted(uncategorized_df['system'].unique()):
            sys_df = uncategorized_df[uncategorized_df['system'] == system]
            
            min_occ = sys_df['occ'].min()
            max_occ = sys_df['occ'].max()
            range_str = f"occ {min_occ}" if min_occ == max_occ else f"occ {min_occ} to {max_occ}"
            
            md += f"* **{system}** ({range_str})\n\n"
            
            for rule in sys_df['rule'].unique():
                rule_df = sys_df[sys_df['rule'] == rule].sort_values('occ')
                parts = [f"occ {r['occ']}: {r['value']}" for _, r in rule_df.iterrows()]
                md += f"  * `{rule}` ({', '.join(parts)})\n\n"
                    
    return md

if __name__ == "__main__":
    # Utilise le fichier passé en argument ou le fichier par défaut de votre export_report.py
    input_file = sys.argv[1] if len(sys.argv) > 1 else "my_global_report_v3.json"
    
    # Si l'entrée est le JSON brut (v3), on adapte le nom de sortie
    input_path = Path(input_file)
    output_file = input_path.with_name(f"synthesis_{input_path.stem}.md")
    
    print(f"Processing JSON: {input_file}...")
    markdown_output = generate_markdown_synthesis(input_file)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_output)
        
    print(f"✅ Report saved to: {output_file}")