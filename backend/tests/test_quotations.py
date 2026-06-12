"""
Test suite for Cortexia Optical - Quotations Module
Tests all CRUD operations for quotations including:
- List quotations
- Create quotation
- Get quotation detail
- Update quotation status (accept/reject)
- Convert quotation to sale
- Download PDF
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - lee de env vars con defaults seguros
from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD


class TestQuotationsModule:
    """Quotations module tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth cookies
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.user = login_response.json()
        print(f"Logged in as: {self.user.get('name')} ({self.user.get('role')})")
        
        # Get patients for testing
        patients_response = self.session.get(f"{BASE_URL}/api/patients?limit=10")
        assert patients_response.status_code == 200
        self.patients = patients_response.json().get("patients", [])
        assert len(self.patients) > 0, "No patients found for testing"
        self.test_patient_id = self.patients[0]["_id"]
        print(f"Using patient: {self.patients[0]['first_name']} {self.patients[0]['last_name']}")
        
        # Get products for testing
        products_response = self.session.get(f"{BASE_URL}/api/inventory/products")
        assert products_response.status_code == 200
        self.products = products_response.json()
        assert len(self.products) > 0, "No products found for testing"
        print(f"Found {len(self.products)} products for testing")
        
        yield
        
        # Cleanup - no explicit cleanup needed as quotations are company-scoped
    
    # ==================== LIST QUOTATIONS ====================
    def test_list_quotations_returns_array(self):
        """GET /api/quotations returns array (may be empty initially)"""
        response = self.session.get(f"{BASE_URL}/api/quotations")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be an array"
        print(f"Found {len(data)} existing quotations")
    
    def test_list_quotations_with_status_filter(self):
        """GET /api/quotations?status=pendiente filters by status"""
        response = self.session.get(f"{BASE_URL}/api/quotations?status=pendiente")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned quotations should have status 'pendiente'
        for q in data:
            assert q.get("status") == "pendiente", f"Expected pendiente, got {q.get('status')}"
        print(f"Found {len(data)} pending quotations")
    
    # ==================== CREATE QUOTATION ====================
    def test_create_quotation_success(self):
        """POST /api/quotations creates a new quotation"""
        product = self.products[0]
        
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [
                {
                    "product_id": product["_id"],
                    "name": product["name"],
                    "quantity": 2,
                    "unit_price": product["sale_price"],
                    "subtotal": product["sale_price"] * 2
                }
            ],
            "subtotal": product["sale_price"] * 2,
            "discount": 50.0,
            "total": (product["sale_price"] * 2) - 50.0,
            "notes": "TEST_Quotation - Prueba automatizada",
            "payment_conditions": "50% anticipo, 50% al entregar",
            "validity_days": 15
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        assert response.status_code == 200, f"Failed to create quotation: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Response should contain _id"
        assert "quotation_number" in data, "Response should contain quotation_number"
        assert data["quotation_number"].startswith("COT-"), f"Quotation number should start with COT-, got {data['quotation_number']}"
        
        self.created_quotation_id = data["_id"]
        print(f"Created quotation: {data['quotation_number']} (ID: {data['_id']})")
        
        return data["_id"]
    
    def test_create_quotation_with_multiple_items(self):
        """POST /api/quotations with multiple products"""
        items = []
        subtotal = 0
        
        for product in self.products[:3]:  # Use first 3 products
            item_subtotal = product["sale_price"] * 1
            items.append({
                "product_id": product["_id"],
                "name": product["name"],
                "quantity": 1,
                "unit_price": product["sale_price"],
                "subtotal": item_subtotal
            })
            subtotal += item_subtotal
        
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": items,
            "subtotal": subtotal,
            "discount": 0,
            "total": subtotal,
            "notes": "TEST_Multiple items quotation",
            "payment_conditions": "Pago al contado",
            "validity_days": 30
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "_id" in data
        print(f"Created multi-item quotation: {data['quotation_number']}")
    
    def test_create_quotation_without_patient_fails(self):
        """POST /api/quotations without patient_id should fail"""
        quotation_data = {
            "items": [{"name": "Test", "quantity": 1, "unit_price": 100, "subtotal": 100}],
            "subtotal": 100,
            "total": 100,
            "validity_days": 15
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("Correctly rejected quotation without patient_id")
    
    # ==================== GET QUOTATION DETAIL ====================
    def test_get_quotation_detail(self):
        """GET /api/quotations/{id} returns quotation with patient_name"""
        # First create a quotation
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "discount": 0,
            "total": product["sale_price"],
            "notes": "TEST_Detail test",
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        assert create_response.status_code == 200
        quotation_id = create_response.json()["_id"]
        
        # Get detail
        response = self.session.get(f"{BASE_URL}/api/quotations/{quotation_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["_id"] == quotation_id
        assert "patient_name" in data, "Response should include patient_name"
        assert "items" in data, "Response should include items"
        assert "subtotal" in data
        assert "discount" in data
        assert "total" in data
        assert "status" in data
        assert data["status"] == "pendiente", f"New quotation should be pendiente, got {data['status']}"
        assert "expiry_date" in data, "Response should include expiry_date"
        
        print(f"Quotation detail: {data['quotation_number']} - Patient: {data['patient_name']} - Total: Q{data['total']}")
    
    def test_get_nonexistent_quotation_returns_404(self):
        """GET /api/quotations/{invalid_id} returns 404"""
        response = self.session.get(f"{BASE_URL}/api/quotations/000000000000000000000000")
        assert response.status_code == 404
        print("Correctly returned 404 for non-existent quotation")
    
    # ==================== UPDATE STATUS ====================
    def test_update_quotation_status_to_aceptada(self):
        """PUT /api/quotations/{id}/status updates to aceptada"""
        # Create quotation first
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "total": product["sale_price"],
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # Update status to aceptada
        response = self.session.put(f"{BASE_URL}/api/quotations/{quotation_id}/status", json={"status": "aceptada"})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify status changed
        detail_response = self.session.get(f"{BASE_URL}/api/quotations/{quotation_id}")
        assert detail_response.json()["status"] == "aceptada"
        print("Successfully updated quotation status to aceptada")
    
    def test_update_quotation_status_to_rechazada(self):
        """PUT /api/quotations/{id}/status updates to rechazada"""
        # Create quotation first
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "total": product["sale_price"],
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # Update status to rechazada
        response = self.session.put(f"{BASE_URL}/api/quotations/{quotation_id}/status", json={"status": "rechazada"})
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify status changed
        detail_response = self.session.get(f"{BASE_URL}/api/quotations/{quotation_id}")
        assert detail_response.json()["status"] == "rechazada"
        print("Successfully updated quotation status to rechazada")
    
    def test_update_quotation_invalid_status_fails(self):
        """PUT /api/quotations/{id}/status with invalid status fails"""
        # Create quotation first
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "total": product["sale_price"],
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # Try invalid status
        response = self.session.put(f"{BASE_URL}/api/quotations/{quotation_id}/status", json={"status": "invalid_status"})
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Correctly rejected invalid status")
    
    # ==================== CONVERT TO SALE ====================
    def test_convert_quotation_to_sale(self):
        """POST /api/quotations/{id}/convert creates sale and finance entry"""
        # Create quotation first
        product = self.products[0]
        total = product["sale_price"] * 2
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 2, "unit_price": product["sale_price"], "subtotal": total}],
            "subtotal": total,
            "total": total,
            "notes": "TEST_Convert to sale",
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # Convert to sale
        response = self.session.post(f"{BASE_URL}/api/quotations/{quotation_id}/convert?payment_method=efectivo&amount_paid={total}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Response should contain sale _id"
        assert "message" in data
        print(f"Converted quotation to sale: {data['_id']}")
        
        # Verify quotation status changed to convertida
        detail_response = self.session.get(f"{BASE_URL}/api/quotations/{quotation_id}")
        assert detail_response.json()["status"] == "convertida"
        print("Quotation status correctly updated to convertida")
        
        # Verify sale was created
        sale_response = self.session.get(f"{BASE_URL}/api/sales/{data['_id']}")
        assert sale_response.status_code == 200
        sale = sale_response.json()
        assert sale["total"] == total
        print(f"Sale verified: Total Q{sale['total']}")
    
    def test_convert_quotation_partial_payment(self):
        """POST /api/quotations/{id}/convert with partial payment"""
        product = self.products[0]
        total = product["sale_price"] * 2
        partial_payment = total / 2
        
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 2, "unit_price": product["sale_price"], "subtotal": total}],
            "subtotal": total,
            "total": total,
            "notes": "TEST_Partial payment",
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # Convert with partial payment
        response = self.session.post(f"{BASE_URL}/api/quotations/{quotation_id}/convert?payment_method=tarjeta&amount_paid={partial_payment}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        sale_id = response.json()["_id"]
        sale_response = self.session.get(f"{BASE_URL}/api/sales/{sale_id}")
        sale = sale_response.json()
        
        assert sale["amount_paid"] == partial_payment
        assert sale["balance"] == total - partial_payment
        assert sale["status"] == "pendiente"  # Not fully paid
        print(f"Partial payment sale created: Paid Q{sale['amount_paid']}, Balance Q{sale['balance']}")
    
    def test_convert_already_converted_quotation_fails(self):
        """POST /api/quotations/{id}/convert on converted quotation fails"""
        # Create and convert quotation
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "total": product["sale_price"],
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # First conversion
        self.session.post(f"{BASE_URL}/api/quotations/{quotation_id}/convert?payment_method=efectivo")
        
        # Try to convert again
        response = self.session.post(f"{BASE_URL}/api/quotations/{quotation_id}/convert?payment_method=efectivo")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Correctly rejected converting already converted quotation")
    
    # ==================== PDF DOWNLOAD ====================
    def test_download_quotation_pdf(self):
        """GET /api/quotations/{id}/pdf returns PDF file"""
        # Create quotation first
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "total": product["sale_price"],
            "notes": "TEST_PDF download",
            "payment_conditions": "Pago al contado",
            "validity_days": 15
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        quotation_id = create_response.json()["_id"]
        
        # Download PDF
        response = self.session.get(f"{BASE_URL}/api/quotations/{quotation_id}/pdf")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 0, "PDF content should not be empty"
        
        # Check content-disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "cotizacion" in content_disposition.lower()
        
        print(f"PDF downloaded successfully: {len(response.content)} bytes")
    
    # ==================== SEARCH/FILTER ====================
    def test_search_quotations_by_patient(self):
        """GET /api/quotations?patient_id={id} filters by patient"""
        # Create quotation for specific patient
        product = self.products[0]
        quotation_data = {
            "patient_id": self.test_patient_id,
            "items": [{"product_id": product["_id"], "name": product["name"], "quantity": 1, "unit_price": product["sale_price"], "subtotal": product["sale_price"]}],
            "subtotal": product["sale_price"],
            "total": product["sale_price"],
            "validity_days": 15
        }
        
        self.session.post(f"{BASE_URL}/api/quotations", json=quotation_data)
        
        # Search by patient
        response = self.session.get(f"{BASE_URL}/api/quotations?patient_id={self.test_patient_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # All returned quotations should be for this patient
        for q in data:
            assert q.get("patient_id") == self.test_patient_id
        print(f"Found {len(data)} quotations for patient {self.test_patient_id}")
    
    def test_filter_quotations_todas(self):
        """GET /api/quotations?status=todas returns all quotations"""
        response = self.session.get(f"{BASE_URL}/api/quotations?status=todas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Filter 'todas' returned {len(data)} quotations")


class TestQuotationsAuth:
    """Test authentication requirements for quotations"""
    
    def test_list_quotations_without_auth_fails(self):
        """GET /api/quotations without auth returns 401"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/quotations")
        assert response.status_code == 401
        print("Correctly rejected unauthenticated request")
    
    def test_create_quotation_without_auth_fails(self):
        """POST /api/quotations without auth returns 401"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/quotations", json={
            "patient_id": "test",
            "items": [],
            "subtotal": 0,
            "total": 0,
            "validity_days": 15
        })
        assert response.status_code == 401
        print("Correctly rejected unauthenticated create request")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
