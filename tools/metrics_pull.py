#!/usr/bin/env python3
"""
AIHR 指标拉取脚本 —— 产出「数据结果」给主理人看。

为什么需要本脚本：
  沙箱 Bash 环境无外网出口（socket 直连 googleapis.com 超时），无法在对话内
  实时拉取 GSC / GA4。本脚本在有网络出口的机器（主理人本地 / 有 egress 的 CI）
  运行，产出真实排名 / 展现 / 点击 / 跳出率。

依赖（隔离 venv）：
  pip install google-api-python-client google-auth google-analytics-data

GSC（排名/展现/点击/收录）—— 用现成服务账号，无需额外配置：
  export GSC_SITE_URL="sc-domain:aihrlab.online"   # 或 https://www.aihrlab.online/
  python tools/metrics_pull.py --gsc --days 30

GA4（跳出率/会话）—— 需 GA4 服务账号凭据 + 媒体资源 ID：
  export GA4_CREDENTIALS_FILE="/path/to/ga4-sa.json"
  export GA4_PROPERTY_ID="123456789"               # 数字，不带 properties/ 前缀
  python tools/metrics_pull.py --ga4 --days 30

两者一起：
  python tools/metrics_pull.py --gsc --ga4 --days 30

输出：终端表格 + 同目录 metrics_<date>.json 快照（便于对比趋势）。

注意：百度统计(百度统计 b53ffd...) 的跳出率需百度统计 API（token+uuid），
与本脚本的 GA4 不同源；如需百度侧跳出率，另接百度统计 API，本脚本暂不含。
"""
import os, sys, json, argparse
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GSC_CREDS = os.path.join(ROOT, "gsc_service_account.json")
GSC_SITE = os.environ.get("GSC_SITE_URL", "sc-domain:aihrlab.online")


def _gsc_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        GSC_CREDS, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return build("searchconsole", "v1", credentials=creds)


def pull_gsc(days):
    end = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")  # GSC 有 ~3 天延迟
    start = (datetime.now() - timedelta(days=days + 3)).strftime("%Y-%m-%d")
    svc = _gsc_service()

    def q(body):
        return svc.searchanalytics().query(siteUrl=GSC_SITE, body=body).execute().get("rows", [])

    out = {"window": f"{start}~{end}"}
    tot = q({"startDate": start, "endDate": end, "dimensions": [], "rowLimit": 1})
    out["totals"] = (tot[0] if tot else {})
    out["daily"] = [
        {"date": r["keys"][0], "impressions": r.get("impressions"), "clicks": r.get("clicks"),
         "ctr": round(r.get("ctr", 0), 4), "position": round(r.get("position", 0), 2)}
        for r in sorted(q({"startDate": start, "endDate": end, "dimensions": ["date"], "rowLimit": 500}),
                        key=lambda x: x["keys"][0])
    ]
    out["top_queries"] = [
        {"query": r["keys"][0], "impressions": r.get("impressions"), "clicks": r.get("clicks"),
         "position": round(r.get("position", 0), 1)}
        for r in sorted(q({"startDate": start, "endDate": end, "dimensions": ["query"], "rowLimit": 25}),
                        key=lambda x: -x.get("impressions", 0))[:25]
    ]
    out["top_pages"] = [
        {"page": r["keys"][0], "impressions": r.get("impressions"), "clicks": r.get("clicks"),
         "position": round(r.get("position", 0), 1)}
        for r in sorted(q({"startDate": start, "endDate": end, "dimensions": ["page"], "rowLimit": 25}),
                        key=lambda x: -x.get("impressions", 0))[:25]
    ]
    return out


def pull_ga4(days):
    cred_file = os.environ.get("GA4_CREDENTIALS_FILE")
    prop = os.environ.get("GA4_PROPERTY_ID")
    if not cred_file or not prop:
        return {"error": "GA4 未配置：需设置 GA4_CREDENTIALS_FILE 与 GA4_PROPERTY_ID 环境变量"}
    from google.oauth2 import service_account
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension
    creds = service_account.Credentials.from_service_account_file(
        cred_file, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    client = BetaAnalyticsDataClient(credentials=creds)
    end = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    req = RunReportRequest(
        property=f"properties/{prop}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[Metric(name="sessions"), Metric(name="bounceRate"),
                 Metric(name="engagedSessions"), Metric(name="screenPageViews")],
        dimensions=[Dimension(name="date")],
    )
    resp = client.run_report(req)
    rows = []
    for row in resp.rows:
        rows.append({
            "date": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "bounceRate": round(float(row.metric_values[1].value), 4),
            "engagedSessions": int(row.metric_values[2].value),
            "pageViews": int(row.metric_values[3].value),
        })
    return {"window": f"{start}~{end}", "daily": rows,
            "avg_bounceRate": round(sum(r["bounceRate"] for r in rows) / len(rows), 4) if rows else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsc", action="store_true", help="拉取 GSC 排名/展现/点击")
    ap.add_argument("--ga4", action="store_true", help="拉取 GA4 跳出率/会话")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    if not args.gsc and not args.ga4:
        args.gsc = args.ga4 = True

    result = {}
    if args.gsc:
        print(">>> 拉取 GSC ...", file=sys.stderr)
        result["gsc"] = pull_gsc(args.days)
    if args.ga4:
        print(">>> 拉取 GA4 ...", file=sys.stderr)
        result["ga4"] = pull_ga4(args.days)

    snap = os.path.join(HERE, f"metrics_{datetime.now():%Y%m%d}.json")
    with open(snap, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n快照已存: {snap}", file=sys.stderr)


if __name__ == "__main__":
    main()
