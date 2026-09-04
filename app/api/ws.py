from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from app.core.ws import ws_manager
from app.api.deps import get_current_user_ws
from app.models.tenancy import User

router = APIRouter()

@router.websocket("")
@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None),
    user: User = Depends(get_current_user_ws)
):
    is_state = user.role in ["state_admin", "inspector"]
    await ws_manager.connect(websocket, school_id=user.school_id, is_state=is_state)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming ping / pong or client message
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, school_id=user.school_id)
    except Exception:
        ws_manager.disconnect(websocket, school_id=user.school_id)
