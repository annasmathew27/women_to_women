HerEase service providing platform
Team Name: ZeroDay
Team Members
Member 1: Geethika Anil -Muthoot Institute of Technology and Science
Member 2: Anna S Mathew -Muthoot Institute of Technology and Science
Hosted Project Link
https://women-to-women-3.onrender.com
Project Description
Its a women to women support and service platform designed to create a safer and more trusted environment for women seeking help.It has a very easy and interactive UI which helps the customers to place their request specifying their requirement,time and the money they are willing to pay. 

The Problem statement
women often faces safety and risk concerns when accessing local services.Existing platforms lack a secure,women-only system with proper location validation and structured service control,increasing risk and hesitation
The Solution
Its a women to women servicing providing app which ensures that both the service provider as well as the receiver is woman.
It is very easy to use and helps those women who are leading a life of solitude to request their day to day services like doing laundry or something else from a women so that they feel more at ease knowing that it is a woman at the other end coming over to complete the mentioned task.

Technical Details
Technologies/Components Used
For Software:

Languages used: JavaScript, Python,CSS,html,SQL
Frameworks used: Flask
Libraries used: gunicorn,werkzeug,jinja2,leaflet.js,SQLite3
Tools used: VS Code,Git,Github,Render(for deployment)
Features
List the key features of your project:

Feature 1: Separate signup and login systems for receivers and providers
Feature 2:location based service matching
Feature 3: Structured service request system
Feature 4:Secure service completion workflow

Implementation
For Software:
Installation
 npm install, pip install -r requirements.txt,python -m venv venv,
Run
 python app.py
 
Project Documentation
Software:
Screenshots :
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/3ffb8ce9-26f7-4cf2-9aa8-cbc4cd6a0082" />
it allows the receiver or provider to directly specify their address in the map itself.For receiver,they can specify additional details to their location.For provider they can specify their service area radius.
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/6d4f47a5-88b7-4e66-a3f1-07a19ecf885e" />
it shows the history of service requested with the service requested ,date and time.It also shows whether the service is provided or not.
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/2295e000-8c87-44eb-b3b0-20c17392be0e" />
It shows that their is separate clean and clear login and signup page for both the sender and reciever making it easy to use.
API Documentation
Base URL: https://women-to-women-1.onrender.com
Save Receiver Location + Check Availability
POST /api/receiver/location
Description:
1.Saves receiver location and checks if providers are available within radius.
Copy code
{
  "location_text": "Perth CBD",
  "lat": -31.9523,
  "lng": 115.8613
}
Response:
{
  "ok": true,
  "can_serve": true,
  "providers_in_range": 2,
  "providers_total": 5,
  "reason": "Service is available for your location."
}
2. Create Service Request
POST /api/requests
Description:
Creates a new service request by receiver.
Copy code
{
  "title": "Home Cleaning",
  "category": "Cleaning",
  "details": "Need kitchen cleaning",
  "scheduled_date": "2026-02-25",
  "scheduled_time": "10:00",
  "duration_min": 120,
  "hourly_wage": 25
}
Response:
{
  "ok": true,
  "id": 12
}
3️ Get Receiver Requests
GET /api/requests
Description:
Returns logged-in user's requests.
Response:
[
  {
    "id": 12,
    "title": "Home Cleaning",
    "status": "Open",
    "created_at": "2026-02-21T10:30:00"
  }
]
4️ Mark Request as Serviced
POST /api/requests/<req_id>/resolve
Description:
Marks request as serviced (provider or receiver authorized).
Response:
{
  "ok": true,
  "status": "Serviced"
}

Diagrams
System Architecture:
3-Tier Architecture
🧱 Layer 1 — Presentation Layer (Frontend)
HTML
CSS
JavaScript
Leaflet.js (Map)
Browser Geolocation API
Handles:
UI rendering
Form submissions
API calls (fetch)
Map interaction
⚙️ Layer 2 — Application Layer (Backend)
Flask
REST APIs
Authentication logic
Radius filtering logic (Haversine formula)
Role-based access control
Handles:
Business logic
Request validation
Authorization
Service matching
🗄 Layer 3 — Data Layer
SQLite (currently)
Tables:
Users
Requests
Handles:
Data storage
Query execution
Status tracking

AI Tools Used :
ChatGPT
Team Contributions:
Anna S Mathew:UI
Geethika Anil:Backend,deployment
