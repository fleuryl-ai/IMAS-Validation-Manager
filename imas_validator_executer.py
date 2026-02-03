import subprocess
import os
import shutil
import glob
import argparse
import re

# --- CONFIGURATION ---
START_SHOT = 57269
END_SHOT = 58693
TIMEOUT_SECONDS = 1000
#END_SHOT = 57275
URI_TEMPLATE = "imas:hdf5?path=/Imas_public/public/imasdb/west/3/{shot}/0"

# Source folder created by imas_validator
VALIDATE_REPORTS_ROOT = "validate_reports"
# Folder where we will centralize all .txt files for the global report
COLLECTED_DIR = "collected_txt_reports"
CRASH_LOG = "crashed_validation.txt"

def get_latest_report_dir():
    """Finds the most recent directory in validate_reports."""
    dirs = [os.path.join(VALIDATE_REPORTS_ROOT, d) for d in os.listdir(VALIDATE_REPORTS_ROOT) 
            if os.path.isdir(os.path.join(VALIDATE_REPORTS_ROOT, d))]
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)

def validate_shot(shot, timeout):
    """Executes validation for a given shot."""
    uri = URI_TEMPLATE.format(shot=shot)
    print(f"--> Shot {shot} : Validation in progress...", end=" ", flush=True)
    
    command = ["imas_validator", "validate", uri, "--verbose"]
    
    try:
        # Command execution
        # We ignore stdout because the tool already writes its files to validate_reports
        process = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        
        if process.returncode != 0 and not os.path.exists(VALIDATE_REPORTS_ROOT):
            # If the process fails without even creating a folder
            raise Exception(f"Exit code {process.returncode} - {process.stderr}")

        # 1. Identify the timestamped folder that was just created
        latest_dir = get_latest_report_dir()
        
        if latest_dir:
            # 2. Search for the .txt file inside
            # The name contains '|' instead of '/'
            txt_files = glob.glob(os.path.join(latest_dir, "*.txt"))
            
            if txt_files:
                source_txt = txt_files[0]
                dest_txt = os.path.join(COLLECTED_DIR, f"{shot}.txt")
                
                # 3. Copy the .txt to our centralized folder
                shutil.copy2(source_txt, dest_txt)
                print(f"OK (centralized in {COLLECTED_DIR})")
                
                # Optional: Clean up the timestamped folder to avoid disk saturation
                # shutil.rmtree(latest_dir) 
            else:
                print("WARNING (Folder created but .txt not found)")
        else:
            print("ERROR (No report folder generated)")

    except Exception as e:
        print(f"CRASH !")
        with open(CRASH_LOG, "a") as f_crash:
            f_crash.write(f"Shot {shot} : {str(e)}\n")

def run_campaign(start_shot, end_shot, timeout):
    if not os.path.exists(COLLECTED_DIR):
        os.makedirs(COLLECTED_DIR)

    print(f"Validation campaign : {start_shot} to {end_shot}")
    
    for shot in range(start_shot, end_shot + 1):
        validate_shot(shot, timeout)

    print("\nCampaign finished.")
    print(f"Files collected in : {COLLECTED_DIR}")

def retry_crashed_shots(timeout):
    if not os.path.exists(CRASH_LOG):
        print(f"File {CRASH_LOG} not found.")
        return

    if not os.path.exists(COLLECTED_DIR):
        os.makedirs(COLLECTED_DIR)

    with open(CRASH_LOG, 'r') as f:
        lines = f.readlines()

    shots_to_retry = set()
    clean_lines = []
    
    # Identify shots to retry and prepare file cleanup
    for line in lines:
        match = re.search(r"(?:Choc|Shot) (\d+)", line)
        if match:
            shots_to_retry.add(int(match.group(1)))
        else:
            clean_lines.append(line)

    if not shots_to_retry:
        print("No shots to retry detected in the crash file.")
        return

    print(f"Retrying crashed shots : {sorted(shots_to_retry)}")

    # Rewrite the crash file without the shots we are going to retry
    # (If they crash again, validate_shot will add the error line)
    with open(CRASH_LOG, 'w') as f:
        f.writelines(clean_lines)

    for shot in sorted(shots_to_retry):
        validate_shot(shot, timeout)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMAS validation executor")
    parser.add_argument("--retry-crashed", action="store_true", help="Retries shots listed in crashed_validation.txt")
    parser.add_argument("--start-shot", type=int, default=START_SHOT, help="Start shot number")
    parser.add_argument("--end-shot", type=int, default=END_SHOT, help="End shot number")
    parser.add_argument("--timeout", "-t", type=int, default=TIMEOUT_SECONDS, help="Timeout for each validation in seconds")
    args = parser.parse_args()

    if args.retry_crashed:
        retry_crashed_shots(args.timeout)
    else:
        run_campaign(args.start_shot, args.end_shot, args.timeout)
