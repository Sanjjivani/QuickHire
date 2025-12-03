# QuickHire
QuickHire is a modern, full-featured job portal platform that connects job seekers with employers through an intuitive, feature-rich interface with real-time communication capabilities.

✨ Features
👥 Dual-Role Platform
Job Seekers: Browse jobs, apply, chat with employers, manage profiles

Employers: Post jobs, browse candidates, direct hiring, manage applications


===============================================================================

🎯 Core Features:


✅ Modern UI/UX with dark/light theme support

✅ Real-time chat system between employers and job seekers

✅ Interactive maps for location-based job/candidate search

✅ Comprehensive dashboards with analytics

✅ Review & rating system for both parties

✅ Responsive design for all device sizes

✅ Direct hiring without job postings

✅ Application tracking with status updates

✅ Skill-based matching system

=====================================================================================

🛠️ Technical Features:

Role-based authentication and authorization

Session management with Flask-Login

Database ORM with SQLAlchemy

Real-time updates with WebSocket-like features

File upload capabilities

Email notifications system

Admin panel for system management

==================================================================================

🏗️ Architecture
Tech Stack
Frontend:

HTML5, CSS3, JavaScript (ES6+)

Bootstrap 5.3 for responsive design

Jinja2 templating engine

Font Awesome 6 for icons

Chart.js for data visualization

SweetAlert2 for notifications

Backend:

Python 3.8+

Flask 2.3+ web framework

SQLAlchemy ORM

Flask-Login for authentication

Flask-WTF for forms

Flask-Migrate for database migrations

Database: mysql 

=========================================================================================


🚀 Quick Start
Installation
Clone the repository

bash
https://github.com/Sanjjivani/QuickHire.git
cd quickhire
Create a virtual environment

bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
Install dependencies

bash
pip install -r requirements.txt
Configure the application

bash
cp config.example.py config.py
# Edit config.py with your settings
Initialize the database

bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
Run the application

bash
# Development
python run.py

# Or with Flask
flask run --debug
Access the application

Open browser: http://localhost:5000

Default admin: admin@quickhire.com / admin123
