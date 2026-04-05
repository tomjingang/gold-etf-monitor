#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions - 黄金ETF + 伦敦金价格推送
使用Yahoo Finance API获取数据
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
import json

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

def generate_push_content(etf_data, gold_data):
    """生成推送内容"""
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    lines = []
    lines.append("=" * 60)
    lines.append("📊 黄金ETF + 伦敦金价格推送")
    lines.append("=" * 60)
    lines.append(f"⏰ 推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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

def generate_email_html(etf_data, gold_data):
    """生成简洁易读的HTML邮件内容"""
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 生成国际金价HTML - 使用简单表格
    gold_html = ""
    for name, data in gold_data.items():
        color = "#28a745" if data['change'] >= 0 else "#dc3545"
        emoji = "📈" if data['change'] >= 0 else "📉"
        gold_html += f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid #ddd;font-size:16px;">{emoji} {name}</td>
            <td style="padding:12px;border-bottom:1px solid #ddd;font-size:18px;font-weight:bold;">${data['price']:.2f}</td>
            <td style="padding:12px;border-bottom:1px solid #ddd;font-size:16px;color:{color};">{data['change']:+.2f} ({data['change_pct']:+.2f}%)</td>
        </tr>
        """
    
    # 生成ETF HTML
    etf_html = ""
    for etf in etf_data:
        color = "#28a745" if etf['change'] >= 0 else "#dc3545"
        emoji = "📈" if etf['change'] >= 0 else "📉"
        etf_html += f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid #ddd;font-size:16px;">{emoji} {etf['name']}</td>
            <td style="padding:12px;border-bottom:1px solid #ddd;font-size:18px;font-weight:bold;">¥{etf['price']:.3f}</td>
            <td style="padding:12px;border-bottom:1px solid #ddd;font-size:16px;color:{color};">{etf['change']:+.3f} ({etf['change_pct']:+.2f}%)</td>
        </tr>
        """
    
    # 简洁的HTML邮件模板
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
                <p style="margin:10px 0 0 0;color:white;opacity:0.9;font-size:14px;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </td>
        </tr>
        
        <!-- 内容 -->
        <tr>
            <td style="padding:30px;">
                <!-- 国际金价 -->
                <h2 style="margin:0 0 15px 0;color:#333;font-size:18px;border-left:4px solid #667eea;padding-left:10px;">🌍 国际金价</h2>
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:30px;">
                    <thead>
                        <tr style="background:#f8f9fa;">
                            <th style="padding:12px;text-align:left;font-weight:600;color:#555;">名称</th>
                            <th style="padding:12px;text-align:left;font-weight:600;color:#555;">价格</th>
                            <th style="padding:12px;text-align:left;font-weight:600;color:#555;">涨跌</th>
                        </tr>
                    </thead>
                    <tbody>
                        {gold_html}
                    </tbody>
                </table>
                
                <!-- 黄金ETF -->
                <h2 style="margin:0 0 15px 0;color:#333;font-size:18px;border-left:4px solid #667eea;padding-left:10px;">📈 黄金ETF</h2>
                <table width="100%" cellpadding="0" cellspacing="0">
                    <thead>
                        <tr style="background:#f8f9fa;">
                            <th style="padding:12px;text-align:left;font-weight:600;color:#555;">名称</th>
                            <th style="padding:12px;text-align:left;font-weight:600;color:#555;">价格</th>
                            <th style="padding:12px;text-align:left;font-weight:600;color:#555;">涨跌</th>
                        </tr>
                    </thead>
                    <tbody>
                        {etf_html}
                    </tbody>
                </table>
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
    today = datetime.now().strftime('%Y-%m-%d')
    
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
    
    print("=" * 60)
    print("🕐 GitHub Actions - 黄金ETF + 伦敦金价格推送")
    print("=" * 60)
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 数据来源: Yahoo Finance")
    print("=" * 60)
    print()
    
    # 获取数据
    print("🔄 正在获取黄金ETF价格...")
    etf_data = get_etf_prices()
    
    print("🔄 正在获取国际金价...")
    gold_data = get_gold_prices()
    
    # 生成推送内容
    push_content = generate_push_content(etf_data, gold_data)
    
    # 打印推送内容
    print("\n" + push_content)
    
    # 保存推送内容
    with open('push_notification.txt', 'w', encoding='utf-8') as f:
        f.write(push_content)
    print("\n✅ 推送内容已保存: push_notification.txt")
    
    # 生成并保存HTML邮件
    email_html = generate_email_html(etf_data, gold_data)
    with open('email_body.html', 'w', encoding='utf-8') as f:
        f.write(email_html)
    print("✅ 邮件内容已保存: email_body.html")
    
    # 保存数据
    save_data(etf_data, gold_data)

if __name__ == "__main__":
    main()
