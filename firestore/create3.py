import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

doc = {
  "name": "陳素宥3",
  "mail": "s1131234@o365st.pu.edu.tw",
  "lab": 579
}

doc_ref = db.collection("靜宜資管2026a")
doc_ref.add(doc)

