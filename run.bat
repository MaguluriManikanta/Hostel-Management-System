@echo off
title Hostel Management System
echo Starting Hostel Management System...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
