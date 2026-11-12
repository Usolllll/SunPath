"""志愿表 CSV 导入（FR-M6-04）：解析、逐行校验、生成草案方案与校验报告。

设计边界：
- 只接受结构化 CSV（院校名称、专业组名称、梯度），不解析自由文本；
- 每行独立校验，可部分成功：合法行进入草案方案，非法行逐行给出原因；
- 专业组必须属于当前画像的推荐候选池（与手动保存方案同一套校验，避免“导入绕过限制”）；
- 不做任何录取概率推断，梯度仅为用户标注（冲/稳/保）。
"""
import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MajorGroup
from app.utils.export import safe_cell

HEADER = ['序号', '院校名称', '专业组名称', '梯度', '备注']
MAX_ROWS = 120
MAX_CONTENT = 200_000
RISK_LABELS = {'冲': 'reach', '稳': 'steady', '保': 'safe', 'reach': 'reach', 'steady': 'steady', 'safe': 'safe'}


def template_csv() -> str:
    rows = [
        HEADER,
        ['1', '浙江大学', '工科试验班（信息）', '冲', '示例行，导入前请替换'],
        ['2', '南京大学', '理科试验班类', '稳', ''],
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return buffer.getvalue()


def read_rows(content: str) -> list[dict]:
    """解析 CSV 文本为行字典；自动跳过空行，兼容 BOM 与全角空格。"""
    text = (content or '').lstrip('\ufeff')
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    header = [cell.strip() for cell in rows[0]]
    index = {name: header.index(name) for name in HEADER if name in header}
    missing = [name for name in ('院校名称',) if name not in index]
    if missing:
        raise ValueError('CSV 缺少表头：' + '、'.join(missing) + '（请使用导入模板）')
    parsed = []
    for line_no, cells in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in cells):
            continue
        def cell(name):
            position = index.get(name)
            return cells[position].strip() if position is not None and position < len(cells) else ''
        parsed.append({
            'line': line_no,
            'school': cell('院校名称'),
            'group': cell('专业组名称'),
            'risk_label': cell('梯度'),
            'note': cell('备注'),
        })
    return parsed


def _groups_by_school(db: Session) -> dict[str, list[MajorGroup]]:
    catalog: dict[str, list[MajorGroup]] = {}
    for group in db.scalars(select(MajorGroup)).all():
        catalog.setdefault(group.university.name.strip(), []).append(group)
    return catalog


def validate(db: Session, rows: list[dict], allowed_ids: set[int]) -> tuple[list[dict], list[dict]]:
    """返回 (合法行, 错误行)；合法行带 group_id 与 risk。"""
    catalog = _groups_by_school(db)
    accepted, errors, seen = [], [], set()
    for row in rows:
        school = row['school']
        if not school:
            errors.append({**row, 'reason': '院校名称为空'})
            continue
        candidates = catalog.get(school, [])
        if not candidates:
            errors.append({**row, 'reason': '未收录该院校，请核对名称或先加入收藏'})
            continue
        group_name = row['group']
        if group_name:
            matches = [group for group in candidates if group.name.strip() == group_name]
            if not matches:
                errors.append({**row, 'reason': f'该院校下没有专业组「{group_name}」'})
                continue
            group = matches[0]
        elif len(candidates) == 1:
            group = candidates[0]
        else:
            options = '、'.join(group.name for group in candidates[:3])
            errors.append({**row, 'reason': f'该院校有多个专业组，请填写专业组名称（如：{options}）'})
            continue
        if group.id in seen:
            errors.append({**row, 'reason': '同一专业组在表格中重复出现'})
            continue
        if group.id not in allowed_ids:
            errors.append({**row, 'reason': '该专业组不在当前画像的可选范围内（选科/位次/招生要求或预算不满足）'})
            continue
        seen.add(group.id)
        risk = RISK_LABELS.get((row['risk_label'] or '').strip())
        accepted.append({**row, 'group_id': group.id, 'risk': risk, 'group_name': group.name})
    return accepted, errors
