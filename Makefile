VENV = venv
PYTHON = .$(VENV)/bin/python3
PIP = .$(VENV)/bin/pip
BREW_INSTALL = "curl -SL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

activate:
	. .$(VENV)/bin/activate

setup: requirements.txt
	docker pull python

	python3 -m $(VENV) .$(VENV)
	. .$(VENV)/bin/activate
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install_redis:
ifeq ($(shell uname), Linux)
	echo "intalling redis with apt --- UNTESTED ---"
	apt install lsb-release curl gpg
	curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
	echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
	apt-get update
	apt-get install redis
endif
ifeq ($(shell uname), Darwin)
	@$(MAKE) -f $(lastword $(MAKEFILE_LIST)) install_brew
	echo "intalling redis with brew"
	brew install redis
endif

install_xcode:
	xcode-select --install

install_brew:
	curl -S -o install.sh https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh

http_start: activate
	$(PYTHON) http_server.py & 

http_stop: activate
	$(PYTHON) http_server.py -1

http_restart: http_stop http_start

redis_start:
	redis-server --daemonize yes --port 6379
	redis-cli ping

redis_stop:
	redis-cli shutdown

redis_restart: redis_stop redis_start

test_run: .env redis_start activate
	$(PYTHON) http_server.py & 
	$(PYTHON) test.py
	$(PYTHON) http_server.py -1

test_no_setup: redis_start activate test_run

test: setup install_redis test_no_setup

run: redis_start activate http_start

shutdown: http_stop redis_stop

clean:
	rm -rf __pycache__
	rm -rf util/__pycache__
	rm -rf *.out
	rm -rf logs/*
	rm dump.rdb
	
containerize:
	pip freeze > requirements.txt 
	tar cfzv assignment.tar.gz * .env