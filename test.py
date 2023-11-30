import datetime, time
from datetime import timedelta
import unittest
unittest.TestLoader.sortTestMethodsUsing = None # run tests in alpha order
import concurrent.futures
import redis.exceptions as redis_excp

import redis_proxy
from redis_proxy import requests
import util.logger as log
import util.load_env as env


class TestConfiguration(unittest.TestCase):
    
    client = redis_proxy.RedisProxy.get_instance()
    config = client.redis_client.config_get()
    
    def test_global_expiry(self):
        # used in setex command
        self.assertEqual(env.TTL_SEC, self.client.TTL_SEC)

    def test_lru_evictiion_policy(self):
        self.assertTrue('lru' in self.config['maxmemory-policy'])
        self.assertNotEqual(self.config['maxmemory'], '0')
        
    def test_fixed_key_size(self):
        self.assertEqual(int(self.config['proto-max-bulk-len']), self.client.CACHE_CAPACITY) #'proto-max-bulk-len': self.CACHE_CAPACITY   
    
    def test_max_clients(self):
        self.assertEqual(int(self.config['maxclients']), self.client.MAX_CLIENTS)
    
    def test_max_value_size(self):
        self.assertEqual(self.client.CACHE_CAPACITY, env.CACHE_CAPACITY)


class TestConcurrentUsers(unittest.TestCase):
    # global test variables
    test_key, test_url = 'test:{}', env.THIRD_PARTY_TEST_URL
    
    client = redis_proxy.RedisProxy.get_instance()
    client.redis_client.flushall()    

    logger = log.setup_logger(__file__, "TestConcurrentUsers", 0)
    logger.info(f"\n\t---->>> STARTED TEST Redis RUN at {datetime.datetime.now()} ")

    def test_concurrent_users_over_capacity(self):

        test_key = self.test_key.format('con_over')
        self.client.redis_get(self.test_url, test_key)
        num_clients = self.client.MAX_CLIENTS**2

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_clients) as executor:
            with self.assertRaises(redis_excp.ConnectionError):
                [r for r in executor.map(self.client.check_key,[test_key]*num_clients)]
  
  
class TestLRUEviction(unittest.TestCase):

    # global test variables
    test_key, test_url = 'test{}', env.THIRD_PARTY_TEST_URL

    client = redis_proxy.RedisProxy.get_instance()
    client.redis_client.flushall()
    start_evicted_keys = client.redis_client.info()['evicted_keys']
    
    logger = log.setup_logger(__file__, "TestLRUEviction", 0)
    logger.info(f"\n\t---->>> STARTED TEST LRU RUN at {datetime.datetime.now()} ")
    
    def test_lru_eviction(self):
        # test eviction policy
        test_key = self.test_key.format('lru_policy:')
        for i in range(0, 20):
            self.client.redis_get(self.test_url, test_key+str(i))
            time.sleep(.5) # to prevent overload to test url

        if 0 < int(self.client.redis_client.config_get('maxmemory')['maxmemory']) < self.client.redis_client.memory_stats()["total.allocated"]:
            evicted_keys = self.client.redis_client.info()["evicted_keys"]
            self.logger.debug(f'evicted keys start < end - {self.start_evicted_keys} < {evicted_keys}')
            # assertions
            self.assertGreater(evicted_keys, self.start_evicted_keys)


class TestRedis(unittest.TestCase):
    
    # global test variables
    test_key, test_url = 'test:{}', env.THIRD_PARTY_TEST_URL
    
    client = redis_proxy.RedisProxy.get_instance()
    client.redis_client.flushall()
    start_evicted_keys = client.redis_client.info()['evicted_keys']
    
    logger = log.setup_logger(__file__, "TestRedis", 0)
    logger.info(f"\n\t---->>> STARTED TEST Redis RUN at {datetime.datetime.now()} ")

    def test_single_backing_instance(self):
        with self.assertRaises(Exception):
            rp1 = redis_proxy.RedisProxy()
        rp1 = redis_proxy.RedisProxy.get_instance()
        rp2 = redis_proxy.RedisProxy.get_instance()
        self.assertTrue(rp1==rp2)
        self.assertTrue(rp1 is rp2)

    def test_global_expiry_set(self):

        test_key = self.test_key.format('global_set')
    
        self.client.redis_get(self.test_url, test_key)        
        ttl_curr_time1 = self.client.redis_client.ttl(test_key)
        time.sleep(1)
        ttl_curr_time2 = self.client.redis_client.ttl(test_key)

        self.logger.debug(f"{test_key} - 0<{ttl_curr_time1}<{self.client.TTL_SEC} && -2=={ttl_curr_time2}")
        
        # assertions
        self.assertGreater(ttl_curr_time1, 0)
        self.assertLessEqual(ttl_curr_time2, self.client.TTL_SEC-1)
    
    def test_global_expiry_expires(self):

        test_key = self.test_key.format('global_exp')
        try:
            self.client.redis_get(self.test_url, test_key)
        except:
            self.client.redis_client.flushdb()
            self.client.redis_get(self.test_url, test_key)
        
        check_value1 = self.client.check_key(test_key)
        time.sleep(1)
        check_value2 = self.client.redis_client.ttl(test_key)
        
        self.logger.debug(f"{test_key} - check_value1!=None & check_value2==None -- {type(check_value1)} : {type(check_value2)}")
        
        # assertions
        self.assertNotEqual(check_value1, None)
        self.assertLessEqual(check_value2, self.client.TTL_SEC) # key should return None value, since the ttl expired.
      
    def test_redis_get__setex(self):

        test_key = self.test_key.format('get_setex')
        start_value0 = self.client.check_key(test_key)
        start_value1 = self.client.redis_get(self.test_url, test_key)

        start_value2 = self.client.check_key(test_key)
        start_value3 = self.client.redis_get(self.test_url, test_key)
       
        self.logger.debug(f"{test_key} - val0: {len(start_value1)} != None & val2: {len(start_value2)} == val3: {len(start_value3)}  ")

        # assertions
        self.assertEqual(start_value0, None)
        self.assertEqual(start_value1, start_value3)
         
    def test_valid_data_saved_to_rcache(self):

        test_key = self.test_key.format('to_cache')
        t0 = datetime.datetime.now()
        self.client.redis_get(self.test_url, test_key)
        t1 = datetime.datetime.now()-t0

        t2 = datetime.datetime.now()
        self.client.redis_get(self.test_url, test_key)
        t3 = datetime.datetime.now() - t2
        
        self.logger.debug(f"{test_key}- Time 1 : {t1} >? Time 2: {t3} && Time1 / Time3 : {t1/t3} >? 10")
        
        # assertions
        self.assertLess(t3, t1)
        self.assertGreater(t1/t3, 10)


class TestWebRedis(unittest.TestCase):
    # global test variables
    test_key, test_url = 'test{}', env.THIRD_PARTY_TEST_URL
    test_http_server = f"http://{env.HTTP_HOST}:{env.HTTP_PORT}"
    
    client = redis_proxy.RedisProxy.get_instance()
    client.redis_client.flushall()
    
    logger = log.setup_logger(__file__, "TestWebRedis", 0)
    logger.info(f"\n\t---->>> STARTED TEST Http RUN at {datetime.datetime.now()} ")

    def test_http_web_service(self):

        test_key = self.test_key.format('http')
        payload = {"url":self.test_url, "params":None, "key":test_key}
        
        # test time to make each request
        t1 = datetime.datetime.now()
        res1 = requests.get(self.test_http_server,  params=payload)
        t2 = datetime.datetime.now() - t1
        
        t1 = datetime.datetime.now()
        res2 = requests.get(self.test_http_server,  params=payload)
        t3 = datetime.datetime.now() - t1
        
        t1 = datetime.datetime.now()
        res3 = requests.get(self.test_http_server,  params=payload)
        t4 = datetime.datetime.now() - t1
        
        self.logger.debug(f'{test_key} - try 1 time: {t2} try 2 time: {t3} try 3 time: {t4}')
        
        t_delta = timedelta(microseconds=100000)
        # assertions
        self.assertGreater(t2, t_delta)
        self.assertLess(t3, t_delta)
        self.assertEqual(res1.content, res2.content)
        self.assertLess(t4, t_delta)
        self.assertEqual(res2.content, res3.content)
        

if __name__ == '__main__':
    unittest.main(verbosity=2)
