"""
Test suite for Agenda (Appointments) module - Daily, Weekly, Monthly views
Tests the appointments API endpoints with date and date range queries
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAgendaAPI:
    """Appointments/Agenda endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth cookies"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": "Demo123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.user = login_response.json()
        
        # Get a patient ID for creating appointments
        patients_response = self.session.get(f"{BASE_URL}/api/patients?limit=5")
        assert patients_response.status_code == 200
        patients = patients_response.json().get('patients', [])
        self.patient_id = patients[0]['_id'] if patients else None
        
        yield
        
        # Cleanup - logout
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    # ===== Daily View Tests =====
    def test_get_appointments_daily_view_with_date_param(self):
        """GET /api/appointments?date=YYYY-MM-DD returns daily appointments"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = self.session.get(f"{BASE_URL}/api/appointments?date={today}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All appointments should be for the specified date
        for apt in data:
            assert apt['date'] == today
            assert 'patient_name' in apt
            assert 'time' in apt
            assert 'status' in apt
    
    def test_get_appointments_daily_view_empty_date(self):
        """GET /api/appointments?date=future returns empty for future date"""
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        response = self.session.get(f"{BASE_URL}/api/appointments?date={future_date}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should be empty or have no appointments for far future
    
    # ===== Weekly View Tests =====
    def test_get_appointments_weekly_view_with_date_range(self):
        """GET /api/appointments?date_from=X&date_to=Y returns range of appointments"""
        # Get current week range
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday
        
        date_from = week_start.strftime('%Y-%m-%d')
        date_to = week_end.strftime('%Y-%m-%d')
        
        response = self.session.get(f"{BASE_URL}/api/appointments?date_from={date_from}&date_to={date_to}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All appointments should be within the date range
        for apt in data:
            apt_date = apt['date']
            assert date_from <= apt_date <= date_to, f"Appointment date {apt_date} not in range {date_from} to {date_to}"
    
    # ===== Monthly View Tests =====
    def test_get_appointments_monthly_view_with_date_range(self):
        """GET /api/appointments?date_from=X&date_to=Y returns month of appointments"""
        # Get current month range
        today = datetime.now()
        month_start = today.replace(day=1)
        next_month = month_start.replace(month=month_start.month % 12 + 1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1)
        month_end = next_month - timedelta(days=1)
        
        date_from = month_start.strftime('%Y-%m-%d')
        date_to = month_end.strftime('%Y-%m-%d')
        
        response = self.session.get(f"{BASE_URL}/api/appointments?date_from={date_from}&date_to={date_to}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All appointments should be within the month range
        for apt in data:
            apt_date = apt['date']
            assert date_from <= apt_date <= date_to
    
    # ===== CRUD Tests =====
    def test_create_appointment_success(self):
        """POST /api/appointments creates new appointment"""
        if not self.patient_id:
            pytest.skip("No patient available for test")
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        appointment_data = {
            "patient_id": self.patient_id,
            "date": tomorrow,
            "time": "10:00",
            "duration": 30,
            "type": "consulta",
            "notes": "TEST_Appointment for agenda testing"
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments", json=appointment_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "_id" in data
        assert data["message"] == "Cita creada"
        
        # Store for cleanup
        self.created_appointment_id = data["_id"]
        
        # Verify by GET
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{data['_id']}")
        assert get_response.status_code == 200
        apt = get_response.json()
        assert apt["date"] == tomorrow
        assert apt["time"] == "10:00"
        assert apt["type"] == "consulta"
        assert apt["status"] == "pendiente"
    
    def test_create_appointment_missing_patient(self):
        """POST /api/appointments without patient_id returns 422"""
        appointment_data = {
            "date": "2026-04-15",
            "time": "10:00",
            "duration": 30,
            "type": "consulta"
        }
        
        response = self.session.post(f"{BASE_URL}/api/appointments", json=appointment_data)
        assert response.status_code == 422  # Validation error
    
    def test_update_appointment_status_confirmada(self):
        """PUT /api/appointments/{id} updates status to confirmada"""
        if not self.patient_id:
            pytest.skip("No patient available for test")
        
        # Create appointment first
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        create_response = self.session.post(f"{BASE_URL}/api/appointments", json={
            "patient_id": self.patient_id,
            "date": tomorrow,
            "time": "11:00",
            "duration": 30,
            "type": "examen"
        })
        assert create_response.status_code == 200
        apt_id = create_response.json()["_id"]
        
        # Update status
        update_response = self.session.put(f"{BASE_URL}/api/appointments/{apt_id}", json={
            "status": "confirmada"
        })
        
        assert update_response.status_code == 200
        assert update_response.json()["message"] == "Cita actualizada"
        
        # Verify status changed
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "confirmada"
    
    def test_update_appointment_status_completada(self):
        """PUT /api/appointments/{id} updates status to completada"""
        if not self.patient_id:
            pytest.skip("No patient available for test")
        
        # Create appointment first
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        create_response = self.session.post(f"{BASE_URL}/api/appointments", json={
            "patient_id": self.patient_id,
            "date": tomorrow,
            "time": "12:00",
            "duration": 30,
            "type": "control"
        })
        assert create_response.status_code == 200
        apt_id = create_response.json()["_id"]
        
        # Update status
        update_response = self.session.put(f"{BASE_URL}/api/appointments/{apt_id}", json={
            "status": "completada"
        })
        
        assert update_response.status_code == 200
        
        # Verify status changed
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "completada"
    
    def test_cancel_appointment(self):
        """DELETE /api/appointments/{id} cancels appointment (sets status to cancelada)"""
        if not self.patient_id:
            pytest.skip("No patient available for test")
        
        # Create appointment first
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        create_response = self.session.post(f"{BASE_URL}/api/appointments", json={
            "patient_id": self.patient_id,
            "date": tomorrow,
            "time": "13:00",
            "duration": 30,
            "type": "entrega"
        })
        assert create_response.status_code == 200
        apt_id = create_response.json()["_id"]
        
        # Cancel appointment
        delete_response = self.session.delete(f"{BASE_URL}/api/appointments/{apt_id}")
        
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Cita cancelada"
        
        # Verify status is cancelada
        get_response = self.session.get(f"{BASE_URL}/api/appointments/{apt_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "cancelada"
    
    def test_get_appointment_not_found(self):
        """GET /api/appointments/{invalid_id} returns 404"""
        response = self.session.get(f"{BASE_URL}/api/appointments/000000000000000000000000")
        assert response.status_code == 404
    
    # ===== Filter Tests =====
    def test_get_appointments_filter_by_status(self):
        """GET /api/appointments?status=pendiente filters by status"""
        response = self.session.get(f"{BASE_URL}/api/appointments?status=pendiente")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All appointments should have pendiente status
        for apt in data:
            assert apt['status'] == 'pendiente'
    
    def test_get_appointments_without_auth_returns_401(self):
        """GET /api/appointments without auth returns 401"""
        # Create new session without auth
        new_session = requests.Session()
        response = new_session.get(f"{BASE_URL}/api/appointments")
        assert response.status_code == 401
    
    # ===== Appointment Types Tests =====
    def test_create_appointment_all_types(self):
        """POST /api/appointments works for all appointment types"""
        if not self.patient_id:
            pytest.skip("No patient available for test")
        
        types = ['consulta', 'examen', 'control', 'entrega']
        base_date = datetime.now() + timedelta(days=2)
        
        for i, apt_type in enumerate(types):
            date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            response = self.session.post(f"{BASE_URL}/api/appointments", json={
                "patient_id": self.patient_id,
                "date": date,
                "time": f"0{9+i}:00",
                "duration": 30,
                "type": apt_type,
                "notes": f"TEST_Type test: {apt_type}"
            })
            
            assert response.status_code == 200, f"Failed to create appointment of type {apt_type}"
            data = response.json()
            assert "_id" in data
    
    # ===== Response Structure Tests =====
    def test_appointment_response_includes_patient_name(self):
        """GET /api/appointments includes patient_name in response"""
        response = self.session.get(f"{BASE_URL}/api/appointments")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            apt = data[0]
            assert 'patient_name' in apt, "Response should include patient_name"
            assert 'patient_phone' in apt, "Response should include patient_phone"
    
    def test_appointments_sorted_by_date_and_time(self):
        """GET /api/appointments returns appointments sorted by date and time"""
        response = self.session.get(f"{BASE_URL}/api/appointments")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 1:
            # Check sorting
            for i in range(len(data) - 1):
                current = f"{data[i]['date']} {data[i]['time']}"
                next_apt = f"{data[i+1]['date']} {data[i+1]['time']}"
                assert current <= next_apt, "Appointments should be sorted by date and time"
