import random, json, hashlib
from sqlalchemy.orm import Session
from . import models, crypto_vault
from datetime import datetime, timedelta

def compile_paper(db: Session, code: str, num_questions: int, key_release_delay_sec: int, compiled_by: int):
    # Get vault questions
    qs = db.query(models.Question).all()
    if len(qs) < num_questions:
        raise ValueError(f"Vault only has {len(qs)} questions, need {num_questions}")
    # Dirichlet-like weighted sampling balancing difficulty
    random.shuffle(qs)
    # Simple stratified pick
    buckets = {1:[],2:[],3:[],4:[],5:[]}
    for q in qs: buckets[q.difficulty].append(q)
    target_dist = [0.15,0.2,0.3,0.2,0.15]
    picked = []
    for diff, frac in enumerate(target_dist, start=1):
        n = int(num_questions * frac)
        picked.extend(random.sample(buckets[diff], min(n, len(buckets[diff]))))
    # fill remainder
    remaining = [q for q in qs if q not in picked]
    while len(picked) < num_questions and remaining:
        picked.append(remaining.pop())
    picked = picked[:num_questions]
    random.shuffle(picked)

    manifest = {}
    for q in picked:
        manifest[q.subject] = manifest.get(q.subject, 0) + 1

    paper_obj = {
        "code": code,
        "questions": [
            {"qid": q.qid, "subject": q.subject, "difficulty": q.difficulty,
             "text": q.text, "options": json.loads(q.options_json), "answer_index": q.answer_index}
            for q in picked
        ]
    }
    paper_hash = hashlib.sha3_256(json.dumps(paper_obj, sort_keys=True).encode()).hexdigest()
    key = crypto_vault.generate_paper_key()
    encrypted_blob = crypto_vault.encrypt_paper(key, paper_obj)

    release_at = datetime.utcnow() + timedelta(seconds=key_release_delay_sec)
    paper = models.ExamPaper(
        code=code,
        manifest_json=json.dumps(manifest),
        paper_hash=paper_hash,
        question_ids_json=json.dumps([q.id for q in picked]),
        encrypted_blob=encrypted_blob,
        key_release_at=release_at,
        encryption_key=key,
        compiled_by=compiled_by
    )
    # upsert
    existing = db.query(models.ExamPaper).filter(models.ExamPaper.code == code).first()
    if existing:
        existing.manifest_json = paper.manifest_json
        existing.paper_hash = paper_hash
        existing.question_ids_json = paper.question_ids_json
        existing.encrypted_blob = encrypted_blob
        existing.key_release_at = release_at
        existing.encryption_key = key
        existing.compiled_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing, encrypted_blob
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper, encrypted_blob
