"""
SuperAdmin Panel Tests - Testing companies, branches, and users management for SuperAdmin role
Tests the following features:
- GET /api/companies - list companies with counts (superadmin only)
- POST /api/companies - create company with admin user (superadmin only)
- GET /api/branches?company_id=X - list branches for specific company
- POST /api/branches?company_id=X - create branch for specific company
- POST /api/users?company_id=X - create user for specific company
- Access control: regular admin should NOT access /api/companies
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - lee de env vars con defaults seguros
from _credentials import SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD


class TestSuperAdminAuth:
    """Test SuperAdmin authentication and access"""
    
    @pytest.fixture(scope="class")
    def superadmin_session(self):
        """Get authenticated session for superadmin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        assert response.status_code == 200, f"SuperAdmin login failed: {response.text}"
        data = response.json()
        assert data.get("role") == "superadmin", f"Expected superadmin role, got {data.get('role')}"
        return session
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Get authenticated session for regular admin"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert data.get("role") == "admin", f"Expected admin role, got {data.get('role')}"
        return session
    
    def test_superadmin_login_returns_correct_role(self, superadmin_session):
        """Verify superadmin login returns role=superadmin"""
        response = superadmin_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "superadmin"
        assert data["company_id"] is None  # SuperAdmin has no company
        print(f"SuperAdmin user: {data['name']} ({data['email']})")
    
    def test_admin_login_returns_correct_role(self, admin_session):
        """Verify regular admin login returns role=admin"""
        response = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["company_id"] is not None  # Admin has a company
        print(f"Admin user: {data['name']} ({data['email']}), company_id: {data['company_id']}")


class TestCompaniesEndpoint:
    """Test /api/companies endpoint - SuperAdmin only"""
    
    @pytest.fixture(scope="class")
    def superadmin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_list_companies_superadmin_success(self, superadmin_session):
        """GET /api/companies returns list with counts for superadmin"""
        response = superadmin_session.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} companies")
        
        # Verify each company has required fields
        for company in data:
            assert "_id" in company
            assert "name" in company
            assert "branches_count" in company
            assert "users_count" in company
            assert "patients_count" in company
            print(f"  - {company['name']}: {company['branches_count']} branches, {company['users_count']} users, {company['patients_count']} patients")
    
    def test_list_companies_admin_denied(self, admin_session):
        """GET /api/companies returns 403 for regular admin"""
        response = admin_session.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 403
        print("Regular admin correctly denied access to /api/companies")
    
    def test_list_companies_unauthenticated_denied(self):
        """GET /api/companies returns 401 for unauthenticated user"""
        response = requests.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 401
        print("Unauthenticated user correctly denied access to /api/companies")
    
    def test_create_company_superadmin_success(self, superadmin_session):
        """POST /api/companies creates company with admin user"""
        timestamp = int(time.time())
        company_data = {
            "name": f"TEST_Optica_{timestamp}",
            "legal_name": f"TEST Optica Legal {timestamp}",
            "tax_id": f"NIT-{timestamp}",
            "address": "Test Address 123",
            "phone": "5555-1234",
            "email": f"test_optica_{timestamp}@test.com",
            "admin_name": f"Test Admin {timestamp}",
            "admin_email": f"test_admin_{timestamp}@test.com",
            "admin_password": "TestPass123!"
        }
        
        response = superadmin_session.post(f"{BASE_URL}/api/companies", json=company_data)
        assert response.status_code == 200, f"Create company failed: {response.text}"
        data = response.json()
        assert "_id" in data
        assert data["name"] == company_data["name"]
        print(f"Created company: {data['name']} with ID: {data['_id']}")
        
        # Verify company appears in list
        list_response = superadmin_session.get(f"{BASE_URL}/api/companies")
        companies = list_response.json()
        created_company = next((c for c in companies if c["_id"] == data["_id"]), None)
        assert created_company is not None
        assert created_company["users_count"] >= 1  # At least the admin user
        print(f"Verified company in list with {created_company['users_count']} users")
        
        return data["_id"]
    
    def test_create_company_admin_denied(self, admin_session):
        """POST /api/companies returns 403 for regular admin"""
        company_data = {
            "name": "Should Not Create",
            "legal_name": "Should Not Create",
            "tax_id": "NIT-000",
            "address": "Test",
            "phone": "1234",
            "email": "shouldnot@test.com",
            "admin_name": "Test",
            "admin_email": "shouldnot_admin@test.com",
            "admin_password": "Test123!"
        }
        response = admin_session.post(f"{BASE_URL}/api/companies", json=company_data)
        assert response.status_code == 403
        print("Regular admin correctly denied from creating companies")
    
    def test_get_company_by_id_superadmin(self, superadmin_session):
        """GET /api/companies/{id} returns company details"""
        # First get list to find a company
        list_response = superadmin_session.get(f"{BASE_URL}/api/companies")
        companies = list_response.json()
        if len(companies) > 0:
            company_id = companies[0]["_id"]
            response = superadmin_session.get(f"{BASE_URL}/api/companies/{company_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["_id"] == company_id
            print(f"Got company details: {data['name']}")


class TestBranchesForCompany:
    """Test /api/branches with company_id parameter - SuperAdmin functionality"""
    
    @pytest.fixture(scope="class")
    def superadmin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_company_id(self, superadmin_session):
        """Get or create a test company for branch tests"""
        list_response = superadmin_session.get(f"{BASE_URL}/api/companies")
        companies = list_response.json()
        if len(companies) > 0:
            return companies[0]["_id"]
        return None
    
    def test_list_branches_for_company(self, superadmin_session, test_company_id):
        """GET /api/branches?company_id=X returns branches for specific company"""
        if not test_company_id:
            pytest.skip("No company available for testing")
        
        response = superadmin_session.get(f"{BASE_URL}/api/branches?company_id={test_company_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} branches for company {test_company_id}")
        
        for branch in data:
            assert "_id" in branch
            assert "name" in branch
            print(f"  - {branch['name']}")
    
    def test_create_branch_for_company(self, superadmin_session, test_company_id):
        """POST /api/branches?company_id=X creates branch for specific company"""
        if not test_company_id:
            pytest.skip("No company available for testing")
        
        timestamp = int(time.time())
        branch_data = {
            "name": f"TEST_Sucursal_{timestamp}",
            "address": f"Test Branch Address {timestamp}",
            "phone": "5555-9999",
            "email": f"test_branch_{timestamp}@test.com"
        }
        
        response = superadmin_session.post(
            f"{BASE_URL}/api/branches?company_id={test_company_id}",
            json=branch_data
        )
        assert response.status_code == 200, f"Create branch failed: {response.text}"
        data = response.json()
        assert "_id" in data
        assert data["name"] == branch_data["name"]
        print(f"Created branch: {data['name']} with ID: {data['_id']}")
        
        # Verify branch appears in list
        list_response = superadmin_session.get(f"{BASE_URL}/api/branches?company_id={test_company_id}")
        branches = list_response.json()
        created_branch = next((b for b in branches if b["_id"] == data["_id"]), None)
        assert created_branch is not None
        print(f"Verified branch in list for company")
    
    def test_create_branch_without_company_id_fails(self, superadmin_session):
        """POST /api/branches without company_id returns 400 for superadmin"""
        branch_data = {
            "name": "Should Fail Branch",
            "address": "Test",
            "phone": "1234"
        }
        response = superadmin_session.post(f"{BASE_URL}/api/branches", json=branch_data)
        assert response.status_code == 400
        print("SuperAdmin correctly required to specify company_id")


class TestUsersForCompany:
    """Test /api/users with company_id parameter - SuperAdmin functionality"""
    
    @pytest.fixture(scope="class")
    def superadmin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    @pytest.fixture(scope="class")
    def test_company_id(self, superadmin_session):
        """Get a test company for user tests"""
        list_response = superadmin_session.get(f"{BASE_URL}/api/companies")
        companies = list_response.json()
        if len(companies) > 0:
            return companies[0]["_id"]
        return None
    
    def test_list_users_superadmin(self, superadmin_session):
        """GET /api/users returns all users for superadmin"""
        response = superadmin_session.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} total users")
        
        for user in data[:5]:  # Print first 5
            print(f"  - {user['name']} ({user['email']}) - role: {user['role']}")
    
    def test_create_user_for_company(self, superadmin_session, test_company_id):
        """POST /api/users?company_id=X creates user for specific company"""
        if not test_company_id:
            pytest.skip("No company available for testing")
        
        timestamp = int(time.time())
        user_data = {
            "name": f"TEST_User_{timestamp}",
            "email": f"test_user_{timestamp}@test.com",
            "password": "TestPass123!",
            "role": "user"
        }
        
        response = superadmin_session.post(
            f"{BASE_URL}/api/users?company_id={test_company_id}",
            json=user_data
        )
        assert response.status_code == 200, f"Create user failed: {response.text}"
        data = response.json()
        assert "_id" in data
        print(f"Created user: {user_data['name']} with ID: {data['_id']}")
        
        # Verify user appears in list
        list_response = superadmin_session.get(f"{BASE_URL}/api/users")
        users = list_response.json()
        created_user = next((u for u in users if u["_id"] == data["_id"]), None)
        assert created_user is not None
        assert created_user["company_id"] == test_company_id
        print(f"Verified user in list with correct company_id")
    
    def test_create_user_without_company_id_fails(self, superadmin_session):
        """POST /api/users without company_id returns 400 for superadmin"""
        user_data = {
            "name": "Should Fail User",
            "email": "shouldfail@test.com",
            "password": "Test123!",
            "role": "user"
        }
        response = superadmin_session.post(f"{BASE_URL}/api/users", json=user_data)
        assert response.status_code == 400
        print("SuperAdmin correctly required to specify company_id")
    
    def test_update_user_status(self, superadmin_session, test_company_id):
        """PUT /api/users/{id} can update user status"""
        # First create a user to update
        timestamp = int(time.time())
        user_data = {
            "name": f"TEST_StatusUser_{timestamp}",
            "email": f"test_status_{timestamp}@test.com",
            "password": "TestPass123!",
            "role": "user"
        }
        
        create_response = superadmin_session.post(
            f"{BASE_URL}/api/users?company_id={test_company_id}",
            json=user_data
        )
        if create_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        user_id = create_response.json()["_id"]
        
        # Update user status to inactive
        update_response = superadmin_session.put(
            f"{BASE_URL}/api/users/{user_id}",
            json={"is_active": False}
        )
        assert update_response.status_code == 200
        print(f"Updated user {user_id} to inactive")
        
        # Verify status changed
        list_response = superadmin_session.get(f"{BASE_URL}/api/users")
        users = list_response.json()
        updated_user = next((u for u in users if u["_id"] == user_id), None)
        assert updated_user is not None
        assert updated_user["is_active"] == False
        print("Verified user status is now inactive")


class TestAccessControl:
    """Test that regular admin cannot access superadmin-only endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return session
    
    def test_admin_cannot_list_companies(self, admin_session):
        """Regular admin cannot access GET /api/companies"""
        response = admin_session.get(f"{BASE_URL}/api/companies")
        assert response.status_code == 403
        print("Access control: Admin denied from listing companies")
    
    def test_admin_cannot_create_company(self, admin_session):
        """Regular admin cannot access POST /api/companies"""
        response = admin_session.post(f"{BASE_URL}/api/companies", json={
            "name": "Test", "legal_name": "Test", "tax_id": "123",
            "address": "Test", "phone": "123", "email": "test@test.com",
            "admin_name": "Test", "admin_email": "admin@test.com", "admin_password": "Test123!"
        })
        assert response.status_code == 403
        print("Access control: Admin denied from creating companies")
    
    def test_admin_can_access_own_branches(self, admin_session):
        """Regular admin CAN access branches for their own company"""
        response = admin_session.get(f"{BASE_URL}/api/branches")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Admin can access their own branches: {len(data)} found")
    
    def test_admin_can_access_own_users(self, admin_session):
        """Regular admin CAN access users for their own company"""
        response = admin_session.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Admin can access their own users: {len(data)} found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
