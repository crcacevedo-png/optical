#!/usr/bin/env python3
"""
Backend API Testing for Ópticas SaaS Platform
Tests all major endpoints with demo credentials
"""

import requests
import sys
import json
from datetime import datetime, timedelta

class OpticasSaaSAPITester:
    def __init__(self, base_url="https://eyecare-erp.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.user_data = None
        
    def log_test(self, name, success, details=""):
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            self.failed_tests.append({"name": name, "details": details})
            print(f"❌ {name} - {details}")
    
    def test_login(self, email, password):
        """Test login with demo credentials"""
        try:
            response = self.session.post(f"{self.base_url}/api/auth/login", 
                                       json={"email": email, "password": password})
            
            if response.status_code == 200:
                self.user_data = response.json()
                self.log_test(f"Login ({email})", True)
                return True
            else:
                self.log_test(f"Login ({email})", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test(f"Login ({email})", False, str(e))
            return False
    
    def test_auth_me(self):
        """Test getting current user info"""
        try:
            response = self.session.get(f"{self.base_url}/api/auth/me")
            success = response.status_code == 200
            details = "" if success else f"Status: {response.status_code}"
            self.log_test("Get current user (/api/auth/me)", success, details)
            return success
        except Exception as e:
            self.log_test("Get current user", False, str(e))
            return False
    
    def test_dashboard(self):
        """Test dashboard data"""
        try:
            response = self.session.get(f"{self.base_url}/api/reports/dashboard")
            success = response.status_code == 200
            if success:
                data = response.json()
                # Check if dashboard has expected fields
                expected_fields = ['appointments_today', 'new_patients', 'sales_count', 'income', 'expense']
                has_fields = all(field in data for field in expected_fields)
                if not has_fields:
                    success = False
                    details = f"Missing expected fields in dashboard data"
                else:
                    details = f"Dashboard loaded with {data.get('appointments_today', 0)} appointments today"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("Dashboard data", success, details)
            return success
        except Exception as e:
            self.log_test("Dashboard data", False, str(e))
            return False
    
    def test_patients_list(self):
        """Test patients listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/patients")
            success = response.status_code == 200
            if success:
                data = response.json()
                patient_count = len(data.get('patients', []))
                details = f"Found {patient_count} patients"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List patients", success, details)
            return success, data.get('patients', []) if success else []
        except Exception as e:
            self.log_test("List patients", False, str(e))
            return False, []
    
    def test_create_patient(self):
        """Test creating a new patient"""
        try:
            patient_data = {
                "first_name": "Test",
                "last_name": "Patient",
                "phone": "+502 5555-9999",
                "dpi": "9999999999999",
                "gender": "M",
                "birth_date": "1990-01-01",
                "email": "test@example.com",
                "address": "Test Address"
            }
            response = self.session.post(f"{self.base_url}/api/patients", json=patient_data)
            success = response.status_code == 200
            if success:
                data = response.json()
                patient_id = data.get('_id')
                details = f"Created patient with ID: {patient_id}"
                return success, patient_id
            else:
                details = f"Status: {response.status_code}, Response: {response.text}"
                self.log_test("Create patient", success, details)
                return False, None
            self.log_test("Create patient", success, details)
        except Exception as e:
            self.log_test("Create patient", False, str(e))
            return False, None
    
    def test_appointments_list(self):
        """Test appointments listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/appointments")
            success = response.status_code == 200
            if success:
                data = response.json()
                appointment_count = len(data) if isinstance(data, list) else 0
                details = f"Found {appointment_count} appointments"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List appointments", success, details)
            return success
        except Exception as e:
            self.log_test("List appointments", False, str(e))
            return False
    
    def test_create_appointment(self, patient_id):
        """Test creating an appointment"""
        if not patient_id:
            self.log_test("Create appointment", False, "No patient ID available")
            return False
            
        try:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            appointment_data = {
                "patient_id": patient_id,
                "date": tomorrow,
                "time": "10:00",
                "type": "Consulta general",
                "duration": 30,
                "notes": "Test appointment"
            }
            response = self.session.post(f"{self.base_url}/api/appointments", json=appointment_data)
            success = response.status_code == 200
            details = "" if success else f"Status: {response.status_code}, Response: {response.text}"
            self.log_test("Create appointment", success, details)
            return success
        except Exception as e:
            self.log_test("Create appointment", False, str(e))
            return False
    
    def test_prescriptions_list(self):
        """Test prescriptions listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/prescriptions/eyeglass")
            success = response.status_code == 200
            if success:
                data = response.json()
                rx_count = len(data) if isinstance(data, list) else 0
                details = f"Found {rx_count} eyeglass prescriptions"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List eyeglass prescriptions", success, details)
            return success
        except Exception as e:
            self.log_test("List eyeglass prescriptions", False, str(e))
            return False
    
    def test_create_prescription(self, patient_id):
        """Test creating an eyeglass prescription"""
        if not patient_id:
            self.log_test("Create prescription", False, "No patient ID available")
            return False
            
        try:
            prescription_data = {
                "patient_id": patient_id,
                "od_sphere": -2.5,
                "od_cylinder": -0.5,
                "od_axis": 90,
                "oi_sphere": -2.0,
                "oi_cylinder": -0.25,
                "oi_axis": 85,
                "observations": "Test prescription",
                "lens_type": "Monofocal",
                "frame_type": "Completo"
            }
            response = self.session.post(f"{self.base_url}/api/prescriptions/eyeglass", json=prescription_data)
            success = response.status_code == 200
            details = "" if success else f"Status: {response.status_code}, Response: {response.text}"
            self.log_test("Create eyeglass prescription", success, details)
            return success
        except Exception as e:
            self.log_test("Create eyeglass prescription", False, str(e))
            return False
    
    def test_inventory_products(self):
        """Test inventory products listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/inventory/products")
            success = response.status_code == 200
            if success:
                data = response.json()
                product_count = len(data) if isinstance(data, list) else 0
                details = f"Found {product_count} products"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List inventory products", success, details)
            return success
        except Exception as e:
            self.log_test("List inventory products", False, str(e))
            return False
    
    def test_sales_list(self):
        """Test sales listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/sales")
            success = response.status_code == 200
            if success:
                data = response.json()
                sales_count = len(data) if isinstance(data, list) else 0
                details = f"Found {sales_count} sales"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List sales", success, details)
            return success
        except Exception as e:
            self.log_test("List sales", False, str(e))
            return False
    
    def test_finance_entries(self):
        """Test finance entries listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/finance")
            success = response.status_code == 200
            if success:
                data = response.json()
                entries_count = len(data) if isinstance(data, list) else 0
                details = f"Found {entries_count} finance entries"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List finance entries", success, details)
            return success
        except Exception as e:
            self.log_test("List finance entries", False, str(e))
            return False
    
    def test_finance_summary(self):
        """Test finance summary"""
        try:
            response = self.session.get(f"{self.base_url}/api/finance/summary")
            success = response.status_code == 200
            if success:
                data = response.json()
                details = f"Income: Q{data.get('income', 0)}, Expense: Q{data.get('expense', 0)}, Profit: Q{data.get('profit', 0)}"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("Finance summary", success, details)
            return success
        except Exception as e:
            self.log_test("Finance summary", False, str(e))
            return False
    
    def test_branches_list(self):
        """Test branches listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/branches")
            success = response.status_code == 200
            if success:
                data = response.json()
                branches_count = len(data) if isinstance(data, list) else 0
                details = f"Found {branches_count} branches"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List branches", success, details)
            return success
        except Exception as e:
            self.log_test("List branches", False, str(e))
            return False
    
    def test_users_list(self):
        """Test users listing"""
        try:
            response = self.session.get(f"{self.base_url}/api/users")
            success = response.status_code == 200
            if success:
                data = response.json()
                users_count = len(data) if isinstance(data, list) else 0
                details = f"Found {users_count} users"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("List users", success, details)
            return success
        except Exception as e:
            self.log_test("List users", False, str(e))
            return False
    
    def test_reports_sales(self):
        """Test sales report"""
        try:
            response = self.session.get(f"{self.base_url}/api/reports/sales")
            success = response.status_code == 200
            if success:
                data = response.json()
                details = f"Sales report: Total Q{data.get('total', 0)}, Count: {data.get('count', 0)}"
            else:
                details = f"Status: {response.status_code}"
            self.log_test("Sales report", success, details)
            return success
        except Exception as e:
            self.log_test("Sales report", False, str(e))
            return False
    
    def test_logout(self):
        """Test logout"""
        try:
            response = self.session.post(f"{self.base_url}/api/auth/logout")
            success = response.status_code == 200
            details = "" if success else f"Status: {response.status_code}"
            self.log_test("Logout", success, details)
            return success
        except Exception as e:
            self.log_test("Logout", False, str(e))
            return False

def main():
    print("🔍 Testing Ópticas SaaS Backend APIs")
    print("=" * 50)
    
    tester = OpticasSaaSAPITester()
    
    # Test admin login (usa env vars, sin hardcode)
    import os as _os
    admin_email = _os.getenv("TEST_ADMIN_EMAIL", "admin@visionclara.gt")
    admin_pw = _os.getenv("TEST_ADMIN_PASSWORD") or _os.getenv("DEMO_PASSWORD", "")
    print("\n📋 Testing Admin Login...")
    if not tester.test_login(admin_email, admin_pw):
        print("❌ Admin login failed, stopping tests")
        return 1
    
    # Test authentication
    print("\n🔐 Testing Authentication...")
    tester.test_auth_me()
    
    # Test dashboard
    print("\n📊 Testing Dashboard...")
    tester.test_dashboard()
    
    # Test patients
    print("\n👥 Testing Patients...")
    patients_success, patients = tester.test_patients_list()
    patient_id = None
    if patients_success:
        create_success, patient_id = tester.test_create_patient()
    
    # Test appointments
    print("\n📅 Testing Appointments...")
    tester.test_appointments_list()
    if patient_id:
        tester.test_create_appointment(patient_id)
    
    # Test prescriptions
    print("\n👓 Testing Prescriptions...")
    tester.test_prescriptions_list()
    if patient_id:
        tester.test_create_prescription(patient_id)
    
    # Test inventory
    print("\n📦 Testing Inventory...")
    tester.test_inventory_products()
    
    # Test sales
    print("\n💰 Testing Sales...")
    tester.test_sales_list()
    
    # Test finance
    print("\n💳 Testing Finance...")
    tester.test_finance_entries()
    tester.test_finance_summary()
    
    # Test branches
    print("\n🏢 Testing Branches...")
    tester.test_branches_list()
    
    # Test users
    print("\n👤 Testing Users...")
    tester.test_users_list()
    
    # Test reports
    print("\n📈 Testing Reports...")
    tester.test_reports_sales()
    
    # Test logout
    print("\n🚪 Testing Logout...")
    tester.test_logout()
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.failed_tests:
        print("\n❌ Failed Tests:")
        for test in tester.failed_tests:
            print(f"  • {test['name']}: {test['details']}")
    
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"✅ Success Rate: {success_rate:.1f}%")
    
    return 0 if success_rate >= 80 else 1

if __name__ == "__main__":
    sys.exit(main())