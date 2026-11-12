"""批次与填报时间配置（FR-M10-01）。

- ``GET /api/batches``：登录即可读（批次下拉、填报时间展示）；
- ``PUT /api/ops/batches``：仅管理员（``require_admin`` / ADMIN_EMAILS 白名单），
  更新后写审计 ``batch.update``（detail 记录实际变更的批次名），与配置更新同一事务提交。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import current_user, require_admin
from app.models.entities import User
from app.services import audit
from app.services import batches as batch_service

router = APIRouter(tags=['批次与填报时间'])


class BatchItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    active: bool = True
    sort_order: int = 0
    fill_start: str | None = None
    fill_end: str | None = None
    note: str | None = None


class BatchesIn(BaseModel):
    batches: list[BatchItemIn] = Field(min_length=1, max_length=20)


@router.get('/batches')
def get_batches(active_only: bool = Query(False), user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    return {'items': batch_service.list_batches(db, active_only=active_only), 'note': batch_service.NOTE}


@router.put('/ops/batches')
def update_batches(body: BatchesIn, request: Request, admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    before = batch_service.snapshot(db)
    try:
        items = batch_service.save_batches(db, body.model_dump())
    except batch_service.BatchValidationError as error:
        db.rollback()
        raise HTTPException(400, str(error)) from None
    changed = batch_service.changed_names(before, items)
    audit.log_action(db, admin, 'batch.update', target='batch_configs',
                     detail={'changed': changed}, request=request)
    db.commit()
    return {'items': batch_service.list_batches(db), 'note': batch_service.NOTE}
