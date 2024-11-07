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
   git clone https://github.com/yourusername/defenseflow-migration.git
   cd defenseflow-migration
