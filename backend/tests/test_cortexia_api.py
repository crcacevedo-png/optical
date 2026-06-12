"""
Cortexia Optical API Tests
Tests for authentication, patients, appointments, prescriptions, inventory, sales, finance, branches, and users
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - lee de env vars con defaults seguros
from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD

class TestAuth:
    """Authentication endpoint tests"""
    
    def test_login_admin_success(self):
        """Test login with admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "_id" in data
        assert data["email"] == ADMIN_EMAIL.lower()
        assert data["role"] == "admin"
        print(f"✓ Admin login successful: {data['name']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@email.com", "password": "wrongpass"}
        )
        assert response.status_code == 401
        print("✓ Invalid credentials rejected correctly")
    
    def test_auth_me_without_token(self):
        """Test /auth/me without authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ Unauthenticated /me request rejected")


class TestDashboard:
    """Dashboard endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
    
    def test_dashboard_loads(self):
        """Test dashboard endpoint returns data"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        # Verify expected fields
        assert "appointments_today" in data
        assert "new_patients" in data
        assert "stock_alerts" in data
        assert "income" in data
        assert "expense" in data
        assert "profit" in data
        print(f"✓ Dashboard loaded: {data['appointments_today']} appointments today, {data['new_patients']} new patients")


class TestPatients:
    """Patient CRUD tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
    
    def test_list_patients(self):
        """Test listing patients"""
        response = self.session.get(f"{BASE_URL}/api/patients")
        assert response.status_code == 200, f"List patients failed: {response.text}"
        data = response.json()
        assert "patients" in data
        assert "total" in data
        print(f"✓ Listed {len(data['patients'])} patients (total: {data['total']})")
    
    def test_search_patients(self):
        """Test patient search"""
        response = self.session.get(f"{BASE_URL}/api/patients", params={"search": "Maria"})
        assert response.status_code == 200, f"Search failed: {response.text}"
        data = response.json()
        print(f"✓ Search returned {len(data['patients'])} results")
    
    def test_create_and_get_patient(self):
        """Test creating a patient and retrieving it"""
        # Create patient
        patient_data = {
            "first_name": "TEST_Juan",
            "last_name": "Prueba",
            "phone": "55551234",
            "email": "test_juan@test.com"
        }
        create_response = self.session.post(f"{BASE_URL}/api/patients", json=patient_data)
        assert create_response.status_code == 200, f"Create patient failed: {create_response.text}"
        created = create_response.json()
        assert "_id" in created
        patient_id = created["_id"]
        
        # Get patient to verify persistence
        get_response = self.session.get(f"{BASE_URL}/api/patients/{patient_id}")
        assert get_response.status_code == 200, f"Get patient failed: {get_response.text}"
        patient = get_response.json()
        assert patient["first_name"] == "TEST_Juan"
        assert patient["last_name"] == "Prueba"
        print(f"✓ Created and verified patient: {patient['first_name']} {patient['last_name']}")


class TestAppointments:
    """Appointment tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_appointments(self):
        """Test listing appointments for today"""
        today = datetime.now().strftime("%Y-%m-%d")
        response = self.session.get(f"{BASE_URL}/api/appointments", params={"date": today})
        assert response.status_code == 200, f"List appointments failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} appointments for {today}")
    
    def test_create_appointment(self):
        """Test creating an appointment"""
        # First get a patient
        patients_response = self.session.get(f"{BASE_URL}/api/patients", params={"limit": 1})
        assert patients_response.status_code == 200
        patients = patients_response.json()["patients"]
        if not patients:
            pytest.skip("No patients available for appointment test")
        
        patient_id = patients[0]["_id"]
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        appointment_data = {
            "patient_id": patient_id,
            "date": tomorrow,
            "time": "10:00",
            "duration": 30,
            "type": "consulta"
        }
        response = self.session.post(f"{BASE_URL}/api/appointments", json=appointment_data)
        assert response.status_code == 200, f"Create appointment failed: {response.text}"
        data = response.json()
        assert "_id" in data
        print(f"✓ Created appointment for {tomorrow} at 10:00")


class TestPrescriptions:
    """Prescription tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_eyeglass_prescriptions(self):
        """Test listing eyeglass prescriptions"""
        response = self.session.get(f"{BASE_URL}/api/prescriptions/eyeglass")
        assert response.status_code == 200, f"List eyeglass Rx failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} eyeglass prescriptions")
    
    def test_list_contact_prescriptions(self):
        """Test listing contact lens prescriptions"""
        response = self.session.get(f"{BASE_URL}/api/prescriptions/contact")
        assert response.status_code == 200, f"List contact Rx failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} contact lens prescriptions")
    
    def test_list_medical_prescriptions(self):
        """Test listing medical prescriptions"""
        response = self.session.get(f"{BASE_URL}/api/prescriptions/medical")
        assert response.status_code == 200, f"List medical Rx failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} medical prescriptions")


class TestInventory:
    """Inventory tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_products(self):
        """Test listing products"""
        response = self.session.get(f"{BASE_URL}/api/inventory/products")
        assert response.status_code == 200, f"List products failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} products")
    
    def test_list_products_with_category_filter(self):
        """Test filtering products by category"""
        response = self.session.get(f"{BASE_URL}/api/inventory/products", params={"category": "armazones"})
        assert response.status_code == 200, f"Filter products failed: {response.text}"
        data = response.json()
        print(f"✓ Filtered products by category: {len(data)} results")
    
    def test_list_stock(self):
        """Test listing stock"""
        response = self.session.get(f"{BASE_URL}/api/inventory/stock")
        assert response.status_code == 200, f"List stock failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} stock items")
    
    def test_stock_alerts(self):
        """Test stock alerts endpoint"""
        response = self.session.get(f"{BASE_URL}/api/inventory/alerts")
        assert response.status_code == 200, f"Stock alerts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} stock alerts")


class TestSales:
    """Sales tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_sales(self):
        """Test listing sales"""
        response = self.session.get(f"{BASE_URL}/api/sales")
        assert response.status_code == 200, f"List sales failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} sales")


class TestFinance:
    """Finance tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_finance_entries(self):
        """Test listing finance entries"""
        response = self.session.get(f"{BASE_URL}/api/finance")
        assert response.status_code == 200, f"List finance failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} finance entries")
    
    def test_finance_summary(self):
        """Test finance summary endpoint"""
        response = self.session.get(f"{BASE_URL}/api/finance/summary")
        assert response.status_code == 200, f"Finance summary failed: {response.text}"
        data = response.json()
        assert "income" in data
        assert "expense" in data
        assert "profit" in data
        print(f"✓ Finance summary: Income={data['income']}, Expense={data['expense']}, Profit={data['profit']}")
    
    def test_create_finance_entry(self):
        """Test creating a finance entry (ingreso)"""
        entry_data = {
            "type": "ingreso",
            "category": "other_income",
            "amount": 100.00,
            "description": "TEST_Ingreso de prueba",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        response = self.session.post(f"{BASE_URL}/api/finance", json=entry_data)
        assert response.status_code == 200, f"Create finance entry failed: {response.text}"
        data = response.json()
        assert "_id" in data
        print(f"✓ Created finance entry (ingreso)")
    
    def test_create_egreso_entry(self):
        """Test creating an egreso entry"""
        entry_data = {
            "type": "egreso",
            "category": "other_expense",
            "amount": 50.00,
            "description": "TEST_Egreso de prueba",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        response = self.session.post(f"{BASE_URL}/api/finance", json=entry_data)
        assert response.status_code == 200, f"Create egreso failed: {response.text}"
        data = response.json()
        assert "_id" in data
        print(f"✓ Created finance entry (egreso)")


class TestBranches:
    """Branch tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_branches(self):
        """Test listing branches"""
        response = self.session.get(f"{BASE_URL}/api/branches")
        assert response.status_code == 200, f"List branches failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} branches")


class TestUsers:
    """User tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
    
    def test_list_users(self):
        """Test listing users"""
        response = self.session.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200, f"List users failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} users")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
