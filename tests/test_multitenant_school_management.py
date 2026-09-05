import pytest
from app.models.academic import Student, SchoolClass, Subject, TeachingAssignment, TimetableSlot
from app.models.finance import StudentInvoice, PaymentTransaction

def test_tenant_students_list_scoped_to_school(client, school_manager_headers):
    response = client.get("/api/v1/school/students", headers=school_manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    for st in data["items"]:
        assert st["roll_number"].startswith("IL-")

def test_tenant_classes_scoped_to_school(client, school_manager_headers, other_school_manager_headers):
    res1 = client.get("/api/v1/school/classes", headers=school_manager_headers)
    res2 = client.get("/api/v1/school/classes", headers=other_school_manager_headers)
    assert res1.status_code == 200
    assert res2.status_code == 200
    classes1 = res1.json()
    classes2 = res2.json()
    assert len(classes1) > 0
    assert len(classes2) > 0
    ids1 = {c["id"] for c in classes1}
    ids2 = {c["id"] for c in classes2}
    assert ids1.isdisjoint(ids2)

def test_class_creation_duplicate_rejected(client, school_manager_headers):
    response = client.post("/api/v1/school/classes", headers=school_manager_headers, json={
        "class_level": 1,
        "stream": "A"
    })
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_subject_creation_duplicate_rejected(client, school_manager_headers):
    response = client.post("/api/v1/school/subjects", headers=school_manager_headers, json={
        "code": "ENG-01",
        "name": "English Duplicate",
        "level": 1
    })
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_subject_creation_unique_success(client, school_manager_headers):
    response = client.post("/api/v1/school/subjects", headers=school_manager_headers, json={
        "code": "CSC-01",
        "name": "Computer Science 1",
        "level": 1
    })
    assert response.status_code == 201
    assert response.json()["code"] == "CSC-01"

def test_timetable_slot_creation_and_listing(client, school_manager_headers):
    response = client.post("/api/v1/school/timetable", headers=school_manager_headers, json={
        "class_id": 1,
        "subject_id": 1,
        "teacher_id": 4,
        "day_of_week": 1,
        "period": 2,
        "room": "Room 101"
    })
    assert response.status_code == 201
    slot = response.json()
    assert slot["day_of_week"] == 1
    assert slot["period"] == 2

    # Listing
    list_res = client.get("/api/v1/school/timetable?class_id=1", headers=school_manager_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) > 0

def test_tenant_invoice_creation_and_payment_flow(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1).first()

    inv_res = client.post("/api/v1/school/finance/invoices", headers=school_manager_headers, json={
        "student_id": str(student.id),
        "term": "Term 1",
        "amount": 150.0,
        "due_date": "2026-10-30"
    })
    assert inv_res.status_code == 201
    invoice = inv_res.json()
    assert invoice["amount"] == 150.0
    assert invoice["status"] == "pending"

    pay_res1 = client.post(f"/api/v1/school/finance/invoices/{invoice['id']}/payments", headers=school_manager_headers, json={
        "amount": 50.0,
        "payment_method": "Zaad",
        "transaction_reference": "TX-ZAAD-101"
    })
    assert pay_res1.status_code == 201
    inv_check1 = client.get(f"/api/v1/school/finance/invoices/{invoice['id']}", headers=school_manager_headers).json()
    assert inv_check1["status"] == "partially_paid"
    assert inv_check1["paid_amount"] == 50.0

    pay_res2 = client.post(f"/api/v1/school/finance/invoices/{invoice['id']}/payments", headers=school_manager_headers, json={
        "amount": 100.0,
        "payment_method": "Sahal",
        "transaction_reference": "TX-SAHAL-102"
    })
    assert pay_res2.status_code == 201
    inv_check2 = client.get(f"/api/v1/school/finance/invoices/{invoice['id']}", headers=school_manager_headers).json()
    assert inv_check2["status"] == "paid"
    assert inv_check2["paid_amount"] == 150.0

def test_tuition_rate_creation_and_update(client, school_manager_headers):
    response = client.post("/api/v1/school/finance/rates", headers=school_manager_headers, json={
        "class_level": 5,
        "term": "Term 2",
        "amount": 125.0
    })
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 125.0
    assert data["class_level"] == 5

def test_school_profile_update(client, school_manager_headers):
    response = client.put("/api/v1/school/profile?contact_phone=%2B252-63-400-9999", headers=school_manager_headers)
    assert response.status_code == 200
    assert response.json()["contact_phone"] == "+252-63-400-9999"

def test_list_teachers_scoped_to_school(client, school_manager_headers, other_school_manager_headers):
    res1 = client.get("/api/v1/school/teachers", headers=school_manager_headers)
    res2 = client.get("/api/v1/school/teachers", headers=other_school_manager_headers)
    assert res1.status_code == 200
    assert res2.status_code == 200
    t1_ids = {t["id"] for t in res1.json()}
    t2_ids = {t["id"] for t in res2.json()}
    assert t1_ids.isdisjoint(t2_ids)

def test_create_teaching_assignment(client, school_manager_headers):
    response = client.post("/api/v1/school/assignments", headers=school_manager_headers, json={
        "teacher_id": 4,
        "class_id": 2,
        "subject_id": 2
    })
    assert response.status_code == 201
    assert response.json()["teacher_id"] == 4

def test_delete_timetable_slot(client, school_manager_headers, db_session):
    slot = TimetableSlot(
        school_id=1,
        class_id=1,
        subject_id=1,
        teacher_id=4,
        day_of_week=4,
        period=4,
        room="Lab 1"
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)

    del_res = client.delete(f"/api/v1/school/timetable/{slot.id}", headers=school_manager_headers)
    assert del_res.status_code == 200
    assert "removed" in del_res.json()["message"]

def test_class_breakdown_counts(client, school_manager_headers):
    response = client.get("/api/v1/school/classes/1/breakdown", headers=school_manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_students" in data
    assert "male_students" in data
    assert "female_students" in data
    assert "subjects" in data

