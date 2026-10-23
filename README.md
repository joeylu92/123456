# Shopee → MakerWorld → 1688 → 芒果 ERP

这套工具用于整理 Shopee 巴西站 `mini jesus` / `mini Jesus 3D` 商品，匹配 MakerWorld 模型和 1688 货源，并生成芒果 ERP 草稿导入前的审核表。

## 规则

- 只保留最近 60 天上架的 Shopee 商品。
- 按商品链接、标题和店铺去重。
- MakerWorld 匹配分数达到阈值后才进入待建草稿列表。
- 只有匹配到 1688 货源时才填写结算价和商品重量；未匹配时保持为空。
- 发布前保留人工审核步骤，避免错误匹配直接进入 ERP。

## 使用

```bash
cd /workspace/123456
python3 -m pipeline init
python3 -m pipeline process --input data/raw.json --output data/mango_review.csv
```

`raw.json` 是采集器的统一中间格式。真实站点采集和芒果 ERP 写入需要浏览器登录态及对应站点网络访问。
