import subprocess
import os
import shutil
import glob

# --- CONFIGURATION ---
START_SHOT = 57269
END_SHOT = 58693
#END_SHOT = 57275
URI_TEMPLATE = "imas:hdf5?path=/Imas_public/public/imasdb/west/3/{shot}/0"

# Dossier source créé par imas_validator
VALIDATE_REPORTS_ROOT = "validate_reports"
# Dossier où nous allons centraliser tous les .txt pour le rapport global
COLLECTED_DIR = "collected_txt_reports"
CRASH_LOG = "crashed_validation.txt"

def get_latest_report_dir():
    """Trouve le répertoire le plus récent dans validate_reports."""
    dirs = [os.path.join(VALIDATE_REPORTS_ROOT, d) for d in os.listdir(VALIDATE_REPORTS_ROOT) 
            if os.path.isdir(os.path.join(VALIDATE_REPORTS_ROOT, d))]
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)

def run_campaign():
    if not os.path.exists(COLLECTED_DIR):
        os.makedirs(COLLECTED_DIR)

    print(f"Campagne de validation : {START_SHOT} à {END_SHOT}")
    
    for shot in range(START_SHOT, END_SHOT + 1):
        uri = URI_TEMPLATE.format(shot=shot)
        print(f"--> Choc {shot} : Validation en cours...", end=" ", flush=True)
        
        command = ["imas_validator", "validate", uri, "--verbose"]
        
        try:
            # Exécution de la commande
            # On ignore stdout car l'outil écrit déjà ses fichiers dans validate_reports
            process = subprocess.run(command, capture_output=True, text=True, timeout=1000)
            
            if process.returncode != 0 and not os.path.exists(VALIDATE_REPORTS_ROOT):
                # Si le process échoue sans même créer de dossier
                raise Exception(f"Exit code {process.returncode} - {process.stderr}")

            # 1. Identifier le dossier horodaté qui vient d'être créé
            latest_dir = get_latest_report_dir()
            
            if latest_dir:
                # 2. Chercher le fichier .txt à l'intérieur
                # Le nom contient des '|' au lieu de '/'
                txt_files = glob.glob(os.path.join(latest_dir, "*.txt"))
                
                if txt_files:
                    source_txt = txt_files[0]
                    dest_txt = os.path.join(COLLECTED_DIR, f"{shot}.txt")
                    
                    # 3. Copier le .txt vers notre dossier centralisé
                    shutil.copy2(source_txt, dest_txt)
                    print(f"OK (centralisé dans {COLLECTED_DIR})")
                    
                    # Optionnel : Nettoyer le dossier horodaté pour ne pas saturer le disque
                    # shutil.rmtree(latest_dir) 
                else:
                    print("AVERTISSEMENT (Dossier créé mais .txt introuvable)")
            else:
                print("ERREUR (Aucun dossier de rapport généré)")

        except Exception as e:
            print(f"CRASH !")
            with open(CRASH_LOG, "a") as f_crash:
                f_crash.write(f"Choc {shot} : {str(e)}\n")
            continue

    print("\nCampagne terminée.")
    print(f"Fichiers collectés dans : {COLLECTED_DIR}")

if __name__ == "__main__":
    run_campaign()
