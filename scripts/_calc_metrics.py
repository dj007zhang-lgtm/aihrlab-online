import csv, os
from collections import Counter
def num(s):
    s=str(s).replace(',','').replace('%','').replace('"','').strip()
    try: return float(s)
    except: return 0.0

BASE=os.path.expanduser("~/WorkBuddy/2026-06-03-17-17-18/aihr-data-inbox/AIHR网站数据")
G=os.path.join(BASE,"GA:GSC","www.aihrlab.online_搜索表现与AI引用-2026-09-14")
B=os.path.join(BASE,"百度统计","2026-09-14")

print("="*70)
print("【A】Bing 有机搜索 SearchPerformanceOverview_All")
print("="*70)
rows=list(csv.DictReader(open(os.path.join(G,'www.aihrlab.online_SearchPerformanceOverview_All_9_14_2026.csv'),encoding='utf-8-sig')))
clicks=imp=0
for r in rows:
    clicks+=num(r['Clicks']); imp+=num(r['Impressions'])
ndays=len(rows); weeks=ndays/7
print(f"天数={ndays} 总点击={clicks:.0f} 总曝光={imp:.0f} CTR={clicks/imp*100:.2f}%")
print(f"周口径(÷{weeks:.2f}周): 曝光 {imp/weeks:.0f}/周  点击 {clicks/weeks:.0f}/周")

print("\n"+"="*70)
print("【B】Bing AI 引用 AIPerformanceOverviewStats")
print("="*70)
rows2=list(csv.DictReader(open(os.path.join(G,'www.aihrlab.online_AIPerformanceOverviewStats_9_14_2026.csv'),encoding='utf-8-sig')))
cit=pages=0
for r in rows2:
    cit+=num(r['Citations']); pages+=num(r['Cited Pages'])
nd2=len(rows2); w2=nd2/7
print(f"天数={nd2} 总引用={cit:.0f} 被引页={pages:.0f}")
print(f"周口径(÷{w2:.2f}周): 引用 {cit/w2:.0f}/周")

print("\n"+"="*70)
print("【C】Bing AI 查询 AISearchQueriesReport")
print("="*70)
rows3=list(csv.DictReader(open(os.path.join(G,'www.aihrlab.online_AISearchQueriesReport_9_14_2026.csv'),encoding='utf-8-sig')))
print(f"查询条数={len(rows3)}")
ic=Counter(r['Intent'] for r in rows3); tc=Counter(r['Topic'] for r in rows3)
print("Intent:", dict(ic)); print("Topic:", dict(tc))
top=sorted(rows3,key=lambda x:-num(x['Citations']))[:15]
print("Top15 查询:")
for r in top:
    print(f"  {r['Grounding Query'][:38]:<40} {r['Intent'] or '-':<13} {r['Topic'] or '-':<20} {r['Citations']}")
tot=sum(num(r['Citations']) for r in rows3)
top1=num(top[0]['Citations'])
print(f"\nAI查询集中度: Top1占 {top1/tot*100:.1f}% | Top3占 {sum(num(r['Citations']) for r in top[:3])/tot*100:.1f}%")

print("\n"+"="*70)
print("【D】百度统计 全部来源.csv (GBK)")
print("="*70)
for enc in ['gbk','gb18030','utf-8']:
    try:
        rowsb=list(csv.DictReader(open(os.path.join(B,'全部来源_20260816-20260914.csv'),encoding=enc)))
        break
    except: continue
print("编码:",enc," 行数:",len(rowsb))
totpv=0
print(f"{'来源':<30}{'PV':>7}{'UV':>7}{'跳出率':>8}")
for r in rowsb:
    pv=num(r.get('浏览量(PV)') or r.get('浏览量') or '0')
    uv=num(r.get('访客数(UV)') or r.get('访客数') or '0')
    br=r.get('跳出率') or r.get('跳出率(%)') or '-'
    totpv+=pv
    nm=(r.get('来源') or r.get('全部来源') or '')[:28]
    print(f"{nm:<30}{pv:>7.0f}{uv:>7.0f}{br:>8}")
print(f"总PV={totpv:.0f}")
