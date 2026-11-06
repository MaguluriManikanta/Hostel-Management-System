# Hostel Management System (HMS)

A complete, modern, web-based Hostel Management System developed strictly in accordance with the Software Requirements Specification (SRS) for Lab 02.

## System Overview
The Hostel Management System automates the core administrative operations of an academic residential hostel:
- **Student Registration (FR-1)**: Online student profile management, photo/document storage, and auto-generation of unique Student IDs (`HS2026xxx`).
- **Room Allocation (FR-2)**: Real-time room availability, strict capacity constraint enforcement, and room reallocation/transfer request workflow.
- **Attendance Management (FR-4)**: Daily roll-call logging by wardens/staff with instant conflict-free upserts, date-wise filtering, and student calendar views.
- **Visitor Entry Management (FR-5)**: In/Out time logging, relationship tracking, visitor history search, and departed status management.
- **Complaint Handling (FR-6)**: Category-wise ticketing (Electrical, Plumbing, Wi-Fi, etc.), priority levels, and real-time status transitions (*Pending* → *In Progress* → *Resolved*).
- **Announcements & Alerts (FR-7)**: Role-targeted announcements with urgency tags broadcasted directly to student dashboards.
- **User Management & RBAC (FR-8)**: Strict role-based access control supporting Administrator, Warden, Student, and Hostel Staff, backed by SHA-256 password hashing and immutable audit logging.
- **Reports & Export (FR-9)**: Block-wise room occupancy metrics, fee collection summaries, and instant CSV report exports.

## Technology Stack
- **Backend**: Python 3.14, FastAPI 0.141, Starlette, Uvicorn ASGI Server
- **Frontend**: HTML5, CSS3 Custom Modern Dark/Teal Theme (matching Fig 6.1 & Fig 6.2 reference mockups), Jinja2 Server-Side Templating
- **Database**: SQLite 3 with Relational Schema & Foreign Key Integrity Constraints
- **Testing & Screenshot Automation**: Playwright (Headless Microsoft Edge)
- **Document Generation**: ReportLab 5.0

## Quick Start Instructions

### 1. Install Dependencies
```bash
pip install fastapi uvicorn jinja2 python-multipart itsdangerous reportlab
```

### 2. Run the Application
From the project root:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

### 3. Demo Credentials
| Role | Username / User ID | Password | Access Capabilities |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full administrative control, student admissions, room management, fee ledger, reports, audit logs |
| **Warden** | `warden` | `warden123` | Attendance roll call, room inspection, complaint resolution, resident notices |
| **Staff** | `staff` | `staff123` | Gate visitor check-in/out, maintenance status updates |
| **Student** | `HS2026042` | `student123` | Resident portal, room details, personal attendance, fee payment, file maintenance tickets |

## Project Structure
```
HostelManagementSystem/
├── app/
│   ├── database.py       # SQLite connection, tables DDL, seed data
│   ├── main.py           # FastAPI routes, controllers, authentication, sessions
│   ├── static/           # CSS styles and uploaded files
│   └── templates/        # Jinja2 HTML templates for all roles and views
├── screenshots/
│   ├── code/             # High-resolution IDE code screenshots
│   └── website/          # Live running application screenshots
├── submission/           # Final Software Engineering submission deliverables
└── test_and_capture.py   # Automated browser test and screenshot script
```
