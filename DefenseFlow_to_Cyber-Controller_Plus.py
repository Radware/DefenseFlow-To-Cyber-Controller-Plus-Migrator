import os, sys, re
import zipfile
import json
import shutil
from requests import Session
import urllib3
import json
from getpass import getpass
import logging
import argparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

pattern = r'^(?P<user>[^:]+):(?P<pass>[^@]+)@(?P<ip>[\d.]+)$'

class Vision():
    def __init__(self, src_ip, src_user, src_pass, dst_ip, dst_user, dst_pass):
        self.src_ip = src_ip
        self.src_user = src_user
        self.src_pass = src_pass
        self.dst_ip = dst_ip
        self.dst_user = dst_user
        self.dst_pass = dst_pass

    def login(self, ip, username, password):
        login_url = 'https://' + ip + '/mgmt/system/user/login'
        sess = Session()
        sess.verify = False
        login_data = {'username': username, 'password': password}
        r = sess.post(url=login_url, json=login_data, verify=False)
        response = r.json()

        if response['status'] == 'ok':
            sess.headers.update({"JSESSIONID": response['jsessionid']})
            print("Login Successful")
        else:
            print(f"Login Error: {r.text}")
            return None

        return sess

    def src_vision_login(self):
        print("--- Login to Source Vision Server ---")
        self.src_session = self.login(self.src_ip, self.src_user, self.src_pass)

    def dst_vision_login(self):
        print("\n--- Login to Destination Cyber-Controller Server ---")
        self.dst_session = self.login(self.dst_ip, self.dst_user, self.dst_pass)

    def download_df_config(self):
        print('Exporting DefenseFlow Configuration from Vision')
        url = 'https://' + self.src_ip + '/mgmt/device/df/config/getfromdevice?saveToDb=false&type=config'
        response = self.src_session.get(url, stream=True)
        # Open the file in binary write mode and download it in chunks
        if 'Content-Disposition' in response.headers:
            # Extract filename from Content-Disposition
            content_disposition = response.headers['Content-Disposition']
            filename = content_disposition.split('filename=')[-1].strip('"')
            
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive new chunks
                    file.write(chunk)

        print(f'Successfully Exported File {filename}')
        return filename

    def upload_df_edited_config(self, filename):
        print('Imoporting DefenseFlow Configuration to Cyber-Controller Plus')
        url = 'https://' + self.dst_ip + f'/mgmt/device/df/config/sendtodevice?fileName={filename}&type=config'
        files = {'Filedata': ('DefenseFlow-To-CCPlus.code-workspace', open(filename, 'rb'), 'application/octet-stream')}
        r = self.dst_session.post(url, files=files)
        if r.status_code != 200:
            print(f"Error: status code {r.status_code} with message {r.text}")
            exit(1)
        
        r_dict = r.json()
        if 'status' in r_dict and r_dict['status'] != 'success':
            print(f"Error: received response with status '{r_dict['status']}' and message '{r_dict['message']}'")
            exit(1)

        print("Successfully Migrated DefenseFlow Configuration to Cyber-Controller Plus")

# Function to check if a file exists
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' does not exist.")
        sys.exit(1)

class DFConfigModifier():

    def __init__(self, df_config_filename, disable_pos, po_precedence):
        self.source_config = df_config_filename
        self.disable_pos = disable_pos
        self.po_precedence = po_precedence
        # Check if the file exists
        check_file_exists(self.source_config)

        # Modify the filename to create a new destination file
        if not self.source_config.endswith(".zip"):
            print("Error: The source file must have a .zip extension.")
            sys.exit(1)

        self.dest_config= self.source_config.replace(".zip", "-edited.zip")

    # Function to modify status.json
    def modify_status_json(self, data):
        keys_to_keep = ["attack-history", "protection-history"]
        modified_data = {}

        for key in data:
            if key in keys_to_keep:
                modified_data[key] = data[key]
            else:
                # Empty the value based on its type (list or dictionary)
                if isinstance(data[key], list):
                    modified_data[key] = []
                elif isinstance(data[key], dict):
                    modified_data[key] = {}
                else:
                    modified_data[key] = None  # For other types, set to None
        
        return modified_data

    # Function to modify protected_object_configuration.json
    def modify_protected_object_config(self, data):
        if self.disable_pos:
            print("Disabling All Protected Objects")
            for item in data.get("protectedObjects", []):
                item["adminStatus"] = "DISABLED"
        return data

    # Function to modify policy-editor-backup.json
    def modify_policy_editor_backup(self, data):
        if "protectionPulses" in data:
            data["protectionPulses"] = []  # Empty the list of policies

        return data
    
    def modify_system_configuration(self, data):
        default_precedence = {
            'dfc.defensepro.policy.precedence.granular.p0.high':'16000', 
            'dfc.defensepro.policy.precedence.granular.p1.high':'63999', 
            'dfc.defensepro.policy.precedence.granular.p2.high':'48000', 
            'dfc.defensepro.policy.precedence.granular.p3.high':'32000', 
            'dfc.defensepro.policy.precedence.standard.p0.high':'8000', 
            'dfc.defensepro.policy.precedence.standard.p1.high':'56000', 
            'dfc.defensepro.policy.precedence.standard.p2.high':'40000', 
            'dfc.defensepro.policy.precedence.standard.p3.high':'24000'
        }

        for precedene_name, value in default_precedence.items():
            if precedene_name in data['modifiedKeys']:
                value = int(data['modifiedKeys'][precedene_name])
            else:
                value = int(default_precedence[precedene_name])
            
            value+=500
            data['modifiedKeys'][precedene_name] = str(value)

        return data

    # Function to extract and modify JSON files from zip, then re-compress
    def process(self):
        temp_dir = "temp_dir"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # Extract the zip file
        with zipfile.ZipFile(self.source_config, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Modify JSON files
        files_to_modify = {
            "status.json": self.modify_status_json,
            "policy-editor-backup.json": self.modify_policy_editor_backup,
            "protected_object_configuration.json": self.modify_protected_object_config,
            "system_configuration.json": self.modify_system_configuration
        }

        for file_name, modify_function in files_to_modify.items():
            if not self.po_precedence and file_name == "system_configuration.json":
                continue
                
            file_path = os.path.join(temp_dir, file_name)
            if os.path.exists(file_path):
                print(f"Modifying {file_name}...")
                with open(file_path, 'r') as f:
                    data = json.load(f)
                modified_data = modify_function(data)
                with open(file_path, 'w') as f:
                    json.dump(modified_data, f, indent=4)
            else:
                print(f"{file_name} not found.")

        # Create a new zip file with the modified contents
        with zipfile.ZipFile(self.dest_config, 'w', zipfile.ZIP_DEFLATED)  as zip_ref:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    zip_ref.write(os.path.join(root, file), 
                                arcname=os.path.relpath(os.path.join(root, file), temp_dir))

        # Clean up temporary files
        shutil.rmtree(temp_dir)
        print(f"DefenseFlow configuration file successfully migrated and saved to disk: '{self.dest_config}'")
        return self.dest_config

def clear_screen():
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Unix-based systems (Linux, Mac)
        os.system('clear')

def print_prerequisites():
    prerequisites = """PREREQUISITES:
- Cyber-Contorller Plus license installed.
- Physical interfaces in DefenseFlow must match those in the Cyber-Controller Plus. However, the IP addresses do not need to be identical.
- Interface associations must be the same between DefenseFlow and the Cyber-Controller Plus.
- Ensure that DefensePro devices are preconfigured on the Cyber-Controller before import.

Press any key to confirm you have read and understood the above."""
    print(prerequisites, end='')

def confirm_prerequisites():
    if os.name == 'nt':  # For Windows
        import msvcrt
        print("Press any key to continue...")
        msvcrt.getch()
        os.system('cls')
    else:  # For Unix-based systems (Linux, Mac)
        import tty
        import termios
        print("Press any key to continue...")
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        os.system('clear')

def parse_args():
    parser = argparse.ArgumentParser(description="",
        epilog=f"""Example usage: 
  python {os.path.basename(__file__)} --mode offline --input DefenseFlowConfiguration_2024-10-15_05-33-54.zip --disable-pos
  python {os.path.basename(__file__)} --mode online --src user:pass@1.1.1.1 --dst user:pass@2.2.2.2 --disable-pos""",
formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--mode', metavar='MODE', type=str, choices=['offline', 'online'], required=True, help="Specify the mode of operation: 'offline' or 'online'")
    parser.add_argument('--src', metavar='u:p@ip', type=str, required=False, help="Source Vision Username ,Password, IP address")
    parser.add_argument('--dst', metavar='u:p@ip',type=str, required=False, help="Destination Cyber-Controller Username ,Password, IP address")
    parser.add_argument('--input', metavar='FILENAME', type=str, required=False, help="Specify the DefenseFlow exported filename (e.g., 'DefenseFlowConfiguration_2024-10-15_05-33-54.zip'). for 'offline' mode only")
    parser.add_argument('--disable-pos', action='store_true' ,required=False, help="Disable all Protected Objects in the DefenseFlow configuration (applies to both online and offline modes)")
    parser.add_argument('--inc-po-precedence', action='store_true', required=False, help="Adds 500 to the default precedence used by DefenseFlow for Policy")
    parser.add_argument('--no-prereq', action='store_true' ,required=False, help="Skip displaying the prerequisites message")

    return parser.parse_args()

def main():
    args = parse_args()
    if not args.no_prereq:
        print_prerequisites()
        confirm_prerequisites()
    
    if args.mode == 'online':
        # Source parsing
        if not args.src:
            print(f"{os.path.basename(__file__)}: error: argument --src: missing")
            exit(1)
        src_match = re.match(pattern, args.src)
        if not src_match:
            print(f"{os.path.basename(__file__)}: error: argument --src: is not in the correct format, expected 'user:pass@ip'")
            exit(1)

        # Destination parsing
        if not args.dst:
            print(f"{os.path.basename(__file__)}: error: argument --dst: missing")
            exit(1)
        dst_match = re.match(pattern, args.dst)
        if not dst_match:
            print(f"{os.path.basename(__file__)}: error: argument --dst: is not in the correct format, expected 'user:pass@ip'")
            exit(1)

        src_ip = src_match.group('ip')
        src_user = src_match.group('user')
        src_pass = src_match.group('pass')
        dst_ip = dst_match.group('ip')
        dst_user = dst_match.group('user')
        dst_pass = dst_match.group('pass')
        disable_pos = args.disable_pos
        po_precedence = args.inc_po_precedence
        online_migration(src_ip, src_user, src_pass, dst_ip, dst_user, dst_pass, disable_pos, po_precedence)
    if args.mode == 'offline':
        if not args.input:
            print(f"{os.path.basename(__file__)}: error: argument --input: missing")
            exit(1)
        df_config_filename = args.input
        disable_pos = args.disable_pos
        po_precedence = args.inc_po_precedence
        offline_migration(df_config_filename, disable_pos, po_precedence)

def online_migration(src_ip, src_user, src_pass, dst_ip, dst_user, dst_pass, disable_pos, po_precedence):
    print("\nStarting online migration of DefenseFlow to Cyber Controller Plus...")
    v = Vision(src_ip, src_user, src_pass, dst_ip, dst_user, dst_pass)
    v.src_vision_login()
    df_config_filename = v.download_df_config()
    dfcm = DFConfigModifier(df_config_filename, disable_pos, po_precedence)
    df_edited_config_file = dfcm.process()
    v.dst_vision_login()
    v.upload_df_edited_config(df_edited_config_file)

def offline_migration(df_config_filename, disable_pos, po_precedence):
    print("\nStarting offline configuration file migration...")
    dfcm = DFConfigModifier(df_config_filename, disable_pos, po_precedence)
    dfcm.process()

if __name__ == "__main__":
    main()