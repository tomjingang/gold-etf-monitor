# 黄金ETF + 伦敦金价格监控

[![Gold ETF Push](https://github.com/YOUR_USERNAME/gold-etf-monitor/actions/workflows/gold-etf.yml/badge.svg)](https://github.com/YOUR_USERNAME/gold-etf-monitor/actions/workflows/gold-etf.yml)

每天自动获取黄金ETF和伦敦金价格，并推送通知。

## 📊 监控内容

- 🌍 **国际金价**: 伦敦金、纽约金期货
- 📈 **黄金ETF**: 华安、易方达、国泰、博时黄金ETF
- ⏰ **推送时间**: 每天北京时间 9:30

## 🚀 快速开始

### 1. Fork/创建仓库

1. 在GitHub上创建新仓库
2. 上传本仓库的所有文件

### 2. 启用Actions

进入仓库的 Actions 标签，启用工作流。

### 3. 测试运行

点击 "Run workflow" 手动触发测试。

## 📱 推送通知

支持多种推送方式：

- ✅ GitHub Actions 日志
- ✅ 微信 (Server酱)
- ✅ 钉钉机器人
- ✅ 邮件

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `.github/workflows/gold-etf.yml` | GitHub Actions工作流 |
| `.github/scripts/gold_price_push.py` | 数据获取和推送脚本 |

## ⏰ 定时设置

默认每天北京时间9:30执行：

```yaml
schedule:
  - cron: '30 1 * * *'  # UTC 1:30 = 北京时间 9:30
```

## 📄 License

MIT License
