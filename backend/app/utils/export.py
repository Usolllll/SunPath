import csv
import io

def safe_cell(value):
    text = str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else text

def plan_csv(plan):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['SunPath 阳光志愿方案', safe_cell(plan.name)])
    p = plan.profile_snapshot
    writer.writerow(['生源省份', p['province'], '考试年份', p['exam_year'], '分数', p['score'], '位次', p['rank']])
    writer.writerow(['注意', '全部为模拟数据；冲稳保为规则估算，不代表真实录取概率。'])
    writer.writerow(['顺序', '院校', '专业组', '专业', '地区', '梯度', '近三年加权参考位次', '招生计划', '选科要求', '风险提示'])
    for index, item in enumerate(plan.items, 1):
        row = [index, item['university']['name'], item['name'], '、'.join(item['majors']), item['university']['region'], {'reach': '冲', 'steady': '稳', 'safe': '保'}[item['risk']], item['baseline_rank'], item['seats'], '、'.join(item['required_subjects']) or '不限', '；'.join(item['warnings'])]
        writer.writerow([safe_cell(v) for v in row])
    return '\ufeff' + output.getvalue()
