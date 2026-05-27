from pydantic import BaseModel, EmailStr, model_validator
from typing import List, Optional


def _clean_optical_fields(data):
    """Normalize optical prescription field values. Reduces nesting in model validators."""
    if not isinstance(data, dict):
        return data
    plano_aliases = ('plano', 'pl', 'piano', 'neutro', 'n')
    for k, v in data.items():
        if not isinstance(v, str):
            continue
        stripped = v.strip().lower()
        if stripped == '':
            data[k] = None
        elif stripped in plano_aliases:
            data[k] = 0.0
    return data

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class CompanyCreate(BaseModel):
    name: str
    legal_name: str = ""
    tax_id: str = ""
    address: str = ""
    phone: str
    email: EmailStr
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    admin_name: str
    admin_email: EmailStr
    admin_password: str

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None
    prescription_style: Optional[dict] = None

class BranchCreate(BaseModel):
    name: str
    address: str
    phone: str
    email: Optional[EmailStr] = None

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    dpi: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    phone: str
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "Guatemala"
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    notes: Optional[str] = None
    branch_id: Optional[str] = None

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dpi: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    notes: Optional[str] = None
    branch_id: Optional[str] = None

class AppointmentCreate(BaseModel):
    patient_id: str
    branch_id: Optional[str] = None
    professional_id: Optional[str] = None
    professional_name: Optional[str] = None
    date: str
    time: str
    duration: int = 30
    type: str
    status: Optional[str] = "pendiente"
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    duration: Optional[int] = None
    type: Optional[str] = None
    professional_name: Optional[str] = None
    notes: Optional[str] = None

class EyeglassPrescriptionCreate(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    od_sphere: Optional[float] = None
    od_cylinder: Optional[float] = None
    od_axis: Optional[int] = None
    od_addition: Optional[float] = None
    od_dp: Optional[float] = None
    oi_sphere: Optional[float] = None
    oi_cylinder: Optional[float] = None
    oi_axis: Optional[int] = None
    oi_addition: Optional[float] = None
    oi_dp: Optional[float] = None
    observations: Optional[str] = None
    lens_type: Optional[str] = None
    frame_type: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def clean_optical_values(cls, data):
        return _clean_optical_fields(data)

class MedicalPrescriptionCreate(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    diagnosis: Optional[str] = None
    medications: List[dict]
    instructions: Optional[str] = None

class ContactLensPrescriptionCreate(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    od_power: Optional[float] = None
    od_bc: Optional[float] = None
    od_dia: Optional[float] = None
    od_cylinder: Optional[float] = None
    od_axis: Optional[int] = None
    od_addition: Optional[float] = None
    oi_power: Optional[float] = None
    oi_bc: Optional[float] = None
    oi_dia: Optional[float] = None
    oi_cylinder: Optional[float] = None
    oi_axis: Optional[int] = None
    oi_addition: Optional[float] = None
    brand: Optional[str] = None
    lens_type: Optional[str] = None
    replacement: Optional[str] = None
    observations: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def clean_optical_values(cls, data):
        return _clean_optical_fields(data)

class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    brand: Optional[str] = None
    description: Optional[str] = None
    cost_price: float
    sale_price: float
    min_stock: int = 0
    initial_stock: int = 0
    branch_id: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    cost_price: Optional[float] = None
    sale_price: Optional[float] = None
    min_stock: Optional[int] = None

class InventoryMovement(BaseModel):
    product_id: str
    branch_id: Optional[str] = None
    type: str
    quantity: int
    notes: Optional[str] = None
    reference: Optional[str] = None

class SaleCreate(BaseModel):
    patient_id: Optional[str] = None
    items: List[dict]
    subtotal: float
    discount: float = 0
    tax: float = 0
    total: float
    payment_method: str
    amount_paid: float
    notes: Optional[str] = None

class FinanceEntryCreate(BaseModel):
    type: str
    category: str
    amount: float
    description: str
    date: Optional[str] = None
    reference: Optional[str] = None

class QuotationCreate(BaseModel):
    patient_id: str
    items: List[dict]
    subtotal: float
    discount: float = 0
    discount_type: str = "amount"
    total: float
    notes: Optional[str] = None
    payment_conditions: Optional[str] = None
    validity_days: int = 15

class QuotationStatusUpdate(BaseModel):
    status: str

class ConsultationCreate(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_date: str
    consultation_time: Optional[str] = None
    consultation_type: str = "general"
    chief_complaint: str
    anamnesis: Optional[str] = None
    findings: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    recommendations: Optional[str] = None
    notes: Optional[str] = None
    wears_glasses: Optional[bool] = None
    glasses_since: Optional[str] = None
    glasses_type: Optional[str] = None
    ocular_surgeries: Optional[str] = None
    ocular_trauma: Optional[str] = None
    ocular_diseases: Optional[str] = None
    diabetes: Optional[bool] = None
    hypertension: Optional[bool] = None
    autoimmune_disease: Optional[bool] = None
    autoimmune_details: Optional[str] = None
    current_medications: Optional[str] = None
    allergies: Optional[str] = None
    family_glaucoma: Optional[bool] = None
    family_glaucoma_relationship: Optional[str] = None
    family_macular_degeneration: Optional[bool] = None
    family_macular_relationship: Optional[str] = None
    family_high_myopia: Optional[bool] = None
    family_high_myopia_relationship: Optional[str] = None
    family_other_history: Optional[str] = None
    va_distance_without_rx_od: Optional[str] = None
    va_distance_without_rx_oi: Optional[str] = None
    va_distance_with_rx_od: Optional[str] = None
    va_distance_with_rx_oi: Optional[str] = None
    va_near_without_rx_od: Optional[str] = None
    va_near_without_rx_oi: Optional[str] = None
    va_near_with_rx_od: Optional[str] = None
    va_near_with_rx_oi: Optional[str] = None
    va_pinhole_od: Optional[str] = None
    va_pinhole_oi: Optional[str] = None
    visual_acuity_method: Optional[str] = None

class ConsultationUpdate(BaseModel):
    consultation_type: Optional[str] = None
    chief_complaint: Optional[str] = None
    anamnesis: Optional[str] = None
    findings: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    recommendations: Optional[str] = None
    notes: Optional[str] = None
    wears_glasses: Optional[bool] = None
    glasses_since: Optional[str] = None
    glasses_type: Optional[str] = None
    ocular_surgeries: Optional[str] = None
    ocular_trauma: Optional[str] = None
    ocular_diseases: Optional[str] = None
    diabetes: Optional[bool] = None
    hypertension: Optional[bool] = None
    autoimmune_disease: Optional[bool] = None
    autoimmune_details: Optional[str] = None
    current_medications: Optional[str] = None
    allergies: Optional[str] = None
    family_glaucoma: Optional[bool] = None
    family_glaucoma_relationship: Optional[str] = None
    family_macular_degeneration: Optional[bool] = None
    family_macular_relationship: Optional[str] = None
    family_high_myopia: Optional[bool] = None
    family_high_myopia_relationship: Optional[str] = None
    family_other_history: Optional[str] = None
    va_distance_without_rx_od: Optional[str] = None
    va_distance_without_rx_oi: Optional[str] = None
    va_distance_with_rx_od: Optional[str] = None
    va_distance_with_rx_oi: Optional[str] = None
    va_near_without_rx_od: Optional[str] = None
    va_near_without_rx_oi: Optional[str] = None
    va_near_with_rx_od: Optional[str] = None
    va_near_with_rx_oi: Optional[str] = None
    va_pinhole_od: Optional[str] = None
    va_pinhole_oi: Optional[str] = None
    visual_acuity_method: Optional[str] = None

class SupplierCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "Guatemala"
    tax_id: Optional[str] = None
    categories: Optional[List[str]] = []
    notes: Optional[str] = None

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    categories: Optional[List[str]] = None
    notes: Optional[str] = None

class PlanCreate(BaseModel):
    name: str
    price: float = 0
    max_branches: int = 1
    max_patients: int = 50
    modules: List[str] = []
    is_active: bool = True

class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    max_branches: Optional[int] = None
    max_patients: Optional[int] = None
    modules: Optional[List[str]] = None
    is_active: Optional[bool] = None

class AnnouncementCreate(BaseModel):
    title: str
    message: str
    type: str = "info"
    target_plans: Optional[List[str]] = []
    target_cities: Optional[List[str]] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    target_plans: Optional[List[str]] = None
    target_cities: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: Optional[bool] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    branch_id: Optional[str] = None
