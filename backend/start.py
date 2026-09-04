import sys
sys.path.insert(0, r'.')
from uvicorn.config import Config
from uvicorn.server import Server
config = Config(app="app.server:app", host="0.0.0.0", port=8000)
server = Server(config)
server.run()