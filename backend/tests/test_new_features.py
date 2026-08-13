"""
Test new features for Cortexia Optical:
1. Edit Patient (PUT /api/patients/{id})
2. Global Search (GET /api/search)
3. Consultation with linked prescriptions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNewFeatures:
    """Test the 3 new features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.user = login_response.json()
        print(f"Logged in as: {self.user['email']}")
    
    # ========== FEATURE 1: Edit Patient ==========
    def test_get_patients_list(self):
        """Test getting patients list"""
        response = self.session.get(f"{BASE_URL}/api/patients")
        assert response.status_code == 200
        data = response.json()
        assert "patients" in data
        assert "total" in data
        print(f"Found {data['total']} patients")
        return data
    
    def test_edit_patient_phone(self):
        """Test editing a patient's phone number"""
        # First get patients
        patients_response = self.session.get(f"{BASE_URL}/api/patients?search=Maria")
        assert patients_response.status_code == 200
        patients = patients_response.json()["patients"]
        
        if len(patients) == 0:
            pytest.skip("No patient named Maria found")
        
        patient = patients[0]
        patient_id = patient["_id"]
        original_phone = patient.get("phone", "")
        print(f"Testing edit for patient: {patient['first_name']} {patient['last_name']}, ID: {patient_id}")
        
        # Update phone
        new_phone = "99998888"
        update_response = self.session.put(f"{BASE_URL}/api/patients/{patient_id}", json={
            "phone": new_phone
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        print(f"Phone updated to: {new_phone}")
        
        # Verify the change persisted
        get_response = self.session.get(f"{BASE_URL}/api/patients/{patient_id}")
        assert get_response.status_code == 200
        updated_patient = get_response.json()
        assert updated_patient["phone"] == new_phone, f"Phone not updated. Expected {new_phone}, got {updated_patient['phone']}"
        print(f"Verified phone is now: {updated_patient['phone']}")
        
        # Restore original phone
        restore_response = self.session.put(f"{BASE_URL}/api/patients/{patient_id}", json={
            "phone": original_phone or "55551234"
        })
        assert restore_response.status_code == 200
        print(f"Restored phone to: {original_phone or '55551234'}")
    
    def test_edit_patient_multiple_fields(self):
        """Test editing multiple patient fields"""
        patients_response = self.session.get(f"{BASE_URL}/api/patients?limit=1")
        assert patients_response.status_code == 200
        patients = patients_response.json()["patients"]
        
        if len(patients) == 0:
            pytest.skip("No patients found")
        
        patient = patients[0]
        patient_id = patient["_id"]
        
        # Update multiple fields
        update_data = {
            "address": "TEST_Updated Address 123",
            "notes": "TEST_Updated notes"
        }
        update_response = self.session.put(f"{BASE_URL}/api/patients/{patient_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Verify
        get_response = self.session.get(f"{BASE_URL}/api/patients/{patient_id}")
        assert get_response.status_code == 200
        updated = get_response.json()
        assert updated["address"] == update_data["address"]
        assert updated["notes"] == update_data["notes"]
        print(f"Multiple fields updated successfully for patient {patient_id}")
    
    # ========== FEATURE 2: Global Search ==========
    def test_global_search_patients(self):
        """Test global search for patients"""
        response = self.session.get(f"{BASE_URL}/api/search?q=Maria")
        assert response.status_code == 200
        results = response.json()
        assert isinstance(results, list)
        
        patient_results = [r for r in results if r["type"] == "patient"]
        print(f"Search 'Maria' returned {len(patient_results)} patient results")
        
        if len(patient_results) > 0:
            result = patient_results[0]
            assert "id" in result
            assert "title" in result
            assert "subtitle" in result
            assert result["type"] == "patient"
            print(f"First patient result: {result['title']} - {result['subtitle']}")
    
    def test_global_search_products(self):
        """Test global search for products"""
        response = self.session.get(f"{BASE_URL}/api/search?q=lente")
        assert response.status_code == 200
        results = response.json()
        
        product_results = [r for r in results if r["type"] == "product"]
        print(f"Search 'lente' returned {len(product_results)} product results")
        
        for result in product_results[:3]:
            print(f"  Product: {result['title']} - {result['subtitle']}")
    
    def test_global_search_consultations(self):
        """Test global search for consultations"""
        response = self.session.get(f"{BASE_URL}/api/search?q=Vision")
        assert response.status_code == 200
        results = response.json()
        
        consultation_results = [r for r in results if r["type"] == "consultation"]
        print(f"Search 'Vision' returned {len(consultation_results)} consultation results")
        
        for result in consultation_results[:3]:
            print(f"  Consultation: {result['title']} - {result['subtitle']}")
    
    def test_global_search_min_length(self):
        """Test that search requires minimum 2 characters"""
        response = self.session.get(f"{BASE_URL}/api/search?q=a")
        # Should return 422 validation error for min_length=2
        assert response.status_code == 422, f"Expected 422 for single char search, got {response.status_code}"
        print("Search correctly requires minimum 2 characters")
    
    def test_global_search_empty_results(self):
        """Test search with no results"""
        response = self.session.get(f"{BASE_URL}/api/search?q=xyznonexistent123")
        assert response.status_code == 200
        results = response.json()
        assert isinstance(results, list)
        assert len(results) == 0
        print("Empty search returns empty list correctly")
    
    # ========== FEATURE 3: Consultation with Prescriptions ==========
    def test_get_consultation_with_prescriptions(self):
        """Test getting a consultation that has linked prescriptions"""
        # First get consultations
        consultations_response = self.session.get(f"{BASE_URL}/api/consultations?limit=10")
        assert consultations_response.status_code == 200
        consultations = consultations_response.json()
        
        if len(consultations) == 0:
            pytest.skip("No consultations found")
        
        # Try to find a consultation with prescriptions
        for con in consultations:
            con_id = con["_id"]
            detail_response = self.session.get(f"{BASE_URL}/api/consultations/{con_id}")
            assert detail_response.status_code == 200
            detail = detail_response.json()
            
            eyeglass_count = len(detail.get("eyeglass_prescriptions", []))
            contact_count = len(detail.get("contact_prescriptions", []))
            medical_count = len(detail.get("medical_prescriptions", []))
            total_rx = eyeglass_count + contact_count + medical_count
            
            if total_rx > 0:
                print(f"Found consultation {con_id} with {total_rx} prescriptions:")
                print(f"  - Eyeglass: {eyeglass_count}")
                print(f"  - Contact: {contact_count}")
                print(f"  - Medical: {medical_count}")
                
                # Verify prescription structure
                if eyeglass_count > 0:
                    rx = detail["eyeglass_prescriptions"][0]
                    assert "_id" in rx
                    assert "created_at" in rx
                    print(f"  Eyeglass Rx ID: {rx['_id']}")
                return
        
        print("No consultations with linked prescriptions found - this is OK if none exist")
    
    def test_consultation_detail_includes_patient_info(self):
        """Test that consultation detail includes patient info"""
        consultations_response = self.session.get(f"{BASE_URL}/api/consultations?limit=1")
        assert consultations_response.status_code == 200
        consultations = consultations_response.json()
        
        if len(consultations) == 0:
            pytest.skip("No consultations found")
        
        con_id = consultations[0]["_id"]
        detail_response = self.session.get(f"{BASE_URL}/api/consultations/{con_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        
        # Should have patient info
        assert "patient_name" in detail or "patient_id" in detail
        print(f"Consultation {con_id} has patient info: {detail.get('patient_name', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
