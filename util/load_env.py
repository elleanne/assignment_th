import os
from dotenv import load_dotenv

load_dotenv()

RP_HOST = os.getenv('RP_HOST')
RP_PORT = int(os.getenv('RP_PORT'))
RP_DB = int(os.getenv('RP_DB'))
TTL_SEC = int(os.getenv('TTL_SEC'))
CACHE_CAPACITY=int(os.getenv('CACHE_CAPACITY'))*1048576 # MB to Bytes
MAX_CLIENTS = int(os.getenv('MAX_CLIENTS'))
MAX_MEMORY = int(os.getenv('MAX_MEMORY'))*1048576 # MB to Bytes
EVICT_POLICY = os.getenv('EVICT_POLICY')
SERVER_PID_FILE = os.getenv('SERVER_PID_FILE')
HTTP_PORT = int(os.getenv('HTTP_PORT'))
HTTP_HOST = os.getenv('HTTP_HOST')
LOG_FILE = os.getenv('LOG_FILE')


THIRD_PARTY_TEST_URL=os.getenv('THIRD_PARTY_TEST_URL')