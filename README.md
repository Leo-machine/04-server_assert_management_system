# 电网资产及其配件数字化运营系统

主线：入库 → 装机 → 拆下 → 借出（三级审批）→ 归还。设计依据见 `docs/配件资产管理系统_设计文档_v1.md`。

## 启动

```bash
# 后端
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5174 ，使用由系统管理员分配或审批的账号登录。

## 测试

```bash
cd backend
source .venv/bin/activate
pytest -q
```

## Demo 范围说明（书面裁剪）

本期 **Demo 已实现**：登录鉴权（演示级）、主线流转、三级审批（回避/一票否决/审批人角色校验）、投运锁拆、超期告警、报废/调拨、盘点发现层、可调余量、型号/品牌/供应商主数据。

相对设计文档，以下能力 **本期明确不做**（字段或枚举可能预留）：

| 项 | 说明 |
|---|---|
| 状态「在途」 | 借出/调拨/归还直接落目标态，不经中转态 |
| 校正履历 | 盘点错位仅登记差异，不写说明性履历 |
| 维保换新成对 | `event_group_id` 已预留，未做旧件报废+新件入库绑定 |
| 服务器退役 | API 禁止设为退役；无逐件处置清单 |
| 生产级鉴权 | Demo 令牌 + 本地密码哈希，不可用于生产 |
| 附件上传 | 报废影像为字符串引用，无文件存储 |

配件类型相对设计文档扩展为八类（RAID 与 HBA 分列；算力卡对应原 GPU）。
