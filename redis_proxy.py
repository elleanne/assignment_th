import redis
# Only disable warning for requests import (issue with support with macos & urllib3 https://github.com/urllib3/urllib3/issues/3020)
import warnings
warnings.filterwarnings(action='ignore')
import requests
warnings.filterwarnings(action='default')

import util.logger as log
import util.load_env as env

'''
Defualt Redis config settings
'''
MAX_DATA_LEN = 512 * 1048576    # 512 MB
BASE_MAX_CLIENTS = 10000        # Redis default = 10k
BASE_TTL = 60                   # Global expiry in seconds
BASE_CACHE_CAPACITY = 2**32     # Fixed key size : redis default = 2^32 
BASE_MAX_MEMORY = 0             # default redis mem allocatiion is set to 0 (unlimited)
BASE_DATABASE = 0               # default Redis db to use


class RedisProxy:
    """
    Creates the connection to redis and handles the functionality of redis GET

    Methods
    -------
    get_instance()
        get the current (singleton) instance of RedisProxy
    __validate_input(params_dict)
        validate the parameters passed to __init__ are valid for redis
    __set_eviction_policy(policy)
        set the eviction policy for the redis connection
    __set_config_features(kv_dict)
        set config parameters for valid redis config values
    check_key(key)
        returns the value of the key from the redis db
    redis_get(url, key)
        returns data for the given key if it exists, or the data from the url if not    
    """
    __instance = None
    
    
    @staticmethod 
    def get_instance():
      """ Static access method for the RedisProxy class. """
      if RedisProxy.__instance == None:
        RedisProxy(rp_host=env.RP_HOST, rp_port=env.RP_PORT, rp_db=env.RP_DB, ttl_sec=env.TTL_SEC, cache_capacity=env.CACHE_CAPACITY, max_clients=env.MAX_CLIENTS, max_mem=env.MAX_MEMORY, evict_policy=env.EVICT_POLICY)
      return RedisProxy.__instance

  
    def __init__(self, rp_host='localhost', rp_port=6379, rp_db=0, ttl_sec=60, cache_capacity=6, max_clients=10, max_mem=0, evict_policy='allkeys-lru'):
        
        """
        Initialize redis connection with pool. Singleton instance.
        
        Parameters
        -------
        rp_host : str
            the host address
        
        rp_port : int
            the port number to use for the redis connection

        rp_db : int
            the database to connect to (starts at 0). Defaults to 0 when a negative int is given
        
        ttl_sec : int
            number of seconds before a key expires. If less than 0, defaults to 60 seconds
            
        cache_capacity : int
            max number of key/value pairs that can be cached. Must be between 0 - 2^32
            
        max_clients : int
            max number of clients that can be connected at a time. must be between 0-10,000
        
        max_mem : int
            max memory allocated for Redis to use, in conjunction with evict_policy.    
        
        evict_policy : str
            Must be a valid redis eviction policy
        """
        
        # SINGLETON 
        if RedisProxy.__instance != None:
            raise Exception("This class is a singleton! Use 'redis_proxy.RedisProxy.get_instance()' to get the single insance.")
        else:
            RedisProxy.__instance = self
        
        # validate the user passsed values that are valid for Redis connection
        ok, msg = self.__validate_input({rp_port:int, rp_db:int, ttl_sec:int, cache_capacity:int, max_clients:int, max_mem:int, evict_policy:str})
        if not ok:
            raise TypeError([msg])

        # pool creates Single backing instance
        self.pool = redis.ConnectionPool(host=rp_host, port=rp_port, db=rp_db, max_connections=max_clients, decode_responses=True)
        self.redis_client = redis.Redis(connection_pool=self.pool)

        # SET feature settings
        self.TTL_SEC = ttl_sec                   
        self.CACHE_CAPACITY = cache_capacity if cache_capacity < BASE_CACHE_CAPACITY else BASE_CACHE_CAPACITY   
        self.MAX_CLIENTS = max_clients if max_clients < BASE_MAX_CLIENTS else BASE_MAX_CLIENTS       
        self.MAX_MEMORY = max_mem       
        
        # SET CONFIG values
        self.__set_eviction_policy(evict_policy)
        self.__set_config_features({'proto-max-bulk-len': self.CACHE_CAPACITY, 'maxclients': self.MAX_CLIENTS, 'maxmemory': self.MAX_MEMORY})
        
        self.logger = log.setup_logger(__file__, __class__, 0)
    
    
    def __validate_input(self, params_dict):
        """
        validate inputs are useable for the REDIS library
        
        Parameters
        ----------
        params_dict : dict
            key = variable to validate
            value = expected type of the variable

        Returns
        -------
        tuple(ok : bool, message : str/None)
            if ok is False, raise an exception with the message
        """
        
        def check_type(variable, expected_type):
            """
            helper function to check param is epected type & check that INTs are greater than 0
            
            Parameters
            ----------
            variable : any
            expected_type : type(data_type)

            Returns
            -------
            bool
            """
            if type(variable) != expected_type:
                try:
                    variable = expected_type(variable)
                except:
                    return False
            if expected_type == type(int) and variable < 0:
                return False
            return True
        
        for param in params_dict.keys():
            ex_type = params_dict.get(param)
            if not check_type(param, ex_type):
                return False, f"ERROR: {param} must be of type {ex_type} and not negative."
            
        return True, None

         
    def __set_eviction_policy(self, policy):
        """
        Set the eviction policy for redis keys. Limited to valid Redis eviction policies.
        
        Parameters
        -------
        policy : str
            policy to be used if valid redis policy
        """
        if policy in {'noeviction','allkeys-lru','allkeys-lfu','allkeys-random','volatile-lru','volatile-lfu','volatile-random','volatile-ttl'}:
            self.redis_client.config_set('maxmemory-policy', policy)


    def __set_config_features(self, kv_dict):
        """
        Set all desired config policies. 
        
        Parameters
        ----------
        kv_dict : {str : any}
            The key must be a valid redis config value
            The value should be validated by validate_input() before it is passed to this function.
        """
        for key in kv_dict:
            value = kv_dict.get(key)
            self.redis_client.config_set(key, value)


    def check_key(self, key):
        """
        Check if a key is in the redis DB
        Time Complexity : O(1)
        
        Parameters
        ----------
        key : str
            The desired redis lookup key

        Returns
        -------
        value
            None OR the value for the requested key
        
        """
        return self.redis_client.get(key)    

    
    def redis_get(self, http_url, key, payload=None):
        """
        Cached GET
        map http get to redis get
        Time Complexity : O(N) - due to .decode()
        
        Parameters
        ----------
        http_url : str
            The desired url for the http request
        key : str
            The key for the desired data

        Returns
        -------
        data
            the value stored in the redis db for the requested key
        """

        data = self.check_key(key) # O(1)
        if data is None:
            try:    
                
                if payload:
                    data = requests.get(http_url, params=payload)
                else:
                    data = requests.get(http_url)        
                data = data.content.decode() # O(N)
        
                if len(data) <= MAX_DATA_LEN:
                    self.redis_client.setex(key, self.TTL_SEC, data) # O(1)
            except Exception as e:
                self.logger.error("EXCEPTION in redis_get() {} : {}".format(e, e.__class__))
                data = None
        
        if isinstance(data, bytes):
            data = data.decode()
        
        return data