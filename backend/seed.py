from app.database import SessionLocal, Base, engine
from app import models, auth
import json, random
Base.metadata.create_all(bind=engine)
db = SessionLocal()

def get_or_create(email, password, role, full_name, a11y="standard"):
    u = db.query(models.User).filter(models.User.email==email).first()
    if u: return u
    u = models.User(email=email, password_hash=auth.get_password_hash(password), role=role, full_name=full_name, a11y_profile=a11y)
    db.add(u); db.commit(); db.refresh(u)
    print(f"Created {role}: {email} / {password}")
    return u

admin = get_or_create("admin@zt.local", "admin123", "admin", "ZT Admin")
teacher = get_or_create("teacher@zt.local", "teacher123", "teacher", "Dr. Meera Rao")
student = get_or_create("student@zt.local", "student123", "student", "Aarav S.", "standard")

# seed questions if empty
count = db.query(models.Question).count()
if count < 60:
    print(f"Seeding questions, current {count} ...")
    from app import crypto_vault
    last = db.query(models.CustodyLedger).order_by(models.CustodyLedger.id.desc()).first()
    prev_tx = last.tx_hash if last else "0xgenesis"
    samples = [
      ("Calculus",5,"Evaluate ∫₀^π x sin x / (1+cos²x) dx",["π²/4","π²/8","π/2","π"],0),
      ("Algebra",4,"If det(A)=3 for a 3×3 real matrix, det(adj(adj A)) = ?",["27","81","243","729"],2),
      ("Physics-Mechanics",2,"A projectile at 49 m/s, 30°. Max height?",["30.6 m","61.2 m","15.3 m","122 m"],0),
      ("Organic Chem",3,"Which is aromatic and follows Hückel 4n+2?",["Cyclooctatetraene","Cyclopentadienyl anion","Cyclobutadiene","Cycloheptatriene"],1),
      ("Statistics",3,"E[T] for Geometric(p), support 1,2,…",["1/p","(1-p)/p","p","1/(1-p)"],0),
      ("Calculus",1,"The limit limₙ (1+1/n)ⁿ = ?",["0","1","e","∞"],2),
      ("EM Theory",2,"∮ B·dl = μ₀ (I + ε₀ dΦE/dt). This is:",["Faraday","Ampère-Maxwell","Gauss","Biot-Savart"],1),
      ("Statistics",1,"Median of [3,7,7,19,21,34,52] ?",["7","19","21","17"],1),
      ("Algebra",2,"Solve: 2x² - 5x + 2 = 0",["2, 0.5","1,2","-2,-0.5","3,-1"],0),
      ("Inorganic",1,"pH of 0.01 M HCl ?",["1","2","3","12"],1),
    ]
    # expand to ~120
    subs = ["Calculus","Algebra","Physics-Mechanics","EM Theory","Organic Chem","Inorganic","Biology","Logical Reasoning","Statistics","Geometry","Thermodynamics","Probability"]
    qid_n = count+1
    while qid_n <= 120:
        s, d, t, opts, ans = random.choice(samples)
        subj = random.choice(subs)
        text = t + f"  (v{qid_n})"
        content = text + "".join(opts)
        cid = crypto_vault.mock_ipfs_cid(content)
        tx = crypto_vault.custody_tx(prev_tx, "SUBMIT", cid)
        prev_tx = tx
        q = models.Question(
            qid=f"Q-{qid_n:04d}",
            subject=subj,
            difficulty=d,
            text=text,
            options_json=json.dumps(opts),
            answer_index=ans,
            author_id=teacher.id,
            ipfs_cid=cid,
            custody_tx=tx
        )
        db.add(q)
        db.add(models.CustodyLedger(tx_hash=tx, action="SUBMIT", details=f"Q-{qid_n:04d}"))
        qid_n += 1
    db.commit()
    print("Seeded questions to 120")
else:
    print(f"Questions already present: {count}")

db.close()
print("\nSeed complete.")
print("Login accounts:")
print(" admin   admin@zt.local / admin123")
print(" teacher teacher@zt.local / teacher123")
print(" student student@zt.local / student123")
