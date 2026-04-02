from __future__ import annotations

import csv
from pathlib import Path


def write_source_catalog(path: Path) -> None:
    rows = [
        ["事件数据", "政策类事件", "中国政府网", "https://www.gov.cn/", "已自动接入", "gov 采集器"],
        ["事件数据", "政策类事件", "国家发展改革委官网", "https://www.ndrc.gov.cn/", "已自动接入", "ndrc 采集器"],
        ["事件数据", "政策类事件", "证监会官网", "https://www.csrc.gov.cn/", "已自动接入", "csrc 采集器"],
        ["事件数据", "公司行为事件", "巨潮资讯网", "https://www.cninfo.com.cn/", "已自动接入", "cninfo 采集器"],
        ["事件数据", "公司行为事件", "上交所官网", "https://www.sse.com.cn/", "已自动接入", "sse 采集器"],
        ["事件数据", "公司行为事件", "深交所官网", "https://www.szse.cn/", "已自动接入", "szse 采集器"],
        ["事件数据", "行业/技术事件", "36氪产业板块", "https://www.36kr.com/newsflashes/catalog/2", "已自动接入", "kr36 采集器"],
        ["事件数据", "行业/技术事件", "各行业协会官网", "N/A", "已登记待接入", "需按行业单独补充"],
        ["事件数据", "行业/技术事件", "东方财富行业频道", "https://finance.eastmoney.com/a/cywjh.html", "已自动接入", "eastmoney 采集器"],
        ["事件数据", "宏观/地缘事件", "财新网", "https://mini.caixin.com/", "已自动接入", "caixin 采集器（mini 列表页）"],
        ["事件数据", "宏观/地缘事件", "第一财经", "https://www.yicai.com/", "已自动接入", "yicai 采集器"],
        ["行情数据", "个股行情", "Tushare", "https://tushare.pro/", "已登记待接入", "任务3/4优先"],
        ["行情数据", "个股行情", "聚宽", "https://www.joinquant.com/", "已登记待接入", "任务3/4优先"],
        ["行情数据", "停复牌信息", "巨潮资讯网", "https://www.cninfo.com.cn/", "已登记待接入", "任务3/4优先"],
        ["行情数据", "停复牌信息", "上交所官网", "https://www.sse.com.cn/", "已登记待接入", "任务3/4优先"],
        ["行情数据", "停复牌信息", "深交所官网", "https://www.szse.cn/", "已登记待接入", "任务3/4优先"],
        ["财务数据", "定期财务报表", "巨潮资讯网", "https://www.cninfo.com.cn/", "已登记待接入", "任务3优先"],
        ["财务数据", "定期财务报表", "上交所官网", "https://www.sse.com.cn/", "已登记待接入", "任务3优先"],
        ["财务数据", "定期财务报表", "深交所官网", "https://www.szse.cn/", "已登记待接入", "任务3优先"],
        ["财务数据", "关键财务指标", "Tushare", "https://tushare.pro/", "已登记待接入", "任务3优先"],
        ["财务数据", "关键财务指标", "东方财富个股财务", "https://data.eastmoney.com/", "已登记待接入", "任务3优先"],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["data_group", "source_category", "source_name", "url", "status", "note"])
        writer.writerows(rows)

