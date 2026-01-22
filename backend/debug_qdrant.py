import qdrant_client
from qdrant_client import QdrantClient
import inspect

print(f"Qdrant Client Version: {qdrant_client.__version__}")
client = QdrantClient(path="./qdrant_data_test")
print(f"Client Object: {client}")
print(f"Has search? {'search' in dir(client)}")
print("Attributes:", [x for x in dir(client) if not x.startswith("_")])
