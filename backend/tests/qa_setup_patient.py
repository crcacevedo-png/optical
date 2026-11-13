import os, requests, json, random
API = os.environ["API"]
s = requests.Session()
r = s.post(f"{API}/api/auth/login", json={"email": "admin@cortexia.gt", "password": "DemoAdmin2026!"})
assert r.status_code == 200, r.text
H = {"X-CSRF-Token": s.cookies.get("csrf_token") or "", "Origin": API}
n = random.randint(1000, 9999)
if not os.environ.get("APPT"):
  r = s.post(f"{API}/api/patients", headers=H, json={"first_name": "QA_Exam", "last_name": f"Paciente{n}", "name": f"QA_Exam Paciente{n}", "phone": "55551234"})
  print(r.status_code, r.text[:400])

if os.environ.get("APPT"):
    r = s.post(f"{API}/api/appointments", headers=H, json={"patient_id": os.environ["APPT"], "date": "2026-11-13", "time": "10:00", "duration": 30, "type": "control", "notes": "QA_ cita examen"})
    print("appt", r.status_code, r.text[:300])
