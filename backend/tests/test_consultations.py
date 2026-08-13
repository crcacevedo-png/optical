"""
Test suite for Consultations Module - Cortexia Optical
Tests: CRUD operations for consultations, linked prescriptions, patient consultation history
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConsultationsModule:
    """Test consultations CRUD and linked prescriptions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.user = login_response.json()
        
        # Get a patient for testing
        patients_response = self.session.get(f"{BASE_URL}/api/patients", params={"limit": 10})
        assert patients_response.status_code == 200
        patients = patients_response.json().get("patients", [])
        assert len(patients) > 0, "No patients found for testing"
        self.test_patient = patients[0]
        self.test_patient_id = self.test_patient["_id"]
        
        yield
        
        # Cleanup - logout
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    # ===== GET /api/consultations =====
    def test_list_consultations_returns_200(self):
        """GET /api/consultations returns list of consultations"""
        response = self.session.get(f"{BASE_URL}/api/consultations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/consultations returns {len(data)} consultations")
    
    def test_list_consultations_has_required_fields(self):
        """Consultations list items have required fields"""
        response = self.session.get(f"{BASE_URL}/api/consultations")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            consultation = data[0]
            required_fields = ["_id", "patient_id", "consultation_date", "consultation_type", "chief_complaint"]
            for field in required_fields:
                assert field in consultation, f"Missing field: {field}"
            print(f"✓ Consultation has all required fields: {required_fields}")
        else:
            print("⚠ No consultations to verify fields")
    
    # ===== POST /api/consultations =====
    def test_create_consultation_success(self):
        """POST /api/consultations creates consultation with clinical fields"""
        consultation_data = {
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_time": "10:30",
            "consultation_type": "general",
            "chief_complaint": "TEST_Vision borrosa de lejos",
            "anamnesis": "Paciente refiere dificultad para ver de lejos desde hace 2 meses",
            "findings": "AV OD: 20/40, OI: 20/50. Refraccion: OD -1.00, OI -1.25",
            "diagnosis": "TEST_Miopia simple bilateral",
            "treatment_plan": "Prescripcion de lentes correctivos",
            "recommendations": "Control en 6 meses",
            "notes": "Paciente de prueba automatizada"
        }
        
        response = self.session.post(f"{BASE_URL}/api/consultations", json=consultation_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Response should contain _id"
        assert "message" in data, "Response should contain message"
        
        self.created_consultation_id = data["_id"]
        print(f"✓ Created consultation with ID: {self.created_consultation_id}")
        
        # Verify by GET
        get_response = self.session.get(f"{BASE_URL}/api/consultations/{self.created_consultation_id}")
        assert get_response.status_code == 200
        created = get_response.json()
        assert created["chief_complaint"] == consultation_data["chief_complaint"]
        assert created["diagnosis"] == consultation_data["diagnosis"]
        print(f"✓ Verified consultation data persisted correctly")
    
    def test_create_consultation_requires_patient_id(self):
        """POST /api/consultations fails without patient_id"""
        response = self.session.post(f"{BASE_URL}/api/consultations", json={
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "chief_complaint": "Test complaint"
        })
        assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"
        print("✓ Validation error when patient_id missing")
    
    def test_create_consultation_requires_chief_complaint(self):
        """POST /api/consultations fails without chief_complaint"""
        response = self.session.post(f"{BASE_URL}/api/consultations", json={
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d")
        })
        assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"
        print("✓ Validation error when chief_complaint missing")
    
    # ===== GET /api/consultations/{id} =====
    def test_get_consultation_detail_with_linked_prescriptions(self):
        """GET /api/consultations/{id} returns full detail with linked prescriptions"""
        # First create a consultation
        consultation_data = {
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "primera_vez",
            "chief_complaint": "TEST_Revision general",
            "diagnosis": "TEST_Emetropia"
        }
        create_response = self.session.post(f"{BASE_URL}/api/consultations", json=consultation_data)
        assert create_response.status_code == 200
        consultation_id = create_response.json()["_id"]
        
        # Get detail
        response = self.session.get(f"{BASE_URL}/api/consultations/{consultation_id}")
        assert response.status_code == 200
        
        data = response.json()
        # Check patient info is included
        assert "patient_name" in data, "Should include patient_name"
        # Check prescription arrays exist
        assert "eyeglass_prescriptions" in data, "Should include eyeglass_prescriptions array"
        assert "medical_prescriptions" in data, "Should include medical_prescriptions array"
        assert "contact_prescriptions" in data, "Should include contact_prescriptions array"
        
        print(f"✓ GET /api/consultations/{consultation_id} returns full detail")
        print(f"  - Patient: {data.get('patient_name')}")
        print(f"  - Eyeglass Rx: {len(data.get('eyeglass_prescriptions', []))}")
        print(f"  - Medical Rx: {len(data.get('medical_prescriptions', []))}")
    
    def test_get_consultation_not_found(self):
        """GET /api/consultations/{id} returns 404 for invalid ID"""
        response = self.session.get(f"{BASE_URL}/api/consultations/000000000000000000000000")
        assert response.status_code == 404
        print("✓ Returns 404 for non-existent consultation")
    
    # ===== PUT /api/consultations/{id} =====
    def test_update_consultation_clinical_fields(self):
        """PUT /api/consultations/{id} updates clinical fields"""
        # Create consultation
        create_response = self.session.post(f"{BASE_URL}/api/consultations", json={
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "control",
            "chief_complaint": "TEST_Control post operatorio",
            "diagnosis": "TEST_Evolucion favorable"
        })
        assert create_response.status_code == 200
        consultation_id = create_response.json()["_id"]
        
        # Update
        update_data = {
            "diagnosis": "TEST_Evolucion favorable - Alta medica",
            "treatment_plan": "No requiere tratamiento adicional",
            "recommendations": "Control anual"
        }
        update_response = self.session.put(f"{BASE_URL}/api/consultations/{consultation_id}", json=update_data)
        assert update_response.status_code == 200
        
        # Verify update persisted
        get_response = self.session.get(f"{BASE_URL}/api/consultations/{consultation_id}")
        assert get_response.status_code == 200
        updated = get_response.json()
        assert updated["diagnosis"] == update_data["diagnosis"]
        assert updated["treatment_plan"] == update_data["treatment_plan"]
        assert updated["recommendations"] == update_data["recommendations"]
        
        print(f"✓ PUT /api/consultations/{consultation_id} updated clinical fields")
    
    # ===== POST /api/prescriptions/eyeglasses with consultation_id =====
    def test_create_eyeglass_prescription_linked_to_consultation(self):
        """POST /api/prescriptions/eyeglasses with consultation_id links prescription"""
        # Create consultation
        create_response = self.session.post(f"{BASE_URL}/api/consultations", json={
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "general",
            "chief_complaint": "TEST_Necesita lentes nuevos",
            "diagnosis": "TEST_Miopia OD -2.00 OI -1.75"
        })
        assert create_response.status_code == 200
        consultation_id = create_response.json()["_id"]
        
        # Create eyeglass prescription linked to consultation
        rx_data = {
            "patient_id": self.test_patient_id,
            "consultation_id": consultation_id,
            "od_sphere": -2.00,
            "od_cylinder": -0.50,
            "od_axis": 180,
            "oi_sphere": -1.75,
            "oi_cylinder": -0.25,
            "oi_axis": 175,
            "lens_type": "Monofocal",
            "observations": "TEST_Receta generada desde consulta"
        }
        rx_response = self.session.post(f"{BASE_URL}/api/prescriptions/eyeglass", json=rx_data)
        assert rx_response.status_code == 200, f"Expected 200, got {rx_response.status_code}: {rx_response.text}"
        
        rx_id = rx_response.json()["_id"]
        print(f"✓ Created eyeglass prescription {rx_id} linked to consultation {consultation_id}")
        
        # Verify prescription appears in consultation detail
        detail_response = self.session.get(f"{BASE_URL}/api/consultations/{consultation_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        
        eyeglass_rx = detail.get("eyeglass_prescriptions", [])
        assert len(eyeglass_rx) > 0, "Consultation should have linked eyeglass prescription"
        assert any(rx["_id"] == rx_id for rx in eyeglass_rx), "Created prescription should be in list"
        print(f"✓ Eyeglass prescription appears in consultation detail")
    
    # ===== POST /api/prescriptions/medical with consultation_id =====
    def test_create_medical_prescription_linked_to_consultation(self):
        """POST /api/prescriptions/medical with consultation_id links prescription"""
        # Create consultation
        create_response = self.session.post(f"{BASE_URL}/api/consultations", json={
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "urgencia",
            "chief_complaint": "TEST_Ojo rojo y dolor",
            "diagnosis": "TEST_Conjuntivitis bacteriana"
        })
        assert create_response.status_code == 200
        consultation_id = create_response.json()["_id"]
        
        # Create medical prescription linked to consultation
        rx_data = {
            "patient_id": self.test_patient_id,
            "consultation_id": consultation_id,
            "diagnosis": "Conjuntivitis bacteriana",
            "medications": [
                {"name": "Tobramicina 0.3%", "dosage": "1 gota", "frequency": "cada 4 horas", "duration": "7 dias"},
                {"name": "Lagrimas artificiales", "dosage": "1 gota", "frequency": "cada 2 horas", "duration": "14 dias"}
            ],
            "instructions": "TEST_Evitar tocar los ojos. Lavado de manos frecuente."
        }
        rx_response = self.session.post(f"{BASE_URL}/api/prescriptions/medical", json=rx_data)
        assert rx_response.status_code == 200, f"Expected 200, got {rx_response.status_code}: {rx_response.text}"
        
        rx_id = rx_response.json()["_id"]
        print(f"✓ Created medical prescription {rx_id} linked to consultation {consultation_id}")
        
        # Verify prescription appears in consultation detail
        detail_response = self.session.get(f"{BASE_URL}/api/consultations/{consultation_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        
        medical_rx = detail.get("medical_prescriptions", [])
        assert len(medical_rx) > 0, "Consultation should have linked medical prescription"
        assert any(rx["_id"] == rx_id for rx in medical_rx), "Created prescription should be in list"
        print(f"✓ Medical prescription appears in consultation detail")
    
    # ===== GET /api/patients/{id} includes consultations =====
    def test_patient_detail_includes_consultations(self):
        """GET /api/patients/{id} includes consultations array"""
        # Create a consultation for the test patient
        create_response = self.session.post(f"{BASE_URL}/api/consultations", json={
            "patient_id": self.test_patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "seguimiento",
            "chief_complaint": "TEST_Seguimiento de tratamiento",
            "diagnosis": "TEST_Mejoria clinica"
        })
        assert create_response.status_code == 200
        
        # Get patient detail
        response = self.session.get(f"{BASE_URL}/api/patients/{self.test_patient_id}")
        assert response.status_code == 200
        
        patient = response.json()
        assert "consultations" in patient, "Patient detail should include consultations array"
        assert isinstance(patient["consultations"], list), "consultations should be a list"
        
        # Verify our test consultation is in the list
        consultations = patient["consultations"]
        test_consultations = [c for c in consultations if "TEST_" in (c.get("chief_complaint") or "")]
        assert len(test_consultations) > 0, "Patient should have test consultations"
        
        print(f"✓ GET /api/patients/{self.test_patient_id} includes {len(consultations)} consultations")
    
    # ===== Search consultations =====
    def test_list_consultations_filter_by_patient(self):
        """GET /api/consultations?patient_id=X filters by patient"""
        response = self.session.get(f"{BASE_URL}/api/consultations", params={"patient_id": self.test_patient_id})
        assert response.status_code == 200
        
        data = response.json()
        # All returned consultations should be for this patient
        for c in data:
            assert c.get("patient_id") == self.test_patient_id, "All consultations should be for the specified patient"
        
        print(f"✓ Filter by patient_id returns {len(data)} consultations")


class TestConsultationsEdgeCases:
    """Edge cases and error handling for consultations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
        })
        assert login_response.status_code == 200
        
        patients_response = self.session.get(f"{BASE_URL}/api/patients", params={"limit": 1})
        self.test_patient_id = patients_response.json()["patients"][0]["_id"]
        
        yield
        self.session.post(f"{BASE_URL}/api/auth/logout")
    
    def test_consultation_types_accepted(self):
        """All consultation types are accepted"""
        types = ["general", "control", "urgencia", "primera_vez", "seguimiento"]
        
        for ctype in types:
            response = self.session.post(f"{BASE_URL}/api/consultations", json={
                "patient_id": self.test_patient_id,
                "consultation_date": datetime.now().strftime("%Y-%m-%d"),
                "consultation_type": ctype,
                "chief_complaint": f"TEST_Tipo {ctype}"
            })
            assert response.status_code == 200, f"Type '{ctype}' should be accepted, got {response.status_code}"
        
        print(f"✓ All consultation types accepted: {types}")
    
    def test_eyeglass_prescription_without_consultation_id(self):
        """Eyeglass prescription can be created without consultation_id"""
        rx_data = {
            "patient_id": self.test_patient_id,
            "od_sphere": -1.00,
            "oi_sphere": -1.25,
            "observations": "TEST_Receta sin consulta vinculada"
        }
        response = self.session.post(f"{BASE_URL}/api/prescriptions/eyeglass", json=rx_data)
        assert response.status_code == 200, f"Should allow prescription without consultation_id"
        print("✓ Eyeglass prescription created without consultation_id")
    
    def test_medical_prescription_without_consultation_id(self):
        """Medical prescription can be created without consultation_id"""
        rx_data = {
            "patient_id": self.test_patient_id,
            "diagnosis": "TEST_Diagnostico directo",
            "medications": [{"name": "Medicamento test", "dosage": "1 tab", "frequency": "c/8h", "duration": "5 dias"}]
        }
        response = self.session.post(f"{BASE_URL}/api/prescriptions/medical", json=rx_data)
        assert response.status_code == 200, f"Should allow prescription without consultation_id"
        print("✓ Medical prescription created without consultation_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
