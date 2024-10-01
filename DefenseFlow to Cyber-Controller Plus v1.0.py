# from vision import Vision
import os, sys
# from dfConfigModifier import DFConfigModifier
import zipfile
import json
import shutil
from requests import Session
import urllib3
import json
from getpass import getpass
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Vision():
    def __init__(self):
        pass

    def login(self, ip, username, password):
        login_url = 'https://' + ip + '/mgmt/system/user/login'
        sess = Session()
        sess.verify = False
        login_data = {'username': username, 'password': password}
        r = sess.post(url=login_url, json=login_data, verify=False)
        response = r.json()

        if response['status'] == 'ok':
            sess.headers.update({"JSESSIONID": response['jsessionid']})
            print("Loging Successful")
        else:
            print(f"Login Error: {r.text}")
            return None

        return sess

    def src_vision_login(self):
        print("--- Source Cyber-Controller Details ---")
        self.src_cc_ip = input("Address: ")
        self.src_cc_user = input("Username: ")
        self.src_cc_password = getpass("Password: ")
        self.src_session = self.login(self.src_cc_ip, self.src_cc_user, self.src_cc_password)

    def dst_vision_login(self):
        print("\n--- Destination Cyber-Controller Details ---")
        self.dst_cc_ip = input("Address: ")
        self.dst_cc_user = input("Username: ")
        self.dst_cc_password = getpass("Password: ")
        self.dst_session = self.login(self.dst_cc_ip, self.dst_cc_user, self.dst_cc_password)

    def download_df_config(self):
        print('Exporting DefenseFlow Configuration')
        url = 'https://' + self.src_cc_ip + '/mgmt/device/df/config/getfromdevice?saveToDb=false&type=config'
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
        print('Imoporting DefenseFlow Configuration')
        url = 'https://' + self.dst_cc_ip + f'/mgmt/device/df/config/sendtodevice?fileName={filename}&type=config'
        files = {'Filedata': ('DefenseFlow-To-CCPlus.code-workspace', open(filename, 'rb'), 'application/octet-stream')}
        response = self.dst_session.post(url, files=files)
        print(response.status_code)
        print(response.text)

    def get_parent_site_id(parent_site_name, session, dst_cc_ip):
        parent_site_name_url = 'https://' + dst_cc_ip + '/mgmt/system/config/tree/site/byname/' + parent_site_name
        parent_site_name_response = session.get(parent_site_name_url, verify=False)
        data = json.loads(parent_site_name_response.text)
        if "There is no site with name" in parent_site_name_response.text:
            return False
        else:
            parent_site_id = data['ormID']
            return parent_site_id

    def get_parent_site_name(device_parent_id, session, ip):
        parent_site_id_url = 'https://' + ip + '/mgmt/system/config/tree/site/byid/' + device_parent_id
        parent_site_id_response = session.get(parent_site_id_url, verify=False)
        data = json.loads(parent_site_id_response.text)
        if "There is no site with name" in parent_site_id_response.text:
            return False
        else:
            parent_site_name = data['name']
            return parent_site_name

    def extract_sites_and_devices(self, data, src_session, src_cc_ip, parent_id=None):
        sites = []
        devices = []

        for item in data["children"]:
            if item["meIdentifier"]["managedElementClass"] == "com.radware.insite.model.device.Device":
                device_parent_id = parent_id if parent_id else data["meIdentifier"]["managedElementID"]

                # parent_site_name = get_parent_site_name(device_parent_id)

                device = {
                    "name": item["name"],
                    "type": item["type"],
                    "managementIp": item["managementIp"],
                    "id": item["meIdentifier"]["managedElementID"],
                    "parentOrmID": device_parent_id
                    # "parent_site_name": parent_site_name
                }
                devices.append(device)
            elif item["meIdentifier"]["managedElementClass"] == "com.radware.insite.model.device.Site":
                site_parent_id = parent_id if parent_id else data["meIdentifier"]["managedElementID"]
                parent_site_name = self.get_parent_site_name(site_parent_id, src_session, src_cc_ip)

                site = {
                    "name": item["name"],
                    "id": item["meIdentifier"]["managedElementID"],
                    "parent_site_name": parent_site_name,
                    "parentOrmID": site_parent_id
                }

                sites.append(site)
                extracted_sites, extracted_devices = self.extract_sites_and_devices(item, src_session, src_cc_ip,
                                                                            item["meIdentifier"]["managedElementID"])
                sites.extend(extracted_sites)
                devices.extend(extracted_devices)

        return sites, devices

    def extract_device_access_data(self, device_ip, existing_file_data, session, src_cc_ip):
        url = 'https://' + src_cc_ip + '/mgmt/system/config/tree/device/byip/' + device_ip
        response = session.get(url, verify=False)
        data = json.loads(response.text)
        device_access_data = data["deviceSetup"]['deviceAccess']
        del device_access_data['ormID']

        for device in existing_file_data['devices']:
            if device['managementIp'] == device_ip:
                device['deviceAccess'] = device_access_data
                break

        return existing_file_data


    def get_site_name_by_id(self, site_id, json_data):
        # Extracting the name of the site by ID
        site_name = None

        for site in json_data['sites']:
            if site['id'] == site_id:
                site_name = site['name']
                break

        return site_name

    def copy_devices_from_vision_to_cc(self):
        self.main('/mgmt/system/config/tree/Physical')
        self.main('/mgmt/system/config/tree/Organization')


    def main(self, url_suffix):

        src_session = self.src_session

        url = 'https://' + self.src_cc_ip + url_suffix
        response = src_session.get(url, verify=False)
        data = json.loads(response.text)

        # Extract sites and devices
        extracted_sites, extracted_devices = self.extract_sites_and_devices(data, src_session, self.src_cc_ip)

        # Construct the final JSON structure
        final_json = {
            "sites": extracted_sites,
            "devices": extracted_devices
        }

        for device in final_json['devices']:
            device_ip = device['managementIp']
            final_json = self.extract_device_access_data(device_ip, final_json, src_session, self.src_cc_ip)

        src_cc_root_site_name = data["name"]

        dst_session = self.dst_session
        url = 'https://' + self.dst_cc_ip + url_suffix
        response = dst_session.get(url, verify=False)
        data = json.loads(response.text)

        dst_cc_root_site_name = data["name"]
        dst_cc_root_site_id = data["meIdentifier"]["managedElementID"]

        if dst_cc_root_site_name != src_cc_root_site_name:
            url = 'https://' + self.dst_cc_ip + '/mgmt/system/config/tree/site'
            payload = {
                "ormID": dst_cc_root_site_id,
                "name": src_cc_root_site_name
            }
            response = dst_session.put(url, json=payload, verify=False)
            if response.status_code != 200:
                print("Failed to change root site name")
                logging.error('Failed to change root site name')
            else:
                print("Root site name has been successfully changed to", src_cc_root_site_name)
                logging.info("Root site name has been successfully changed to " + src_cc_root_site_name)

        for site in final_json["sites"]:
            site_name = site["name"]
            parent_site_name = site["parent_site_name"]

            parent_site_id = self.get_parent_site_id(parent_site_name, dst_session, self.dst_cc_ip)
            if not parent_site_id:
                parent_site_id = dst_cc_root_site_id

            # Make POST request
            payload = {
                "parentOrmID": parent_site_id,
                "name": site_name
            }
            url = 'https://' + self.dst_cc_ip + '/mgmt/system/config/tree/site'

            response = dst_session.post(url, verify=False, json=payload)
            if response.status_code != 200:
                print("Failed to add site: ", site_name)
                error = response.json()
                error_message = error['message']
                logging.error("Failed to add site - " + site_name + ' ' + error_message)
            else:
                print("Added site:", site_name)
                logging.info("Added site: " + site_name)

        for device in final_json["devices"]:
            device_name = device['name']

            src_parent_device_id = device['parentOrmID']
            parent_site_name = self.get_site_name_by_id(src_parent_device_id, final_json)

            if not parent_site_name:
                parent_orm_id = dst_cc_root_site_id
            else:
                parent_orm_id = self.get_parent_site_id(parent_site_name, dst_session, self.dst_cc_ip)

            payload = {
                "name": device['name'],
                "parentOrmID": parent_orm_id,
                "type": device['type'],
                "deviceSetup": {
                    "deviceAccess": device['deviceAccess']
                }
            }

            url = 'https://' + self.dst_cc_ip + '/mgmt/system/config/tree/device'
            response = dst_session.post(url, verify=False, json=payload)
            if response.status_code != 200:
                print("Failed to add device:", device_name)
                error = response.json()
                error_message = error['message']
                logging.error("Failed to add device - " + device_name + ' ' + error_message)
            else:
                print("Added device:", device_name)
                logging.info("Added device: " + device_name)


# Function to check if a file exists
def check_file_exists(file_path):
    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' does not exist.")
        sys.exit(1)

class DFConfigModifier():
    def __init__(self, df_config_file):
        df_config_file
        
        # Check if the file exists
        check_file_exists(df_config_file)

        # Modify the filename to create a new destination file
        if not df_config_file.endswith(".zip"):
            print("Error: The source file must have a .zip extension.")
            sys.exit(1)
        self.source_config = df_config_file
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
        # Ask user for confirmation to disable all items
        while True:
            confirm = input("Do you want to disable all items in protected_object_configuration.json? (yes/no): ").lower()
            if confirm in ['yes', 'no']:
                break
            else:
                print("Please enter 'yes' or 'no'.")
        
        if confirm == "yes":
            for item in data.get("protectedObjects", []):
                item["adminStatus"] = "DISABLED"
        return data

    # Function to modify policy-editor-backup.json
    def modify_policy_editor_backup(self, data):
        if "protectionPulses" in data:
            data["protectionPulses"] = []  # Empty the list of policies

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
            "protected_object_configuration.json": self.modify_protected_object_config
        }

        for file_name, modify_function in files_to_modify.items():
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
        print(f"New zip file created: {self.dest_config}")
        return self.dest_config

def clear_screen():
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Unix-based systems (Linux, Mac)
        os.system('clear')

def print_ascii_art():
    art = """
 _____        __                    ______ _                 __  __ _                 _   _                _____           _       _   
|  __ \      / _|                  |  ____| |               |  \/  (_)               | | (_)              / ____|         (_)     | |  
| |  | | ___| |_ ___ _ __  ___  ___| |__  | | _____      __ | \  / |_  __ _ _ __ __ _| |_ _  ___  _ __   | (___   ___ _ __ _ _ __ | |_ 
| |  | |/ _ \  _/ _ \ '_ \/ __|/ _ \  __| | |/ _ \ \ /\ / / | |\/| | |/ _` | '__/ _` | __| |/ _ \| '_ \   \___ \ / __| '__| | '_ \| __|
| |__| |  __/ ||  __/ | | \__ \  __/ |    | | (_) \ V  V /  | |  | | | (_| | | | (_| | |_| | (_) | | | |  ____) | (__| |  | | |_) | |_ 
|_____/ \___|_| \___|_| |_|___/\___|_|    |_|\___/ \_/\_/   |_|  |_|_|\__, |_|  \__,_|\__|_|\___/|_| |_| |_____/ \___|_|  |_| .__/ \__|
                                                                       __/ |                                                | |        
                                                                      |___/                                                 |_|        
Version: 1.0
Written by: Daniel Offek
"""
    print(art)

def print_prerequisites():
    prerequisites = """PREREQUISITES:
- Cyber-Contorller Plus license installed.
- Physical interfaces in DefenseFlow must match those in the Cyber-Controller Plus. However, the IP addresses do not need to be identical.
- Interface associations must be the same between DefenseFlow and the Cyber-Controller Plus.
- If using Offline miration mode, ensure that DefensePro devices are preconfigured on the Cyber-Controller.

Press any key to confirm you have read and understood the above."""
    print(prerequisites, end='')

def confirm_prerequisites():
    if os.name == 'nt':  # For Windows
        import msvcrt
        msvcrt.getch()
    else:  # For Unix-based systems (Linux, Mac)
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def main_menu():
    clear_screen()
    print_ascii_art()
    print_prerequisites()
    confirm_prerequisites()
    while True:
        clear_screen()
        print("1. Online Migration - Requires access to both Vision and Cyber Controller")
        print("2. Offline Migration - Requires DefenseFlow configuration file")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1/2/3): ")

        if choice == '1':
            complete_migration_online()
            exit(0)
        elif choice == '2':
            offline_configuration_edit()
            exit(0)
        elif choice == '3':
            print("Exiting the program.")
            break
        else:
            print("Invalid choice, please select 1, 2, or 3.")

def complete_migration_online():
    print("\nStarting complete migration of DefenseFlow to Cyber Controller Plus...")
    v = Vision()
    v.src_vision_login()
    df_config_file = v.download_df_config()
    dfcm = DFConfigModifier(df_config_file)
    df_edited_config_file = dfcm.process()
    v.dst_vision_login()
    while True:
        answer = input('Do you want to copy all devices and site hirarchy (yes/no): ').lower()
        if answer in ['yes', 'no']:
            break
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")
    if answer == 'yes':
        v.copy_devices_from_vision_to_cc()
    v.upload_df_edited_config(df_edited_config_file)

def offline_configuration_edit():
    print("\nStarting offline configuration file edit...")
    df_config_file = input("Enter DefenseFlow Configuration Filename: ")
    dfcm = DFConfigModifier(df_config_file)
    dfcm.process()

if __name__ == "__main__":
    main_menu()
    # v = Vision()
    # v.dst_vision_login()
    # v.upload_df_edited_config('DefenseFlowConfiguration_2024-09-30_09-43-10-edited.zip')
