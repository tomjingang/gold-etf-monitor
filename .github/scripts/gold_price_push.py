#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions - 黄金ETF + 伦敦金价格推送
使用Yahoo Finance API获取数据，生成趋势图
时间显示为北京时间 (UTC+8)
"""

import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os
import json
import base64
from io import BytesIO

# 黄金ETF代码 (Yahoo Finance格式)
ETF_CODES = {
    '518880.SS': '华安黄金ETF',  # 上交所
    '159934.SZ': '易方达黄金ETF',  # 深交所
    '518800.SS': '国泰黄金ETF',
    '159937.SZ': '博时黄金ETF',
}

# 伦敦金代码
GOLD_SYMBOLS = {
    'GC=F': '纽约金期货',  # COMEX黄金期货
    'XAUUSD=X': '伦敦金/美元',  # 现货黄金
}

def get_beijing_time():
    """获取北京时间 (UTC+8)"""
    from datetime import timezone
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

def get_etf_prices():
    """获取黄金ETF价格"""
    results = []
    
    for code, name in ETF_CODES.items():
        try:
            ticker = yf.Ticker(code)
            hist = ticker.history(period="5d")
            
            if len(hist) > 0:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest
                
                change = latest['Close'] - prev['Close']
                change_pct = (change / prev['Close']) * 100 if prev['Close'] != 0 else 0
                
                results.append({
                    'name': name,
                    'code': code,
                    'price': latest['Close'],
                    'change': change,
                    'change_pct': change_pct,
                    'volume': latest['Volume']
                })
        except Exception as e:
            print(f"获取 {name} 失败: {e}")
    
    return results

def get_gold_prices():
    """获取伦敦金/国际金价"""
    results = {}
    
    for symbol, name in GOLD_SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            
            if len(hist) > 0:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else latest
                
                change = latest['Close'] - prev['Close']
                change_pct = (change / prev['Close']) * 100 if prev['Close'] != 0 else 0
                
                results[name] = {
                    'price': latest['Close'],
                    'change': change,
                    'change_pct': change_pct
                }
        except Exception as e:
            print(f"获取 {name} 失败: {e}")
    
    return results

def get_historical_data(days=45):
    """获取过去N天的历史数据用于绘图"""
    
    # 获取伦敦金历史数据
    gold_hist = {}
    for symbol, name in GOLD_SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")
            if len(hist) > 0:
                gold_hist[name] = hist
        except Exception as e:
            print(f"获取 {name} 历史数据失败: {e}")
    
    # 获取ETF历史数据（以华安黄金ETF为代表）
    etf_hist = {}
    for code, name in list(ETF_CODES.items())[:1]:  # 只取第一个作为代表
        try:
            ticker = yf.Ticker(code)
            hist = ticker.history(period=f"{days}d")
            if len(hist) > 0:
                etf_hist[name] = hist
        except Exception as e:
            print(f"获取 {name} 历史数据失败: {e}")
    
    return gold_hist, etf_hist

def create_trend_chart(gold_hist, etf_hist, days=45):
    """创建趋势图"""
    
    beijing_time = get_beijing_time()
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 创建图表
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle(f'黄金ETF + 伦敦金价格趋势 (过去{days}天)\n北京时间: {beijing_time.strftime("%Y-%m-%d %H:%M")}', 
                 fontsize=16, fontweight='bold')
    
    # 子图1: 伦敦金/国际金价
    ax1 = axes[0]
    for name, hist in gold_hist.items():
        ax1.plot(hist.index, hist['Close'], linewidth=2, label=name, marker='o', markersize=3)
    
    ax1.set_title('🌍 国际金价趋势', fontsize=14, fontweight='bold', pad=10)
    ax1.set_xlabel('日期', fontsize=12)
    ax1.set_ylabel('价格 (USD)', fontsize=12)
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 子图2: 黄金ETF
    ax2 = axes[1]
    for name, hist in etf_hist.items():
        ax2.plot(hist.index, hist['Close'], linewidth=2, label=name, color='#667eea', marker='o', markersize=3)
    
    ax2.set_title('📈 黄金ETF趋势', fontsize=14, fontweight='bold', pad=10)
    ax2.set_xlabel('日期', fontsize=12)
    ax2.set_ylabel('价格 (CNY)', fontsize=12)
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    # 保存图片
    chart_path = 'gold_trend_chart.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✅ 趋势图已保存: {chart_path}")
    return chart_path

def chart_to_base64(chart_path):
    """将图片转换为base64编码"""
    with open(chart_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def generate_push_content(etf_data, gold_data):
    """生成推送内容"""
    
    beijing_time = get_beijing_time()
    
    lines = []
    lines.append("=" * 60)
    lines.append("📊 黄金ETF + 伦敦金价格推送")
    lines.append("=" * 60)
    lines.append(f"⏰ 推送时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    lines.append("📡 数据来源: Yahoo Finance")
    lines.append("=" * 60)
    lines.append("")
    
    # 国际金价
    lines.append("🌍 国际金价:")
    for name, data in gold_data.items():
        emoji = "📈" if data['change'] >= 0 else "📉"
        lines.append(f"   {emoji} {name}: ${data['price']:.2f}")
        lines.append(f"      涨跌: {data['change']:+.2f} ({data['change_pct']:+.2f}%)")
    lines.append("")
    
    # 黄金ETF
    lines.append("📈 黄金ETF:")
    for etf in etf_data:
        emoji = "📈" if etf['change'] >= 0 else "📉"
        lines.append(f"   {emoji} {etf['name']}: ¥{etf['price']:.3f}")
        lines.append(f"      涨跌: {etf['change']:+.3f} ({etf['change_pct']:+.2f}%)")
    lines.append("")
    
    lines.append("=" * 60)
    lines.append("✅ 推送完成!")
    lines.append("=" * 60)
    
    return "\n".join(lines)

def generate_email_body(etf_data, gold_data, chart_base64=None):
    """生成HTML邮件内容，包含趋势图"""
    
    beijing_time = get_beijing_time()
    today = beijing_time.strftime('%Y-%m-%d')
    now = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 国际金价部分
    gold_section = ""
    for name, data in gold_data.items():
        trend = "↑" if data['change'] >= 0 else "↓"
        gold_section += f"{trend} {name}<br>"
        gold_section += f"&nbsp;&nbsp;&nbsp;价格: ${data['price']:.2f}<br>"
        gold_section += f"&nbsp;&nbsp;&nbsp;涨跌: {data['change']:+.2f} ({data['change_pct']:+.2f}%)<br><br>"
    
    # ETF部分
    etf_section = ""
    for etf in etf_data:
        trend = "↑" if etf['change'] >= 0 else "↓"
        etf_section += f"{trend} {etf['name']}<br>"
        etf_section += f"&nbsp;&nbsp;&nbsp;价格: ¥{etf['price']:.3f}<br>"
        etf_section += f"&nbsp;&nbsp;&nbsp;涨跌: {etf['change']:+.3f} ({etf['change_pct']:+.2f}%)<br><br>"
    
    # 图片部分
    chart_html = ""
    if chart_base64:
        chart_html = f'''<div style="text-align:center;margin:20px 0;">
            <img src="data:image/png;base64,{chart_base64}" alt="黄金ETF + 伦敦金价格趋势" style="max-width:100%;height:auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        </div>'''
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>黄金ETF + 伦敦金价格推送</title>
</head>
<body style="margin:0;padding:20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:white;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <!-- 头部 -->
        <tr>
            <td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:30px;text-align:center;border-radius:10px 10px 0 0;">
                <h1 style="margin:0;color:white;font-size:24px;">📊 黄金ETF + 伦敦金价格推送</h1>
                <p style="margin:10px 0 0 0;color:white;opacity:0.9;font-size:14px;">{now} (北京时间)</p>
            </td>
        </tr>
        
        <!-- 趋势图 -->
        <tr>
            <td style="padding:20px;background:#fafafa;">
                <h2 style="margin:0 0 15px 0;color:#333;font-size:18px;">📈 过去45天趋势</h2>
                {chart_html}
            </td>
        </tr>
        
        <!-- 内容 -->
        <tr>
            <td style="padding:30px;">
                <!-- 国际金价 -->
                <h2 style="margin:0 0 15px 0;color:#333;font-size:18px;border-left:4px solid #667eea;padding-left:10px;">🌍 国际金价</h2>
                <div style="background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:20px;line-height:1.8;">
                    {gold_section}
                </div>
                
                <!-- 黄金ETF -->
                <h2 style="margin:0 0 15px 0;color:#333;font-size:18px;border-left:4px solid #667eea;padding-left:10px;">📈 黄金ETF</h2>
                <div style="background:#f8f9fa;padding:15px;border-radius:8px;line-height:1.8;">
                    {etf_section}
                </div>
            </td>
        </tr>
        
        <!-- 底部 -->
        <tr>
            <td style="background:#f8f9fa;padding:20px;text-align:center;border-radius:0 0 10px 10px;">
                <p style="margin:0;color:#28a745;font-size:16px;font-weight:bold;">✅ 推送完成</p>
                <p style="margin:10px 0 0 0;color:#666;font-size:12px;">本邮件由 GitHub Actions 自动发送</p>
                <p style="margin:5px 0 0 0;font-size:12px;"><a href="https://github.com/tomjingang/gold-etf-monitor" style="color:#667eea;text-decoration:none;">查看仓库</a></p>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    return html

def save_data(etf_data, gold_data):
    """保存数据到CSV"""
    beijing_time = get_beijing_time()
    today = beijing_time.strftime('%Y-%m-%d')
    
    # 保存ETF数据
    if etf_data:
        df = pd.DataFrame(etf_data)
        df.to_csv(f'gold_etf_{today}.csv', index=False)
        print(f"✅ ETF数据已保存: gold_etf_{today}.csv")
    
    # 保存金价数据
    if gold_data:
        gold_df = pd.DataFrame([
            {'name': k, 'price': v['price'], 'change': v['change'], 'change_pct': v['change_pct']}
            for k, v in gold_data.items()
        ])
        gold_df.to_csv(f'gold_price_{today}.csv', index=False)
        print(f"✅ 金价数据已保存: gold_price_{today}.csv")

def main():
    """主函数"""
    
    beijing_time = get_beijing_time()
    
    print("=" * 60)
    print("🕐 GitHub Actions - 黄金ETF + 伦敦金价格推送")
    print("=" * 60)
    print(f"⏰ 执行时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    print("📡 数据来源: Yahoo Finance")
    print("=" * 60)
    print()
    
    # 获取历史数据并生成趋势图
    print("🔄 正在获取历史数据(45天)...")
    gold_hist, etf_hist = get_historical_data(days=45)
    
    print("📊 正在生成趋势图...")
    chart_path = create_trend_chart(gold_hist, etf_hist, days=45)
    
    # 将图片转换为base64
    chart_base64 = chart_to_base64(chart_path)
    print("✅ 图片已转换为base64")
    
    # 获取最新数据
    print("\n🔄 正在获取最新黄金ETF价格...")
    etf_data = get_etf_prices()
    
    print("🔄 正在获取最新国际金价...")
    gold_data = get_gold_prices()
    
    # 生成推送内容
    push_content = generate_push_content(etf_data, gold_data)
    
    # 打印推送内容
    print("\n" + push_content)
    
    # 保存推送内容
    with open('push_notification.txt', 'w', encoding='utf-8') as f:
        f.write(push_content)
    print("\n✅ 推送内容已保存: push_notification.txt")
    
    # 生成HTML邮件内容（包含图片）
    email_html = generate_email_body(etf_data, gold_data, chart_base64)
    with open('email_body.html', 'w', encoding='utf-8') as f:
        f.write(email_html)
    print("✅ 邮件内容已保存: email_body.html (包含趋势图)")
    
    # 同时保存base64图片数据供工作流使用
    with open('chart_base64.txt', 'w', encoding='utf-8') as f:
        f.write(chart_base64)
    print("✅ 图片base64已保存: chart_base64.txt")
    
    # 保存数据
    save_data(etf_data, gold_data)

if __name__ == "__main__":
    main()
