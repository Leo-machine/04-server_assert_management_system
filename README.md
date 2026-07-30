# 服务器配件资产管理系统 — Demo

主线：入库 → 装机 → 拆下 → 借出（三级审批）→ 归还。设计依据见 `docs/`。

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

浏览器打开 http://127.0.0.1:5173 。顶栏切换「当前操作人」以走三级审批。

## 测试

```bash
cd backend
source .venv/bin/activate
pytest -q
```
