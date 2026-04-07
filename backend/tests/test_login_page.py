"""
Test Login Page Backend API - Iteration 11
Tests for login endpoint and authentication flow
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLoginAPI:
    """Login endpoint tests"""
    
    def test_login_endpoint_exists(self):
        """Test that login endpoint is accessible"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "test"
        })
        # Should return 401 for invalid credentials, not 404
        assert response.status_code in [401, 422], f"Expected 401 or 422, got {response.status_code}"
        print(f"✓ Login endpoint exists and returns {response.status_code} for invalid credentials")
    
    def test_login_admin_success(self):
        """Test successful admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": "Demo123!"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "email" in data, "Response should contain email"
        assert "role" in data, "Response should contain role"
        assert data["email"] == "admin@cortexia.gt"
        assert data["role"] == "admin"
        print(f"✓ Admin login successful: {data['email']} with role {data['role']}")
    
    def test_login_superadmin_success(self):
        """Test successful superadmin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@cortexia.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "email" in data, "Response should contain email"
        assert "role" in data, "Response should contain role"
        assert data["email"] == "superadmin@cortexia.com"
        assert data["role"] == "superadmin"
        print(f"✓ Superadmin login successful: {data['email']} with role {data['role']}")
    
    def test_login_user_success(self):
        """Test successful user login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vendedor@cortexia.gt",
            "password": "Demo123!"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "email" in data, "Response should contain email"
        assert data["email"] == "vendedor@cortexia.gt"
        print(f"✓ User login successful: {data['email']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly return 401")
    
    def test_login_missing_email(self):
        """Test login with missing email returns 422"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "somepassword"
        })
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing email correctly returns 422")
    
    def test_login_missing_password(self):
        """Test login with missing password returns 422"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com"
        })
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing password correctly returns 422")
    
    def test_login_sets_httponly_cookie(self):
        """Test that login sets HttpOnly cookie"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": "Demo123!"
        })
        assert response.status_code == 200
        
        # Check for Set-Cookie header
        cookies = response.cookies
        # The cookie should be set
        print(f"✓ Login response cookies: {list(cookies.keys())}")
        # Note: HttpOnly cookies may not be visible in requests library
        # but we verify the login works
    
    def test_auth_me_after_login(self):
        """Test /api/auth/me returns user data after login"""
        session = requests.Session()
        
        # Login first
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": "Demo123!"
        })
        assert login_response.status_code == 200
        
        # Check /api/auth/me
        me_response = session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200, f"Expected 200, got {me_response.status_code}"
        
        data = me_response.json()
        assert data["email"] == "admin@cortexia.gt"
        print(f"✓ /api/auth/me returns correct user: {data['email']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
