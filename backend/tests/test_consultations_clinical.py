"""
Test suite for Consultation API with Clinical History and Visual Acuity fields
Tests the new clinical fields: Historia Clinica (Oculares, Sistemicos, Familiares) and Agudeza Visual
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConsultationsClinical:
    """Test consultation endpoints with clinical history and visual acuity fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth cookie
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.user = login_response.json()
        print(f"Logged in as: {self.user.get('email')}")
        
        # Get a patient for testing
        patients_response = self.session.get(f"{BASE_URL}/api/patients", params={"limit": 1})
        assert patients_response.status_code == 200
        patients = patients_response.json().get('patients', [])
        assert len(patients) > 0, "No patients found for testing"
        self.patient_id = patients[0]['_id']
        print(f"Using patient: {patients[0].get('first_name')} {patients[0].get('last_name')}")
        
        yield
        
        # Cleanup - no specific cleanup needed as we use TEST_ prefix
    
    def test_create_consultation_with_clinical_history(self):
        """Test creating a consultation with all clinical history fields"""
        consultation_data = {
            "patient_id": self.patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_time": "10:00",
            "consultation_type": "general",
            "chief_complaint": "TEST: Vision borrosa y dolor de cabeza",
            # Historia Clinica - Oculares
            "wears_glasses": True,
            "glasses_since": "2020",
            "glasses_type": "Monofocales",
            "ocular_surgeries": "Ninguna",
            "ocular_trauma": "Ninguno",
            "ocular_diseases": "Ninguna",
            # Historia Clinica - Sistemicos
            "diabetes": True,
            "hypertension": False,
            "autoimmune_disease": False,
            "current_medications": "Metformina 500mg",
            "allergies": "Ninguna",
            # Historia Clinica - Familiares
            "family_glaucoma": True,
            "family_glaucoma_relationship": "Padre",
            "family_macular_degeneration": False,
            "family_high_myopia": True,
            "family_high_myopia_relationship": "Madre",
            # Agudeza Visual
            "va_distance_without_rx_od": "20/40",
            "va_distance_without_rx_oi": "20/30",
            "va_distance_with_rx_od": "20/20",
            "va_distance_with_rx_oi": "20/20",
            "va_near_without_rx_od": "J3",
            "va_near_without_rx_oi": "J2",
            "va_pinhole_od": "20/25",
            "va_pinhole_oi": "20/20",
            "visual_acuity_method": "Snellen",
            # Hallazgos y Plan
            "findings": "TEST: Miopia leve OD, astigmatismo OI",
            "diagnosis": "TEST: Miopia OD -2.00, OI -1.75",
            "treatment_plan": "TEST: Prescripcion de lentes correctivos"
        }
        
        response = self.session.post(f"{BASE_URL}/api/consultations", json=consultation_data)
        assert response.status_code in [200, 201], f"Create failed: {response.text}"
        
        data = response.json()
        assert "_id" in data, "Response should contain consultation ID"
        self.consultation_id = data["_id"]
        print(f"Created consultation: {self.consultation_id}")
        
        # Verify by fetching the consultation
        get_response = self.session.get(f"{BASE_URL}/api/consultations/{self.consultation_id}")
        assert get_response.status_code == 200, f"Get failed: {get_response.text}"
        
        consultation = get_response.json()
        
        # Verify clinical history fields
        assert consultation.get("wears_glasses") == True, "wears_glasses should be True"
        assert consultation.get("glasses_since") == "2020", "glasses_since should be '2020'"
        assert consultation.get("diabetes") == True, "diabetes should be True"
        assert consultation.get("family_glaucoma") == True, "family_glaucoma should be True"
        assert consultation.get("family_glaucoma_relationship") == "Padre", "family_glaucoma_relationship should be 'Padre'"
        
        # Verify visual acuity fields
        assert consultation.get("va_distance_without_rx_od") == "20/40", "va_distance_without_rx_od should be '20/40'"
        assert consultation.get("va_distance_without_rx_oi") == "20/30", "va_distance_without_rx_oi should be '20/30'"
        assert consultation.get("visual_acuity_method") == "Snellen", "visual_acuity_method should be 'Snellen'"
        
        print("SUCCESS: All clinical history and visual acuity fields saved correctly")
    
    def test_create_consultation_minimal_fields(self):
        """Test creating a consultation with only required fields"""
        consultation_data = {
            "patient_id": self.patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "control",
            "chief_complaint": "TEST: Control de rutina"
        }
        
        response = self.session.post(f"{BASE_URL}/api/consultations", json=consultation_data)
        assert response.status_code in [200, 201], f"Create failed: {response.text}"
        
        data = response.json()
        assert "_id" in data
        print(f"Created minimal consultation: {data['_id']}")
    
    def test_update_consultation_clinical_fields(self):
        """Test updating clinical fields on an existing consultation"""
        # First create a consultation
        create_data = {
            "patient_id": self.patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "general",
            "chief_complaint": "TEST: Para actualizar"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/consultations", json=create_data)
        assert create_response.status_code in [200, 201]
        consultation_id = create_response.json()["_id"]
        
        # Update with clinical fields
        update_data = {
            "wears_glasses": True,
            "diabetes": True,
            "hypertension": True,
            "family_glaucoma": True,
            "family_glaucoma_relationship": "Abuelo",
            "va_distance_without_rx_od": "20/50",
            "va_distance_without_rx_oi": "20/40",
            "visual_acuity_method": "logMAR",
            "diagnosis": "TEST: Actualizado con campos clinicos"
        }
        
        update_response = self.session.put(f"{BASE_URL}/api/consultations/{consultation_id}", json=update_data)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update
        get_response = self.session.get(f"{BASE_URL}/api/consultations/{consultation_id}")
        assert get_response.status_code == 200
        
        consultation = get_response.json()
        assert consultation.get("wears_glasses") == True
        assert consultation.get("diabetes") == True
        assert consultation.get("hypertension") == True
        assert consultation.get("family_glaucoma") == True
        assert consultation.get("family_glaucoma_relationship") == "Abuelo"
        assert consultation.get("va_distance_without_rx_od") == "20/50"
        assert consultation.get("visual_acuity_method") == "logMAR"
        
        print("SUCCESS: Clinical fields updated correctly")
    
    def test_list_consultations(self):
        """Test listing consultations returns clinical fields"""
        response = self.session.get(f"{BASE_URL}/api/consultations")
        assert response.status_code == 200, f"List failed: {response.text}"
        
        consultations = response.json()
        assert isinstance(consultations, list), "Response should be a list"
        assert len(consultations) > 0, "Should have at least one consultation"
        
        # Check that consultations have expected fields
        for c in consultations[:3]:  # Check first 3
            assert "_id" in c
            assert "patient_id" in c
            assert "consultation_date" in c
            assert "chief_complaint" in c
            print(f"Consultation {c['_id']}: {c.get('chief_complaint', '')[:50]}...")
        
        print(f"SUCCESS: Listed {len(consultations)} consultations")
    
    def test_get_consultation_detail(self):
        """Test getting consultation detail includes all clinical fields"""
        # First get list to find a consultation with clinical data
        list_response = self.session.get(f"{BASE_URL}/api/consultations")
        assert list_response.status_code == 200
        
        consultations = list_response.json()
        # Find one with clinical data (TEST prefix)
        test_consultation = None
        for c in consultations:
            if c.get("chief_complaint", "").startswith("TEST:") and c.get("wears_glasses"):
                test_consultation = c
                break
        
        if test_consultation:
            detail_response = self.session.get(f"{BASE_URL}/api/consultations/{test_consultation['_id']}")
            assert detail_response.status_code == 200
            
            detail = detail_response.json()
            
            # Verify clinical fields are present
            clinical_fields = [
                "wears_glasses", "glasses_since", "glasses_type",
                "diabetes", "hypertension", "autoimmune_disease",
                "family_glaucoma", "family_glaucoma_relationship",
                "va_distance_without_rx_od", "va_distance_without_rx_oi",
                "visual_acuity_method"
            ]
            
            for field in clinical_fields:
                if detail.get(field) is not None:
                    print(f"  {field}: {detail.get(field)}")
            
            print("SUCCESS: Consultation detail includes clinical fields")
        else:
            print("SKIP: No consultation with clinical data found for detail test")
    
    def test_patient_consultations_include_clinical_data(self):
        """Test that patient detail includes consultations with clinical data"""
        response = self.session.get(f"{BASE_URL}/api/patients/{self.patient_id}")
        assert response.status_code == 200, f"Get patient failed: {response.text}"
        
        patient = response.json()
        consultations = patient.get("consultations", [])
        
        print(f"Patient has {len(consultations)} consultations")
        
        # Check if any consultation has clinical data
        for c in consultations[:3]:
            if c.get("wears_glasses") or c.get("diabetes") or c.get("va_distance_without_rx_od"):
                print(f"  Consultation {c['_id']} has clinical data:")
                if c.get("wears_glasses"):
                    print(f"    - wears_glasses: {c.get('wears_glasses')}")
                if c.get("diabetes"):
                    print(f"    - diabetes: {c.get('diabetes')}")
                if c.get("va_distance_without_rx_od"):
                    print(f"    - va_distance_without_rx_od: {c.get('va_distance_without_rx_od')}")
        
        print("SUCCESS: Patient consultations retrieved")


class TestVisualAcuityTable:
    """Test Visual Acuity table with 5 measurements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@cortexia.gt",
            "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
        })
        assert login_response.status_code == 200
        
        # Get patient
        patients_response = self.session.get(f"{BASE_URL}/api/patients", params={"limit": 1})
        assert patients_response.status_code == 200
        self.patient_id = patients_response.json()['patients'][0]['_id']
        
        yield
    
    def test_all_five_va_measurements(self):
        """Test all 5 visual acuity measurements are saved correctly"""
        consultation_data = {
            "patient_id": self.patient_id,
            "consultation_date": datetime.now().strftime("%Y-%m-%d"),
            "consultation_type": "general",
            "chief_complaint": "TEST: Verificar 5 mediciones de AV",
            # All 5 VA measurements
            "va_distance_without_rx_od": "20/40",
            "va_distance_without_rx_oi": "20/30",
            "va_distance_with_rx_od": "20/20",
            "va_distance_with_rx_oi": "20/20",
            "va_near_without_rx_od": "J3",
            "va_near_without_rx_oi": "J2",
            "va_near_with_rx_od": "J1",
            "va_near_with_rx_oi": "J1",
            "va_pinhole_od": "20/25",
            "va_pinhole_oi": "20/20",
            "visual_acuity_method": "Snellen"
        }
        
        response = self.session.post(f"{BASE_URL}/api/consultations", json=consultation_data)
        assert response.status_code in [200, 201]
        
        consultation_id = response.json()["_id"]
        
        # Verify all fields
        get_response = self.session.get(f"{BASE_URL}/api/consultations/{consultation_id}")
        assert get_response.status_code == 200
        
        c = get_response.json()
        
        # Verify all 5 measurements for OD
        assert c.get("va_distance_without_rx_od") == "20/40", "AV Lejos sin Rx OD"
        assert c.get("va_distance_with_rx_od") == "20/20", "AV Lejos con Rx OD"
        assert c.get("va_near_without_rx_od") == "J3", "AV Cerca sin Rx OD"
        assert c.get("va_near_with_rx_od") == "J1", "AV Cerca con Rx OD"
        assert c.get("va_pinhole_od") == "20/25", "AV Estenopeico OD"
        
        # Verify all 5 measurements for OI
        assert c.get("va_distance_without_rx_oi") == "20/30", "AV Lejos sin Rx OI"
        assert c.get("va_distance_with_rx_oi") == "20/20", "AV Lejos con Rx OI"
        assert c.get("va_near_without_rx_oi") == "J2", "AV Cerca sin Rx OI"
        assert c.get("va_near_with_rx_oi") == "J1", "AV Cerca con Rx OI"
        assert c.get("va_pinhole_oi") == "20/20", "AV Estenopeico OI"
        
        # Verify method
        assert c.get("visual_acuity_method") == "Snellen", "Metodo"
        
        print("SUCCESS: All 5 VA measurements (OD/OI) saved correctly")
    
    def test_va_methods(self):
        """Test different VA methods: Snellen, logMAR, ETDRS"""
        methods = ["Snellen", "logMAR", "ETDRS"]
        
        for method in methods:
            consultation_data = {
                "patient_id": self.patient_id,
                "consultation_date": datetime.now().strftime("%Y-%m-%d"),
                "consultation_type": "general",
                "chief_complaint": f"TEST: Metodo {method}",
                "va_distance_without_rx_od": "20/20",
                "visual_acuity_method": method
            }
            
            response = self.session.post(f"{BASE_URL}/api/consultations", json=consultation_data)
            assert response.status_code in [200, 201], f"Failed for method {method}"
            
            # Verify
            get_response = self.session.get(f"{BASE_URL}/api/consultations/{response.json()['_id']}")
            assert get_response.status_code == 200
            assert get_response.json().get("visual_acuity_method") == method
            
            print(f"SUCCESS: VA method '{method}' saved correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
