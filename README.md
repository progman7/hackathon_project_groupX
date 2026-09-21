# hackathon_project_groupX
SpotUM is a study spot finder for Maastricht University students. It shows in real time which study rooms and lecture halls across UM’s campus buildings are free or busy, and lets students book a room for a specific date and time in just a few clicks.

# UM Study Spot Finder

An app for finding free study rooms/spots at the university.

## Requirements

- Python 3.9 or newer
- pip (usually comes with Python)

## How to run the project

1. Clone the repository and navigate into the project folder:
git clone https://github.com/progman7/hackathon_project_groupX.git
cd hackathon_project_groupX

2. Create a virtual environment (recommended):
python3 -m venv venv
source venv/bin/activate
(On Windows, use instead: venv\Scripts\activate)

3. Install dependencies:
pip install -r requirements.txt

4. Seed the database with demo data:
python seed_demo_data.py

5. Run the application:
python app.py

6. Open the address shown in the terminal in your browser (usually http://127.0.0.1:5000)
   
7. Admin password is spotum2026

## Project structure

- app.py — main application file
- seed_demo_data.py — script to populate the database with test data
- requirements.txt — list of dependencies
- templates/ — HTML page templates
