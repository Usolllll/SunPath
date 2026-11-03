"""Generate a local demo .env once, without printing secrets or replacing existing settings."""
from pathlib import Path
import secrets

target = Path(__file__).resolve().parents[1] / '.env'
if target.exists():
    print('backend/.env already exists; preserved.')
else:
    target.write_text('DATABASE_URL=sqlite:///sunpath.db\nJWT_SECRET=' + secrets.token_urlsafe(48) + '\nJWT_EXPIRE_MINUTES=1440\nCORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]\nDEMO_EMAIL=demo@sunpath.cn\nDEMO_PASSWORD=Sunpath2026!\n', encoding='utf-8')
    print('Created backend/.env for local SQLite demo. For MySQL, use .env.example.')
