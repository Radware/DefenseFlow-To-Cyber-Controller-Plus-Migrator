# DefenseFlow to Cyber-Controller Plus Migration Script

This repository contains a Python script designed to facilitate the migration of DefenseFlow configurations to Cyber-Controller Plus. The script automates key steps in the migration process, ensuring configurations are correctly adapted and imported.

## Overview

This script supports two main modes of operation:
- **Online Mode**: Automates exporting configurations from DefenseFlow (via Vision) and importing them directly into Cyber-Controller Plus.
- **Offline Mode**: Requires manual export and import of configurations, but automates the conversion for compatibility.

## Features

- **Automates DefenseFlow to Cyber-Controller Plus migration**.
- **Two modes**:
  - **Online**: Fully automated, requiring access to both Vision and Cyber-Controller Plus.
  - **Offline**: Semi-automated, with manual configuration file handling.
- **Optional features**:
  - **Disable All Protected Objects**: Facilitates a gradual migration, allowing the systems to run concurrently.
  - **Increment Policy Precedence**: Adjusts policy precedence to avoid collisions when both systems are operational.

## Prerequisites

Ensure the following are available before running the script:

1. **Python 3.6** installed with the `requests` library.
2. **Cyber-Controller Plus** license installed, with DefensePro devices properly associated.
3. **DefenseFlow physical interfaces**:
   - Must match those in Cyber-Controller Plus. The IP addresses can differ.
   - Interface associations must align between both systems.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/Radware/DefenseFlow-To-Cyber-Controller-Plus-Migrator.git
   cd DefenseFlow-To-Cyber-Controller-Plus-Migrator
   ```
2. Install the required Python dependencies:
   ```bash
   pip install requests
   ```

## Usage

### Basic Command

```bash
python3 DefenseFlow_to_Cyber-Controller_Plus.py [OPTIONS]
```

### Parameters

- **--mode**  
  Mode of operation (`offline` or `online`).  
  Example: `--mode offline`

- **--src**  
  Source details (username, password, and IP) for Vision in online mode.  
  Format: `user:pass@ip`  
  Example: `--src admin:password@1.1.1.1`

- **--dst**  
  Destination details (username, password, and IP) for Cyber-Controller Plus.  
  Format: `user:pass@ip`  
  Example: `--dst admin:password@2.2.2.2`

- **--input**  
  DefenseFlow configuration file for offline mode.  
  Example: `--input DefenseFlowConfiguration_2024-10-15_05-33-54.zip`

- **--disable-pos**  
  Disable all Protected Objects during the migration. Useful for gradual migration.

### Example Usage

```bash
# Offline mode example
python3 script_name.py --mode offline --input DefenseFlowConfiguration_2024-10-15_05-33-54.zip --disable-pos

# Online mode example
python3 script_name.py --mode online --src admin:password@1.1.1.1 --dst admin:password@2.2.2.2 --disable-pos
```

### Considerations and Known Caveats

#### 1. Large Configurations May Cause Timeout Errors
When importing large configurations, **Cyber-Controller Plus (CC Plus)** may return a timeout error. This typically happens because the system takes longer than expected to process the configuration.

**Solution:**  
Even if the script displays a timeout error, the configuration may have been successfully imported. To verify, check the **import/export log** on CC Plus.

#### 2. DNS Allow List with Non-RFC Domain Names Will Fail During Import
If a **non-RFC-compliant domain name** exists in the DNS allow list, the import will fail. This is due to differences in Allow List handling between **DefenseFlow** and **Cyber-Controller Plus**.

**Solution:**  
Before running the script, remove any **non-RFC-compliant domain names** from DefenseFlow. To identify the exact domain name that caused the import failure, check the **import/export log**.

### How to Check Import/Export Logs
To review the import/export logs on **Cyber-Controller Plus**, connect via SSH using the `root` user and execute the following commands:

```bash
root@cyber-controller-server:~# cddfclogs
root@cyber-controller-server:~# cat import_export_configuration.log
