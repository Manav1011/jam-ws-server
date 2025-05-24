import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

active_channels = {}
clients = {}

async def remove_from_dict(websocket: WebSocket):
    host_key = next((k for k, v in active_channels.items() if v == websocket), None)
    if host_key:
        del active_channels[host_key]
        
    client_key = next((k for k, v in clients.items() if v == websocket), None)
    if client_key:
        del clients[client_key]
    if websocket in clients:
        del clients[websocket]
    print(f"Removed {websocket} from all dictionaries.")

@app.get("/")
async def root():
    return JSONResponse(content={"message": "WebSocket server running"})

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            message = json.loads(message)

            if message["client"] == "host":
                if message['type'] == 'connection':
                    active_channels[message['channel_id']] = websocket
                if message["type"] == 'set_offer':
                    participant_id = message['participant_id']
                    client_socket = clients.get(participant_id)
                    if client_socket:
                        msg = {
                            "type": "set_offer",
                            "sdp": message['sdp']
                        }
                        await client_socket.send_text(json.dumps(msg))

            elif message["client"] == "participant":
                if message['type'] == 'connection':
                    channel_id = message['channel_id']
                    if channel_id in active_channels:
                        host = active_channels[channel_id]
                        participant_id = message['participant_id']
                        clients[participant_id] = websocket
                        msg = {
                            'type': 'send_offer',
                            "participant_id": participant_id
                        }
                        await host.send_text(json.dumps(msg))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "not_found",
                            "message": f"Channel ID {channel_id} not found."
                        }))
                if message['type'] == 'set_answer':
                    host = active_channels.get(message['channel_id'])
                    if host:
                        msg = {
                            "type": "set_answer",
                            "sdp": message["sdp"],
                            "participant_id": message["participant_id"]
                        }
                        await host.send_text(json.dumps(msg))
    except WebSocketDisconnect:
        await remove_from_dict(websocket)
        print("WebSocket disconnected")
    except Exception as e:
        await remove_from_dict(websocket)
        print(f"Error: {e}")
    finally:
        await remove_from_dict(websocket)

# Only needed for local testing
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8765, reload=False)
