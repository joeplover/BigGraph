"""统一应用入口 — 注册所有路由，供 uvicorn / Docker 使用

生产环境通过 `uvicorn main:app --host 0.0.0.0 --port 8000` 启动。
"""
from api.ragControll import app
from api.auth import router as auth_router
from api.ppt_agent_router import router as ppt_agent_router

# 注册认证 & PPT Agent 路由
app.include_router(auth_router)
app.include_router(ppt_agent_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)