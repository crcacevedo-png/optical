"""
Test Branch Filtering Feature
Tests branch_id filtering on appointments, sales, inventory/stock, inventory/alerts, and dashboard endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASSWORD = "Demo123!"


class TestBranchFiltering:
    """Test branch_id filtering on various endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get branches"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.user = login_response.json()
        
        # Get branches
        branches_response = self.session.get(f"{BASE_URL}/api/branches")
        assert branches_response.status_code == 200, f"Failed to get branches: {branches_response.text}"
        self.branches = branches_response.json()
        
        print(f"Logged in as: {self.user['email']}, role: {self.user['role']}")
        print(f"Found {len(self.branches)} branches")
        for b in self.branches:
            print(f"  - Branch: {b['name']} (ID: {b['_id']})")
        
        yield
        
        # Logout
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    # ==================== APPOINTMENTS TESTS ====================
    def test_appointments_without_branch_filter(self):
        """GET /api/appointments without branch_id returns all appointments"""
        response = self.session.get(f"{BASE_URL}/api/appointments")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Appointments without filter: {len(data)} appointments")
        assert isinstance(data, list)
    
    def test_appointments_with_branch_filter(self):
        """GET /api/appointments?branch_id=X filters by branch"""
        if len(self.branches) < 1:
            pytest.skip("No branches available")
        
        branch_id = self.branches[0]['_id']
        response = self.session.get(f"{BASE_URL}/api/appointments", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Appointments for branch {branch_id}: {len(data)} appointments")
        
        # Verify all returned appointments belong to the specified branch
        for apt in data:
            if apt.get('branch_id'):
                assert apt['branch_id'] == branch_id, f"Appointment {apt['_id']} has wrong branch_id"
    
    def test_appointments_with_second_branch_filter(self):
        """GET /api/appointments?branch_id=X for second branch"""
        if len(self.branches) < 2:
            pytest.skip("Less than 2 branches available")
        
        branch_id = self.branches[1]['_id']
        response = self.session.get(f"{BASE_URL}/api/appointments", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Appointments for second branch {branch_id}: {len(data)} appointments")
        
        for apt in data:
            if apt.get('branch_id'):
                assert apt['branch_id'] == branch_id, f"Appointment {apt['_id']} has wrong branch_id"
    
    # ==================== SALES TESTS ====================
    def test_sales_without_branch_filter(self):
        """GET /api/sales without branch_id returns all sales"""
        response = self.session.get(f"{BASE_URL}/api/sales")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Sales without filter: {len(data)} sales")
        assert isinstance(data, list)
    
    def test_sales_with_branch_filter(self):
        """GET /api/sales?branch_id=X filters by branch"""
        if len(self.branches) < 1:
            pytest.skip("No branches available")
        
        branch_id = self.branches[0]['_id']
        response = self.session.get(f"{BASE_URL}/api/sales", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Sales for branch {branch_id}: {len(data)} sales")
        
        for sale in data:
            if sale.get('branch_id'):
                assert sale['branch_id'] == branch_id, f"Sale {sale['_id']} has wrong branch_id"
    
    def test_sales_with_second_branch_filter(self):
        """GET /api/sales?branch_id=X for second branch"""
        if len(self.branches) < 2:
            pytest.skip("Less than 2 branches available")
        
        branch_id = self.branches[1]['_id']
        response = self.session.get(f"{BASE_URL}/api/sales", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Sales for second branch {branch_id}: {len(data)} sales")
        
        for sale in data:
            if sale.get('branch_id'):
                assert sale['branch_id'] == branch_id, f"Sale {sale['_id']} has wrong branch_id"
    
    # ==================== INVENTORY STOCK TESTS ====================
    def test_stock_without_branch_filter(self):
        """GET /api/inventory/stock without branch_id returns all stock"""
        response = self.session.get(f"{BASE_URL}/api/inventory/stock")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Stock without filter: {len(data)} items")
        assert isinstance(data, list)
    
    def test_stock_with_branch_filter(self):
        """GET /api/inventory/stock?branch_id=X filters by branch"""
        if len(self.branches) < 1:
            pytest.skip("No branches available")
        
        branch_id = self.branches[0]['_id']
        response = self.session.get(f"{BASE_URL}/api/inventory/stock", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Stock for branch {branch_id}: {len(data)} items")
        
        for item in data:
            if item.get('branch_id'):
                assert item['branch_id'] == branch_id, f"Stock item has wrong branch_id"
    
    def test_stock_with_second_branch_filter(self):
        """GET /api/inventory/stock?branch_id=X for second branch"""
        if len(self.branches) < 2:
            pytest.skip("Less than 2 branches available")
        
        branch_id = self.branches[1]['_id']
        response = self.session.get(f"{BASE_URL}/api/inventory/stock", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Stock for second branch {branch_id}: {len(data)} items")
        
        for item in data:
            if item.get('branch_id'):
                assert item['branch_id'] == branch_id, f"Stock item has wrong branch_id"
    
    # ==================== INVENTORY ALERTS TESTS ====================
    def test_alerts_without_branch_filter(self):
        """GET /api/inventory/alerts without branch_id returns all alerts"""
        response = self.session.get(f"{BASE_URL}/api/inventory/alerts")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Alerts without filter: {len(data)} alerts")
        assert isinstance(data, list)
    
    def test_alerts_with_branch_filter(self):
        """GET /api/inventory/alerts?branch_id=X filters by branch"""
        if len(self.branches) < 1:
            pytest.skip("No branches available")
        
        branch_id = self.branches[0]['_id']
        response = self.session.get(f"{BASE_URL}/api/inventory/alerts", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Alerts for branch {branch_id}: {len(data)} alerts")
        
        for alert in data:
            if alert.get('branch_id'):
                assert alert['branch_id'] == branch_id, f"Alert has wrong branch_id"
    
    def test_alerts_with_second_branch_filter(self):
        """GET /api/inventory/alerts?branch_id=X for second branch"""
        if len(self.branches) < 2:
            pytest.skip("Less than 2 branches available")
        
        branch_id = self.branches[1]['_id']
        response = self.session.get(f"{BASE_URL}/api/inventory/alerts", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Alerts for second branch {branch_id}: {len(data)} alerts")
        
        for alert in data:
            if alert.get('branch_id'):
                assert alert['branch_id'] == branch_id, f"Alert has wrong branch_id"
    
    # ==================== DASHBOARD TESTS ====================
    def test_dashboard_without_branch_filter(self):
        """GET /api/reports/dashboard without branch_id returns aggregated data"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Dashboard without filter: {data}")
        
        # Verify dashboard structure
        assert 'appointments_today' in data
        assert 'new_patients' in data
        assert 'sales_count_today' in data
        assert 'total_sales_today' in data
        assert 'stock_alerts' in data
        assert 'income' in data
        assert 'expense' in data
        assert 'profit' in data
    
    def test_dashboard_with_branch_filter(self):
        """GET /api/reports/dashboard?branch_id=X filters dashboard data by branch"""
        if len(self.branches) < 1:
            pytest.skip("No branches available")
        
        branch_id = self.branches[0]['_id']
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Dashboard for branch {branch_id}: {data}")
        
        # Verify dashboard structure
        assert 'appointments_today' in data
        assert 'new_patients' in data
        assert 'sales_count_today' in data
        assert 'total_sales_today' in data
        assert 'stock_alerts' in data
    
    def test_dashboard_with_second_branch_filter(self):
        """GET /api/reports/dashboard?branch_id=X for second branch"""
        if len(self.branches) < 2:
            pytest.skip("Less than 2 branches available")
        
        branch_id = self.branches[1]['_id']
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard", params={"branch_id": branch_id})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Dashboard for second branch {branch_id}: {data}")
        
        # Verify dashboard structure
        assert 'appointments_today' in data
        assert 'new_patients' in data
        assert 'sales_count_today' in data
    
    # ==================== BRANCHES ENDPOINT TEST ====================
    def test_branches_list(self):
        """GET /api/branches returns list of branches"""
        response = self.session.get(f"{BASE_URL}/api/branches")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"Branches: {len(data)} branches")
        
        assert isinstance(data, list)
        assert len(data) >= 1, "Expected at least 1 branch"
        
        # Verify branch structure
        for branch in data:
            assert '_id' in branch
            assert 'name' in branch
            print(f"  Branch: {branch['name']} (ID: {branch['_id']})")
    
    def test_multiple_branches_exist(self):
        """Verify that 2+ branches exist for BranchFilter to show"""
        response = self.session.get(f"{BASE_URL}/api/branches")
        assert response.status_code == 200
        data = response.json()
        
        print(f"Total branches: {len(data)}")
        for b in data:
            print(f"  - {b['name']}")
        
        # The BranchFilter component only shows when >1 branch exists
        assert len(data) >= 2, "Expected at least 2 branches for BranchFilter to be visible"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
