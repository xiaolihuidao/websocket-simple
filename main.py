from fastapi import FastAPI,WebSocket,WebSocketDisconnect,Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from typing import Dict,List

app = FastAPI()
templates = Jinja2Templates(directory="templates")
##管理Websocket的连接
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    ##connect方法
    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket
        await self.broadcast({
            "type": "system",
            "message": f"{username} 加入了聊天",
            "time": datetime.now().strftime("%H:%M:%S")
        }
        )

    ##管理websocket连接断开
    def disconnect(self,username:str):
        if username in self.active_connections:
            del self.active_connections[username]
    
    
    ##发送私聊消息
    async def send_personal_message(self, message: dict, recipient: str):
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_json(message)
        else:
            # 如果接收者不在线，通知发送者
            sender = message.get("sender")
            if sender and sender in self.active_connections:
                await self.active_connections[sender].send_json({
                    "type": "error",
                    "message": f"用户 {recipient} 不在线",
                    "time": datetime.now().strftime("%H:%M:%S")
                })

    ##广播消息给全体成员
    async def broadcast(self,message:dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

    ##返回所有在线用户的列表
    def get_online_users(self)->List[str]:
        return list(self.active_connections.keys())


manager=ConnectionManager()

##HTTP GET 请求处理函数，返回聊天页面
@app.get("/")
async def get_chat_page(request:Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    try:
        await manager.connect(username, websocket)
        await manager.send_personal_message({
            "type": "user_list",
            "users": manager.get_online_users(),
            "time": datetime.now().strftime("%H:%M:%S")
        }, username)
        
        while True:
            data = await websocket.receive_json()  # 改为接收JSON格式消息
            msg_type = data.get("type", "public")
            
            if msg_type == "private":
                # 处理私聊消息
                recipient = data.get("to")
                content = data.get("message")
                if recipient and content:
                    await manager.send_personal_message({
                        "type": "private",
                        "sender": username,
                        "message": content,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }, recipient)
                    # 给自己也发送一份（显示已发送）
                    await manager.send_personal_message({
                        "type": "private_sent",
                        "recipient": recipient,
                        "message": content,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }, username)
            else:
                # 处理群聊消息
                await manager.broadcast({
                    "type": "public",
                    "username": username,
                    "message": data.get("message"),
                    "time": datetime.now().strftime("%H:%M:%S")
                })
    except WebSocketDisconnect:
        manager.disconnect(username)
        await manager.broadcast({
            "type": "system",
            "message": f"{username} 离开了聊天",
            "time": datetime.now().strftime("%H:%M:%S")
        })
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(username)