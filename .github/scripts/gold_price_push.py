#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions - 黄金/原油投资推送系统
功能：
1. 获取纽约金、伦敦金、中国黄金ETF价格
2. 获取WTI/布伦特原油价格
3. 基于技术分析生成投资建议
4. 回测优化建议策略
5. 生成趋势图并发送邮件
时间显示为北京时间 (UTC+8)
"""

import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，适用于GitHub Actions
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os
import json
import time

# ============ 数据配置 ============
# 黄金相关
GOLD_SYMBOLS = {
    'GC=F': {'name': '纽约金期货', 'type': 'futures', 'currency': 'USD'},
    'GLD': {'name': 'SPDR黄金ETF(参考伦敦金)', 'type': 'etf', 'currency': 'USD'},
}

# 中国黄金ETF
CHINA_GOLD_ETF = {
    '518880.SS': '华安黄金ETF',
    '159934.SZ': '易方达黄金ETF',
    '518800.SS': '国泰黄金ETF',
    '159937.SZ': '博时黄金ETF',
}

# 原油期货
OIL_SYMBOLS = {
    'CL=F': {'name': 'WTI原油', 'type': 'futures', 'currency': 'USD'},
    'BZ=F': {'name': '布伦特原油', 'type': 'futures', 'currency': 'USD'},
}

# 回测数据存储文件
BACKTEST_FILE = 'backtest_history.json'
ADVICE_HISTORY_FILE = 'advice_history.json'


def get_beijing_time():
    """获取北京时间 (UTC+8)"""
    from datetime import timezone
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


def fetch_data(symbol, period='90d', max_retries=3):
    """获取指定品种的完整数据，带重试机制"""
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            if len(hist) == 0:
                return None
            return calculate_indicators(hist)
        except Exception as e:
            print(f"获取 {symbol} 数据失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
            else:
                return None


def calculate_indicators(df):
    """计算技术指标"""
    df = df.copy()
    
    # 移动平均线
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA10'] = df['Close'].rolling(window=10).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 布林带
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    # 波动率
    df['Volatility'] = df['Close'].rolling(window=20).std() / df['Close'].rolling(window=20).mean() * 100
    
    return df


def get_gold_data():
    """获取黄金相关数据"""
    results = {'ny_gold': None, 'london_gold': None, 'china_etf': []}
    
    # 纽约金
    ny_data = fetch_data('GC=F', period='60d')
    if ny_data is not None and len(ny_data) > 1:
        latest = ny_data.iloc[-1]
        prev = ny_data.iloc[-2]
        results['ny_gold'] = {
            'name': '纽约金期货',
            'price': latest['Close'],
            'change': latest['Close'] - prev['Close'],
            'change_pct': (latest['Close'] - prev['Close']) / prev['Close'] * 100,
            'ma20': latest['MA20'],
            'ma60': latest['MA60'],
            'rsi': latest['RSI'],
            'macd': latest['MACD'],
            'macd_signal': latest['MACD_Signal'],
            'volatility': latest['Volatility'],
            'history': ny_data
        }
    
    # 伦敦金
    london_data = fetch_data('XAUUSD=X', period='60d')
    if london_data is not None and len(london_data) > 1:
        latest = london_data.iloc[-1]
        prev = london_data.iloc[-2]
        results['london_gold'] = {
            'name': '伦敦金',
            'price': latest['Close'],
            'change': latest['Close'] - prev['Close'],
            'change_pct': (latest['Close'] - prev['Close']) / prev['Close'] * 100,
            'ma20': latest['MA20'],
            'rsi': latest['RSI'],
            'volatility': latest['Volatility'],
            'history': london_data
        }
    
    # 中国黄金ETF
    for code, name in CHINA_GOLD_ETF.items():
        try:
            etf_data = fetch_data(code, period='60d')
            if etf_data is not None and len(etf_data) > 1:
                latest = etf_data.iloc[-1]
                prev = etf_data.iloc[-2]
                results['china_etf'].append({
                    'code': code,
                    'name': name,
                    'price': latest['Close'],
                    'change': latest['Close'] - prev['Close'],
                    'change_pct': (latest['Close'] - prev['Close']) / prev['Close'] * 100,
                    'volume': latest['Volume'],
                    'rsi': latest['RSI']
                })
        except Exception as e:
            print(f"获取 {name} 失败: {e}")
    
    return results


def get_oil_data():
    """获取原油相关数据"""
    results = {'wti': None, 'brent': None}
    
    # WTI原油
    wti_data = fetch_data('CL=F', period='60d')
    if wti_data is not None and len(wti_data) > 1:
        latest = wti_data.iloc[-1]
        prev = wti_data.iloc[-2]
        results['wti'] = {
            'name': 'WTI原油',
            'price': latest['Close'],
            'change': latest['Close'] - prev['Close'],
            'change_pct': (latest['Close'] - prev['Close']) / prev['Close'] * 100,
            'ma20': latest['MA20'],
            'ma60': latest['MA60'],
            'rsi': latest['RSI'],
            'macd': latest['MACD'],
            'macd_signal': latest['MACD_Signal'],
            'volatility': latest['Volatility'],
            'history': wti_data
        }
    
    # 布伦特原油
    brent_data = fetch_data('BZ=F', period='60d')
    if brent_data is not None and len(brent_data) > 1:
        latest = brent_data.iloc[-1]
        prev = brent_data.iloc[-2]
        results['brent'] = {
            'name': '布伦特原油',
            'price': latest['Close'],
            'change': latest['Close'] - prev['Close'],
            'change_pct': (latest['Close'] - prev['Close']) / prev['Close'] * 100,
            'ma20': latest['MA20'],
            'rsi': latest['RSI'],
            'history': brent_data
        }
    
    return results


def analyze_market(gold_data, oil_data):
    """分析市场并生成投资建议"""
    advice = {
        'gold': {'action': 'hold', 'confidence': 50, 'allocation_pct': 0, 'reasons': []},
        'oil': {'action': 'hold', 'confidence': 50, 'allocation_pct': 0, 'reasons': []},
        'portfolio': {'gold_pct': 0, 'oil_pct': 0, 'cash_pct': 100}
    }
    
    # 黄金分析
    if gold_data['ny_gold']:
        ny = gold_data['ny_gold']
        trend_score = 0
        
        # 趋势判断
        if ny['price'] > ny['ma20']:
            trend_score += 1
            advice['gold']['reasons'].append("价格站上20日均线")
        if ny['ma20'] > ny['ma60']:
            trend_score += 1
            advice['gold']['reasons'].append("均线多头排列")
        if ny['macd'] > ny['macd_signal']:
            trend_score += 1
            advice['gold']['reasons'].append("MACD金叉")
        
        # RSI判断
        if ny['rsi'] < 30:
            trend_score += 1
            advice['gold']['reasons'].append("RSI超卖")
        elif ny['rsi'] > 70:
            trend_score -= 1
            advice['gold']['reasons'].append("RSI超买")
        
        # 生成建议
        if trend_score >= 2:
            advice['gold']['action'] = 'buy'
            advice['gold']['confidence'] = min(50 + trend_score * 10, 85)
            advice['gold']['allocation_pct'] = 25
        elif trend_score <= -1:
            advice['gold']['action'] = 'reduce'
            advice['gold']['confidence'] = min(50 + abs(trend_score) * 10, 75)
            advice['gold']['allocation_pct'] = 10
        else:
            advice['gold']['reasons'].append("趋势不明确，建议观望")
        
        # 设置目标价和止损
        if advice['gold']['action'] == 'buy':
            advice['gold']['target'] = ny['price'] * 1.04
            advice['gold']['stop_loss'] = ny['price'] * 0.97
    
    # 原油分析
    if oil_data['wti']:
        wti = oil_data['wti']
        trend_score = 0
        
        if wti['price'] > wti['ma20']:
            trend_score += 1
            advice['oil']['reasons'].append("价格站上20日均线")
        if wti['macd'] > wti['macd_signal']:
            trend_score += 1
            advice['oil']['reasons'].append("MACD金叉")
        if wti['rsi'] < 30:
            trend_score += 1
            advice['oil']['reasons'].append("RSI超卖")
        
        if trend_score >= 2:
            advice['oil']['action'] = 'buy'
            advice['oil']['confidence'] = min(50 + trend_score * 10, 80)
            advice['oil']['allocation_pct'] = 20
        elif trend_score <= 0:
            advice['oil']['action'] = 'reduce'
            advice['oil']['confidence'] = 55
            advice['oil']['allocation_pct'] = 5
        
        if advice['oil']['action'] == 'buy':
            advice['oil']['target'] = wti['price'] * 1.05
            advice['oil']['stop_loss'] = wti['price'] * 0.94
    
    # 组合配置
    total_allocation = advice['gold']['allocation_pct'] + advice['oil']['allocation_pct']
    advice['portfolio'] = {
        'gold_pct': advice['gold']['allocation_pct'],
        'oil_pct': advice['oil']['allocation_pct'],
        'cash_pct': max(100 - total_allocation, 40)
    }
    
    return advice


def run_backtest(days=30):
    """运行简化回测"""
    if not os.path.exists(ADVICE_HISTORY_FILE):
        return None
    
    with open(ADVICE_HISTORY_FILE, 'r') as f:
        advice_history = json.load(f)
    
    if len(advice_history) < 5:
        return None
    
    # 获取历史价格
    gold_hist = fetch_data('GC=F', period=f'{days+10}d')
    if gold_hist is None:
        return None
    
    results = {'gold_return': 0, 'win_rate': 0, 'total_trades': 0, 'profitable_trades': 0}
    
    for advice in advice_history[-days:]:
        if 'gold' in advice and advice['gold'].get('action') == 'buy':
            advice_date = advice.get('date')
            try:
                matching_rows = gold_hist[gold_hist.index.strftime('%Y-%m-%d') == advice_date]
                if len(matching_rows) > 0:
                    idx = gold_hist.index.get_loc(matching_rows.index[0])
                    if idx >= 0 and idx < len(gold_hist) - 1:
                        entry = gold_hist.iloc[idx]['Close']
                        exit_price = gold_hist.iloc[min(idx+1, len(gold_hist)-1)]['Close']
                        ret = (exit_price - entry) / entry * 100
                        results['gold_return'] += ret
                        results['total_trades'] += 1
                        if ret > 0:
                            results['profitable_trades'] += 1
            except:
                pass
    
    if results['total_trades'] > 0:
        results['win_rate'] = results['profitable_trades'] / results['total_trades'] * 100
        results['avg_return'] = results['gold_return'] / results['total_trades']
    
    return results


def create_trend_chart(gold_data, oil_data, days=45):
    """创建趋势图"""
    beijing_time = get_beijing_time()
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle(f'Gold & Oil Market Trend (Past {days} Days)\nBeijing Time: {beijing_time.strftime("%Y-%m-%d %H:%M")}', 
                 fontsize=16, fontweight='bold')
    
    # 子图1: 纽约金
    ax1 = axes[0]
    if gold_data['ny_gold'] and 'history' in gold_data['ny_gold']:
        hist = gold_data['ny_gold']['history'].tail(days)
        ax1.plot(hist.index, hist['Close'], linewidth=2, label='NY Gold Futures', color='#FFD700', marker='o', markersize=2)
        ax1.plot(hist.index, hist['MA20'], linewidth=1, label='MA20', color='#FF6B6B', linestyle='--')
        ax1.fill_between(hist.index, hist['BB_Lower'], hist['BB_Upper'], alpha=0.1, color='gray', label='Bollinger Bands')
    ax1.set_title('New York Gold Futures', fontsize=14, fontweight='bold', pad=10)
    ax1.set_ylabel('Price (USD)', fontsize=11)
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 子图2: 伦敦金
    ax2 = axes[1]
    if gold_data['london_gold'] and 'history' in gold_data['london_gold']:
        hist = gold_data['london_gold']['history'].tail(days)
        ax2.plot(hist.index, hist['Close'], linewidth=2, label='London Gold', color='#FFA500', marker='o', markersize=2)
        ax2.plot(hist.index, hist['MA20'], linewidth=1, label='MA20', color='#4ECDC4', linestyle='--')
    ax2.set_title('London Gold Spot', fontsize=14, fontweight='bold', pad=10)
    ax2.set_ylabel('Price (USD)', fontsize=11)
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 子图3: 原油
    ax3 = axes[2]
    if oil_data['wti'] and 'history' in oil_data['wti']:
        hist = oil_data['wti']['history'].tail(days)
        ax3.plot(hist.index, hist['Close'], linewidth=2, label='WTI Crude Oil', color='#2196F3', marker='o', markersize=2)
        ax3.plot(hist.index, hist['MA20'], linewidth=1, label='MA20', color='#FF6B6B', linestyle='--')
    if oil_data['brent'] and 'history' in oil_data['brent']:
        hist = oil_data['brent']['history'].tail(days)
        ax3.plot(hist.index, hist['Close'], linewidth=2, label='Brent Crude Oil', color='#4CAF50', marker='s', markersize=2)
    ax3.set_title('Crude Oil Futures', fontsize=14, fontweight='bold', pad=10)
    ax3.set_xlabel('Date', fontsize=11)
    ax3.set_ylabel('Price (USD)', fontsize=11)
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    chart_path = 'market_trend_chart.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✅ 趋势图已保存: {chart_path}")
    return chart_path


def generate_push_content(gold_data, oil_data, advice, backtest):
    """生成推送内容"""
    beijing_time = get_beijing_time()
    
    lines = []
    lines.append("=" * 70)
    lines.append("📊 黄金/原油市场推送 + 智能投资建议")
    lines.append("=" * 70)
    lines.append(f"⏰ 推送时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    lines.append("📡 数据来源: Yahoo Finance")
    lines.append("=" * 70)
    lines.append("")
    
    # 黄金价格
    lines.append("─" * 70)
    lines.append("🥇 黄金价格")
    lines.append("─" * 70)
    if gold_data['ny_gold']:
        ny = gold_data['ny_gold']
        emoji = "📈" if ny['change'] >= 0 else "📉"
        lines.append(f"{emoji} 纽约金期货: ${ny['price']:.2f} ({ny['change_pct']:+.2f}%)")
        lines.append(f"   RSI: {ny['rsi']:.1f} | MA20: ${ny['ma20']:.2f} | 波动率: {ny['volatility']:.2f}%")
    if gold_data['london_gold']:
        lg = gold_data['london_gold']
        emoji = "📈" if lg['change'] >= 0 else "📉"
        lines.append(f"{emoji} 伦敦金: ${lg['price']:.2f} ({lg['change_pct']:+.2f}%)")
    
    # 中国黄金ETF
    lines.append("")
    lines.append("📈 中国黄金ETF:")
    for etf in gold_data['china_etf']:
        emoji = "📈" if etf['change'] >= 0 else "📉"
        lines.append(f"   {emoji} {etf['name']}: ¥{etf['price']:.3f} ({etf['change_pct']:+.2f}%)")
    
    # 原油价格
    lines.append("")
    lines.append("─" * 70)
    lines.append("🛢️ 原油价格")
    lines.append("─" * 70)
    if oil_data['wti']:
        wti = oil_data['wti']
        emoji = "📈" if wti['change'] >= 0 else "📉"
        lines.append(f"{emoji} WTI原油: ${wti['price']:.2f} ({wti['change_pct']:+.2f}%)")
        lines.append(f"   RSI: {wti['rsi']:.1f} | MA20: ${wti['ma20']:.2f} | 波动率: {wti['volatility']:.2f}%")
    if oil_data['brent']:
        brent = oil_data['brent']
        emoji = "📈" if brent['change'] >= 0 else "📉"
        lines.append(f"{emoji} 布伦特原油: ${brent['price']:.2f} ({brent['change_pct']:+.2f}%)")
    
    # 投资建议
    lines.append("")
    lines.append("─" * 70)
    lines.append("💡 智能投资建议")
    lines.append("─" * 70)
    
    action_map = {'buy': '🟢 买入', 'sell': '🔴 卖出', 'hold': '🟡 持有', 'reduce': '🟠 减仓'}
    
    gold = advice['gold']
    lines.append(f"\n🥇 黄金: {action_map.get(gold['action'], '⚪ 观望')}")
    lines.append(f"   置信度: {gold['confidence']}% | 建议仓位: {gold['allocation_pct']}%")
    if gold.get('target'):
        lines.append(f"   目标价: ${gold['target']:.2f} | 止损价: ${gold['stop_loss']:.2f}")
    lines.append(f"   理由: {'; '.join(gold['reasons'])}")
    
    oil = advice['oil']
    lines.append(f"\n🛢️ 原油: {action_map.get(oil['action'], '⚪ 观望')}")
    lines.append(f"   置信度: {oil['confidence']}% | 建议仓位: {oil['allocation_pct']}%")
    if oil.get('target'):
        lines.append(f"   目标价: ${oil['target']:.2f} | 止损价: ${oil['stop_loss']:.2f}")
    lines.append(f"   理由: {'; '.join(oil['reasons'])}")
    
    # 资产配置
    portfolio = advice['portfolio']
    lines.append("")
    lines.append("📊 推荐资产配置:")
    lines.append(f"   黄金: {portfolio['gold_pct']}% | 原油: {portfolio['oil_pct']}% | 现金: {portfolio['cash_pct']}%")
    
    # 回测结果
    if backtest:
        lines.append("")
        lines.append("─" * 70)
        lines.append("📈 策略回测 (近30天)")
        lines.append("─" * 70)
        lines.append(f"   累计收益: {backtest.get('gold_return', 0):.2f}%")
        lines.append(f"   胜率: {backtest.get('win_rate', 0):.1f}% ({backtest.get('profitable_trades', 0)}/{backtest.get('total_trades', 0)})")
        if 'avg_return' in backtest:
            lines.append(f"   平均单次收益: {backtest['avg_return']:.2f}%")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("⚠️ 风险提示: 以上建议基于技术分析，不构成投资建议")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def generate_email_html(gold_data, oil_data, advice, backtest):
    """生成邮件HTML"""
    beijing_time = get_beijing_time()
    
    action_color = {'buy': '#28a745', 'sell': '#dc3545', 'hold': '#ffc107', 'reduce': '#fd7e14'}
    action_text = {'buy': '买入', 'sell': '卖出', 'hold': '持有', 'reduce': '减仓'}
    
    # 市场数据部分
    market_html = ""
    
    if gold_data['ny_gold']:
        ny = gold_data['ny_gold']
        color = '#28a745' if ny['change'] >= 0 else '#dc3545'
        market_html += f"""
        <div style="background:#fff8e1;padding:12px;border-radius:8px;margin-bottom:10px;">
            <strong>🥇 纽约金期货</strong><br>
            <span style="color:{color};font-size:18px;font-weight:bold;">${ny['price']:.2f}</span> 
            <span style="color:{color};">({ny['change_pct']:+.2f}%)</span><br>
            <small>RSI: {ny['rsi']:.1f} | MA20: ${ny['ma20']:.2f} | 波动率: {ny['volatility']:.2f}%</small>
        </div>"""
    
    if gold_data['london_gold']:
        lg = gold_data['london_gold']
        color = '#28a745' if lg['change'] >= 0 else '#dc3545'
        market_html += f"""
        <div style="background:#fff8e1;padding:12px;border-radius:8px;margin-bottom:10px;">
            <strong>💰 伦敦金</strong><br>
            <span style="color:{color};font-size:18px;font-weight:bold;">${lg['price']:.2f}</span> 
            <span style="color:{color};">({lg['change_pct']:+.2f}%)</span>
        </div>"""
    
    if gold_data['china_etf']:
        market_html += '<div style="margin:15px 0;"><strong>📈 中国黄金ETF</strong></div>'
        for etf in gold_data['china_etf']:
            color = '#28a745' if etf['change'] >= 0 else '#dc3545'
            market_html += f"""
            <div style="background:#f5f5f5;padding:8px 12px;border-radius:5px;margin-bottom:5px;">
                {etf['name']}: <span style="color:{color};font-weight:bold;">¥{etf['price']:.3f} ({etf['change_pct']:+.2f}%)</span>
            </div>"""
    
    if oil_data['wti']:
        wti = oil_data['wti']
        color = '#28a745' if wti['change'] >= 0 else '#dc3545'
        market_html += f"""
        <div style="background:#e3f2fd;padding:12px;border-radius:8px;margin:15px 0 10px 0;">
            <strong>🛢️ WTI原油</strong><br>
            <span style="color:{color};font-size:18px;font-weight:bold;">${wti['price']:.2f}</span> 
            <span style="color:{color};">({wti['change_pct']:+.2f}%)</span><br>
            <small>RSI: {wti['rsi']:.1f} | MA20: ${wti['ma20']:.2f} | 波动率: {wti['volatility']:.2f}%</small>
        </div>"""
    
    if oil_data['brent']:
        brent = oil_data['brent']
        color = '#28a745' if brent['change'] >= 0 else '#dc3545'
        market_html += f"""
        <div style="background:#e3f2fd;padding:12px;border-radius:8px;margin-bottom:10px;">
            <strong>🛢️ 布伦特原油</strong><br>
            <span style="color:{color};font-size:18px;font-weight:bold;">${brent['price']:.2f}</span> 
            <span style="color:{color};">({brent['change_pct']:+.2f}%)</span>
        </div>"""
    
    # 投资建议部分
    gold = advice['gold']
    oil = advice['oil']
    portfolio = advice['portfolio']
    
    gold_color = action_color.get(gold['action'], '#6c757d')
    oil_color = action_color.get(oil['action'], '#6c757d')
    
    advice_html = f"""
    <div style="margin:20px 0;">
        <h2 style="color:#333;border-left:4px solid #667eea;padding-left:10px;">💡 智能投资建议</h2>
        <div style="display:flex;flex-wrap:wrap;gap:15px;margin-top:15px;">
            <div style="flex:1;min-width:250px;background:{gold_color}15;padding:15px;border-radius:8px;border-left:4px solid {gold_color};">
                <h3 style="margin:0 0 10px 0;color:{gold_color};">🥇 黄金 - {action_text.get(gold['action'], '观望')}</h3>
                <p style="margin:5px 0;">置信度: <strong>{gold['confidence']}%</strong></p>
                <p style="margin:5px 0;">建议仓位: <strong>{gold['allocation_pct']}%</strong></p>
                {f'<p style="margin:5px 0;">目标价: ${gold["target"]:.2f}</p>' if gold.get('target') else ''}
                {f'<p style="margin:5px 0;">止损价: ${gold["stop_loss"]:.2f}</p>' if gold.get('stop_loss') else ''}
                <p style="margin:5px 0;font-size:12px;color:#666;">{'; '.join(gold['reasons'])}</p>
            </div>
            <div style="flex:1;min-width:250px;background:{oil_color}15;padding:15px;border-radius:8px;border-left:4px solid {oil_color};">
                <h3 style="margin:0 0 10px 0;color:{oil_color};">🛢️ 原油 - {action_text.get(oil['action'], '观望')}</h3>
                <p style="margin:5px 0;">置信度: <strong>{oil['confidence']}%</strong></p>
                <p style="margin:5px 0;">建议仓位: <strong>{oil['allocation_pct']}%</strong></p>
                {f'<p style="margin:5px 0;">目标价: ${oil["target"]:.2f}</p>' if oil.get('target') else ''}
                {f'<p style="margin:5px 0;">止损价: ${oil["stop_loss"]:.2f}</p>' if oil.get('stop_loss') else ''}
                <p style="margin:5px 0;font-size:12px;color:#666;">{'; '.join(oil['reasons'])}</p>
            </div>
        </div>
    </div>
    """
    
    # 资产配置
    allocation_html = f"""
    <div style="background:#f5f5f5;padding:15px;border-radius:8px;margin:15px 0;">
        <h3 style="margin:0 0 15px 0;">📊 推荐资产配置</h3>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <div style="flex:1;min-width:80px;text-align:center;background:#FFD700;padding:15px;border-radius:5px;">
                <div style="font-size:28px;font-weight:bold;">{portfolio['gold_pct']}%</div>
                <div style="font-size:12px;">黄金</div>
            </div>
            <div style="flex:1;min-width:80px;text-align:center;background:#2196F3;padding:15px;border-radius:5px;color:white;">
                <div style="font-size:28px;font-weight:bold;">{portfolio['oil_pct']}%</div>
                <div style="font-size:12px;">原油</div>
            </div>
            <div style="flex:1;min-width:80px;text-align:center;background:#4CAF50;padding:15px;border-radius:5px;color:white;">
                <div style="font-size:28px;font-weight:bold;">{portfolio['cash_pct']}%</div>
                <div style="font-size:12px;">现金</div>
            </div>
        </div>
    </div>
    """
    
    # 回测结果
    backtest_html = ""
    if backtest:
        backtest_html = f"""
        <div style="background:#e8f5e9;padding:15px;border-radius:8px;margin:15px 0;">
            <h3 style="margin:0 0 10px 0;">📈 策略回测 (近30天)</h3>
            <p style="margin:5px 0;">累计收益: <strong>{backtest.get('gold_return', 0):.2f}%</strong></p>
            <p style="margin:5px 0;">胜率: <strong>{backtest.get('win_rate', 0):.1f}%</strong> ({backtest.get('profitable_trades', 0)}/{backtest.get('total_trades', 0)})</p>
            {f'<p style="margin:5px 0;">平均单次收益: {backtest["avg_return"]:.2f}%</p>' if 'avg_return' in backtest else ''}
        </div>
        """
    
    # 完整HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gold & Oil Investment Report</title>
</head>
<body style="margin:0;padding:20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:650px;margin:0 auto;background:white;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <tr>
            <td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:30px;text-align:center;border-radius:10px 10px 0 0;">
                <h1 style="margin:0;color:white;font-size:22px;">黄金/原油市场推送</h1>
                <p style="margin:10px 0 0 0;color:white;opacity:0.9;font-size:14px;">{beijing_time.strftime('%Y-%m-%d %H:%M')} (北京时间)</p>
            </td>
        </tr>
        <tr>
            <td style="padding:25px;">
                <h2 style="margin:0 0 15px 0;color:#333;font-size:18px;border-left:4px solid #FFD700;padding-left:10px;">🥇 黄金价格</h2>
                {market_html}
                
                {advice_html}
                {allocation_html}
                {backtest_html}
                
                <div style="background:#ffebee;padding:15px;border-radius:8px;margin-top:15px;border-left:4px solid #f44336;">
                    <h3 style="margin:0 0 10px 0;color:#c62828;font-size:14px;">⚠️ 风险提示</h3>
                    <ul style="margin:0;padding-left:18px;font-size:12px;color:#666;">
                        <li>以上建议基于技术分析，不构成投资建议</li>
                        <li>请根据自身风险承受能力决策</li>
                        <li>建议设置止损，控制单笔亏损在3-5%</li>
                    </ul>
                </div>
            </td>
        </tr>
        <tr>
            <td style="background:#f8f9fa;padding:20px;text-align:center;border-radius:0 0 10px 10px;">
                <p style="margin:0;color:#28a745;font-size:16px;font-weight:bold;">✅ 推送完成</p>
                <p style="margin:10px 0 0 0;color:#666;font-size:12px;">趋势图请查看邮件附件</p>
                <p style="margin:5px 0 0 0;font-size:12px;"><a href="https://github.com/tomjingang/gold-etf-monitor" style="color:#667eea;text-decoration:none;">查看仓库</a></p>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    return html


def save_data(gold_data, oil_data, advice):
    """保存数据"""
    beijing_time = get_beijing_time()
    today = beijing_time.strftime('%Y-%m-%d')
    
    # 保存价格数据
    price_data = {
        'date': today,
        'ny_gold': gold_data['ny_gold']['price'] if gold_data['ny_gold'] else None,
        'london_gold': gold_data['london_gold']['price'] if gold_data['london_gold'] else None,
        'wti_oil': oil_data['wti']['price'] if oil_data['wti'] else None,
        'brent_oil': oil_data['brent']['price'] if oil_data['brent'] else None,
    }
    
    with open(f'price_data_{today}.json', 'w') as f:
        json.dump(price_data, f, indent=2)
    
    # 保存建议历史
    advice_record = {
        'date': today,
        'gold': advice['gold'],
        'oil': advice['oil'],
        'portfolio': advice['portfolio']
    }
    
    advice_history = []
    if os.path.exists(ADVICE_HISTORY_FILE):
        with open(ADVICE_HISTORY_FILE, 'r') as f:
            advice_history = json.load(f)
    
    # 避免重复记录
    if not any(a['date'] == today for a in advice_history):
        advice_history.append(advice_record)
        with open(ADVICE_HISTORY_FILE, 'w') as f:
            json.dump(advice_history, f, indent=2)
    
    print(f"✅ 数据已保存: price_data_{today}.json")


def main():
    """主函数"""
    beijing_time = get_beijing_time()
    
    print("=" * 70)
    print("📊 黄金/原油市场推送 + 智能投资顾问")
    print("=" * 70)
    print(f"⏰ 执行时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    print("📡 数据来源: Yahoo Finance")
    print("=" * 70)
    
    # 获取数据
    print("\n🔄 正在获取黄金数据...")
    gold_data = get_gold_data()
    
    print("🔄 正在获取原油数据...")
    oil_data = get_oil_data()
    
    # 生成趋势图
    print("\n📊 正在生成趋势图...")
    chart_path = create_trend_chart(gold_data, oil_data, days=45)
    
    # 分析并生成建议
    print("\n🤖 正在分析市场并生成投资建议...")
    advice = analyze_market(gold_data, oil_data)
    
    # 运行回测
    print("\n📈 正在运行回测...")
    backtest = run_backtest(days=30)
    
    # 生成推送内容
    push_content = generate_push_content(gold_data, oil_data, advice, backtest)
    
    # 打印并保存
    print("\n" + push_content)
    
    with open('push_notification.txt', 'w', encoding='utf-8') as f:
        f.write(push_content)
    print("\n✅ 推送内容已保存: push_notification.txt")
    
    # 生成邮件HTML
    email_html = generate_email_html(gold_data, oil_data, advice, backtest)
    with open('email_body.html', 'w', encoding='utf-8') as f:
        f.write(email_html)
    print("✅ 邮件内容已保存: email_body.html")
    
    # 保存数据
    save_data(gold_data, oil_data, advice)
    
    return gold_data, oil_data, advice, backtest


if __name__ == "__main__":
    main()
