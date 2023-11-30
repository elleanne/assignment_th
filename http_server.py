import os, signal
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs

import redis_proxy
import util.logger as log
import util.load_env as env

client = redis_proxy.RedisProxy.get_instance() #redis_proxy.RedisProxy(rp_host=env.RP_HOST, rp_port=env.RP_PORT, rp_db=env.RP_DB, ttl_sec=env.TTL_SEC, cache_capacity=env.CACHE_CAPACITY, max_clients=env.MAX_CLIENTS, max_mem=env.MAX_MEMORY, evict_policy=env.EVICT_POLICY)

class HTTPHandler(http.server.BaseHTTPRequestHandler):
    
    
    def parse_req_params(self):
        """
        Helper for do_GET.
        Parses the GET params & pass to the RedisProxy GET
        
        Returns
        -------
        data : str | None
            data retrieved from Http GET or Redis Get if cached
        """
        url = parse_qs(urlparse(self.path).query).get('url', None)
        payload = parse_qs(urlparse(self.path).query).get('params', None)
        key = parse_qs(urlparse(self.path).query).get('key', None)
        
        if url is not None:
            return client.redis_get(url[0], key[0])
        elif payload is not None:
            return client.redis_get(url[0], key[0], payload)
        return 
    
        
    def do_GET(self):
        """
        Map the HTTP GET method to Redis GET       
        """
        data = self.parse_req_params()
        if data is None:
            status = 404
            data = "{'Status': '404 Not Found'}"
        else:
            status = 200
            data = str(data)

        self.send_response(status)        
        self.send_header('content', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(data, "utf-8"))



httpd = None
logger = log.setup_logger(__file__, 'HTTPServer', 0) # level=debug

def write_to_file(file_name, data):
    """
    write data to a file. Converts data to str in function.

    Parameters
    ----------
    file_name : str
        path to file to save
    data : any
        data to be save to the file
    """
    d_file = open(file_name, 'w')
    try:
        d_file.write(str(data))
    finally:
        d_file.close()
        

def read_file_first_line(file_name):
    """
    Read the first line from a file.

    Parameters
    ----------
    file_name : str
        path to file to read
    
    Returns
    ----------
    data : str
        first line of the requested file
    """
    try:
        d_file = open(file_name, 'r')
        data = d_file.readline()
        d_file.close()
        return data
    except:
        return ""

def run(server_class=socketserver.TCPServer, host="localhost", port=8080):
    """
    Run the HTTP server
    
    Parameters
    ----------
    server_class : socketserver class
        class used to init the server
    host : str
        address to bind the http server to
    port : int
        port to bind to
    """
    try:
        httpd = server_class((host, port), HTTPHandler)
    except:
        logger.warning(f"server already running at: {get_pid(__file__)}")
        return

    try:
        pid  = os.getpid()
        write_to_file(env.SERVER_PID_FILE, pid)
        logger.info(f'http serving at {pid}') 
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()


def get_pid(name):
    """
    Get the current pid number for the running http_server.run()
    Parameters
    ----------
    name : str
        name of the file to look for
    
    Returns
    ----------
    pids : array(int)
        Array of pids found for the given name
    """
    import subprocess
    child = subprocess.Popen(['pgrep', '-f', name], stdout=subprocess.PIPE, shell=False)
    response = child.communicate()[0]
    return [int(pid) for pid in response.split()]
    

def stop():
    """
    Stop the http_server. Try first to stop from the SERVER_PID_FILE.
    If an exception occurs, get_piid is called. If only 1 process iis running, it is killed. If more than one is running, the piids are logged.
    """
    pid = int(read_file_first_line(env.SERVER_PID_FILE))
    if pid is not None:
        try:
            os.kill(pid, signal.SIGKILL)
            logger.info(f"killed server process: {pid}") 
        except:
            pids = get_pid(__file__.lower())
            if len(pids) == 1:
                os.kill(pids[0], signal.SIGKILL)
                logger.info(f"killed server process: {pids[0]}") 
            else:
                logger.debug(f"Found PIDS of {__file__}: {pids}")
                # TODO : decide if killing all found pids is valid, or just allow dev to kill themselves from logs


if __name__ == '__main__':
    from sys import argv

    if len(argv) == 2:
        if int(argv[1]) < 0:
            stop()
        else:
            run(port=int(argv[1]))
    else:
        run()