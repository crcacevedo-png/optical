import os, sys, requests

API = os.environ.get("API", "http://localhost:8001")
s = requests.Session()
r = s.post(f"{API}/api/auth/login", json={"email": "admin@cortexia.gt", "password": "DemoAdmin2026!"})
assert r.status_code == 200, r.text
csrf = s.cookies.get("csrf_token")
H = {"X-CSRF-Token": csrf} if csrf else {}
H["Origin"] = API


def call(method, path, **kw):
    r = s.request(method, f"{API}{path}", headers=H, **kw)
    return r


def ok(r, code=200, label=""):
    flag = "PASS" if r.status_code == code else "FAIL"
    print(f"{flag} {label} -> {r.status_code} {'' if flag == 'PASS' else r.text[:300]}")
    return r


pats = call("GET", "/api/patients", params={"limit": 5}).json()["patients"]
pid = pats[0]["_id"]
c = ok(call("POST", "/api/consultations", json={"patient_id": pid, "consultation_date": "2026-11-12",
                                                 "consultation_type": "control", "chief_complaint": "QA_FLOW vision borrosa",
                                                 "evaluation": {"symptoms": "cefalea", "iop": {"status": "realizado", "od": "15", "os": "16"}, "bogus": 1}}), 200, "create exam").json()
eid = c["_id"]
print("exam_code", c.get("exam_code"))
ws = ok(call("GET", f"/api/clinical/exams/{eid}/workspace"), 200, "workspace").json()
print("eval keys", sorted((ws.get("evaluation") or {}).keys()), "perm", ws["permissions"])
# FR bad axis
ok(call("PUT", f"/api/clinical/exams/{eid}/final-refraction", json={"od": {"sphere": "-2.00", "cyl": "-0.75", "axis": "200"}}), 400, "FR axis invalid")
ok(call("PUT", f"/api/clinical/exams/{eid}/final-refraction", json={"od": {"sphere": "-2.00", "cyl": "-0.75", "axis": ""}, "os": {"sphere": "plano"}}), 200, "FR save draft")
ok(call("POST", f"/api/clinical/exams/{eid}/final-refraction/validate"), 400, "FR validate requires axis")
ok(call("PUT", f"/api/clinical/exams/{eid}/final-refraction", json={"od": {"sphere": "-2.00", "cyl": "-0.75", "axis": "180", "add": "+1.50", "va": "20/20"}, "os": {"sphere": "-1.50", "cyl": "-0.50", "axis": "170", "add": "+1.50"}, "working_distance": "40"}), 200, "FR save")
fr = ok(call("POST", f"/api/clinical/exams/{eid}/final-refraction/validate"), 200, "FR validate").json()["final_refraction"]
print("FR", fr["status"], fr["version"])
# eyeglass draft
d = ok(call("POST", "/api/clinical/prescriptions", json={"kind": "eyeglass", "patient_id": pid, "consultation_id": eid, "fr_version": 1,
       "fields": {"name": "Anteojos para lejos", "usage": "Lejos", "od_sphere": "-2.00", "od_cylinder": "-0.75", "od_axis": "180",
                  "oi_sphere": "-1.50", "oi_cylinder": "-0.50", "oi_axis": "170", "od_dp": "31", "oi_dp": "31", "indications": "Uso permanente", "control": "12 meses"}}), 200, "rx draft").json()
rid = d["_id"]
print("code", d["code"], d["status"])
ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{rid}/issue", json={"confirm_reviewed": False}), 400, "issue needs confirm")
ok(call("POST", "/api/prescriptions/eyeglass/" + rid + "/share-link"), 400, "share draft blocked")
ok(call("POST", "/api/clinical/prescriptions/print", json={"items": [{"kind": "eyeglass", "id": rid}]}), 400, "print draft blocked")
pr = ok(call("POST", "/api/clinical/prescriptions/print", json={"items": [{"kind": "eyeglass", "id": rid}], "internal_review": True}), 200, "print draft internal")
print("pdf", pr.content[:4])
iss = ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{rid}/issue", json={"confirm_reviewed": True}), 200, "issue").json()
print("issued", iss["status"], iss["snapshot"]["fr_version"], iss["snapshot"]["patient_name"])
ok(call("PUT", f"/api/clinical/prescriptions/eyeglass/{rid}", json={"fields": {"od_sphere": "-3"}}), 409, "edit issued blocked")
nv = ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{rid}/new-version"), 200, "new version").json()
print("nv", nv["version"], nv["code"] == iss["code"], nv["status"])
ok(call("PUT", f"/api/clinical/prescriptions/eyeglass/{nv['_id']}", json={"fields": {"od_sphere": "-2.25"}}), 200, "edit nv")
# FR revision keeps issued intact
ok(call("PUT", f"/api/clinical/exams/{eid}/final-refraction", json={"od": {"sphere": "-2.25", "cyl": "-0.75", "axis": "180"}, "os": {"sphere": "-1.50"}}), 200, "FR revise")
ws2 = call("GET", f"/api/clinical/exams/{eid}/workspace").json()
print("FR v", ws2["final_refraction"]["version"], ws2["final_refraction"]["status"], "hist", len(ws2.get("final_refraction_history") or []))
ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{nv['_id']}/issue", json={"confirm_reviewed": True}), 200, "issue nv (from v1 validated)")
lst = ok(call("GET", "/api/clinical/prescriptions", params={"patient_id": pid, "consultation_id": eid}), 200, "list").json()
print([(i["code_display"], i["version"], i["status"], i["from_previous_fr"]) for i in lst["items"]])
dup = ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{rid}/duplicate"), 200, "duplicate").json()
print("dup", dup["code"] != iss["code"], dup["status"], dup.get("name"))
ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{dup['_id']}/void", json={"reason": "x"}), 400, "void short reason")
ok(call("POST", f"/api/clinical/prescriptions/eyeglass/{dup['_id']}/void", json={"reason": "Creada por error"}), 200, "void")
# contact: without adaptation -> issue blocked
cd = ok(call("POST", "/api/clinical/prescriptions", json={"kind": "contact", "patient_id": pid, "consultation_id": eid,
        "fields": {"name": "LC mensual", "od_power": "-2.00", "od_bc": "8.6", "od_dia": "14.2", "design": "esferico"}}), 200, "contact draft").json()
ok(call("POST", f"/api/clinical/prescriptions/contact/{cd['_id']}/issue", json={"confirm_reviewed": True}), 400, "contact issue needs adaptation")
ad = ok(call("POST", "/api/clinical/adaptations", json={"patient_id": pid, "consultation_id": eid, "kind": "contacto",
        "trials": [{"eye": "od", "visit_label": "Consulta 1", "lens": {"power": "-2.00", "bc": "8.6"}, "fit": {"centration": "centrado"}}]}), 200, "adaptation create").json()
ok(call("POST", f"/api/clinical/adaptations/{ad['_id']}/accept"), 400, "accept needs params")
ok(call("PUT", f"/api/clinical/adaptations/{ad['_id']}", json={"decision": "Lente aceptado", "accepted_params": {"od": {"power": "-2.00", "bc": "8.6", "dia": "14.2"}}}), 200, "adaptation update")
ok(call("POST", f"/api/clinical/adaptations/{ad['_id']}/accept"), 200, "accept")
ok(call("PUT", f"/api/clinical/prescriptions/contact/{cd['_id']}", json={"adaptation_id": ad["_id"], "fields": {}}), 200, "link adaptation")
ok(call("POST", f"/api/clinical/prescriptions/contact/{cd['_id']}/issue", json={"confirm_reviewed": True}), 200, "contact issue")
# scleral missing sag
sd = ok(call("POST", "/api/clinical/prescriptions", json={"kind": "scleral", "patient_id": pid, "consultation_id": eid,
        "fields": {"name": "Escleral OD", "od_power": "-4.00", "od_dia": "16.0", "lab": "Lab X", "od_haptic_sup": "estandar"}}), 200, "scleral draft").json()
pdf = ok(call("POST", "/api/clinical/prescriptions/print", json={"items": [{"kind": "eyeglass", "id": rid, "copies": 1}, {"kind": "eyeglass", "id": nv["_id"], "copies": 2}, {"kind": "contact", "id": cd["_id"]}]}), 400, "print sustituida blocked")
pdf = ok(call("POST", "/api/clinical/prescriptions/print", json={"items": [{"kind": "eyeglass", "id": nv["_id"], "copies": 2}, {"kind": "contact", "id": cd["_id"]}]}), 200, "joint print")
open("/tmp/joint.pdf", "wb").write(pdf.content)
ok(call("GET", f"/api/prescriptions/scleral/{sd['_id']}/pdf"), 200, "scleral draft pdf")
ok(call("GET", f"/api/prescriptions/eyeglass/{nv['_id']}/pdf", params={"copies": 3}), 200, "single pdf copies")
ok(call("POST", f"/api/clinical/exams/{eid}/sign"), 400, "sign blocked FR draft")
ok(call("POST", f"/api/clinical/exams/{eid}/final-refraction/discard-revision"), 200, "discard revision")
ok(call("POST", f"/api/clinical/exams/{eid}/sign"), 200, "sign")
ok(call("PUT", f"/api/consultations/{eid}", json={"diagnosis": "x"}), 409, "edit signed blocked")
ok(call("POST", f"/api/clinical/exams/{eid}/reopen", json={"reason": "Corregir diagnostico"}), 200, "reopen")
print("EXAM", eid, "PATIENT", pid)
