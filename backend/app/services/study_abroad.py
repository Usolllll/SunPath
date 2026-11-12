"""留学规划（FR-M11-01）：官方入口索引 + 个性化路径/语言规划。

数据来自 ``app/data/study_abroad.json``（Lead 维护，只读）：2 个语言考试、4 个地区、
18 所学校的官方申请入口、语言参考要求、高考接受情况与资格路径说明。

边界：
- 只做官方入口索引与通用规划提示，**不代填申请表、不承诺录取**；
- 语言对比只有 reached / below / unknown 三态，不出现概率或录取率；
- 申请要求、截止日期与材料清单以学校官网为准，不编造具体学校截止日期；
- 读取失败（文件缺失/损坏）返回空结构，不抛 500。
"""
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select

from app.models.entities import StudyAbroadTarget

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
DATA_FILE = DATA_DIR / 'study_abroad.json'
DISCLAIMER = '申请要求与截止日期以学校官网为准，本模块只做官方入口索引，不代填申请表。'

PATH_CODES = ('gaokao', 'post_gaokao', 'international')
TEST_CODES = ('ielts', 'toefl')
TEST_SCALES = {'ielts': (0, 9), 'toefl': (0, 120)}

GAOKAO_LABELS = {
    True: '参考：接受高考成绩直申',
    False: '参考：通常不接受高考成绩直申',
}
GAOKAO_UNKNOWN_LABEL = '参考：未标注，以官网为准'
PATH_WARNING = '该校通常不接受高考成绩直申，建议考虑预科/国际课程路径，具体以官网为准'

LANGUAGE_LABELS = {
    'reached': '达到参考最低语言要求',
    'below': '低于参考最低语言要求',
    'unknown': '暂无参考语言要求，请查官网',
}

# ---------------------------------------------------------------- 清单与时间线（按路径差异化）
BASE_CHECKLIST = (
    ('language', '语言成绩单（雅思/托福）', '成绩有效期通常为两年；单项分与有效期要求以学校官网为准。'),
    ('transcript', '高中成绩单与毕业证明', '需学校盖章或公证，部分学校要求英文翻译件。'),
    ('recommendation', '推荐信', '通常 1–2 封，由任课老师或升学指导老师撰写。'),
    ('essay', '个人陈述/文书', '按学校题目准备，围绕学术兴趣与经历展开；不得代写或夸大。'),
    ('application', '网申账号与申请费', '在官方申请系统注册账号并支付申请费，保留缴费与提交回执。'),
    ('tests', '标化或入学测试（视学校要求）', '如 SAT/ACT、笔试或入学测试；是否要求以学校官网为准。'),
    ('interview', '面试准备', '部分学校/专业安排面试，提前熟悉申请材料与专业方向。'),
    ('visa', '录取后签证与资金证明', '确认 offer 后按使领馆清单准备签证材料与资金证明。'),
)

PATH_CHECKLIST = {
    'gaokao': (
        ('gaokao_score', '高考成绩单/省排名证明',
         '按学校要求提供高考成绩单与省排名证明；是否接受高考成绩与分数门槛以官网为准。'),
    ),
    'post_gaokao': (
        ('foundation', '预科/国际大一入学要求与升学考核说明',
         '核对预科或国际大一的入学要求、升学考核与目标学位衔接条件，升学不等于直接录取。'),
    ),
    'international': (
        ('international_curriculum', '国际课程成绩单（A-Level/IB/AP）与课程体系说明、预估分',
         '准备国际课程成绩单、课程体系说明与预估分，并核对目标专业的选课要求。'),
    ),
}

TIMELINES = {
    'gaokao': (
        {'stage': '确定方向', 'when': '高一至高二',
         'detail': '确定留学地区与目标学校/专业，核对是否接受高考成绩、英语单科与语言要求。'},
        {'stage': '高考与语言', 'when': '高三 / 提前 6–12 个月',
         'detail': '备战高考并完成雅思/托福考试；语言成绩通常两年有效，预留重考时间。'},
        {'stage': '材料准备', 'when': '申请季前 2–3 个月',
         'detail': '准备高考成绩单、省排名证明、推荐信与文书，逐校核对官方截止日期。'},
        {'stage': '网申提交', 'when': '申请季',
         'detail': '通过学校官网或统一平台提交申请并支付申请费，保留提交回执。'},
        {'stage': '录取后', 'when': '收到 offer 之后',
         'detail': '确认 offer、准备签证与资金证明、安排住宿与行前事项。'},
    ),
    'post_gaokao': (
        {'stage': '确定方向', 'when': '高考出分后 1–3 个月内',
         'detail': '评估高考成绩与语言基础，选择预科或国际大一方向并核对升学衔接要求。'},
        {'stage': '语言与入学要求', 'when': '申请前 2–4 个月',
         'detail': '完成雅思/托福考试，并核对预科/国际大一的入学要求与升学考核方式。'},
        {'stage': '材料准备', 'when': '申请前 1–2 个月',
         'detail': '准备高中成绩单、毕业证明、语言成绩与个人陈述等材料。'},
        {'stage': '提交申请', 'when': '滚动申请',
         'detail': '通过学校官网或合作项目提交申请，确认开课时间与名额，保留回执。'},
        {'stage': '升学与签证', 'when': '预科/国际大一完成后',
         'detail': '达到升学考核要求后升读学位课程，并办理签证与住宿。'},
    ),
    'international': (
        {'stage': '课程规划', 'when': '提前 18–24 个月',
         'detail': '确定国际课程体系（A-Level/IB/AP）与选课，对照目标专业要求规划科目。'},
        {'stage': '语言与标化', 'when': '提前 12–18 个月',
         'detail': '完成雅思/托福考试，按地区要求准备 SAT/ACT 等标化考试。'},
        {'stage': '申请材料', 'when': '申请季前 3–6 个月',
         'detail': '准备课程成绩单、预估分、推荐信与文书，核对 UCAS/Common App 的官方节点。'},
        {'stage': '网申提交', 'when': '申请季',
         'detail': '通过 UCAS、Common App 或学校官网提交申请，保留提交回执。'},
        {'stage': '录取与签证', 'when': '收到 offer 之后',
         'detail': '换取无条件 offer、准备签证与资金证明、安排住宿。'},
    ),
}


class StudyAbroadValidationError(ValueError):
    """留学目标校验失败（API 层转 400）。"""


# ---------------------------------------------------------------- 数据读取
def _empty_data() -> dict:
    return {'meta': {}, 'tests': [], 'regions': []}


@lru_cache
def load_data() -> dict:
    """读取留学索引 JSON；缺失/损坏/结构异常时返回空结构（不 500）。容忍 Lead 追加的新字段。"""
    try:
        payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return _empty_data()
    if not isinstance(payload, dict):
        return _empty_data()
    meta = payload.get('meta') or payload.get('_meta') or {}
    tests = payload.get('tests')
    regions = payload.get('regions')
    return {
        'meta': meta if isinstance(meta, dict) else {},
        'tests': tests if isinstance(tests, list) else [],
        'regions': regions if isinstance(regions, list) else [],
    }


def find_region(data, code):
    if not code:
        return None
    return next((region for region in data.get('regions') or []
                 if isinstance(region, dict) and region.get('code') == code), None)


def find_school(region, school_id):
    if not region or not school_id:
        return None
    return next((school for school in region.get('schools') or []
                 if isinstance(school, dict) and school.get('id') == school_id), None)


def find_test(data, code):
    if not code:
        return None
    return next((test for test in data.get('tests') or []
                 if isinstance(test, dict) and test.get('code') == code), None)


def find_pathway(data, code):
    pathways = (data.get('meta') or {}).get('pathways') or []
    return next((item for item in pathways
                 if isinstance(item, dict) and item.get('code') == code), None)


def _iso_utc(value):
    if value is None:
        return None
    from datetime import timezone
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


# ---------------------------------------------------------------- 选项 / 规划
def options() -> dict:
    """前端选项：meta（含 pathways）+ 2 个考试 + 4 个地区（含 schools 完整字段）+ 免责声明。"""
    data = load_data()
    regions = []
    for region in data.get('regions') or []:
        if not isinstance(region, dict):
            continue
        item = {key: value for key, value in region.items() if key != 'schools'}
        item['schools'] = [dict(school) for school in region.get('schools') or [] if isinstance(school, dict)]
        regions.append(item)
    return {
        'meta': dict(data.get('meta') or {}),
        'tests': [dict(test) for test in data.get('tests') or [] if isinstance(test, dict)],
        'regions': regions,
        'disclaimer': DISCLAIMER,
    }


def _language_plan(test, test_type, user_score, required):
    if required is None:
        status = 'unknown'
    elif user_score >= required:
        status = 'reached'
    else:
        status = 'below'
    return {
        'test_type': test_type,
        'test_label': (test or {}).get('label') or test_type,
        'scale': (test or {}).get('scale'),
        'user_score': user_score,
        'required': required,
        'status': status,
        'label': LANGUAGE_LABELS[status],
    }


def _gaokao_plan(region, school):
    school_gaokao = school.get('gaokao') if isinstance(school.get('gaokao'), dict) else {}
    region_gaokao = region.get('gaokao') if isinstance(region.get('gaokao'), dict) else {}
    accepted = school_gaokao.get('accepted')
    if not isinstance(accepted, bool):
        accepted = None
    label = GAOKAO_LABELS.get(accepted, GAOKAO_UNKNOWN_LABEL)
    return {
        'accepted': accepted,
        'label': label,
        'note': school_gaokao.get('note') or region_gaokao.get('note') or '',
    }


def _links(region, school, test):
    links, seen = [], set()
    for label, url in (
        ('学校官方申请入口', school.get('official_url')),
        ('本地区申请平台/说明', region.get('portal_url')),
        ('考试官方报名入口', (test or {}).get('registration_url')),
    ):
        if not url or url in seen:
            continue
        seen.add(url)
        links.append({'label': label, 'url': url})
    return links


def checklist_for(path: str) -> list[dict]:
    items = [dict(label=label, detail=detail, key=key) for key, label, detail in BASE_CHECKLIST]
    extras = [dict(key=key, label=label, detail=detail)
              for key, label, detail in PATH_CHECKLIST.get(path, PATH_CHECKLIST['gaokao'])]
    return items[:1] + extras + items[1:]


def timeline_for(path: str) -> list[dict]:
    return [dict(item) for item in TIMELINES.get(path, TIMELINES['gaokao'])]


def _build_plan(data, region, school, test, target) -> dict:
    path = target.path if target.path in PATH_CODES else 'gaokao'
    language_data = school.get('language') if isinstance(school.get('language'), dict) else {}
    required = language_data.get(target.test_type)
    language = _language_plan(test, target.test_type, target.test_score, required)

    pathway_meta = find_pathway(data, path) or {}
    region_pathways = region.get('pathways') if isinstance(region.get('pathways'), dict) else {}
    pathway = {
        'code': path,
        'label': pathway_meta.get('label') or path,
        'summary': pathway_meta.get('summary') or '',
        'note': pathway_meta.get('note') or '',
        'region_note': region_pathways.get(path) or '',
    }
    gaokao = _gaokao_plan(region, school)
    warning = PATH_WARNING if path == 'gaokao' and gaokao['accepted'] is False else ''

    return {
        'school': {
            'id': school.get('id'),
            'official_url': school.get('official_url'),
            'name': school.get('name'),
            'name_zh': school.get('name_zh'),
            'intakes': list(school.get('intakes') or []),
            'note': school.get('note') or '',
            'qualifications': list(school.get('qualifications') or []),
        },
        'language': language,
        'pathway': pathway,
        'gaokao': gaokao,
        'path_warning': warning,
        'links': _links(region, school, test),
        'checklist': checklist_for(path),
        'timeline': timeline_for(path),
    }


def target_view(db, user) -> dict:
    """当前用户的留学目标与规划；未保存时 target/plan 均为 null。"""
    target = db.scalar(select(StudyAbroadTarget).where(StudyAbroadTarget.user_id == user.id))
    if not target:
        return {'target': None, 'plan': None, 'disclaimer': DISCLAIMER}
    data = load_data()
    region = find_region(data, target.region)
    school = find_school(region, target.school_id)
    test = find_test(data, target.test_type)
    path = target.path if target.path in PATH_CODES else 'gaokao'
    pathway_meta = find_pathway(data, path) or {}
    target_payload = {
        'region': target.region,
        'region_label': (region or {}).get('label'),
        'school_id': target.school_id,
        'school_name': (school or {}).get('name'),
        'school_name_zh': (school or {}).get('name_zh'),
        'test_type': target.test_type,
        'test_label': (test or {}).get('label') or target.test_type,
        'test_score': target.test_score,
        'target_major': target.target_major,
        'path': path,
        'path_label': pathway_meta.get('label') or path,
        'gaokao_score': target.gaokao_score,
        'saved_at': _iso_utc(target.updated_at or target.created_at),
    }
    plan = _build_plan(data, region, school, test, target) if region and school else None
    return {'target': target_payload, 'plan': plan, 'disclaimer': DISCLAIMER}


# ---------------------------------------------------------------- 保存 / 清除
def _clean_text(value, label: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StudyAbroadValidationError(f'{label}不能为空')
    text = value.strip()
    if len(text) > max_length:
        raise StudyAbroadValidationError(f'{label}不超过 {max_length} 个字符')
    return text


def _clean_score(value, test_type: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StudyAbroadValidationError('语言分数必须是数字')
    score = round(float(value), 1)
    low, high = TEST_SCALES[test_type]
    if not low <= score <= high:
        raise StudyAbroadValidationError(f'语言分数应在 {low}–{high} 之间')
    return score


def save_target(db, user, payload) -> dict:
    """校验并 upsert 本人留学目标（只 flush，commit 由 API 做）；返回最新 target_view。"""
    if not isinstance(payload, dict):
        raise StudyAbroadValidationError('请求体格式不正确')
    data = load_data()

    region_code = _clean_text(payload.get('region'), '留学地区', 20)
    region = find_region(data, region_code)
    if not region:
        raise StudyAbroadValidationError(f'未收录的留学地区：{region_code}')
    school_id = _clean_text(payload.get('school_id'), '学校标识', 40)
    school = find_school(region, school_id)
    if not school:
        raise StudyAbroadValidationError('该学校不属于所选地区或暂未收录')

    test_type = payload.get('test_type')
    if test_type not in TEST_CODES:
        raise StudyAbroadValidationError('语言考试类型只能是 ielts 或 toefl')
    score = _clean_score(payload.get('test_score'), test_type)

    path = payload.get('path') or 'gaokao'
    if path not in PATH_CODES:
        raise StudyAbroadValidationError('留学路径只能是 gaokao / post_gaokao / international')

    gaokao_score = payload.get('gaokao_score')
    if gaokao_score is not None:
        if isinstance(gaokao_score, bool) or not isinstance(gaokao_score, (int, float)):
            raise StudyAbroadValidationError('高考分数必须是数字')
        gaokao_score = round(float(gaokao_score), 1)
        if not 0 <= gaokao_score <= 750:
            raise StudyAbroadValidationError('高考分数应在 0–750 之间')

    major = payload.get('target_major')
    if major is not None:
        if not isinstance(major, str):
            raise StudyAbroadValidationError('目标专业必须是文本')
        major = major.strip() or None
        if major and len(major) > 60:
            raise StudyAbroadValidationError('目标专业不超过 60 个字符')

    target = db.scalar(select(StudyAbroadTarget).where(StudyAbroadTarget.user_id == user.id))
    if target is None:
        target = StudyAbroadTarget(user_id=user.id)
        db.add(target)
    target.region = region_code
    target.school_id = school_id
    target.test_type = test_type
    target.test_score = score
    target.target_major = major
    target.path = path
    target.gaokao_score = gaokao_score
    db.flush()
    db.refresh(target)
    return target_view(db, user)


def clear_target(db, user) -> bool:
    """删除本人留学目标；返回是否确实存在过（只 flush，commit 由 API 做）。"""
    target = db.scalar(select(StudyAbroadTarget).where(StudyAbroadTarget.user_id == user.id))
    if target is None:
        return False
    db.delete(target)
    db.flush()
    return True
